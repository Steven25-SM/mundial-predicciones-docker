#!/usr/bin/env python3
"""Prueba HTTP asíncrona sin librerías externas para capacidad de un nodo.

Ejemplo:
python scripts/prueba_limite_async.py --url http://app1:8000/ranking --requests 2000 --workers 700 --timeout 10

Mide el resultado a nivel HTTP, NO diagnostica por sí sola caída de contenedor.
"""
import argparse
import asyncio
from collections import Counter
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import re
import time
from urllib.parse import urlsplit


def pct(values, p):
    if not values:
        return 0.0
    a = sorted(values)
    return round(a[min(len(a) - 1, max(0, math.ceil(len(a) * p / 100) - 1))], 2)


async def single_request(host, port, target, host_header, timeout):
    started = time.perf_counter()
    writer = None
    try:
        async def transaction():
            nonlocal writer
            reader, writer = await asyncio.open_connection(host, port)
            writer.write((
                f"GET {target} HTTP/1.1\r\nHost: {host_header}\r\n"
                "User-Agent: MundialLab12-Capacidad/1.0\r\n"
                "Accept: */*\r\nConnection: close\r\n\r\n"
            ).encode('ascii'))
            await writer.drain()
            first = await reader.readline()
            # Leer toda la respuesta para medir la petición completa, no solo los headers.
            while await reader.read(65536):
                pass
            parts = first.decode('latin-1', errors='replace').split()
            if len(parts) < 2 or not parts[0].startswith('HTTP/'):
                raise ValueError('respuesta HTTP invalida')
            return int(parts[1])
        status = await asyncio.wait_for(transaction(), timeout=timeout)
        return status, (time.perf_counter() - started) * 1000, ''
    except Exception as exc:
        label = 'timeout' if isinstance(exc, asyncio.TimeoutError) else type(exc).__name__
        return 0, (time.perf_counter() - started) * 1000, label
    finally:
        if writer is not None:
            writer.close()
            try:
                await asyncio.wait_for(writer.wait_closed(), timeout=0.5)
            except Exception:
                pass


async def run(args):
    u = urlsplit(args.url)
    if u.scheme != 'http' or not u.hostname:
        raise SystemExit('La URL debe ser http://... (HTTP local, no HTTPS).')
    host = u.hostname
    port = u.port or 80
    target = (u.path or '/') + (('?' + u.query) if u.query else '')
    header = host if not u.port else f'{host}:{port}'
    results = []
    task_num = 0
    started = time.perf_counter()

    async def worker():
        nonlocal task_num
        while True:
            if task_num >= args.requests:
                return
            task_num += 1
            results.append(await single_request(host, port, target, header, args.timeout))

    # Como solo usamos corutinas, no creamos 1000 hilos de Python en el cliente.
    await asyncio.gather(*(worker() for _ in range(min(args.workers, args.requests))))
    elapsed = time.perf_counter() - started
    ok = sum(200 <= status < 400 for status, _, _ in results)
    codes = Counter(str(status) for status, _, _ in results)
    errors = Counter(error for status, _, error in results if error)
    latencies = [lat for status, lat, _ in results if 200 <= status < 400]
    report = {
        'fecha_utc': datetime.now(timezone.utc).isoformat(),
        'objetivo': args.url,
        'solicitudes': args.requests,
        'concurrencia_objetivo': args.workers,
        'timeout_por_peticion_seg': args.timeout,
        'exitosas': ok,
        'fallidas': len(results) - ok,
        'tasa_exito_pct': round(100 * ok / len(results), 2) if results else 0,
        'codigos_http': dict(codes),
        'tipos_error': dict(errors),
        'duracion_seg': round(elapsed, 3),
        'peticiones_por_seg': round(len(results) / elapsed, 2),
        'latencia_p50_exitosas_ms': pct(latencies, 50),
        'latencia_p95_exitosas_ms': pct(latencies, 95),
        'latencia_max_exitosas_ms': round(max(latencies), 2) if latencies else 0,
        'nota': 'Las fallas pueden ser timeout, red, cliente o servidor; no prueban por si solas caida de app1.'
    }
    outdir = Path('/workspace/evidencias') if Path('/workspace').is_dir() else Path(__file__).resolve().parents[1] / 'evidencias'
    outdir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    outpath = outdir / f'limite_app1_{args.workers}workers_{args.requests}req_{stamp}.json'
    outpath.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
    print(json.dumps(report, indent=2, ensure_ascii=False))
    print('\nReporte JSON:', outpath)


def main():
    ap = argparse.ArgumentParser(description='Prueba gradual de capacidad sin dependencias externas')
    ap.add_argument('--url', default='http://app1:8000/ranking')
    ap.add_argument('--requests', type=int, required=True)
    ap.add_argument('--workers', type=int, required=True)
    ap.add_argument('--timeout', type=float, default=10)
    args = ap.parse_args()
    if not (1 <= args.requests <= 100000 and 1 <= args.workers <= 1200 and 1 <= args.timeout <= 30):
        ap.error('Limites: 1-100000 solicitudes, 1-1200 concurrentes, timeout 1-30 segundos')
    asyncio.run(run(args))


if __name__ == '__main__':
    main()
