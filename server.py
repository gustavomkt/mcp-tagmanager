"""
Servidor MCP dedicado a Google Tag Manager (Tag Manager API v2).

Objetivo: que Tag Manager sea tan estable y determinista como el conector de
Google Ads que ya tienes ("Gustavo google ads- mcp"). Por eso cada tool sigue
las mismas reglas:

  - Nunca asume cuenta/contenedor/workspace implícito: account_id,
    container_id y workspace_id (o version_id) son parámetros explícitos en
    cada llamada. Sin eso, no hay ambigüedad posible sobre qué recurso se
    está tocando.
  - Las acciones que modifican algo en vivo (pausar un tag, publicar una
    versión) exigen confirm=True. Si no lo mandas, la tool se niega a
    ejecutar y te dice exactamente qué faltó — nunca "adivina".
  - Todas las llamadas a la API están envueltas en manejo de errores que
    devuelve un mensaje claro (qué falló y por qué) en vez de dejar que la
    excepción cruda tumbe la sesión de MCP — esa es la causa más común de
    que un conector "se caiga" sin explicación.

Requiere: haber corrido auth_setup.py una vez para generar token.json.
Ver README.md para la puesta en marcha completa.
"""

import json
import logging
import os
from typing import Any, Dict, List, Optional

from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from mcp.server.fastmcp import FastMCP

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [gtm-mcp] %(levelname)s %(message)s"
)
logger = logging.getLogger("gtm-mcp")

TOKEN_PATH = os.environ.get("GTM_TOKEN_PATH", "token.json")

# Mismo patrón "estandarizado" que el resto de los conectores: credenciales
# por variables de entorno, no por archivo, para que correr esto en Render
# (o cualquier otro host) no dependa de subir un token.json a mano.
#
# Reutiliza el MISMO cliente OAuth que ya usa "Gustavo google ads- mcp"
# (GOOGLE_ADS_CLIENT_ID / GOOGLE_ADS_CLIENT_SECRET) — no hace falta un
# cliente nuevo por herramienta. Solo necesita su propio refresh token con
# scopes de Tag Manager: GTM_REFRESH_TOKEN.
#
# Si no defines GTM_CLIENT_ID / GTM_CLIENT_SECRET explícitos, cae de vuelta a
# GOOGLE_ADS_CLIENT_ID / GOOGLE_ADS_CLIENT_SECRET automáticamente.
CLIENT_ID = os.environ.get("GTM_CLIENT_ID") or os.environ.get("GOOGLE_ADS_CLIENT_ID")
CLIENT_SECRET = os.environ.get("GTM_CLIENT_SECRET") or os.environ.get("GOOGLE_ADS_CLIENT_SECRET")
REFRESH_TOKEN = os.environ.get("GTM_REFRESH_TOKEN")

# tagmanager.edit.containers cubre lectura y edición de tags/triggers/variables.
# tagmanager.publish es un scope aparte, específico para crear/publicar versiones.
SCOPES = [
    "https://www.googleapis.com/auth/tagmanager.edit.containers",
    "https://www.googleapis.com/auth/tagmanager.publish",
    "https://www.googleapis.com/auth/tagmanager.readonly",
]

mcp = FastMCP("google-tag-manager")


# ---------------------------------------------------------------------------
# Autenticación y helpers
# ---------------------------------------------------------------------------

def _load_credentials() -> Credentials:
    """Prioridad: variables de entorno (GTM_REFRESH_TOKEN + client_id/secret,
    el mismo patrón que los demás conectores en Render) y, si no existen,
    cae de vuelta al archivo token.json (útil solo para correrlo en tu
    laptop mientras pruebas)."""
    if REFRESH_TOKEN and CLIENT_ID and CLIENT_SECRET:
        creds = Credentials(
            token=None,
            refresh_token=REFRESH_TOKEN,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET,
            scopes=SCOPES,
        )
        creds.refresh(GoogleAuthRequest())
        return creds

    if not os.path.exists(TOKEN_PATH):
        raise RuntimeError(
            "No hay credenciales: define GTM_REFRESH_TOKEN (reutilizando "
            "GOOGLE_ADS_CLIENT_ID/GOOGLE_ADS_CLIENT_SECRET, o tus propios "
            "GTM_CLIENT_ID/GTM_CLIENT_SECRET) como variables de entorno, o "
            f"corre `python auth_setup.py` una vez para generar '{TOKEN_PATH}' "
            "localmente."
        )
    creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(GoogleAuthRequest())
        with open(TOKEN_PATH, "w") as f:
            f.write(creds.to_json())
        logger.info("Token refrescado y guardado en %s", TOKEN_PATH)
    return creds


def _service():
    return build("tagmanager", "v2", credentials=_load_credentials(), cache_discovery=False)


def _path(*parts: str) -> str:
    return "/".join(parts)


def _err(action: str, e: Exception) -> Dict[str, Any]:
    """Convierte cualquier error de la API en una respuesta legible en vez de
    dejar que la excepción tumbe la llamada MCP sin explicación."""
    if isinstance(e, HttpError):
        status = e.resp.status if e.resp is not None else "desconocido"
        try:
            detail = json.loads(e.content.decode("utf-8")).get("error", {}).get("message", str(e))
        except Exception:
            detail = str(e)
        logger.error("Error HTTP %s en %s: %s", status, action, detail)
        return {"ok": False, "action": action, "http_status": status, "error": detail}
    logger.exception("Error inesperado en %s", action)
    return {"ok": False, "action": action, "error": str(e)}


def _require(confirm: bool, action: str) -> Optional[Dict[str, Any]]:
    """Bloquea acciones de escritura si confirm no llegó explícitamente en True."""
    if not confirm:
        return {
            "ok": False,
            "action": action,
            "error": (
                "No ejecuté nada: esta acción modifica algo en vivo y requiere "
                "confirm=true explícito en la llamada."
            ),
        }
    return None


# ---------------------------------------------------------------------------
# Lectura: cuentas, contenedores, workspaces
# ---------------------------------------------------------------------------

@mcp.tool()
def list_accounts() -> Dict[str, Any]:
    """Lista las cuentas de Google Tag Manager a las que tiene acceso esta credencial."""
    try:
        resp = _service().accounts().list().execute()
        return {"ok": True, "accounts": resp.get("account", [])}
    except Exception as e:
        return _err("list_accounts", e)


@mcp.tool()
def list_containers(account_id: str) -> Dict[str, Any]:
    """Lista los contenedores dentro de una cuenta de GTM.

    Args:
        account_id: ID de la cuenta de GTM (obtenido de list_accounts).
    """
    try:
        parent = _path("accounts", account_id)
        resp = _service().accounts().containers().list(parent=parent).execute()
        return {"ok": True, "containers": resp.get("container", [])}
    except Exception as e:
        return _err("list_containers", e)


@mcp.tool()
def list_workspaces(account_id: str, container_id: str) -> Dict[str, Any]:
    """Lista los workspaces (áreas de trabajo) de un contenedor.

    Args:
        account_id: ID de la cuenta de GTM.
        container_id: ID del contenedor.
    """
    try:
        parent = _path("accounts", account_id, "containers", container_id)
        resp = _service().accounts().containers().workspaces().list(parent=parent).execute()
        return {"ok": True, "workspaces": resp.get("workspace", [])}
    except Exception as e:
        return _err("list_workspaces", e)


def _workspace_path(account_id: str, container_id: str, workspace_id: str) -> str:
    return _path(
        "accounts", account_id, "containers", container_id, "workspaces", workspace_id
    )


# ---------------------------------------------------------------------------
# Lectura: tags, triggers, variables
# ---------------------------------------------------------------------------

@mcp.tool()
def list_tags(account_id: str, container_id: str, workspace_id: str) -> Dict[str, Any]:
    """Lista los tags de un workspace, incluyendo cuáles están pausados.

    Args:
        account_id: ID de la cuenta de GTM.
        container_id: ID del contenedor.
        workspace_id: ID del workspace.
    """
    try:
        parent = _workspace_path(account_id, container_id, workspace_id)
        resp = _service().accounts().containers().workspaces().tags().list(parent=parent).execute()
        tags = resp.get("tag", [])
        summary = [
            {
                "tagId": t.get("tagId"),
                "name": t.get("name"),
                "type": t.get("type"),
                "paused": t.get("paused", False),
                "firingTriggerId": t.get("firingTriggerId", []),
                "blockingTriggerId": t.get("blockingTriggerId", []),
            }
            for t in tags
        ]
        return {"ok": True, "tags": summary}
    except Exception as e:
        return _err("list_tags", e)


@mcp.tool()
def get_tag(account_id: str, container_id: str, workspace_id: str, tag_id: str) -> Dict[str, Any]:
    """Obtiene el detalle completo de un tag específico.

    Args:
        account_id: ID de la cuenta de GTM.
        container_id: ID del contenedor.
        workspace_id: ID del workspace.
        tag_id: ID del tag.
    """
    try:
        path = _path(_workspace_path(account_id, container_id, workspace_id), "tags", tag_id)
        tag = _service().accounts().containers().workspaces().tags().get(path=path).execute()
        return {"ok": True, "tag": tag}
    except Exception as e:
        return _err("get_tag", e)


@mcp.tool()
def list_triggers(account_id: str, container_id: str, workspace_id: str) -> Dict[str, Any]:
    """Lista los triggers de un workspace.

    Args:
        account_id: ID de la cuenta de GTM.
        container_id: ID del contenedor.
        workspace_id: ID del workspace.
    """
    try:
        parent = _workspace_path(account_id, container_id, workspace_id)
        resp = _service().accounts().containers().workspaces().triggers().list(parent=parent).execute()
        triggers = resp.get("trigger", [])
        summary = [
            {"triggerId": t.get("triggerId"), "name": t.get("name"), "type": t.get("type")}
            for t in triggers
        ]
        return {"ok": True, "triggers": summary}
    except Exception as e:
        return _err("list_triggers", e)


@mcp.tool()
def list_variables(account_id: str, container_id: str, workspace_id: str) -> Dict[str, Any]:
    """Lista las variables de un workspace.

    Args:
        account_id: ID de la cuenta de GTM.
        container_id: ID del contenedor.
        workspace_id: ID del workspace.
    """
    try:
        parent = _workspace_path(account_id, container_id, workspace_id)
        resp = _service().accounts().containers().workspaces().variables().list(parent=parent).execute()
        variables = resp.get("variable", [])
        summary = [
            {"variableId": v.get("variableId"), "name": v.get("name"), "type": v.get("type")}
            for v in variables
        ]
        return {"ok": True, "variables": summary}
    except Exception as e:
        return _err("list_variables", e)


# ---------------------------------------------------------------------------
# Escritura: pausar / reanudar tags
# ---------------------------------------------------------------------------

def _set_tag_paused(
    account_id: str, container_id: str, workspace_id: str, tag_id: str, paused: bool, confirm: bool
) -> Dict[str, Any]:
    guard = _require(confirm, "set_tag_paused")
    if guard:
        return guard
    try:
        svc = _service().accounts().containers().workspaces().tags()
        path = _path(_workspace_path(account_id, container_id, workspace_id), "tags", tag_id)
        current = svc.get(path=path).execute()
        before = current.get("paused", False)
        current["paused"] = paused
        updated = svc.update(path=path, body=current).execute()
        return {
            "ok": True,
            "tagId": tag_id,
            "name": updated.get("name"),
            "paused_before": before,
            "paused_after": updated.get("paused", paused),
            "note": "Esto solo cambia el workspace. Para que el sitio en vivo lo refleje, "
            "hay que crear y publicar una versión (create_version + publish_version).",
        }
    except Exception as e:
        return _err("set_tag_paused", e)


@mcp.tool()
def pause_tag(
    account_id: str, container_id: str, workspace_id: str, tag_id: str, confirm: bool = False
) -> Dict[str, Any]:
    """Pausa un tag (deja de dispararse). No publica el contenedor.

    Args:
        account_id: ID de la cuenta de GTM.
        container_id: ID del contenedor.
        workspace_id: ID del workspace.
        tag_id: ID del tag a pausar.
        confirm: Debe ser True para ejecutar el cambio.
    """
    return _set_tag_paused(account_id, container_id, workspace_id, tag_id, True, confirm)


@mcp.tool()
def resume_tag(
    account_id: str, container_id: str, workspace_id: str, tag_id: str, confirm: bool = False
) -> Dict[str, Any]:
    """Reanuda (des-pausa) un tag. No publica el contenedor.

    Args:
        account_id: ID de la cuenta de GTM.
        container_id: ID del contenedor.
        workspace_id: ID del workspace.
        tag_id: ID del tag a reanudar.
        confirm: Debe ser True para ejecutar el cambio.
    """
    return _set_tag_paused(account_id, container_id, workspace_id, tag_id, False, confirm)


# ---------------------------------------------------------------------------
# Auditoría — el reemplazo determinista del "léeme la pantalla y adivina"
# ---------------------------------------------------------------------------

@mcp.tool()
def audit_workspace(account_id: str, container_id: str, workspace_id: str) -> Dict[str, Any]:
    """Audita un workspace y regresa una lista estructurada de hallazgos:
    tags sin ningún trigger, triggers que no dispara ningún tag, posibles
    tags duplicados (mismo tipo + mismos triggers), y si algún tag tiene
    Consent Mode configurado. Es de solo lectura, no cambia nada.

    Args:
        account_id: ID de la cuenta de GTM.
        container_id: ID del contenedor.
        workspace_id: ID del workspace.
    """
    try:
        svc = _service().accounts().containers().workspaces()
        parent = _workspace_path(account_id, container_id, workspace_id)
        tags = svc.tags().list(parent=parent).execute().get("tag", [])
        triggers = svc.triggers().list(parent=parent).execute().get("trigger", [])

        trigger_ids = {t.get("triggerId") for t in triggers}
        used_trigger_ids = set()
        tags_without_triggers = []
        signature_groups: Dict[str, List[str]] = {}
        consent_configured = []

        for t in tags:
            firing = t.get("firingTriggerId", []) or []
            blocking = t.get("blockingTriggerId", []) or []
            used_trigger_ids.update(firing)
            used_trigger_ids.update(blocking)

            if not firing and not t.get("paused", False):
                tags_without_triggers.append({"tagId": t.get("tagId"), "name": t.get("name")})

            signature = f"{t.get('type')}::{sorted(firing)}"
            signature_groups.setdefault(signature, []).append(
                f"{t.get('name')} ({t.get('tagId')})"
            )

            consent = t.get("consentSettings", {}).get("consentStatus")
            if consent == "NEEDED":
                consent_configured.append({"tagId": t.get("tagId"), "name": t.get("name")})

        triggers_without_tags = [
            {"triggerId": tid, "name": next((t.get("name") for t in triggers if t.get("triggerId") == tid), tid)}
            for tid in trigger_ids - used_trigger_ids
        ]

        possible_duplicates = [
            names for names in signature_groups.values() if len(names) > 1
        ]

        return {
            "ok": True,
            "total_tags": len(tags),
            "total_triggers": len(triggers),
            "tags_without_triggers": tags_without_triggers,
            "triggers_without_any_tag": triggers_without_tags,
            "possible_duplicate_tags": possible_duplicates,
            "tags_with_consent_mode": consent_configured,
            "consent_mode_configured_anywhere": len(consent_configured) > 0,
        }
    except Exception as e:
        return _err("audit_workspace", e)


# ---------------------------------------------------------------------------
# Versiones: crear, listar, publicar (= "ir a producción")
# ---------------------------------------------------------------------------

@mcp.tool()
def create_version(
    account_id: str,
    container_id: str,
    workspace_id: str,
    name: str,
    notes: str = "",
    confirm: bool = False,
) -> Dict[str, Any]:
    """Crea una nueva versión a partir de los cambios pendientes en el workspace.
    NO la publica — solo la deja lista para revisar y publicar después.

    Args:
        account_id: ID de la cuenta de GTM.
        container_id: ID del contenedor.
        workspace_id: ID del workspace.
        name: Nombre de la versión.
        notes: Descripción de qué cambió y por qué.
        confirm: Debe ser True para ejecutar.
    """
    guard = _require(confirm, "create_version")
    if guard:
        return guard
    try:
        path = _workspace_path(account_id, container_id, workspace_id)
        body = {"name": name, "notes": notes}
        resp = (
            _service()
            .accounts()
            .containers()
            .workspaces()
            .create_version(path=path, body=body)
            .execute()
        )
        version = resp.get("containerVersion", {})
        return {
            "ok": True,
            "versionId": version.get("containerVersionId"),
            "name": version.get("name"),
            "compilerError": resp.get("compilerError", False),
            "syncStatus": resp.get("syncStatus"),
        }
    except Exception as e:
        return _err("create_version", e)


@mcp.tool()
def list_versions(account_id: str, container_id: str) -> Dict[str, Any]:
    """Lista el historial de versiones de un contenedor (para elegir a cuál
    hacer rollback, por ejemplo).

    Args:
        account_id: ID de la cuenta de GTM.
        container_id: ID del contenedor.
    """
    try:
        parent = _path("accounts", account_id, "containers", container_id)
        resp = _service().accounts().containers().versions().list(parent=parent).execute()
        versions = resp.get("containerVersion", [])
        summary = [
            {
                "versionId": v.get("containerVersionId"),
                "name": v.get("name"),
                "deleted": v.get("deleted", False),
            }
            for v in versions
        ]
        return {"ok": True, "versions": summary}
    except Exception as e:
        return _err("list_versions", e)


@mcp.tool()
def publish_version(
    account_id: str, container_id: str, version_id: str, confirm: bool = False
) -> Dict[str, Any]:
    """Publica una versión — esto SÍ va a producción y afecta el sitio en vivo.
    Úsalo tanto para publicar una versión nueva como para hacer rollback a una
    versión anterior (pásale el version_id de la versión vieja).

    Args:
        account_id: ID de la cuenta de GTM.
        container_id: ID del contenedor.
        version_id: ID de la versión a publicar.
        confirm: Debe ser True para ejecutar. Esta acción es de alto riesgo
            porque afecta producción de inmediato.
    """
    guard = _require(confirm, "publish_version")
    if guard:
        return guard
    try:
        path = _path("accounts", account_id, "containers", container_id, "versions", version_id)
        resp = _service().accounts().containers().versions().publish(path=path).execute()
        version = resp.get("containerVersion", {})
        return {
            "ok": True,
            "published_versionId": version.get("containerVersionId"),
            "name": version.get("name"),
            "compilerError": resp.get("compilerError", False),
        }
    except Exception as e:
        return _err("publish_version", e)


if __name__ == "__main__":
    # Si Render (u otro host) define PORT, corre como servicio HTTP —
    # necesario para que sea un conector MCP remoto en Claude, igual que
    # "Gustavo google ads- mcp". Sin PORT, corre por stdio (útil para
    # probarlo local con un cliente MCP en tu laptop).
    port = os.environ.get("PORT")
    if port:
        mcp.settings.host = "0.0.0.0"
        mcp.settings.port = int(port)
        logger.info("Arrancando por HTTP (streamable-http) en 0.0.0.0:%s", port)
        mcp.run(transport="streamable-http")
    else:
        mcp.run()
