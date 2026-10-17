# JFStack Downloader

Proyecto Docker **independiente y autoalojado** que combina JDownloader 2 con un panel autenticado para introducir enlaces, un resolutor prudente de acortadores publicitarios, historial persistente e integración privada con Click'n'Load. No depende de qBittorrent, Jellyfin ni de volúmenes de otras aplicaciones.

[Read in English](../README.md)

> **Versión 0.1.0 (MVP).** Se resuelven automáticamente redirecciones HTTP, etiquetas HTML meta refresh y patrones sencillos de navegación JavaScript estática. Los acortadores con JavaScript complejo, botones temporizados, CAPTCHA y protecciones antibot **no se saltan automáticamente**. Estos casos requieren revisión manual o los plugins propios de JDownloader. `sent` significa entregado a LinkGrabber, no descargado.

## Arquitectura

```text
Navegador / curl
    | Autenticación Basic; puerto 8080 solo en localhost
    v
JFStack intake (FastAPI + resolución de URLs + historial SQLite)
    | 127.0.0.1:9666 (Click'n'Load; nunca publicado en el host)
    v
JDownloader 2 (LinkGrabber + gestor + interfaz HTTPS puerto 5800)
    | SOLO sus propios volúmenes
    +-- ./data/config      (estado de JD)
    +-- ./data/downloads   (archivos descargados)

FastAPI solo utiliza ./data/app (SQLite)
```

La aplicación utiliza `network_mode: service:jdownloader` para llegar al listener Click'n'Load de JDownloader en localhost; ambos contenedores **no comparten montajes del sistema de archivos**. No requiere cuenta MyJDownloader.

## Requisitos

- Servidor Linux con Docker Engine y Docker Compose v2, acceso para descargar imágenes y consultar las URLs.
- Python 3 para el inicializador local (no hace falta durante la ejecución habitual).
- Aproximadamente 1 GB de RAM libre o más según la carga de JDownloader, y espacio para las descargas.
- Acceso privado preferiblemente mediante túnel SSH o VPN/proxy inverso con TLS.

## Instalación

```bash
git clone https://github.com/YOUR-ORG/docker-jdownloader.git
cd docker-jdownloader
python3 scripts/init_env.py
docker compose config --quiet
docker compose up -d --build
docker compose ps
```

Sustituye el repositorio de ejemplo por el tuyo o descomprime el ZIP y ejecuta los comandos desde el directorio extraído. `init_env.py` genera `.env` y dos contraseñas aleatorias independientes, ajusta UID/GID según el usuario que lo ejecute sin root, crea los directorios locales y aplica permisos 600 al `.env`. Repetirlo conserva las contraseñas anteriores.

**Acceso local:**

- Panel: <http://127.0.0.1:8080> (HTTP Basic; `APP_USERNAME` y `APP_PASSWORD` en `.env`).
- Interfaz JDownloader: <https://127.0.0.1:5800> (HTTPS y login propio; `JD_WEB_USERNAME` y `JD_WEB_PASSWORD`). El certificado inicial autofirmado puede provocar una advertencia en el navegador. Configura un certificado fiable o un proxy inverso cuando corresponda.

La imagen Docker utilizada es comunitaria, no oficial de JDownloader. El primer arranque puede ser más lento mientras se inicializa y actualiza la aplicación.

### Acceso por SSH desde tu equipo

Por defecto los puertos solo escuchan en loopback del host. Desde el ordenador cliente:

```bash
ssh -N -L 8080:127.0.0.1:8080 -L 5800:127.0.0.1:5800 user@your-server
```

Después abre las dos URLs localhost anteriores. Puedes exponer **solo las interfaces necesarias** a través de tu propia infraestructura WireGuard/proxy privado con HTTPS y control de acceso, pero nunca el listener Click'n'Load (9666). Si el proxy está en Docker, dirige el panel al contenedor `jdownloader` por el puerto interno `8000`; la interfaz JDownloader usa HTTPS por `5800` y requiere un backend TLS correctamente configurado. No cambies `BIND_ADDRESS` a `0.0.0.0` en redes no confiables.


### Si Click'n'Load aparece como desconectado

En la interfaz de JD abre **Settings → Advanced Settings**, busca `RemoteAPI: Extern Interface` (también puedes buscar `cnl`) y comprueba que esté habilitada. Mantén la opción **Extern Interface Localhost Only** habilitada porque los contenedores comparten un espacio de red y no hace falta exponer el puerto 9666. JDownloader puede pedir autorización para recibir enlaces desde una aplicación externa; acepta el envío desde tu propia instancia en el diálogo de JD. Reinicia JD si has cambiado ajustes que lo necesiten.

```bash
docker compose restart jdownloader app
docker compose logs --tail=80 app
```

La etiqueta *JDownloader connected* confirma que el listener responde; no demuestra que una autorización pendiente se haya aceptado.

## Uso

1. Abre el panel y pega una URL pública HTTP(S) por línea (hasta `APP_MAX_BATCH`, 20 por defecto).
2. Pulsa **Resolve & send**. Los enlaces entran en cola y se procesan con dos workers por defecto.
3. Consulta URL original, URL resultante, método de resolución y estado.
4. `sent`: abre la **interfaz de JDownloader** y revisa **LinkGrabber**. Confirma o inicia descargas según la configuración de JDownloader.
5. `ready`: el endpoint CNL no está disponible; arranca/revisa JD y usa **Send URL to JDownloader** o **Retry resolution**.
6. `manual`: la página requiere interacción, CAPTCHA o redirecciones no soportadas; puedes abrirla desde tu navegador o enviar el enlace a JDownloader para que lo analice con sus plugins.
7. `error`: falló la validación o el procesamiento. Revisa la causa antes de reintentar.

El panel **no sustituye** la gestión de progreso y CAPTCHA de la interfaz nativa de JDownloader. El historial conserva URLs completas, incluidos posibles tokens en parámetros; protege las copias de seguridad de SQLite.

### API

La API usa HTTP Basic y para modificar datos requiere `Content-Type: application/json` y `X-JFStack-Request: 1`. Ejemplo (el comando solicita la contraseña sin incluirla en el histórico de shell):

```bash
curl -u admin -H 'X-JFStack-Request: 1' -H 'Content-Type: application/json' \
  -d '{"links":"https://example.com/file.zip\nhttps://example.org/short"}' \
  http://127.0.0.1:8080/api/jobs
```

Endpoints: `GET /healthz`, `GET /api/status`, `GET /api/jobs`, `POST /api/jobs`, `POST /api/jobs/{id}/retry`, `POST /api/jobs/{id}/send`. `send` entrega la mejor URL disponible tras validar que el destino sea público. El panel no utiliza cuenta MyJDownloader ni sus credenciales remotas.

## Configuración

Todas las opciones se ajustan en un **único** `.env`:

| Variable | Por defecto | Función |
| --- | --- | --- |
| `BIND_ADDRESS` | `127.0.0.1` | Dirección de escucha de las interfaces; mantener loopback por defecto |
| `APP_PORT`, `JD_WEB_PORT` | `8080`, `5800` | Puertos publicados del panel / interfaz JD HTTPS |
| `APP_USERNAME`, `APP_PASSWORD` | `admin`, generada | Credenciales Basic del panel |
| `JD_WEB_USERNAME`, `JD_WEB_PASSWORD` | `admin`, generada | Credenciales HTTPS de JDownloader |
| `PUID`, `PGID` | `1000`, `1000` | Propietario de archivos; el inicializador detecta UID/GID |
| `TZ` | `Europe/Madrid` | Zona horaria |
| `JD_CONFIG_PATH` | `./data/config` | Configuración persistente exclusiva de JD |
| `JD_DOWNLOADS_PATH` | `./data/downloads` | Descargas exclusivas de JD |
| `APP_DATA_PATH` | `./data/app` | SQLite exclusiva del panel |
| `APP_MAX_BATCH` | `20` | Máximo de URLs por envío; rango 1–100 |
| `APP_WORKERS` | `2` | Workers paralelos; rango 1–4 |
| `APP_REQUEST_TIMEOUT` | `12` | Timeout de resolución por enlace; rango 2–30 s |
| `APP_MAX_HOPS` | `8` | Máximo de saltos de redirección/HTML; rango 1–12 |
| `JDOWNLOADER_IMAGE_TAG` | `latest` | Etiqueta de imagen comunitaria; fijar una versión probada en despliegues mantenidos |

Si quieres utilizar rutas absolutas de otros discos, cambia únicamente las variables de ruta correspondientes y confirma permisos de escritura del usuario `PUID:PGID`. **No se necesita ninguna referencia a otros stacks.**

## Operación y copias de seguridad

```bash
# Estado y registros
docker compose ps
docker compose logs -f --tail=100

# Parada y arranque (sin perder la persistencia)
docker compose down
docker compose up -d --build

# Actualización de imágenes (revisar y respaldar antes)
docker compose pull
docker compose up -d --build

# Copia offline consistente de SQLite y JD
docker compose down
tar -czf jfstack-jdownloader-backup.tar.gz .env data/

# Restauración: recuperar .env y data/ en la carpeta del proyecto y después
# docker compose up -d --build
```

Los trabajos pendientes se recuperan después de reiniciar. Si hay un fallo entre la aceptación del enlace por JDownloader y el registro de la respuesta en el panel, reintentar podría generar un duplicado: revisa LinkGrabber antes de reintentos dudosos. No uses `docker compose down -v` para limpiar los datos.

## Seguridad y limitaciones

- Las dos interfaces solo están publicadas en `127.0.0.1`; utiliza SSH o un acceso privado con **HTTPS fiable**. El panel utiliza Basic, por lo que HTTP remoto sin cifrar expondría las credenciales.
- CNL solo escucha en localhost dentro del espacio de red del proyecto. La interfaz de JD tiene HTTPS/autenticación y VNC está deshabilitado.
- Se admiten únicamente HTTP(S), DNS/IP públicas, puertos web estándar, validación de redirecciones y límites de tamaño de inspección HTML y número de saltos. En esta versión **no se ejecuta JavaScript de anuncios**. No envíes enlaces no confiables: los plugins propios de JDownloader pueden seguir otras redirecciones de manera independiente.
- Las peticiones salientes se hacen desde el servidor, lo que puede revelar su IP pública al servicio de destino. No existe VPN/proxy obligatorio ni servicio para saltar restricciones.
- El soporte completo para puertas publicitarias HTML/JS y el seguimiento del progreso nativo quedan como mejoras futuras. Consulta las [notas de arquitectura](ARCHITECTURE.md).

## Desarrollo

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r backend/requirements.txt pytest pytest-asyncio httpx
APP_PASSWORD=local-development-password-long-enough APP_DB_PATH=/tmp/jfstack-dev.sqlite3 \
  PYTHONPATH=backend uvicorn app.main:app --reload --app-dir backend
PYTHONPATH=backend pytest -q tests
```

Para la entrega real de enlaces necesitas JDownloader con su listener Click'n'Load activo. Los tests utilizan fixtures locales y **no** demuestran integración con JD, red Docker, DNS real ni descargas completadas. Ejecuta una prueba real en el servidor de destino antes de depender del servicio.

## Licencia y atribución

El código original de JFStack Downloader se publica bajo licencia MIT (consulta [LICENSE](../LICENSE)). JDownloader y la imagen `jlesage/jdownloader-2` son proyectos independientes con sus propias licencias y responsables; el repositorio no redistribuye sus binarios.
