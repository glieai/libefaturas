# Guia de Integração com o e-Fatura (Webservice AT) – Documentação Técnica da Biblioteca

Este documento explica, de forma detalhada, como a biblioteca `efatura_auth` implementa o modelo de autenticação dos webservices da AT (e-Fatura), alinhado com a documentação oficial.

- Focado em quem quer **entender ou alterar** a biblioteca.
- Para usar a lib na prática, ver `README.md`.

---

## 1. Contexto e requisitos de autenticação

A invocação do webservice e-Fatura usa dois níveis de segurança:

1) Autenticação ao nível do transporte (HTTPS/TLS)
2) Autenticação ao nível da mensagem (SOAP Header – UsernameToken)

Se qualquer um dos níveis falhar, o serviço recusa o pedido (erros de autenticação e/ou cifra).

### 1.1. Pré-requisitos

Antes de invocar o webservice é necessário:

1. Contrato de adesão aos serviços web da AT
   - sujeito passivo (ou produtor de software) adere no Portal das Finanças
   - após aceitação, a AT disponibiliza o processo de pedido de certificado (CSR) específico

2. Certificado digital do produtor de software
   - certificado de 2048 bits emitido pela AT, instalado no software do cliente
   - usado para autenticação TLS do lado do cliente
   - vem acompanhado da chave pública do Sistema de Autenticação (para cifrar a estrutura interna do UsernameToken)

3. Credenciais do Portal das Finanças
   - utilizador/subutilizador (normalmente no formato NIF/Subutilizador)
   - password associada a esse utilizador

---

## 1.2. Autenticação ao nível do transporte (TLS/SSL)

- Comunicação sempre por HTTPS (TLS) com autenticação mútua:
  - o servidor apresenta o certificado do Portal das Finanças
  - o cliente apresenta o certificado de produtor de software emitido pela AT
- Endereço típico de produção para comunicação dos elementos de faturação:

  - `https://servicos.portaldasfinancas.gov.pt:400/fews/faturas`

- O certificado apresentado pelo cliente tem de ser o certificado emitido pela AT para este fim; qualquer outro leva a falha na autenticação TLS.
- O certificado deve ser instalado no keystore/cert store usado pela stack HTTP/SOAP.

A biblioteca `efatura_auth` **não** trata da camada TLS. Assume que o cliente Python (requests, httpx, zeep, etc.) está corretamente configurado com o certificado cliente.

---

## 1.3. Autenticação ao nível da mensagem (UsernameToken)

Além do TLS, cada pedido SOAP inclui um cabeçalho de segurança com as credenciais do utilizador que executa a operação.

Estrutura lógica:

- SOAP Header
  - contém o `wss:Security` com `wss:UsernameToken`
- SOAP Body
  - contém os dados da operação (registo/alteração/consulta de documentos, etc.)

A AT usa um esquema baseado em WS-Security UsernameToken com:

- utilizador / subutilizador (`wss:Username`)
- senha cifrada (`wss:Password`)
- Nonce (`wss:Nonce`)
- timestamp (`wss:Created`)

### 1.3.1. Exemplo conceptual de cabeçalho

```xml
<S:Header>
  <wss:Security xmlns:wss="http://schemas.xmlsoap.org/ws/2002/12/secext">
    <wss:UsernameToken>
      <wss:Username>UTILIZADOR</wss:Username>
      <wss:Password>SENHA_CIFRADA</wss:Password>
      <wss:Nonce>VALOR_NONCE</wss:Nonce>
      <wss:Created>AAAA-MM-DDThh:mm:ssZ</wss:Created>
    </wss:UsernameToken>
  </wss:Security>
</S:Header>
```

Campos:

- `wss:Username` – identificação do utilizador/subutilizador autorizado
- `wss:Password` – senha cifrada, nunca enviada em claro
- `wss:Nonce` – valor aleatório, único por pedido
- `wss:Created` – timestamp da criação do token, em formato ISO 8601 (UTC)

---

### 1.3.2. Campo Username

Regras:

- corresponde ao utilizador/subutilizador do Portal das Finanças associado ao NIF do sujeito passivo
- formatos típicos:
  - utilizador principal: `123456789`
  - utilizador + subutilizador: `123456789/01`
- tem de respeitar tamanho e formato esperados pela AT

Erros de formato, tamanho ou inexistência do utilizador resultam em erros de autenticação do webservice.

---

### 1.3.3. Modelo criptográfico (Password, Nonce, Created)

A AT define um modelo de autenticação baseado em:

- chave de sessão simétrica KS (128 bits, AES)
- algoritmo RSA com chave pública do Sistema de Autenticação (KpubSA)
- AES-128-ECB com PKCS5/PKCS7 padding

Esquemas:

- Password:
  - Password = Base64( AES-128-ECB-PKCS5_KS( SenhaPF ) )

- Created:
  - Created = Base64( AES-128-ECB-PKCS5_KS( TimestampISO ) )

- Nonce:
  - Nonce = Base64( RSA_KpubSA( KS ) )

A senha real do utilizador nunca é enviada em claro; apenas o resultado cifrado.

### 1.3.4. Campos Nonce e Created

- Nonce:
  - valor aleatório impraticável de prever
  - diferente em cada pedido
  - usado para proteger contra replay

- Created:
  - timestamp de criação do UsernameToken
  - formato ISO 8601 em UTC (por exemplo, `2025-01-31T10:15:30.123Z`)
  - usado para limitar a janela temporal de validade

---

## 2. Arquitetura interna da biblioteca `efatura_auth`

Esta secção descreve como o modelo acima é implementado no código.

### 2.1. Estrutura do package

Estrutura recomendada:

- efatura_auth/
  - __init__.py
  - _core.py
  - __main__.py
- README.md
- DOCUMENTATION.md

Função de cada ficheiro:

- __init__.py
  - expõe a API pública:

    - EFaturaCredentials
    - UsernameToken
    - build_username_token(...)
    - build_security_header_xml(...)
    - e funções auxiliares de baixo nível (encrypt_password, encrypt_created, encrypt_nonce, build_created_timestamp)

- _core.py
  - contém toda a implementação de criptografia e construção de UsernameToken:
    - geração da KS (os.urandom 16 bytes)
    - AES-128-ECB com PKCS5/PKCS7 padding
    - carga da chave pública RSA da AT (tanto de certificado X.509 como de chave pública PEM)
    - construção do UsernameToken
    - construção do SOAP Header com WS-Security

- __main__.py
  - CLI para teste de ligação:
    - lê credenciais e ficheiros PEM (chave pública AT, certificados cliente)
    - gera UsernameToken
    - constrói envelope SOAP mínimo
    - faz POST para o endpoint indicado com certificado cliente

---

### 2.2. Classes e funções principais

#### EFaturaCredentials

Representa as credenciais do Portal das Finanças:

- username: string no formato `<NIF>/<subutilizador>`
- password: senha do Portal das Finanças para esse utilizador

Uso típico:

```python
from efatura_auth import EFaturaCredentials

creds = EFaturaCredentials(
    username="599999993/37",
    password="SENHA_PORTAL",
)
```

#### UsernameToken

Representa os campos do UsernameToken já cifrados:

- username: mesmo valor enviado em `<wss:Username>`
- password: Base64(AES_KS(SenhaPF))
- nonce: Base64(RSA_KpubSA(KS))
- created: Base64(AES_KS(TimestampISO))

Tem ainda um método `to_xml()` que gera apenas o bloco `<wss:UsernameToken>...</wss:UsernameToken>`.

#### build_created_timestamp

Responsável por gerar o timestamp ISO 8601 em UTC com milissegundos, e normalizar o sufixo para `Z` (ex.: `2025-01-31T10:15:30.123Z`).

#### encrypt_password / encrypt_created / encrypt_nonce

Implementam diretamente os esquemas:

- encrypt_password:
  - Password = Base64( AES-128-ECB-KS( SenhaPF_UTF8 ) )

- encrypt_created:
  - Created = Base64( AES-128-ECB-KS( TimestampISO_UTF8 ) )

- encrypt_nonce:
  - Nonce = Base64( RSA_KpubSA( KS ) )

Estas funções são internas mas exportadas via __init__ para debugging/validação se necessário.

#### build_username_token

Fluxo:

1. gera KS (16 bytes aleatórios)
2. gera timestamp ISO (build_created_timestamp)
3. calcula password_b64 = encrypt_password(SenhaPF, KS)
4. calcula created_b64  = encrypt_created(TimestampISO, KS)
5. calcula nonce_b64    = encrypt_nonce(KS, KpubSA)
6. devolve UsernameToken(username, password_b64, nonce_b64, created_b64)

#### build_security_header_xml

Recebe um UsernameToken e gera o fragmento:

```xml
<S:Header>
  <wss:Security xmlns:wss="http://schemas.xmlsoap.org/ws/2002/12/secext">
    <wss:UsernameToken>...</wss:UsernameToken>
  </wss:Security>
</S:Header>
```

---

## 3. CLI de teste de ligação (`python -m efatura_auth`)

O entrypoint em `__main__.py` expõe um comando que:

1. lê parâmetros:
   - `--username`
   - `--password` (opcional, senão pede interativamente)
   - `--public-key` (ficheiro PEM com chave pública/certificado AT)
   - `--client-cert` (certificado cliente PEM; pode incluir a chave)
   - `--client-key` (chave privada PEM, se separada)
   - `--ca-cert` (bundle de CAs, opcional)
   - `--endpoint` (URL do webservice da AT)

2. gera credenciais (`EFaturaCredentials`)
3. constrói o UsernameToken (`build_username_token`)
4. gera o SOAP Header (`build_security_header_xml`)
5. monta um envelope SOAP mínimo com um body fictício
6. executa um POST via requests para o endpoint, com o certificado cliente

Exemplo de chamada:

```bash
python -m efatura_auth \
  --username 599999993/37 \
  --public-key caminho/para/at_auth_public.pem \
  --client-cert caminho/para/cert_cliente.pem \
  --client-key caminho/para/chave_privada.pem \
  --endpoint https://servicos.portaldasfinancas.gov.pt:400/fews/faturas
```

Este comando é pensado apenas como ferramenta de diagnóstico:

- valida a leitura da chave pública AT
- valida a geração do UsernameToken
- valida o handshake TLS com o endpoint
- permite ver rapidamente se há erros de certificado, de cipher ou de compatibilidade

---

## 4. Relação entre documentação AT e código

- A secção 1 deste documento espelha o modelo descrito nos manuais oficiais (dois níveis de segurança, UsernameToken com KS, RSA e AES).
- Esse modelo é implementado no `_core.py` através das funções `encrypt_*` e `build_username_token`.
- O `UsernameToken` gerado é injetado no SOAP Header pela função `build_security_header_xml`.
- O CLI (`__main__.py`) existe apenas como ferramenta de validação operacional (certificados corretos, endpoint acessível, relógio sincronizado).

Qualquer alteração ao comportamento da biblioteca deve manter este alinhamento com a especificação da AT.
