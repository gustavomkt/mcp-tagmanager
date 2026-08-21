# GTM Fixer — MCP + panel web de Google Tag Manager

Dos formas de usar la misma automatización de Tag Manager, sobre el mismo
servidor y las mismas credenciales:

1. **Conector MCP** (`/mcp`) — para operar por chat con Claude. Cada acción
   pide explícitamente cuenta / contenedor / workspace (o versión) — nada
   implícito — y las que afectan producción (pausar un tag, publicar una
   versión) exigen `confirm=true`.
2. **Panel web** (`/`) — para operar con clics, desde el navegador, **sin
   tener Claude abierto**. Protegido con contraseña. Ver la sección
   "Panel web" más abajo.

Ambos le pegan a exactamente las mismas funciones Python — no hay lógica
duplicada entre el chat y el panel.

Esto reemplaza el enfoque original "abre Chrome y lee la pantalla", que era
la pestaña más frágil del panel de despacho porque dependía de la interfaz
web de GTM en vez de una API tipada.

Costo: la Tag Manager API es gratis (sin cargos de Google por uso normal).
Se despliega como un Web Service gratuito en Render — mismo plan, mismo
costo (cero) que "Gustavo google ads- mcp".

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
     Manager.
   - `DASHBOARD_PASSWORD` = una contraseña que tú elijas, para entrar al
     panel web (`/`). Sin esta variable, el panel no deja entrar a nadie —
     nunca queda abierto por accidente.
5. Create Web Service. Cuando termine el build, copia la URL pública
   (algo como `https://mcp-tagmanager.onrender.com`).

## 3. Conectarlo en Claude (uso por chat)

Agrégalo como conector MCP remoto nuevo, apuntando a la URL de Render del
paso anterior (con `/mcp` al final, ej. `https://mcp-tagmanager.onrender.com/mcp`
— es el endpoint streamable-http estándar). Ya está hecho: conectado como
**"Gustavo GTM Fixer"**.

## 4. Panel web (uso sin Claude abierto)

Abre `https://mcp-tagmanager.onrender.com/` (la misma URL del servicio,
sin `/mcp`) desde cualquier navegador — tu compu, tu celular, donde sea.
Pide la contraseña (`DASHBOARD_PASSWORD`) y luego deja:

- Ver cuentas → contenedores → workspaces con selects encadenados.
- Ver los tags de un workspace y pausarlos/reanudarlos con un clic.
- Correr la auditoría de buenas prácticas.
- Crear una versión y publicarla (con un modal de confirmación antes de
  tocar producción).

No necesita que tengas una sesión de Claude abierta ni que estés en este
chat — es una aplicación web normal, corriendo 24/7 (dentro de las
limitaciones del plan gratuito de Render, ver "Notas de estabilidad").

**Seguridad del panel:** la contraseña protege el acceso, pero viaja sobre
HTTPS normal (no hay 2FA ni límite de intentos todavía). Es razonable para
uso personal; si en algún momento lo compartes con más gente o quieres algo
más robusto (usuarios separados, límite de intentos, etc.), dilo y se
agrega — no cuesta nada extra en infraestructura, solo más código.

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

## Roadmap: llevar Google Ads, Meta y Shopify al mismo modelo

La idea de "un panel único, operable sin Claude, para las 4 plataformas"
aplica el mismo patrón que aquí a Google Ads, Meta/Social Ads y Shopify.
Para Tag Manager fue posible porque yo mismo generé y controlo su
`GTM_REFRESH_TOKEN`. Para los otros tres, el bloqueo real es que sus
conectores MCP actuales ("Gustavo google ads- mcp", "Gustavo Social Ads",
"Shopify") guardan sus credenciales dentro de la infraestructura de cada
conector — no como algo que yo pueda leer y reutilizar. Dos caminos,
según cada caso:

1. **Si ya están en un servidor propio (como este), con URL pública** —
   se le puede agregar el mismo panel `/` + `/api/*` sin pedir ninguna
   credencial nueva, reusando lo que ya está desplegado. Falta confirmar
   cuáles de los tres viven así.
2. **Si no** — hace falta que generes y me compartas (pegándolo tú mismo
   donde corresponda, nunca yo escribiéndolo) el equivalente al
   `GTM_REFRESH_TOKEN` de cada uno: un token de Meta Marketing API de larga
   duración, un Admin API access token de Shopify, o el refresh token +
   developer token de Google Ads. Con eso puedo desplegar un servicio
   dedicado por plataforma, mismo patrón, mismo costo ($0 en Render).

## Créditos/promos de nube (AWS, Google Cloud)

Investigué qué ofrecen ambos para correr esto gratis más tiempo o sin el
cold-start del plan gratuito de Render:

- **Google Cloud**: crédito de bienvenida para cuentas nuevas (histórico:
  ~$300 USD por 90 días) más un "Always Free tier" permanente que incluye
  1 instancia e2-micro de Compute Engine gratis de por vida en ciertas
  regiones de EE.UU. — ahí sí cabría correr esto 24/7 sin dormirse.
- **AWS**: Free Tier con varios servicios gratis los primeros 12 meses
  (incluye una instancia EC2 t2.micro/t3.micro).

Ambos requieren **crear una cuenta con tarjeta de crédito/débito** (aunque
no se cobre nada dentro del free tier) — eso es una acción que no puedo
hacer yo por ti: entra en la categoría de "crear cuentas y meter datos de
pago", que tengo prohibido hacer aunque me des permiso explícito. Si quieres
ir por esa vía, créala tú y me compartes las credenciales de acceso al
servidor (no la tarjeta) para que yo despliegue ahí — dime cuál prefieres y
seguimos.

Mientras tanto, Render Free sigue siendo la opción de $0 sin fricción de
cuenta nueva, con el único costo real siendo el cold-start de ~50s tras
inactividad.

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
