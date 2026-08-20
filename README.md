# MCP de Google Tag Manager

Conector MCP dedicado a Tag Manager, construido con el mismo criterio que
"Gustavo google ads- mcp": cada acción pide explícitamente cuenta /
contenedor / workspace (o versión) — nada implícito — y las acciones que
afectan producción (pausar un tag, publicar una versión) exigen
`confirm=true`. Esto reemplaza el enfoque anterior "abre Chrome y lee la
pantalla", que era la pestaña más frágil del panel porque dependía de la
interfaz web en vez de una API tipada.

Costo: la Tag Manager API es gratis (sin cargos de Google por uso normal).
Se despliega como un segundo Web Service gratuito en Render, igual que
"Gustavo google ads- mcp" — mismo plan, mismo costo (cero) que ya tienes hoy.

## Cómo están organizadas las credenciales (patrón estandarizado)

Este servidor NO usa un archivo `token.json` en producción — usa variables
de entorno, igual que el resto de tus conectores en Render:

- `GOOGLE_ADS_CLIENT_ID` / `GOOGLE_ADS_CLIENT_SECRET` — se **reutilizan**,
  son el mismo cliente OAuth que ya usa "Gustavo google ads- mcp". No hace
  falta crear un cliente nuevo por herramienta.
- `GTM_REFRESH_TOKEN` — el único valor nuevo, específico de Tag Manager.

Si algún día prefieres un cliente OAuth separado solo para Tag Manager,
puedes definir `GTM_CLIENT_ID` / `GTM_CLIENT_SECRET` y tienen prioridad
sobre los de Google Ads.

## 1. Subir el código a GitHub

1. Repo ya creado: `github.com/gustavomkt/mcp-tagmanager` (público).
2. Sube todos los archivos de esta carpeta **excepto** `client_secret.json`,
   `token.json` y `.flow_state.json` (esos son solo para pruebas locales;
   nunca deben subirse — el `.gitignore` ya los excluye).

## 2. Desplegar en Render

1. Render → New → Web Service → conecta el repo `mcp-tagmanager`.
2. Runtime: Docker (detecta el `Dockerfile` automáticamente).
3. Plan: Free.
4. Environment Variables (agrégalas tú mismo en el dashboard de Render —
   son credenciales, así que no te las voy a rellenar yo):
   - `GOOGLE_ADS_CLIENT_ID` = el mismo valor que ya tienes en el servicio de
     Google Ads.
   - `GOOGLE_ADS_CLIENT_SECRET` = el mismo valor que ya tienes en el servicio
     de Google Ads.
   - `GTM_REFRESH_TOKEN` = el refresh token que ya generamos para Tag
     Manager (te lo compartí aparte en el chat).
5. Create Web Service. Cuando termine el build, copia la URL pública
   (algo como `https://mcp-tagmanager.onrender.com`).

## 3. Conectarlo en Claude

Agrégalo como conector MCP remoto nuevo, apuntando a la URL de Render del
paso anterior (con `/mcp` al final, ej. `https://mcp-tagmanager.onrender.com/mcp`
— es el endpoint streamable-http estándar). Una vez conectado, avísame y
actualizo la pestaña de Tag Manager del panel de control para que use estas
tools reales en vez de las instrucciones basadas en navegador.

## Alternativa: correrlo local con un archivo (sin Render)

Si alguna vez quieres correrlo en tu laptop en vez de Render:

```bash
pip install -r requirements.txt
python auth_setup.py   # una vez, abre tu navegador
python server.py       # sin PORT definido, corre por stdio
```

`server.py` primero busca `GTM_REFRESH_TOKEN` + client_id/secret en
variables de entorno; si no las encuentra, cae de vuelta a `token.json`.

## Tools disponibles

Lectura (no cambian nada):

- `list_accounts()`
- `list_containers(account_id)`
- `list_workspaces(account_id, container_id)`
- `list_tags(account_id, container_id, workspace_id)`
- `get_tag(account_id, container_id, workspace_id, tag_id)`
- `list_triggers(account_id, container_id, workspace_id)`
- `list_variables(account_id, container_id, workspace_id)`
- `audit_workspace(account_id, container_id, workspace_id)` — tags sin
  trigger, triggers sin tag, posibles duplicados, y si hay Consent Mode
  configurado. Es la versión confiable de lo que antes le pedíamos a Claude
  in Chrome que "leyera de la pantalla y adivinara".
- `list_versions(account_id, container_id)`

Escritura (piden `confirm=true`):

- `pause_tag(...)` / `resume_tag(...)` — pausa o reanuda un tag en el
  workspace. No publica el contenedor.
- `create_version(...)` — crea una versión a partir del workspace. No
  publica.
- `publish_version(account_id, container_id, version_id, confirm=true)` —
  publica una versión (va a producción). Úsalo también para hacer rollback:
  pásale el `version_id` de una versión anterior de `list_versions`.

## Notas de estabilidad

- Cada llamada a la API de Google está envuelta en manejo de errores que
  regresa un mensaje claro (`{"ok": false, "error": "..."}`) en vez de
  tumbar la conexión MCP sin explicación — esa clase de fallo silencioso fue
  parte de por qué los otros conectores "se caían" sin avisar.
- El token se refresca solo en cada llamada usando el refresh token; si
  algún día se revoca (cambio de contraseña, revocación manual en
  myaccount.google.com), el error te lo va a decir explícitamente y solo
  hace falta generar un `GTM_REFRESH_TOKEN` nuevo.
- Al ser un Web Service gratuito de Render, se "duerme" tras un rato sin
  uso y la primera llamada después de eso tarda ~50 segundos en responder —
  igual que "Gustavo google ads- mcp" hoy. Es la causa más probable de que
  los conectores parezcan "caerse": no es un error, es el cold start del
  plan gratuito. Si en algún momento quieres eliminar esa demora, la única
  vía es un plan de pago en Render — decisión tuya, no algo que yo cambie
  sin que me lo pidas.
