# libefaturas

Biblioteca em Python para integração com os webservices da AT relacionados com o e-Fatura:

- geração do cabeçalho de autenticação (WS-Security UsernameToken)  
- teste de ligação (TLS + UsernameToken) aos endpoints:
  - e-Fatura (fews/faturas)
  - Comunicação de Séries (SeriesWS)

Foca-se em:

- abstrair a parte chata da criptografia (KS, RSA, AES)  
- dar um teste rápido de infraestrutura (certificados, credenciais, endpoints)  
- servir de base para camadas de alto nível (registo de séries, faturas, etc.)

---

## 1. Quando usar esta biblioteca

Usa esta lib quando:

- queres integrar com:
  - webservice de comunicação de faturas (FatcoreWS)  
  - webservice de comunicação de séries (SeriesWS)  
- já tens:
  - certificado de produtor de software emitido pela AT (cliente TLS)  
  - chave pública / certificado do Sistema de Autenticação (ficheiro .cer/.pem da AT)  
  - credenciais do Portal das Finanças (NIF/subutilizador + password) com permissões WSE

A biblioteca resolve:

- construção do UsernameToken  
- montagem do SOAP Header com WS-Security  
- teste de ligação aos endpoints da AT (produção / homologação), sem precisares de escrever SOAP à mão.

---

## 2. Requisitos

- Python 3.9 ou superior  
- cryptography  
- requests

Instalação típica das dependências no ambiente onde vais usar a lib:

```
pip install cryptography requests
```

Se estiveres a usar o repositório diretamente:

```
cd /caminho/para/libefaturas
pip install -e .
```

---

## 3. Estrutura do package

- libefaturas/
  - __init__.py  
    - API pública (o que importas)
  - security.py  
    - implementação da criptografia / UsernameToken
  - client.py  
    - helpers de ligação e diagnósticos
  - cli.py  
    - implementação da CLI e parsing de argumentos
  - __main__.py  
    - simples entrypoint para `python -m libefaturas`
- README.md  
  - este ficheiro (como usar a lib)
- DOCUMENTATION.md  
  - documentação técnica (modelo de autenticação + arquitetura interna)

---

## 4. API principal

### 4.1. EFaturaCredentials

Representa as credenciais do Portal das Finanças (utilizador/subutilizador):

```
from libefaturas import EFaturaCredentials

creds = EFaturaCredentials(
    username="599999993/37",      # NIF/subutilizador
    password="SENHA_PORTAL",      # senha do Portal das Finanças
)
```

### 4.2. build_username_token

Gera o UsernameToken (Password cifrada, Nonce, Created) a partir das credenciais e da chave pública da AT:

```
from libefaturas import build_username_token

with open("certs/at_public_key.cer", "rb") as f:
    at_public = f.read()

token = build_username_token(
    creds=creds,
    public_key_pem=at_public,
)

print(token.username)  # "599999993/37"
print(token.password)  # Base64(AES_KS(SenhaPF))
print(token.nonce)     # Base64(RSA_KpubSA(KS))
print(token.created)   # Base64(AES_KS(TimestampISO))
```

### 4.3. build_security_header_xml

Gera o fragmento XML do SOAP Header com WS-Security, pronto a injetar no envelope SOAP:

```
from libefaturas import build_security_header_xml

header_xml = build_security_header_xml(token)
print(header_xml)
```

Forma geral:

- `<S:Header>`
  - `<wss:Security ...>`
    - `<wss:UsernameToken>`
      - `<wss:Username>...`
      - `<wss:Password>...`
      - `<wss:Nonce>...`
      - `<wss:Created>...`
    - `</wss:UsernameToken>`
  - `</wss:Security>`
- `</S:Header>`

---

## 5. Teste de ligação (e-Fatura e Séries)

A biblioteca expõe um método de alto nível `test_connection` e um CLI (`python -m libefaturas`) para validar rapidamente:

- se a chave pública da AT é válida  
- se o UsernameToken é gerado sem erro  
- se o certificado cliente é aceite (TLS ok)  
- se o endpoint responde (mesmo com SOAP Fault)

### 5.1. Via Python (programático)

```
from libefaturas import test_connection

result = test_connection(
    username="599999993/37",
    password="SENHA_PORTAL",
    public_key_path="certs/at_public_key.cer",
    endpoint="https://servicos.portaldasfinancas.gov.pt:400/fews/faturas",
    client_cert_path="certs/producer.crt.pem",
    client_key_path="certs/app-wfa-4096.key",
    service="faturas",  # ou "series"
)

print(result)
```

O dicionário `result` contém:

- username_token_ok: se o header foi gerado sem erro  
- tls_ok: se o TLS/HTTP funcionou (sem erro de handshake, etc.)  
- http_status: código HTTP devolvido  
- soap_fault_code / soap_fault_string: se a resposta for um SOAP Fault  
- raw_response_snippet: primeiros bytes do corpo de resposta (para debug)  
- error: mensagem de erro em caso de falha de geração de token ou de TLS/HTTP

### 5.2. Via CLI (linha de comandos)

#### 5.2.1. Testar e-Fatura (fews/faturas)

```
python -m libefaturas \
  --service faturas \
  --username 599999993/37 \
  --public-key certs/at_public_key.cer \
  --client-cert certs/producer.crt.pem \
  --client-key certs/app-wfa-4096.key \
  --endpoint https://servicos.portaldasfinancas.gov.pt:400/fews/faturas
```

Saída típica:

- [1] UsernameToken: OK  
- [2] TLS/HTTP: OK  
- [3] HTTP status: 500  
- [4] SOAP Fault detectado (porque o Body é dummy)

O objetivo aqui é só validar infraestrutura (certificados + header).

#### 5.2.2. Testar Comunicação de Séries (SeriesWS)

```
python -m libefaturas \
  --service series \
  --username 599999993/37 \
  --public-key certs/at_public_key.cer \
  --client-cert certs/producer.crt.pem \
  --client-key certs/app-wfa-4096.key \
  --endpoint https://servicos.portaldasfinancas.gov.pt:422/SeriesWSService
```

Neste modo:

- o Body é um `consultarSeries` real, sem filtros  
- se credenciais e WSE estiverem corretos, deves obter:
  - HTTP 200
  - um `consultarSeriesResponse` com as séries registadas (incluindo codValidacaoSerie, estado, etc.)

Este é o primeiro “teste real” de negócio recomendado para validar:

- UsernameToken  
- certificado cliente  
- permissões do utilizador/subutilizador WSE  
- ativação do serviço de séries para o NIF em causa.

---

## 6. Visão geral das operações suportadas pela AT

A lib, por enquanto, trata apenas de autenticação + teste de ligação. As operações de negócio vão ser construídas em cima disto.

### 6.1. Webservice de Séries (SeriesWS)

Operações existentes no WSDL:

- registarSerie  
  - cria / comunica uma nova série à AT  
  - devolve, entre outras coisas, o codValidacaoSerie que entra no ATCUD

- finalizarSerie  
  - fecha uma série já utilizada  
  - indicas o último número emitido e um motivo

- consultarSeries  
  - consulta séries existentes, com filtros (serie, tipo, estado, datas, etc.)  
  - usada na lib como primeira chamada real de teste

- anularSerie  
  - anula a comunicação de uma série (caso de erro ou série nunca usada)  
  - obriga a declaração explícita de que não houve emissão de documentos nessa série

### 6.2. Webservice de Faturas (FatcoreWS)

Operações definidas no WSDL de faturas:

- RegisterInvoice / ChangeInvoiceStatus / DeleteInvoice  
- RegisterWork / ChangeWorkStatus / DeleteWork  
- RegisterPayment / ChangePaymentStatus / DeletePayment

Notas:

- Register* usam estruturas complexas (InvoiceDataType, WorkDataType, PaymentDataType) com linhas, totais, impostos, etc.  
- DeleteInvoice com dateRange tem o payload estruturalmente mais simples, mas é funcionalmente agressivo (pode apagar um conjunto de documentos).  
- A operação base que faz sentido como primeiro passo real é RegisterInvoice com:
  - 1 fatura  
  - 1 linha  
  - série já comunicada (SeriesWS)  
  - ATCUD consistente

As camadas de alto nível da libefaturas para estas operações irão usar exatamente o mesmo mecanismo de autenticação descrito aqui.

---

## 7. Avisos

- A implementação segue o modelo público da AT (UsernameToken com KS, RSA e AES).  
- É obrigatório validar em ambiente de testes/homologação:
  - aceitação do header e das operações reais  
  - sincronização de relógios (campo Created em UTC)  
  - configuração correta de utilizadores/subutilizadores e permissões WSE no Portal das Finanças.
