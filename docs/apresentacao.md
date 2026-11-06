# Roteiro de demonstração

1. Mostre o `compose.yaml`: Blue é v1, Green é v2 e o Nginx é a entrada pública do laboratório.
2. Inicie com `docker compose up -d --build --wait` e execute `python scripts/traffic.py rollback` para garantir o estado inicial.
3. Rode `python scripts/traffic.py sample` e mostre que todas as respostas vêm de v1.
4. Execute `python scripts/traffic.py canary 10` e repita a amostra. Explique que só uma parcela das requisições foi exposta à v2.
5. Teste `/checkout?falha=1` com o comando de amostragem do README. Observe os erros e execute o rollback. Repita a amostra e compare.
6. Acesse Green diretamente em `http://localhost:8082/checkout`. Faça a troca com `python scripts/traffic.py blue-green green`. Agora toda a nova carga vai para v2.
7. Reverta com `python scripts/traffic.py rollback`. Mostre que Blue já estava disponível e não precisou ser reinstalado.
8. Mostre uma execução da aba Actions e baixe as evidências para relacionar o código com os resultados.
9. Encerre com `docker compose down`.

## Perguntas para revisar antes de apresentar

- **Qual a diferença entre as estratégias?** Canary divide tráfego para observar uma versão gradualmente. Blue-Green mantém dois ambientes e troca o destino principal após a validação.
- **Por que o healthcheck não detectou o erro?** A aplicação estava viva, mas uma operação de negócio falhava. Saúde do processo e qualidade da release são verificações diferentes.
- **Por que não parar Blue?** Ele precisa estar disponível e compatível para o rollback rápido.
- **O rollback resolve qualquer problema?** Não. Dados gravados, migrações incompatíveis e efeitos externos exigem tratamento próprio.
- **O Actions faz deploy em produção?** Não. Ele constrói e testa os containers em um runner temporário e salva as evidências.
- **O percentual é por usuário?** Não. O Nginx usa pesos por requisição; não há afinidade de sessão.

Antes de entregar, o grupo deve executar a demonstração e selecionar as evidências reais que vai usar no relatório.
