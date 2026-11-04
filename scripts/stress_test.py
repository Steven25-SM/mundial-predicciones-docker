"""Prueba de carga para MundialLab12 con desglose real de peticiones por nodo.

Ejemplos dentro de la red Docker:
  python scripts/stress_test.py --url http://app1:8000 --path /health --requests 1000 --workers 50
  python scripts/stress_test.py --url http://app2:8000 --path /health --requests 1000 --workers 50
  python scripts/stress_test.py --url http://nginx --path /health --requests 1000 --workers 50

La respuesta JSON de /health incluye {"status":"ok","node":"<id>"}.
Se guarda un archivo de evidencia JSON por ejecución.
"""
import argparse
import concurrent.futures
from collections import Counter
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import re
import time
import urllib.error
import urllib.parse
import urllib.request


def percentile(values, pct):
    if not values:
        return 0.0
    values = sorted(values)
    return values[min(len(values) - 1, math.ceil(len(values) * pct / 100) - 1)]


def request_one(url):
    start = time.perf_counter()
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            body = response.read()[:1000].decode(errors="replace")
            return (response.status, (time.perf_counter() - start) * 1000, body)
    except urllib.error.HTTPError as exc:
        return (exc.code, (time.perf_counter() - start) * 1000, str(exc))
    except Exception as exc:
        return (0, (time.perf_counter() - start) * 1000, str(exc))


def main():
    parser = argparse.ArgumentParser(description="Carga HTTP y reparto de solicitudes por nodo")
    parser.add_argument("--url", default="http://localhost:8080")
    parser.add_argument("--requests", type=int, default=300)
    parser.add_argument("--workers", type=int, default=20)
    parser.add_argument("--path", default="/ranking")
    args = parser.parse_args()
    if args.requests < 1 or not (1 <= args.workers <= 500):
        parser.error("requests debe ser positivo y workers debe estar entre 1 y 500")
    target = args.url.rstrip("/") + "/" + args.path.lstrip("/")

    started = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        responses = list(pool.map(lambda _: request_one(target), range(args.requests)))
    elapsed = time.perf_counter() - started
    durations = [r[1] for r in responses]
    ok = sum(1 for r in responses if 200 <= r[0] < 400)
    codes = Counter(str(r[0]) for r in responses)

    report = {
        "fecha_utc": datetime.now(timezone.utc).isoformat(),
        "url": target,
        "solicitudes": args.requests,
        "concurrencia": args.workers,
        "exitosas": ok,
        "fallidas": args.requests - ok,
        "codigos_http": dict(sorted(codes.items())),
        "duracion_seg": round(elapsed, 3),
        "peticiones_por_seg": round(args.requests / elapsed, 2),
        "latencia_p50_ms": round(percentile(durations, 50), 2),
        "latencia_p95_ms": round(percentile(durations, 95), 2),
        "latencia_max_ms": round(max(durations), 2),
    }

    if args.path.rstrip("/") == "/health":
        by_node = Counter()
        unidentified = 0
        for code, _, body in responses:
            try:
                data = json.loads(body)
                node = data.get("node")
            except (ValueError, AttributeError, TypeError):
                node = None
            if node and 200 <= code < 400:
                by_node[str(node)] += 1
            else:
                unidentified += 1
        report["peticiones_por_nodo"] = dict(sorted(by_node.items()))
        report["respuestas_sin_nodo"] = unidentified
        report["nota"] = "El nodo es el identificador hostname real enviado por /health."

    output_dir = Path(__file__).resolve().parents[1] / "evidencias"
    output_dir.mkdir(exist_ok=True)
    host = urllib.parse.urlparse(target).netloc
    safe_host = re.sub(r"[^a-zA-Z0-9_-]+", "_", host)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
    output = output_dir / f"stress_{safe_host}_{args.requests}req_{args.workers}workers_{timestamp}.json"
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    print(f"\nReporte creado en {output}")
    if ok != args.requests:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
