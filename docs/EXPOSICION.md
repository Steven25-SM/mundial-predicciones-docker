# Guion de exposición — 5 a 7 minutos

## Diapositiva 1. Problema y objetivo
- Problema: obtener una forma ordenada de registrar los pronósticos de partidos, competir en grupo y calcular puntos con criterios transparentes.
- Objetivo: aplicación educativa, sin dinero real, escalable horizontalmente.

## Diapositiva 2. Actores y requisitos
- Participante: crea cuenta, pronostica, administra sus grupos, consulta clasificación.
- Propietario de sala: invita, renombra, retira miembros, administra su grupo.
- Administrador: crea partidos y publica resultados.
- Regla: 5 exacto, 3 ganador, 2 margen, +2 racha cada tres, +1 por anticipación >24 horas.

## Diapositiva 3. Arquitectura de solución
- Mostrar `diagramas/arquitectura.png`.
- Navegador → Nginx → FastAPI app1 / FastAPI app2 → PostgreSQL compartido.
- Docker Compose: contenedores; balanceo Nginx `least_conn`; volumen persistente.

## Diapositiva 4. Implementación
- Mostrar sitio, cuenta, pronóstico, creación de sala, ingreso por código y tabla de posiciones.
- Indicar validaciones, contraseña PBKDF2, protección CSRF y sesiones firmadas.

## Diapositiva 5. Pruebas y resiliencia
- Mostrar 10 tests automáticos aprobados (si reproducidos en la PC).
- Mostrar estrés 300/20 y 600/40 con reportes JSON reales.
- Mostrar alternancia de nodos `/health` y probar parar/reiniciar app1.

## Diapositiva 6. Conclusiones
1. En primer lugar, se implementó una aplicación educativa que registra pronósticos y calcula puntuaciones mediante reglas verificables.
2. Asimismo, el despliegue contenerizado permitió separar interfaz, lógica y persistencia, simplificando la puesta en marcha.
3. Por otra parte, el uso de dos réplicas detrás de Nginx demostró un esquema básico de escalamiento horizontal y distribución de peticiones.
4. Además, las pruebas funcionales y de carga proporcionan evidencias reproducibles para evaluar el comportamiento del sistema.
5. Finalmente, la arquitectura local satisface el objetivo del ejercicio y puede evolucionar hacia servicios cloud con controles de producción adicionales.

> No afirmar métricas de rendimiento o continuidad que todavía no estén documentadas en los JSON/capturas de tu ejecución.
