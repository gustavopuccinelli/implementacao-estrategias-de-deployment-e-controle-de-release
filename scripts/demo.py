"""Teste de integração: execute depois de docker compose up -d --build --wait."""
import json
from datetime import datetime, timezone
from pathlib import Path
from traffic import fetch, sample, switch


def main():
    evidence = {'executado_em': datetime.now(timezone.utc).isoformat(), 'etapas': []}
    output = Path(__file__).resolve().parents[1] / 'evidencias'
    output.mkdir(exist_ok=True)
    try:
        for port, version in [(8081, 'v1'), (8082, 'v2')]:
            status, data, _ = fetch(f'http://127.0.0.1:{port}/checkout')
            assert status == 200 and data['versao'] == version, data
        # Canary com promoção por etapas, seguido de Blue-Green e reversão.
        for label, green, fault in [
            ('Estado inicial', 0, False),
            ('Canary 10%', 10, False),
            ('Canary 50%', 50, False),
            ('Canary 100%', 100, False),
            ('Rollback do Canary', 0, False),
            ('Blue-Green: troca para Green', 100, False),
            ('Blue-Green: rollback', 0, False),
            ('Canary com regressão simulada', 10, True),
            ('Rollback após regressão', 0, True),
        ]:
            print('\n' + label, flush=True)
            switch(green)
            url = 'http://127.0.0.1:8080/checkout' + ('?falha=1' if fault else '')
            result = sample(url, 100)
            evidence['etapas'].append({'nome': label, 'green_percentual': green, **result})
            actual = result['versoes'].get('v2', 0)
            tolerance = 0 if green in (0, 100) else 3
            assert abs(actual-green) <= tolerance, result
            assert sum(result['versoes'].values()) == 100, result
            expected_errors = actual if fault else 0
            assert result['status'].get('500', 0) == expected_errors, result
            assert result['status'].get('200', 0) == 100-expected_errors, result
        # Um destino parado deve bloquear a promoção e manter Blue funcionando.
        from traffic import compose
        import subprocess
        compose('stop', 'green')
        try:
            try:
                switch(100)
            except subprocess.CalledProcessError:
                pass
            else:
                raise AssertionError('A promoção de Green parado deveria falhar')
            status, data, _ = fetch('http://127.0.0.1:8080/')
            assert status == 200 and data['versao'] == 'v1', data
            evidence['promocao_de_destino_parado_bloqueada'] = True
        finally:
            compose('start', 'green')
        evidence['resultado'] = 'aprovado'
    finally:
        try:
            switch(0)
        finally:
            (output / 'resultado.json').write_text(
                json.dumps(evidence, ensure_ascii=False, indent=2), encoding='utf-8')
    print('\nDemonstração concluída. Evidências em evidencias/resultado.json')


if __name__ == '__main__':
    main()
