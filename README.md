# Implementação: Estratégias de deployment e controle de release

Exemplo prático para o trabalho de Gerenciamento de Configuração de Software. A ideia é observar como Canary e Blue-Green mudam o destino das requisições e como voltar à versão anterior quando algo dá errado.

A aplicação representa uma loja simples e responde em JSON. Não realiza compras nem grava dados. O foco é a implantação, não as funcionalidades da loja.

## Ambiente

```text
                         +-- Blue  (v1, porta 8000)
Cliente -> Nginx :8080 ---|
                         +-- Green (v2, porta 8000)
```

| Endereço local | Função |
| --- | --- |
| http://localhost:8080 | Entrada pelo Nginx; usada na demonstração |
| http://localhost:8081 | Acesso direto ao Blue para testes |
| http://localhost:8082 | Acesso direto ao Green antes de receber tráfego |

As portas são vinculadas apenas ao computador local. Os serviços se comunicam pela rede interna do Compose. O Nginx começa encaminhando 100% do tráfego para Blue.

## Como executar

É necessário ter Git, Python 3.10 ou superior e Docker com o plugin Compose v2. No Windows, use Docker Desktop em modo de containers Linux. Os comandos abaixo funcionam em PowerShell e em terminais Linux/macOS. Se o Python estiver disponível como `python3` ou `py`, substitua `python` nos comandos.

```bash
git clone https://github.com/gustavopuccinelli/implementacao-estrategias-de-deployment-e-controle-de-release.git
cd implementacao-estrategias-de-deployment-e-controle-de-release
docker compose up -d --build --wait
python scripts/traffic.py sample
```

Abra os endereços no navegador para ver os campos `versao` e `ambiente`. Para testar o checkout, acrescente `/checkout` ao endereço. A rota `/health` verifica se a aplicação está respondendo.

## 1. Canary

No Canary, as duas versões atendem ao mesmo tempo. A nova versão recebe apenas uma parte das requisições.

```bash
python scripts/traffic.py canary 10
python scripts/traffic.py sample --count 100
python scripts/traffic.py canary 50
python scripts/traffic.py sample --count 100
python scripts/traffic.py canary 100
python scripts/traffic.py sample --count 100
```

Em 10%, o Nginx usa pesos 90 para Blue e 10 para Green. A amostra deve ficar próxima de 90 respostas v1 e 10 respostas v2. Os pesos representam requisições, não grupos fixos de usuários. Um usuário pode receber versões diferentes em chamadas consecutivas.

Para voltar à v1:

```bash
python scripts/traffic.py rollback
python scripts/traffic.py sample --count 100
```

## 2. Blue-Green

Primeiro, teste a v2 diretamente, sem alterar o tráfego da entrada principal:

```bash
python scripts/traffic.py sample --url http://localhost:8082/checkout --count 10
python scripts/traffic.py blue-green green
python scripts/traffic.py sample --count 100
```

Após a troca, as novas requisições vão para Green. Blue continua ligado para permitir a reversão:

```bash
python scripts/traffic.py blue-green blue
python scripts/traffic.py sample --count 100
```

`rollback` também leva 100% do tráfego para Blue. Neste laboratório, Blue é sempre a v1 estável; o comando não procura automaticamente a última versão de um histórico.

## 3. Simular uma regressão e reverter

A rota `/checkout?falha=1` devolve erro HTTP 500 somente quando atendida pelo Green. A falha é intencional e limitada a essa requisição; sem o parâmetro, Green continua funcionando normalmente.

```bash
python scripts/traffic.py canary 10
python scripts/traffic.py sample --url "http://localhost:8080/checkout?falha=1" --count 100
python scripts/traffic.py rollback
python scripts/traffic.py sample --url "http://localhost:8080/checkout?falha=1" --count 100
```

Na primeira amostra, cerca de 10% das respostas devem apresentar erro. Após o rollback, todas devem voltar a HTTP 200. Isso mostra a redução do impacto e a recuperação do atendimento. O healthcheck permanece saudável durante a regressão, mostrando por que também precisamos de testes de negócio e métricas.

O rollback nesta demonstração é solicitado por comando. Não há monitoramento de produção decidindo automaticamente quando reverter.

## Testes e evidências

```bash
python -m unittest discover -s tests -v
python scripts/demo.py
```

O segundo comando exige os containers em execução. Ele testa os destinos diretamente, as etapas 0/10/50/100%, Blue-Green, os rollbacks, a falha simulada e a rejeição de uma promoção para Green parado. Ao terminar, retorna o tráfego ao Blue.

Os resultados reais são gravados em `evidencias/resultado.json`, com horário, versões e códigos HTTP por etapa. A pasta é ignorada pelo Git para não misturar saídas de execuções diferentes. Os números apresentados acima são expectativas, não registros de uma execução.

O workflow **Testar Canary e Blue-Green**, na aba [Actions](https://github.com/gustavopuccinelli/implementacao-estrategias-de-deployment-e-controle-de-release/actions), executa os testes em cada push e pull request. Também pode ser iniciado por **Run workflow**. Cada execução publica o artefato `evidencias-deployment`, com o JSON e os logs. Esse workflow sobe um ambiente temporário de teste; não publica uma aplicação na internet.

## Como a troca funciona

O script verifica a saúde dos destinos que receberão tráfego, monta o bloco `upstream`, salva um backup da configuração e executa `nginx -t`. Se a validação falhar, restaura o arquivo anterior. Com a configuração válida, envia `nginx -s reload`, aguarda o encerramento dos workers antigos e confirma uma resposta com o cabeçalho da nova configuração. Essa espera evita medir uma mistura das configurações antiga e nova logo após a troca.

O reload é gracioso: requisições já em andamento podem terminar na versão anterior. Não desligamos Blue durante a troca. Desativamos o retry automático do proxy neste laboratório para que os erros da versão candidata apareçam na amostra em vez de serem ocultados por uma segunda tentativa em Blue.

As alterações ficam no container do Nginx. Ao recriá-lo, a configuração volta ao estado inicial (100% Blue). Execute os comandos de troca um por vez. Se recriar Blue ou Green e seus endereços internos mudarem, execute novamente a troca para atualizar a resolução dos nomes no Nginx.

## Estrutura

```text
app/                  API e Dockerfile das duas versões
nginx/                Proxy e configuração inicial
scripts/traffic.py    Troca de tráfego, rollback e amostragem
scripts/demo.py       Demonstração automatizada e evidências
tests/                Testes unitários
.github/workflows/    Testes de integração no GitHub Actions
compose.yaml          Definição dos serviços
docs/apresentacao.md  Roteiro para demonstrar e explicar o trabalho
```

## Limites do exemplo

- v1 e v2 usam o mesmo código-base, com identificação e comportamento definidos por configuração. Em um sistema real, cada release normalmente possui sua própria imagem imutável.
- O exemplo não contém banco de dados, sessões, TLS ou autenticação. Redirecionar tráfego não desfaz dados já gravados nem migrações incompatíveis.
- Um worker facilita observar os pesos. As tolerâncias dos testes são adequadas ao laboratório, não critérios de promoção para produção.
- As tags de imagem fixam as linhas de versão, mas não o digest. Um novo build pode receber correções da imagem base.
- Feature flags e Kubernetes não fazem parte desta implementação; podem ser extensões do grupo.

Para consultar os containers e encerrar:

```bash
docker compose ps
docker compose logs nginx
docker compose down
```

Se alguma porta estiver ocupada, encerre o processo que a utiliza ou adapte as portas e os endereços dos scripts. Se `docker compose` não conseguir acessar o daemon, confirme que Docker Desktop está aberto.

## Relação com o relatório

Este repositório pode acompanhar a seção 6, **Implementação prática**, antes do comparativo e da conclusão da Parte 7. No relatório, descreva a arquitetura, os comandos utilizados e os resultados obtidos em uma execução identificada. A comparação de riscos, custo e limitações deve considerar que este ambiente é apenas uma demonstração local.

## Referências

- [Nginx: upstream e balanceamento por pesos](https://nginx.org/en/docs/http/ngx_http_upstream_module.html).
- [Nginx: reload e controle de processos](https://nginx.org/en/docs/control.html).
- [Docker Compose: ordem de inicialização e healthchecks](https://docs.docker.com/compose/how-tos/startup-order/).
- [AWS: Blue/Green Deployments on AWS](https://docs.aws.amazon.com/whitepapers/latest/blue-green-deployments/introduction.html).
- [Google SRE: Canarying Releases](https://sre.google/workbook/canarying-releases/).
