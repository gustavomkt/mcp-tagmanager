"""
Corre este script UNA SOLA VEZ, en una máquina con navegador (tu laptop, no
un servidor headless), para generar token.json.

Qué hace: abre tu navegador, te pide iniciar sesión con la cuenta de Google
que tiene acceso a tu(s) cuenta(s) de Tag Manager, te muestra la pantalla de
consentimiento de los scopes de Tag Manager, y guarda el token resultante
(incluyendo refresh token) en token.json. server.py usa ese archivo para
autenticarse y lo refresca solo cuando expira — no vuelves a tocar esto salvo
que revoques el acceso o cambies de cuenta.

Requisito previo: haber creado un OAuth Client ID tipo "Desktop app" en
Google Cloud Console y descargado su JSON como client_secret.json en esta
misma carpeta (ver README.md, paso 3).
"""

import os

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/tagmanager.edit.containers",
    "https://www.googleapis.com/auth/tagmanager.publish",
    "https://www.googleapis.com/auth/tagmanager.readonly",
]

CLIENT_SECRETS_PATH = os.environ.get("GTM_CLIENT_SECRETS", "client_secret.json")
TOKEN_PATH = os.environ.get("GTM_TOKEN_PATH", "token.json")


def main() -> None:
    if not os.path.exists(CLIENT_SECRETS_PATH):
        raise SystemExit(
            f"No encontré '{CLIENT_SECRETS_PATH}'.\n\n"
            "Descárgalo desde Google Cloud Console → APIs y servicios → "
            "Credenciales → tu OAuth Client ID (tipo 'Desktop app') → "
            "Download JSON, y guárdalo en esta carpeta con ese nombre "
            "(o define la variable de entorno GTM_CLIENT_SECRETS con la ruta)."
        )

    flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS_PATH, SCOPES)
    creds = flow.run_local_server(port=0)

    with open(TOKEN_PATH, "w") as f:
        f.write(creds.to_json())

    print(f"Listo. Guardé el token en '{TOKEN_PATH}'.")
    print("Ya puedes correr server.py (o conectarlo como MCP en Claude).")


if __name__ == "__main__":
    main()
