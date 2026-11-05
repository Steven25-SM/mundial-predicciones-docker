"""Ejecuta las pruebas REALES y guarda un reporte legible de los escenarios.

Uso en la raiz del proyecto (con pytest/httpx y requisitos instalados):
    python scripts/pruebas_detalladas.py
El runner usa la suite real en tests/ y NO toca la BD de Docker.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
EVIDENCIAS = ROOT / "evidencias"
EVIDENCIAS.mkdir(parents=True, exist_ok=True)

CASOS = [
    ("test_full_journey", "Flujo funcional completo", "Registro de participante, inicio de sesión, alta de partido, pronóstico 2-1, creación de sala, publicación 2-1, ranking 6 puntos, validación 422 y rechazo CSRF 403."),
    ("test_exact_result_and_early_bonus", "Marcador exacto y anticipación", "Pronóstico 2-1; real 2-1; registrado 25 h antes => 5 puntos por exactitud + 1 por anticipación = 6."),
    ("test_correct_winner_only", "Acierto del ganador", "Pronóstico 1-0; real 3-1; registrado 10 min antes => 3 puntos por ganador; diferencia errónea."),
    ("test_correct_margin_adds_two", "Margen correcto", "Pronóstico 3-1; real 2-0; registrado 10 min antes => ganador 3 + margen 2 = 5."),
    ("test_draw_correct_without_exact_score", "Empate correcto", "Pronóstico 2-2; real 0-0 => 3 puntos por empate, sin exactitud."),
    ("test_wrong_prediction_is_zero_last_minute", "Pronóstico incorrecto", "Pronóstico 0-2; real 2-0; registrado 10 min antes => 0 puntos."),
    ("test_early_strictly_more_than_24_hours", "Límite de 24 horas", "A 24 h exactas no hay bonus; a 24 h y 1 segundo hay +1 de anticipación."),
    ("test_third_straight_correct_gets_two_points", "Racha de tres aciertos", "Tres aciertos consecutivos del ganador: bonos de racha 0, 0 y +2."),
    ("test_unpredicted_match_resets_streak", "Racha interrumpida", "Tres partidos finalizados, sin pronóstico en el segundo => total 6 puntos y racha 1."),
    ("test_unfinished_match_does_not_count", "Partido sin finalizar", "Un partido sin marcador final no suma puntos => total 0."),
]


def ejemplos_calculados():
    sys.path.insert(0, str(ROOT / "app"))
    from scoring import score_prediction
    kickoff = datetime(2026, 12, 1, 20, 0)
    anticipado = kickoff - timedelta(hours=25)
    tarde = kickoff - timedelta(minutes=10)
    tests = [
        ("Marcador exacto", (2, 1, 2, 1, anticipado, kickoff)),
        ("Ganador correcto", (1, 0, 3, 1, tarde, kickoff)),
        ("Margen correcto", (3, 1, 2, 0, tarde, kickoff)),
        ("Empate correcto", (2, 2, 0, 0, tarde, kickoff)),
        ("Pronóstico incorrecto", (0, 2, 2, 0, tarde, kickoff)),
    ]
    out = []
    for title, args in tests:
        result = score_prediction(*args)
        out.append({
            "ejemplo": title,
            "pronostico": f"{args[0]}-{args[1]}",
            "real": f"{args[2]}-{args[3]}",
            "base": result["base"],
            "diferencia": result["difference"],
            "anticipacion": result["anticipation"],
            "total": result["total"],
        })
    return out


def main():
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    args = [sys.executable, "-m", "pytest", "-vv", "-rA", "--tb=short", "tests"]
    print("=" * 72)
    print("LABORATORIO 12 — PRUEBAS AUTOMATICAS CON DETALLES")
    print("Suite real: tests/test_routes.py + tests/test_scoring.py")
    print("BD de pruebas: SQLite en memoria; NO modifica PostgreSQL de Docker")
    print("Ejecutando 10 casos reales...\n", flush=True)
    result = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    output = result.stdout + ("\n" + result.stderr if result.stderr else "")
    print(output)
    statuses = {}
    for line in output.splitlines():
        match = re.search(r"tests/[^\s]+::(test_\w+)\s+(PASSED|FAILED|SKIPPED|ERROR)", line)
        if match:
            statuses[match.group(1)] = match.group(2)
    summary = ["LABORATORIO 12 — EVIDENCIA DE PRUEBAS AUTOMATICAS", "", "LISTADO DETALLADO DE VALIDACIONES:"]
    cases_json = []
    for i, (key, label, desc) in enumerate(CASOS, start=1):
        state = statuses.get(key, "SIN RESULTADO")
        line = f"{i:02d}. [{state}] {label}\n    Se probó: {desc}"
        print(line)
        summary.append(line)
        cases_json.append({"test": key, "prueba": label, "detalle": desc, "resultado": state})
    summary += ["", "EJEMPLOS REALES CALCULADOS POR scoring.py:"]
    examples = []
    try:
        examples = ejemplos_calculados()
        for e in examples:
            line = (f"- {e['ejemplo']}: pronóstico {e['pronostico']}, resultado {e['real']} => "
                    f"base {e['base']} + margen {e['diferencia']} + anticipación {e['anticipacion']} = {e['total']} puntos")
            print(line)
            summary.append(line)
    except Exception as exc:
        summary.append(f"No se pudieron calcular ejemplos adicionales: {exc}")
        print(summary[-1])
    passed = sum(c["resultado"] == "PASSED" for c in cases_json)
    complete = result.returncode == 0 and passed == len(CASOS)
    summary.append(f"\nRESULTADO: {passed}/{len(CASOS)} aprobadas; salida pytest={result.returncode}; "
                   + ("SUITE COMPLETA" if complete else "REVISAR PRUEBAS"))
    txt = EVIDENCIAS / f"tests_detallados_{stamp}.txt"
    js = EVIDENCIAS / f"tests_detallados_{stamp}.json"
    txt.write_text("\n".join(summary) + "\n\nSALIDA COMPLETA DE PYTEST:\n" + output, encoding="utf-8")
    js.write_text(json.dumps({
        "fecha_utc": stamp, "casos": cases_json, "aprobados": passed,
        "total": len(CASOS), "suite_completa": complete,
        "ejemplos_calculados": examples,
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    print("\n" + "=" * 72)
    print(summary[-1]); print(f"REPORTE TXT: {txt}"); print(f"REPORTE JSON: {js}")
    sys.exit(0 if complete else 1)


if __name__ == "__main__":
    main()
