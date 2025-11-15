# efatura-auth

Biblioteca em Python para construir o cabeçalho de autenticação (WS-Security UsernameToken) dos webservices da AT (e-Fatura, etc.), de acordo com os manuais públicos da Autoridade Tributária.

Esta biblioteca trata apenas da **autenticação a nível da mensagem** (UsernameToken):
- gera a chave de sessão simétrica KS (128 bits, AES)
- calcula:
  - Nonce = Base64( RSA_KpubSA( KS ) )
  - Password = Base64( AES-128-ECB PKCS5( SenhaPF ) )
  - Created = Base64( AES-128-ECB PKCS5( Timestamp ISO 8601 UTC ) )
- gera o fragmento XML do SOAP Header com o UsernameToken

A parte de transporte (HTTPS/TLS com certificado cliente emitido pela AT) continua a ser tua responsabilidade.

---

## 1. Quando usar esta biblioteca

Usa esta lib quando:

- precisas comunicar com o e-Fatura (ou outros webservices AT que usam o mesmo esquema de UsernameToken)
- já tens:
  - certificado cliente emitido pela AT (produtor de software)
  - chave pública / certificado do Sistema de Autenticação (fornecido pela AT)
  - credenciais de Portal das Finanças (NIF/subutilizador + password)

Ela resolve apenas a parte chata da criptografia do UsernameToken.

---

## 2. Requisitos

- Python 3.9 ou superior  
- cryptography  
- requests (apenas necessário para o comando de teste de ligação)

Instalação típica:

```bash
pip install cryptography requests
```

Se estiveres a usar o repositório diretamente:

- garante que a pasta efatura_auth/ está no teu PYTHONPATH ou instalas com:

```bash
pip install -e .
```

---

## 3. Estrutura do package

- efatura_auth/
  - __init__.py  → API pública (o que importas)
  - _core.py     → implementação da criptografia / UsernameToken
  - __main__.py  → CLI de teste de ligação (python -m efatura_auth)
- README.md      → este ficheiro (como usar a lib)
- DOCUMENTATION.md → documentação técnica detalhada

---

## 4. Quickstart

### 4.1. Preparar credenciais e chave pública AT

```python
from efatura_auth import EFaturaCredentials

creds = EFaturaCredentials(
    username="599999993/37",      # NIF/subutilizador
    password="SENHA_PORTAL",      # senha do Portal das Finanças
)

with open("at_auth_public.pem", "rb") as f:
    at_public_pem = f.read()
```

### 4.2. Construir o UsernameToken

```python
from efatura_auth import build_username_token

token = build_username_token(
    creds=creds,
    public_key_pem=at_public_pem,
)

print(token.username)  # "599999993/37"
print(token.password)  # Base64(AES_KS(SenhaPF))
print(token.nonce)     # Base64(RSA_KpubSA(KS))
print(token.created)   # Base64(AES_KS(Timestamp ISO))
```

### 4.3. Gerar o SOAP Header

```python
from efatura_auth import build_security_header_xml

header_xml = build_security_header_xml(token)
print(header_xml)
```

Forma geral da saída:

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

Este fragmento deve ser colocado no SOAP Header em todas as chamadas ao webservice da AT.

---

## 5. Teste de ligação (handshake end-to-end)

O package inclui um comando de linha que:

- lê a chave pública/certificado da AT em PEM
- gera o UsernameToken (Password, Nonce, Created)
- faz um POST SOAP mínimo para o endpoint indicado
- usa o teu certificado cliente para o handshake TLS

### 5.1. Exemplo de execução

```bash
python -m efatura_auth \
  --username 599999993/37 \
  --public-key caminho/para/at_auth_public.pem \
  --client-cert caminho/para/cert_cliente.pem \
  --client-key caminho/para/chave_privada.pem \
  --endpoint https://servicos.portaldasfinancas.gov.pt:400/fews/faturas
```

Notas:

- se não passares `--password`, a senha é pedida no terminal (sem eco)
- se tiveres um único PEM com certificado + chave, usa só `--client-cert` e omite `--client-key`
- podes usar `--ca-cert` para um bundle de CAs específico; se não passares, é usado o default do sistema

Saída típica:

- HTTP status code  
- headers de resposta  
- primeiros bytes do corpo (normalmente um SOAP Fault – suficiente para validar handshake + autenticação de transporte)

Se a chamada não rebentar com erro de TLS/HTTP, a infra está alinhada:
- certificado cliente válido
- endpoint acessível
- geração do UsernameToken OK

---

## 6. Integração com cliente SOAP/HTTP

Fluxo típico:

1) Configuras o teu cliente:

- `requests`, `httpx`, `zeep`, etc.
- defines cert=(cert_cliente, chave_privada) ou equivalente
- defines o endpoint (ex.: produção e-Fatura: `https://servicos.portaldasfinancas.gov.pt:400/fews/faturas`)

2) Geras o UsernameToken:

- `token = build_username_token(creds, at_public_pem)`

3) Geras o SOAP Header:

- `header_xml = build_security_header_xml(token)`

4) Montas o envelope SOAP completo (Header + Body) e envias.

Exemplo minimalista de POST com `requests`:

```python
import requests
from efatura_auth import (
    EFaturaCredentials,
    build_username_token,
    build_security_header_xml,
)

creds = EFaturaCredentials(username="599999993/37", password="SENHA_PORTAL")

with open("at_auth_public.pem", "rb") as f:
    at_public_pem = f.read()

token = build_username_token(creds, at_public_pem)
header_xml = build_security_header_xml(token)

envelope = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<S:Envelope xmlns:S="http://schemas.xmlsoap.org/soap/envelope/">'
    f"{header_xml}"
    "<S:Body>"
    # aqui entra o body SOAP real (envio de faturas, etc.)
    "</S:Body>"
    "</S:Envelope>"
)

response = requests.post(
    "https://servicos.portaldasfinancas.gov.pt:400/fews/faturas",
    data=envelope.encode("utf-8"),
    headers={"Content-Type": "text/xml; charset=utf-8"},
    cert=("cert_cliente.pem", "chave_privada.pem"),
    timeout=30,
)

print(response.status_code)
print(response.text[:1000])
```

---

## 7. Avisos

- A implementação segue o modelo público da AT (UsernameToken com KS, RSA e AES).  
- Continua a ser obrigatório validar em ambiente oficial de testes/homologação que:
  - o header é aceite sem erros de autenticação
  - o relógio do servidor está corretamente sincronizado (campo Created em UTC)
