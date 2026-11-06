"""Troca de tráfego e amostragem, sem dependências além de Python e Docker."""
import argparse
import json
import subprocess
import time
from collections import Counter
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]


def compose(*args, **kwargs):
    return subprocess.run(['docker', 'compose', *args], cwd=ROOT, check=True,
                          text=True, encoding='utf-8', **kwargs)


def config(green):
    if not 0 <= green <= 100:
        raise ValueError('Percentual deve estar entre 0 e 100')
    servers = []
    for name, weight in [('blue', 100-green), ('green', green)]:
        if weight:
            servers.append(f'    server {name}:8000 weight={weight} max_fails=0;')
    return ('upstream loja {\n' + '\n'.join(servers) + '\n}\n'
            'server {\n    listen 80;\n    location / {\n'
            '        proxy_pass http://loja;\n        proxy_next_upstream off;\n'
            '        proxy_connect_timeout 2s;\n        proxy_read_timeout 5s;\n'
            f'        add_header X-Release-Weight "{green}" always;\n'
            '    }\n}\n')


def fetch(url):
    try:
        response = urlopen(Request(url, headers={'Connection': 'close'}), timeout=5)
    except HTTPError as error:
        response = error
    with response:
        return response.status, json.loads(response.read()), response.headers


def switch(green):
    content = config(green)
    for name, weight in [('blue', 100-green), ('green', green)]:
        if weight:
            compose('exec', '-T', name, 'python', '-c',
                    "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2)")
    # O backup fica fora de conf.d, pois o Nginx lê todos os arquivos *.conf.
    shell = '''set -eu
cat > /tmp/release-candidate
master=$(cat /var/run/nginx.pid)
old_workers=$(cat /proc/$master/task/$master/children)
cp /etc/nginx/conf.d/default.conf /tmp/release-backup
cp /tmp/release-candidate /etc/nginx/conf.d/default.conf
if nginx -t && nginx -s reload; then
    for pid in $old_workers; do
        attempt=0
        while kill -0 "$pid" 2>/dev/null; do
            attempt=$((attempt + 1))
            if [ "$attempt" -ge 100 ]; then
                echo 'Workers antigos ainda estão drenando; confira os logs.' >&2
                exit 1
            fi
            sleep 0.1
        done
    done
    exit 0
else
    cp /tmp/release-backup /etc/nginx/conf.d/default.conf
    exit 1
fi
'''
    compose('exec', '-T', 'nginx', 'sh', '-c', shell, input=content)
    # O sinal de reload é assíncrono: só concluir após uma resposta da nova configuração.
    for _ in range(50):
        try:
            status, _, headers = fetch('http://127.0.0.1:8080/health')
            if status == 200 and headers.get('X-Release-Weight') == str(green):
                print(f'Tráfego aplicado: Blue {100-green}% | Green {green}%')
                return
        except (OSError, ValueError):
            pass
        time.sleep(0.1)
    raise RuntimeError('Reload não confirmado. Confira os logs antes de continuar.')


def sample(url, count):
    versions, statuses = Counter(), Counter()
    for _ in range(count):
        try:
            status, data, _ = fetch(url)
            versions[data.get('versao', 'desconhecida')] += 1
            statuses[str(status)] += 1
        except (URLError, TimeoutError, OSError, ValueError):
            statuses['erro_de_conexao_ou_resposta'] += 1
    result = {'requisicoes': count, 'versoes': dict(versions), 'status': dict(statuses)}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('canary')
    p.add_argument('percent', type=int, choices=range(101), metavar='0..100')
    p = sub.add_parser('blue-green')
    p.add_argument('environment', choices=['blue', 'green'])
    sub.add_parser('rollback')
    p = sub.add_parser('sample')
    p.add_argument('--url', default='http://127.0.0.1:8080/')
    p.add_argument('--count', type=int, default=100)
    args = parser.parse_args()
    if args.command == 'sample':
        if args.count < 1:
            parser.error('--count deve ser positivo')
        sample(args.url, args.count)
    else:
        green = args.percent if args.command == 'canary' else (
            100 if args.command == 'blue-green' and args.environment == 'green' else 0)
        switch(green)


if __name__ == '__main__':
    main()
