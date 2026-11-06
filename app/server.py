"""API pequena para identificar qual versão recebeu cada requisição."""
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit


def response_for(path, version, environment):
    url = urlsplit(path)
    if url.path not in ('/', '/health', '/checkout'):
        return 404, {'erro': 'Rota não encontrada'}
    data = {'versao': version, 'ambiente': environment}
    if url.path == '/health':
        data['status'] = 'ok'
    elif url.path == '/checkout':
        # Falha controlada para mostrar que healthcheck não substitui teste de negócio.
        fault = parse_qs(url.query).get('falha') == ['1']
        if environment == 'green' and fault:
            return 500, {**data, 'erro': 'Falha simulada no checkout novo'}
        data['mensagem'] = 'Checkout novo' if version == 'v2' else 'Checkout atual'
    else:
        data['mensagem'] = 'Loja de exemplo - estratégias de deployment'
    return 200, data


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        status, data = response_for(self.path, os.getenv('APP_VERSION', 'v1'),
                                    os.getenv('APP_ENVIRONMENT', 'blue'))
        payload = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(payload)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(payload)


if __name__ == '__main__':
    ThreadingHTTPServer(('0.0.0.0', 8000), Handler).serve_forever()
