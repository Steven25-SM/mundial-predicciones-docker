# Guía de despliegue — Mundial Predicciones Docker

Aplicación educativa de pronósticos de fútbol. Repositorio sugerido: **`mundial-predicciones-docker`**.

> **Alcance:** despliegue para **laboratorio o demostración local**. Publicar el código en GitHub **no publica automáticamente una página web en Internet**. Para exposición pública permanente hacen falta un servidor, HTTPS, manejo de secretos, copias de seguridad y medidas de seguridad adicionales.

## Arquitectura

```text
Navegador → localhost:8080 → Nginx (balanceador least_conn)
                                      ├── app1 (FastAPI)
                                      └── app2 (FastAPI)
                                          ↓
                                  PostgreSQL compartido
```

- `db`: PostgreSQL con un volumen persistente.
- `init`: inicializa la base de datos y el administrador (finaliza normalmente con código 0).
- `app1` y `app2`: dos instancias de la misma aplicación.
- `nginx`: proxy inverso y balanceador, expuesto en el puerto **8080**.

## Requisitos

- Docker Desktop con el motor Linux/WSL 2 **o** Docker Engine + plugin Docker Compose.
- Git, si descargarás el proyecto con `git clone` (también puedes descargar el ZIP desde GitHub).
- Puerto **8080** disponible y conexión a Internet para descargar imágenes al iniciar por primera vez.
- No es necesario instalar Python, PostgreSQL ni Nginx por separado.

### Instalación en Windows 10/11

1. Si no tienes WSL 2, abre PowerShell **como administrador** y ejecuta:

   ```powershell
   wsl --install
   wsl --update
   ```

   Reinicia Windows si se solicita. Consulta las instrucciones oficiales de Docker Desktop: https://docs.docker.com/desktop/setup/install/windows-install/
2. Instala y abre **Docker Desktop**: https://www.docker.com/products/docker-desktop/ . Espera hasta ver que el motor esté funcionando y usa **contenedores Linux**.
3. Descarga el repositorio (sustituye `TU_USUARIO` por el usuario dueño del repositorio):

   ```powershell
   git clone https://github.com/TU_USUARIO/mundial-predicciones-docker.git
   cd mundial-predicciones-docker
   ```

   Si descargaste un ZIP, descomprímelo y abre PowerShell en la carpeta donde está `compose.yaml`.

### Instalación en Linux

Instala Docker Engine y el plugin Compose usando las instrucciones oficiales para tu distribución: https://docs.docker.com/engine/install/ . Después:

```bash
git clone https://github.com/TU_USUARIO/mundial-predicciones-docker.git
cd mundial-predicciones-docker
cp .env.example .env
```

Continúa desde **Configuración**. Usa `nano .env` o tu editor habitual.

## Configuración (obligatoria)

En Windows, dentro de la carpeta del proyecto:

```powershell
Copy-Item .env.example .env
notepad .env
```

Edita los valores de este archivo **local y privado**:

```dotenv
DB_PASSWORD=UNA_CLAVE_NUEVA_SOLO_LETRAS_Y_NUMEROS
SESSION_SECRET=UNA_CADENA_ALEATORIA_LARGA_Y_PRIVADA
ADMIN_EMAIL=admin@mundial.local
ADMIN_PASSWORD=OTRA_CLAVE_NUEVA_Y_PRIVADA
```

- Cambia **DB_PASSWORD**, **SESSION_SECRET** y **ADMIN_PASSWORD**; no reutilices las claves de los ejemplos ni otras previamente compartidas.
- `DB_PASSWORD` se inserta en una URL interna; utiliza únicamente letras y números para evitar caracteres que requieran codificación en URL.
- `ADMIN_EMAIL` identifica la cuenta de administración; para pruebas locales no necesita existir realmente.
- **Nunca subas `.env` a GitHub**. Solo debe subirse `.env.example`, que incluye valores ficticios.

## Iniciar la aplicación

Ejecuta desde la carpeta que contiene `compose.yaml`:

```powershell
docker compose up -d --build
docker compose ps
```

La primera ejecución descarga imágenes y compila la aplicación. Deben aparecer `db`, `app1`, `app2` y `nginx` ejecutándose; `init` debe haber terminado correctamente (`Exited (0)` / `Completed`).

Abre en el navegador:

- **Página principal:** http://localhost:8080
- **Inicio de sesión:** http://localhost:8080/ingresar
- **Ranking:** http://localhost:8080/ranking
- **Comprobación de salud:** http://localhost:8080/health

El administrador inicia sesión con los valores `ADMIN_EMAIL` y `ADMIN_PASSWORD` configurados inicialmente en `.env`.

## Comprobar los dos nodos

Desde **PowerShell en Windows**:

```powershell
1..12 | ForEach-Object {
    (Invoke-RestMethod http://localhost:8080/health).node
}
```

Normalmente aparecen identificadores de ambos contenedores: Nginx distribuye las peticiones. Si solo aparece uno, revisa el estado de ambos nodos con `docker compose ps`.

### Demostrar tolerancia a fallos

```powershell
docker compose stop app1
Invoke-RestMethod http://localhost:8080/health
docker compose ps -a
docker compose start app1
docker compose ps
```

Durante la detención de `app1`, `app2` debería continuar respondiendo. Nginx podría producir errores transitorios mientras detecta el fallo; anótalos como parte del resultado real. Tras recuperar `app1`, vuelve a probar `/health`.

## Prueba de estrés opcional

En PowerShell, desde la carpeta del proyecto, con los servicios funcionando:

```powershell
docker run --rm --network mundial-lab12_default -v "${PWD}:/workspace" -w /workspace python:3.12-slim python scripts/stress_test.py --url http://nginx --path /ranking --requests 1000 --workers 50
```

El nombre `mundial-lab12_default` viene de `name: mundial-lab12` dentro de `compose.yaml`, **no del nombre de la carpeta o del repositorio**. El script de pruebas registra resultados en `evidencias/`, que deben permanecer locales salvo que se decida publicar evidencia anonimizada.

Las pruebas de carga deben hacerse sobre servicios y equipos propios, aumentando gradualmente la concurrencia y monitorizando recursos con `docker compose stats`.

## Operación y solución de problemas

| Problema | Qué hacer |
|---|---|
| Error `dockerDesktopLinuxEngine` | Abrir Docker Desktop y esperar al motor en ejecución. |
| No aparece la página | `docker compose ps` y `docker compose logs --tail 100 nginx app1 app2 db init`. |
| Puerto 8080 ocupado | Cambiar en `compose.yaml` `"8080:80"` por `"8088:80"`, levantar el proyecto y abrir `http://localhost:8088`. |
| Contenedor `init` terminado | Es normal si terminó con código **0**; inicializa la BD y finaliza. |
| Contraseña de BD cambiada después de usar la app | El volumen de PostgreSQL conserva la clave anterior; restablece la clave original o migra la contraseña correctamente. **No elimines el volumen si hay datos importantes.** |
| Cambios en código no aparecen | `docker compose up -d --build` y luego recarga fuerte del navegador (`Ctrl + Shift + R`). |
| Nginx devuelve 502 | Revisa `docker compose ps` y espera a que las aplicaciones estén `healthy`. |

Ver los logs:

```powershell
docker compose logs --tail 100 app1 app2 nginx db init
```

Detener el despliegue **sin borrar la base de datos**:

```powershell
docker compose down
```

Reanudar posteriormente:

```powershell
docker compose up -d
```

> ⚠️ **No ejecutes `docker compose down -v`** si quieres conservar usuarios, salas, pronósticos y partidos: `-v` elimina los volúmenes de datos.

## Seguridad y limitaciones

- La solución está diseñada para demostraciones locales, no como plataforma pública lista para producción.
- `.env` contiene secretos; se excluye del repositorio mediante `.gitignore`. Nunca lo adjuntes a capturas, videos o incidencias.
- Si publicaste secretos por accidente, **rota las claves**; borrarlas del archivo no garantiza eliminarlas del historial de Git.
- Antes de exponer una instancia a Internet, configura HTTPS, autenticación y cookies seguras, backups, protección contra abuso, revisión de dependencias y gestión segura de secretos.
- GitHub aloja el **código**; la aplicación se ejecutará en la máquina del compañero que complete estos pasos.

## Estructura de interés

```text
compose.yaml             # PostgreSQL, init, app1, app2, nginx
.env.example             # Variables de ejemplo, sin credenciales reales
app/                     # FastAPI, HTML y CSS
nginx/default.conf       # Balanceo de carga
scripts/stress_test.py   # Pruebas de estrés
tests/                   # Pruebas automáticas
docs/                    # Informe y diagramas
evidencias/               # Salida local de pruebas, no publicar por defecto
```

**Documentación oficial:** https://docs.docker.com/compose/gettingstarted/ y https://docs.github.com/en/migrations/importing-source-code/using-the-command-line-to-import-source-code/adding-locally-hosted-code-to-github
