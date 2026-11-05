# LAB 12 — Capacidad máxima del nodo 1 (video: 1 min 20 s)

**Objetivo:** aumentar progresivamente la concurrencia **sobre un solo nodo** (`app1`) y mostrar cuándo deja de mejorar el rendimiento, se ralentiza o empieza a responder con errores. **No es necesario congelar la laptop.**

**Equipo:** ASUS TUF A15, Ryzen 7 7445HS, 16 GB RAM. **Resultado anterior:** 10,000 solicitudes / 450 concurrentes / 0 errores / 159.02 peticiones por segundo / p95 3,368.89 ms. El nodo **no se cayó**, pero se volvió más lento.

**IMPORTANTE — ANTES DE GRABAR:** copia el archivo `scripts/prueba_limite_async.py` de este kit dentro de `MundialLab12/scripts/`. Este generador usa conexiones asíncronas para probar más de 500 concurrentes sin crear cientos de hilos del cliente. El script anterior `stress_test.py` **no acepta más de 500**. Utiliza el mismo generador en las 3–4 pruebas para compararlas correctamente. El generador también utiliza recursos de tu PC, por lo que no mide exclusivamente el servidor.

## Preparación (sin grabar)

**Terminal 1 — PowerShell dentro de `MundialLab12`**

**`docker compose up -d`**  
*Inicia el proyecto.*

**`docker compose ps`**  
*Confirma que `app1`, `app2`, `nginx` y `db` están activos.*

**Terminal 2 — PowerShell dentro de `MundialLab12`**

**`docker compose stats`**  
*Muestra CPU y RAM de los contenedores. Déjala abierta.*

Abre también **http://localhost:8080/ranking**. Cierra juegos y otras apps pesadas. **Ahora inicia Bandicam.**

## Durante el video — Terminal 1: 3 pruebas y una cuarta opcional

Ejecuta la siguiente **solo cuando termine la anterior**. Detente si aparecen muchos errores, falta RAM o Windows se vuelve inestable.

### 1. Punto de partida: 450 concurrentes

**`docker run --rm --network mundial-lab12_default -v "${PWD}:/workspace" -w /workspace python:3.12-slim python scripts/prueba_limite_async.py --url http://app1:8000/ranking --requests 1000 --workers 450 --timeout 10`**

*Repite el nivel máximo previo de **450 concurrentes**, pero con menos peticiones para ahorrar tiempo. **No es una repetición exacta** del ensayo anterior de 10,000 peticiones.*

### 2. Carga superior: 700 concurrentes

**`docker run --rm --network mundial-lab12_default -v "${PWD}:/workspace" -w /workspace python:3.12-slim python scripts/prueba_limite_async.py --url http://app1:8000/ranking --requests 1500 --workers 700 --timeout 10`**

*Incrementa la concurrencia un 56 % respecto a 450; comprueba si baja el rendimiento o aparecen errores.*

### 3. Carga exigente: 950 concurrentes

**`docker run --rm --network mundial-lab12_default -v "${PWD}:/workspace" -w /workspace python:3.12-slim python scripts/prueba_limite_async.py --url http://app1:8000/ranking --requests 2000 --workers 950 --timeout 10`**

*Más del doble de concurrencia que el nivel anterior de 450. Busca latencia elevada, respuestas fallidas o pérdida de rendimiento.*

### 4. SOLO SI sigue estable y queda tiempo: 1,200 concurrentes

**`docker run --rm --network mundial-lab12_default -v "${PWD}:/workspace" -w /workspace python:3.12-slim python scripts/prueba_limite_async.py --url http://app1:8000/ranking --requests 2500 --workers 1200 --timeout 10`**

*Es el máximo de concurrencia permitido **en este script**, no el máximo real de tu laptop. Omítela si hay errores relevantes, falta de RAM o llevas cerca de 80 segundos.*

## Al finalizar — Terminal 1

**`docker compose ps -a`**  
*Comprueba si `app1` sigue activo o se detuvo.*

**`docker inspect --format '{{.RestartCount}} {{.State.OOMKilled}} {{.State.Status}}' $(docker compose ps -q app1)`**  
*Muestra reinicios, posible falta de memoria y estado del contenedor. Si el contenedor se reinició, no supongas la causa sin revisar los logs.*

**`docker compose logs --tail 20 app1`**  
*Comprueba errores del servidor.*

Muestra `http://localhost:8080/ranking` para comprobar que la **página sigue funcionando mediante Nginx**. Detén Bandicam.

## ¿Qué datos decir o mostrar?

- **`exitosas` y `fallidas`:** disponibilidad de las respuestas HTTP, no prueba de caída física.
- **`peticiones_por_seg`:** capacidad efectiva de procesamiento bajo esa carga.
- **`latencia_p95_exitosas_ms`:** respuesta del 95 % más rápido de las peticiones exitosas; si sube mucho, hay degradación.
- **`docker compose stats`:** CPU y RAM durante la ejecución.
- **`docker compose ps -a` / `docker inspect`:** evidencia de si `app1` se detuvo o reinició.

Los reportes JSON se guardan automáticamente en `MundialLab12/evidencias/`.

**Regla de seguridad:** si el equipo pierde capacidad de respuesta o casi agota la RAM, cancela con **`Ctrl + C`**. Si las pruebas terminan con 0 errores pero la latencia aumenta y los req/s no suben, **eso es saturación/degradación**, una conclusión válida. No afirmes que el nodo se cayó si sigue activo. Para que el video dure 1:20, prioriza los tres primeros niveles; la duración de cada ejecución depende del equipo y no puede garantizarse.
