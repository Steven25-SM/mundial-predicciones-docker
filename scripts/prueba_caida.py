"""Prueba educativa de carga sostenida y fallo controlado para MundialLab12.

Ejecutar dentro de la red Docker del proyecto:
    python scripts/prueba_caida.py --url http://nginx --duration 70 --workers 20

El script SOLO envía solicitudes GET a /health y registra resultados.
NO detiene ni reinicia contenedores: estas acciones se ejecutan manualmente
con `docker compose stop app1` / `docker compose start app1`.
"""

import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import threading
import time
import urllib.error
import urllib.request


def request_health(url, timeout):
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            body = response.read(2048)
            status = response.status
            try:
                node = json.loads(body).get('node') if status == 200 else None
            except (ValueError, AttributeError, TypeError):
                node = None
            return status, node, round((time.perf_counter() - started) * 1000, 1), None
    except urllib.error.HTTPError as exc:
        return exc.code, None, round((time.perf_counter() - started) * 1000, 1), str(exc)
    except Exception as exc:
        return 0, None, round((time.perf_counter() - started) * 1000, 1), str(exc)


def main():
    parser = argparse.ArgumentParser(description='Carga continua + evidencia de fallo controlado por nodo')
    parser.add_argument('--url', default='http://nginx', help='Servidor Nginx dentro de Docker')
    parser.add_argument('--duration', type=int, default=70, help='Segundos de prueba (30-300)')
    parser.add_argument('--workers', type=int, default=20, help='Concurrencia (1-100)')
    parser.add_argument('--stop-second', type=int, default=20, help='Aviso para detener nodo 1')
    parser.add_argument('--restart-second', type=int, default=45, help='Aviso para reiniciarlo')
    args = parser.parse_args()
    if not 30 <= args.duration <= 300:
        parser.error('duration debe estar entre 30 y 300 segundos')
    if not 1 <= args.workers <= 100:
        parser.error('workers debe estar entre 1 y 100')
    if not (5 <= args.stop_second < args.restart_second < args.duration - 5):
        parser.error('debe cumplirse 5 <= stop-second < restart-second < duration-5')

    url = args.url.rstrip('/') + '/health'
    start = time.monotonic()
    lock = threading.Lock()
    stop_event = threading.Event()
    totals = Counter()
    by_node = Counter()
    http_codes = Counter()
    windows = defaultdict(lambda: {'peticiones': 0, 'exitosas': 0, 'fallidas': 0,
                                   'por_nodo': Counter(), 'codigos_http': Counter(),
                                   'latencias_ms': []})
    errors = Counter()

    def worker():
        while not stop_event.is_set():
            t = time.monotonic()
            if t - start >= args.duration:
                break
            code, node, latency, error = request_health(url, 5)
            bucket = int((t - start) // 5)
            ok = code == 200 and bool(node)
            with lock:
                totals['peticiones'] += 1
                totals['exitosas' if ok else 'fallidas'] += 1
                http_codes[str(code)] += 1
                window = windows[bucket]
                window['peticiones'] += 1
                window['exitosas' if ok else 'fallidas'] += 1
                window['codigos_http'][str(code)] += 1
                window['latencias_ms'].append(latency)
                if ok:
                    by_node[str(node)] += 1
                    window['por_nodo'][str(node)] += 1
                if error:
                    errors[error[:120]] += 1

    def show_interval(idx):
        with lock:
            w = windows.get(idx)
            if not w:
                print(f'[{idx * 5:02d}-{(idx+1)*5:02d}s] sin respuestas terminadas', flush=True)
                return
            nodes = ', '.join(f'{node}={n}' for node, n in sorted(w['por_nodo'].items())) or 'ninguno'
            print(f'[{idx * 5:02d}-{(idx+1)*5:02d}s] '
                  f'OK={w["exitosas"]} ERROR={w["fallidas"]} | nodos: {nodes}', flush=True)

    print('=== PRUEBA DE FALLO CONTROLADO /health ===', flush=True)
    print(f'Destino: {url} | Duración: {args.duration}s | Concurrencia: {args.workers}', flush=True)
    print('IMPORTANTE: esta prueba NO detiene nodos automáticamente.', flush=True)
    print(f'A los {args.stop_second}s: ejecuta en otra terminal `docker compose stop app1`', flush=True)
    print(f'A los {args.restart_second}s: ejecuta en otra terminal `docker compose start app1`', flush=True)
    print('-' * 64, flush=True)

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(worker) for _ in range(args.workers)]
        next_bucket = 0
        announced = set()
        while True:
            elapsed = time.monotonic() - start
            sec = int(elapsed)
            for moment, action in ((args.stop_second, 'DETENER app1: docker compose stop app1'),
                                   (args.restart_second, 'RECUPERAR app1: docker compose start app1')):
                if sec >= moment and moment not in announced:
                    announced.add(moment)
                    print(f'\n>>> SEGUNDO {sec}: {action} <<<\n', flush=True)
            while (next_bucket + 1) * 5 <= elapsed and next_bucket * 5 < args.duration:
                show_interval(next_bucket)
                next_bucket += 1
            if elapsed >= args.duration:
                break
            time.sleep(0.15)
        stop_event.set()
        for future in futures:
            future.result()

    measured = round(time.monotonic() - start, 3)
    recorded_windows = []
    for idx in sorted(windows):
        w = windows[idx]
        latencies = sorted(w['latencias_ms'])
        recorded_windows.append({
            'inicio_seg': idx * 5, 'fin_seg': (idx + 1) * 5,
            'peticiones': w['peticiones'], 'exitosas': w['exitosas'],
            'fallidas': w['fallidas'], 'por_nodo': dict(w['por_nodo']),
            'codigos_http': dict(w['codigos_http']),
            'latencia_p95_ms': latencies[max(0, min(len(latencies)-1, int(len(latencies)*.95)))] if latencies else None,
        })
    report = {
        'fecha_utc': datetime.now(timezone.utc).isoformat(),
        'experimento': 'Interrupcion manual de app1 durante carga HTTP sostenida',
        'url': url, 'duracion_solicitada_seg': args.duration, 'duracion_real_seg': measured,
        'trabajadores_concurrentes': args.workers,
        'aviso_detener_app1_seg': args.stop_second,
        'aviso_reiniciar_app1_seg': args.restart_second,
        'nota': 'Los avisos NO ejecutan stop/start. Registrar en video los momentos reales.',
        'total_solicitudes': totals['peticiones'],
        'exitosas': totals['exitosas'], 'fallidas': totals['fallidas'],
        'peticiones_por_seg': round(totals['peticiones']/measured, 2),
        'codigos_http': dict(http_codes), 'peticiones_por_nodo': dict(by_node),
        'errores_frecuentes': dict(errors.most_common(5)),
        'intervalos_5seg': recorded_windows,
    }
    output = Path(__file__).resolve().parents[1] / 'evidencias'
    output.mkdir(parents=True, exist_ok=True)
    filename = 'caida_nodo_{}.json'.format(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    destination = output / filename
    destination.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
    print('\n' + '=' * 64)
    print('RESUMEN FINAL')
    for field in ('total_solicitudes', 'exitosas', 'fallidas', 'peticiones_por_seg', 'codigos_http', 'peticiones_por_nodo'):
        print(f'{field}: {report[field]}')
    print(f'Reporte JSON: {destination}')
    print('Si detuviste app1, comprueba que vuelva a estar activo al finalizar.')


if __name__ == '__main__':
    main()
