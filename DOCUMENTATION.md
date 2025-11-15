# libefaturas – Documentação Técnica

Este documento explica, de forma detalhada, como a biblioteca `libefaturas` implementa o modelo de autenticação dos webservices da AT (e-Fatura e Comunicação de Séries) e como está organizada internamente.

- Focado em quem quer entender ou alterar a biblioteca.  
- Para usar a lib na prática, ver `README.md`.

---

## 1. Modelo de autenticação da AT

A invocação dos webservices da AT (e-Fatura, SeriesWS, etc.) usa dois níveis de segurança:

1) Autenticação ao nível do transporte (HTTPS/TLS)  
2) Autenticação ao nível da mensagem (SOAP Header – UsernameToken)

Se qualquer um dos níveis falhar, o serviço recusa o pedido (erros de autenticação e/ou cifra).

### 1.1. Pré-requisitos

Antes de invocar qualquer serviço (faturas ou séries) é necessário:

1. Contrato de adesão aos serviços web da AT  
   - sujeito passivo (ou produtor de software) adere no Portal das Finanças  
   - AT disponibiliza processo de pedido de certificado (CSR) específico

2. Certificado digital de produtor de software  
   - certificado de 2048 bits emitido pela AT, instalado no software cliente  
   - usado como certificado cliente na ligação TLS  
   - acompanhado pela chave pública do Sistema de Autenticação (ficheiro .cer/.pem), usada no UsernameToken

3. Credenciais de Portal das Finanças  
   - utilizador/subutilizador (formato típico NIF/Subutilizador)  
   - password associada  
   - permissões WSE ativas para os serviços em causa (e-Fatura, Séries, etc.)

---

## 1.2. Autenticação ao nível do transporte (TLS/SSL)

- Comunicação por HTTPS (TLS) com autenticação mútua:
  - servidor → certificado do Portal das Finanças  
  - cliente → certificado de produtor de software da AT

Endpoints típicos em produção:

- e-Fatura:  
  - https://servicos.portaldasfinancas.gov.pt:400/fews/faturas
- Comunicação de Séries:  
  - https://servicos.portaldasfinancas.gov.pt:422/SeriesWSService

O certificado cliente utilizado pela lib tem de ser exatamente o certificado emitido pela AT para aquele NIF. A biblioteca não trata da camada TLS; isso é feito pela stack HTTP/SOAP (requests, httpx, zeep, etc.).

---

## 1.3. Autenticação ao nível da mensagem (UsernameToken)

Cada pedido SOAP inclui um cabeçalho de segurança WS-Security com:

- wss:Username – utilizador/subutilizador  
- wss:Password – senha cifrada  
- wss:Nonce – valor aleatório, único por pedido  
- wss:Created – timestamp em ISO 8601 (UTC)

Estrutura conceptual:

```
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

### 1.3.1. Campo Username

- corresponde ao utilizador/subutilizador do Portal das Finanças associado ao NIF do sujeito passivo  
- formatos típicos:
  - 123456789
  - 123456789/01  
- erros de formato, tamanho ou inexistência resultam em erros de autenticação (faults específicos da AT).

### 1.3.2. Modelo criptográfico (Password, Nonce, Created)

A AT define um modelo de autenticação baseado em:

- chave de sessão simétrica KS (128 bits, AES)  
- RSA com chave pública do Sistema de Autenticação (KpubSA)  
- AES-128-ECB com PKCS5/PKCS7 padding

Esquemas:

- Password = Base64( AES-128-ECB-PKCS5_KS( SenhaPF ) )  
- Created  = Base64( AES-128-ECB-PKCS5_KS( TimestampISO ) )  
- Nonce    = Base64( RSA_KpubSA( KS ) )

A senha real do utilizador nunca é enviada em claro; apenas os resultados cifrados.

### 1.3.3. Campos Nonce e Created

- Nonce:
  - valor aleatório impraticável de prever  
  - diferente em cada pedido  
  - evita ataques de replay

- Created:
  - timestamp de criação do token  
  - ISO 8601 em UTC (ex.: 2025-01-31T10:15:30.123Z)  
  - deve estar dentro de uma janela temporal aceitável para a AT

---

## 2. Arquitetura interna da biblioteca libefaturas

### 2.1. Estrutura de ficheiros

- libefaturas/
  - __init__.py  
    - API pública:
      - EFaturaCredentials  
      - UsernameToken  
      - build_username_token(...)  
      - build_security_header_xml(...)  
      - test_connection(...)  
      - funções auxiliares de baixo nível (encrypt_*)
  - _core.py  
    - implementação da parte criptográfica:
      - geração da KS (os.urandom(16))  
      - AES-128-ECB + PKCS5/PKCS7  
      - leitura da chave pública RSA a partir de .cer/.pem  
      - construção do UsernameToken  
      - construção do SOAP Header
  - __main__.py  
    - CLI (python -m libefaturas):
      - parse de argumentos  
      - pedido da password se não for fornecida  
      - invocação de test_connection(...)  
      - output em modo “checklist”

- README.md  
  - guia de utilização para devs consumidores  
- DOCUMENTATION.md  
  - este documento, para devs da própria lib

---

### 2.2. Classes e funções principais

#### EFaturaCredentials

Representa credenciais do Portal das Finanças:

- username: NIF/Subutilizador  
- password: senha do Portal

[INICIO CODE BLOCK PYTHON]
from libefaturas import EFaturaCredentials

creds = EFaturaCredentials(
    username="599999993/37",
    password="SENHA_PORTAL",
)
```

#### UsernameToken

Representa o token já cifrado:

- username  
- password (Base64(AES_KS(SenhaPF)))  
- nonce (Base64(RSA_KpubSA(KS)))  
- created (Base64(AES_KS(TimestampISO)))

Tem método to_xml() que gera `<wss:UsernameToken>...</wss:UsernameToken>`.

#### build_created_timestamp

- gera timestamp ISO 8601 em UTC com milissegundos  
- normaliza o sufixo para Z (ex.: 2025-01-31T10:15:30.123Z)

#### encrypt_password / encrypt_created / encrypt_nonce

Implementam diretamente os esquemas da AT:

- encrypt_password  
  - Password = Base64( AES-128-ECB_KS( SenhaPF_UTF8 ) )

- encrypt_created  
  - Created = Base64( AES-128-ECB_KS( TimestampISO_UTF8 ) )

- encrypt_nonce  
  - Nonce = Base64( RSA_KpubSA( KS ) )

São funções internas expostas via __init__ para debugging e testes.

#### build_username_token

Fluxo:

1. gera KS (16 bytes)  
2. gera timestamp ISO (build_created_timestamp)  
3. calcula password_b64 = encrypt_password(SenhaPF, KS)  
4. calcula created_b64  = encrypt_created(TimestampISO, KS)  
5. calcula nonce_b64    = encrypt_nonce(KS, KpubSA)  
6. devolve UsernameToken(username, password_b64, nonce_b64, created_b64)

#### build_security_header_xml

Recebe um UsernameToken e gera:

```
<S:Header>
  <wss:Security xmlns:wss="http://schemas.xmlsoap.org/ws/2002/12/secext">
    <wss:UsernameToken>...</wss:UsernameToken>
  </wss:Security>
</S:Header>
```

---

## 3. test_connection – comportamento técnico

A função test_connection(...) encapsula um teste de ponta a ponta.

Parâmetros principais:

- username, password  
- public_key_path (ficheiro .cer/.pem da AT com a chave pública)  
- endpoint (URL SOAP – faturas ou séries)  
- client_cert_path, client_key_path (cert + key do produtor de software)  
- ca_cert_path (opcional – bundle de CAs)  
- service:
  - "faturas" → Body dummy  
  - "series"  → Body real consultarSeries

Comportamento:

1. Gera UsernameToken com build_username_token e build_security_header_xml.  
2. Monta envelope SOAP:

   - service="faturas" → Body dummy (ConnectionTest, apenas handshake)  
   - service="series" → Body real:

```
<S:Body>
  <consultarSeries xmlns="http://at.gov.pt/"/>
</S:Body>
```

3. Faz POST com o certificado cliente.  
4. Devolve um dicionário com:
   - estado da geração do token  
   - estado do TLS/HTTP  
   - HTTP status  
   - eventuais SOAP Faults  
   - excerto do corpo de resposta

O CLI (python -m libefaturas) apenas formata este resultado de forma amigável e define o exit code.

---

## 4. Webservice de Séries (SeriesWS) – visão técnica

Webservice exposto em produção, tipicamente:

- https://servicos.portaldasfinancas.gov.pt:422/SeriesWSService

Operações do WSDL (não implementadas ainda na lib em alto nível, mas suportadas via o mesmo header):

1. registarSerie  
   - regista uma nova série  
   - campos-chave:
     - serie  
     - tipoSerie  
     - classeDoc  
     - tipoDoc  
     - numInicialSeq  
     - dataInicioPrevUtiliz  
     - numCertSWFatur  
     - meioProcessamento  
   - resposta inclui codValidacaoSerie e metadados

2. finalizarSerie  
   - marca série como finalizada  
   - campos-chave:
     - serie, classeDoc, tipoDoc  
     - codValidacaoSerie  
     - seqUltimoDocEmitido  
     - justificacao

3. consultarSeries  
   - consulta séries com filtros opcionais:
     - serie, tipoSerie, classeDoc, tipoDoc  
     - codValidacaoSerie  
     - dataRegistoDe, dataRegistoAte  
     - estado, meioProcessamento  
   - resposta traz múltiplos blocos infoSerie (série, estado, codValidacaoSerie, datas, etc.)  
   - usado pela lib como primeira chamada real de teste (service="series").

4. anularSerie  
   - anula a comunicação de uma série  
   - campos-chave:
     - serie, classeDoc, tipoDoc  
     - codValidacaoSerie  
     - motivo  
     - declaracaoNaoEmissao (confirmação de que não houve emissão de docs nessa série)

A lógica de negócio destes pedidos/respostas é externa à lib; aqui apenas se garante o header e a comunicação.

---

## 5. Webservice de Faturas (FatcoreWS) – visão técnica

O WSDL de faturas expõe, entre outras, estas operações:

- RegisterInvoice  
- ChangeInvoiceStatus  
- DeleteInvoice  
- RegisterWork  
- ChangeWorkStatus  
- DeleteWork  
- RegisterPayment  
- ChangePaymentStatus  
- DeletePayment

Características:

- Os Register* usam tipos complexos:
  - InvoiceDataType, WorkDataType, PaymentDataType  
  - com listas de linhas, impostos, retenções, totais, etc.

- ChangeInvoiceStatus exige:
  - eFaturaMDVersion  
  - TaxRegistrationNumber  
  - InvoiceHeader (InvoiceNo, ATCUD, InvoiceDate, InvoiceType, SelfBillingIndicator, CustomerTaxID, CustomerTaxIDCountry)  
  - InvoiceStatus

- DeleteInvoice pode ser chamado com:
  - documentsList (lista de InvoiceHeader)  
  - ou dateRange (StartDate/EndDate)  
  - e reason (10–500 chars)

Estruturalmente, DeleteInvoice com dateRange é o payload mais curto, mas é funcionalmente agressivo. A operação base que faz sentido como primeiro passo real é RegisterInvoice com:

- 1 fatura  
- 1 linha  
- série já registada via SeriesWS  
- ATCUD consistente

As futuras camadas de alto nível da libefaturas para estas operações vão construir os corpos SOAP em cima da autenticação já implementada.

---

## 6. Relação entre documentação AT e a biblioteca

- A secção 1 deste documento espelha o modelo definido nos manuais oficiais (dois níveis de segurança, UsernameToken com KS, RSA e AES).  
- _core.py implementa esse modelo com as funções encrypt_* e build_username_token.  
- build_security_header_xml traduz o modelo em XML SOAP.  
- test_connection e o CLI são ferramentas de diagnóstico:
  - e-Fatura → valida handshake e headers com um Body neutro  
  - Séries → valida tudo e ainda confirma que consultarSeries responde com dados reais.

Qualquer alteração ao comportamento da biblioteca deve manter este alinhamento com a especificação da AT.
