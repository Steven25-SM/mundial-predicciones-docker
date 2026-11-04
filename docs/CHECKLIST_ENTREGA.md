# Checklist de entrega — Laboratorio 12

Marca solo lo que hayas realizado en tu propia computadora.

## 1. Análisis (2 pts)
- [ ] Explicar problema, usuarios y cinco criterios de puntuación.
- [ ] Requisitos funcionales, no funcionales y seguridad.
- [ ] Justificar por qué entorno local con Docker satisface el escenario de laboratorio.

## 2. Diseño (2 pts)
- [ ] Pegar captura o imagen de `diagramas/arquitectura.png`.
- [ ] Pegar imagen de `diagramas/modelo_datos.png`.
- [ ] Pegar imagen de `diagramas/flujo_puntuacion.png`.
- [ ] Explicar balanceador, dos instancias, persistencia y sesiones compartidas.

## 3. Implementación (2 pts)
- [ ] Captura Docker Desktop / `docker compose ps` con `app1` y `app2` saludables.
- [ ] Captura de inicio, registro y login.
- [ ] Captura creando tres partidos en Admin.
- [ ] Captura de pronósticos de participante.
- [ ] Captura de sala creada con código de invitación.
- [ ] Captura de otro usuario ingresando a la sala.
- [ ] Captura del ranking global y de sala (con puntos).
- [ ] Evidenciar corrección de resultado y recálculo de puntuación.
- [ ] Mostrar salida de `/health` con distintos identificadores de instancia.

## 4. Documentación y pruebas (2 pts)
- [ ] Adjuntar salida de `python -m pytest -q tests`.
- [ ] Ejecutar y guardar prueba de estrés 300 req / 20 workers.
- [ ] Ejecutar y guardar prueba de estrés 600 req / 40 workers.
- [ ] Adjuntar JSON de ambos escenarios y capturas de terminal.
- [ ] Ejecutar y documentar detención de `app1`, confirmando continuidad de `app2`.
- [ ] Adjuntar informe, conclusiones y capturas con títulos/descripción.
- [ ] Exponer el guion de `EXPOSICION.md` con demostración del sitio.

**Aclaración:** el archivo de estrés se crea solamente al ejecutar la prueba; no se incluye una salida inventada.
