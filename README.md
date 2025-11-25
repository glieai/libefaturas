# libefaturas

Biblioteca Python para consumir os webservices oficiais da AT (e-Fatura / SeriesWS) sem ter de montar SOAP, WS-Security e certificados à mão. O foco é disponibilizar uma API simples para aplicações que precisem de:

- gerar o cabeçalho WS-Security (UsernameToken)
- comunicar séries (SeriesWS)
- comunicar faturas, trabalhos e pagamentos (FatcoreWS)

---

## Instalação rápida

```bash
pip install libefaturas
```

Requisitos mínimos:

- Python 3.9+
- certificado de produtor de software emitido pela AT (ficheiros `.crt/.pem` + chave privada)
- credenciais de utilizador/subutilizador com permissões WSE
- chave pública do Sistema de Autenticação (normalmente fornecida como `.cer`)

---

## 1. Criar o cliente base

Todas as operações partem de `EFaturasClient`, que trata do UsernameToken, header WS-Security e chamada SOAP/TLS.

```python
from libefaturas import EFaturasClient

client = EFaturasClient(
    username="599999993/37",                  # utilizador/subutilizador WSE
    password="SENHA_PORTAL",
    public_key_path="certs/at_public_key.cer",
    client_cert_path="certs/software.crt.pem",
    client_key_path="certs/software.key.pem",
    ca_cert_path="certs/ca_at.pem",           # opcional (usa truststore do sistema se omitido)
    environment="test",                       # ou "prod"
)
```

Quando precisares de validar a infraestrutura antes de chamar operações reais, usa `test_connection`:

```python
from libefaturas import test_connection

health = test_connection(
    username="599999993/37",
    password="SENHA_PORTAL",
    public_key_path="certs/at_public_key.cer",
    client_cert_path="certs/software.crt.pem",
    client_key_path="certs/software.key.pem",
    service="series",  # ou "faturas"
)
print(health)  # informa se o UsernameToken/TLS/endpoint estão OK
```

---

## 2. Comunicação de séries (SeriesWS)

```python
from datetime import date
from libefaturas import SeriesService
from libefaturas.series import (
    CreateSeriesInput,
    FinalizeSeriesInput,
    CancelSeriesInput,
    SeriesFilter,
)

series = SeriesService(client)

# Registar nova série
resp = series.create_series(
    CreateSeriesInput(
        serie="A",
        tipo_serie="N",                      # ex.: Normal
        classe_doc="FT",                     # classe definida pela AT
        tipo_doc="FT",                       # tipo de documento
        num_inicial_seq=1,
        data_inicio=date(2024, 1, 1),
        num_cert_sw="9999",                  # certificado do software ou "0"
        meio_processamento="E",              # ex.: eletrónico
    )
)
assert resp.result.ok, resp.result.message
print(resp.series.codigo_validacao)

# Consultar séries existentes
series_list = series.list_series(SeriesFilter(estado="A"))
for serie in series_list.series:
    print(serie.serie, serie.estado, serie.codigo_validacao)

# Finalizar uma série
final = series.close_series(
    FinalizeSeriesInput(
        serie="A",
        classe_doc="FT",
        tipo_doc="FT",
        codigo_validacao="X1Y2Z3A4",
        seq_ultimo_doc_emitido=120,
        justificacao="Série substituída",
    )
)
print(final.result.ok)

# Anular uma série
cancel = series.cancel_series(
    CancelSeriesInput(
        serie="B",
        classe_doc="FT",
        tipo_doc="FT",
        codigo_validacao="Q1W2E3R4",
        motivo="01",                         # códigos definidos pela AT
        declaracao_nao_emissao=True,
    )
)
print(cancel.result.message)
```

`SeriesService` devolve sempre `SeriesOperationResult` (para operações sobre uma única série) ou `SeriesListResult` com `OperationResult` indicando o sucesso (`result.ok`).

---

## 3. Comunicação de faturas, trabalhos e pagamentos (FatcoreWS)

O serviço expõe nove operações (Register/Change/Delete para Invoice, Work e Payment). Cada uma recebe um dataclass que espelha o payload do WSDL e valida comprimentos, enums, formatos e ranges antes de serializar para XML. Podes continuar a passar dicionários, mas eles são convertidos para os dataclasses e validados antes do envio (erros levantam `PayloadValidationError`).

```python
from datetime import date, datetime
from decimal import Decimal
from libefaturas import FaturasService
from libefaturas.faturas import (
    ChannelInfo,
    DocumentTotals,
    InvoiceData,
    InvoiceLineSummary,
    InvoiceStatus,
    RegisterInvoiceInput,
    Tax,
)

fatcore = FaturasService(client, validate_xml=True)  # valida XML vs XSD se instalares 'libefaturas[validation]'

invoice = InvoiceData(
    invoice_no="FT A/2024/1",
    atcud="ATCUD-EXEMPLO",
    invoice_date=date(2024, 1, 15),
    invoice_type="FT",
    self_billing_indicator=0,
    customer_tax_id="999999990",
    customer_tax_id_country="PT",
    document_status=InvoiceStatus(invoice_status="N", invoice_status_date=datetime.now()),
    hash_characters="ABCD",
    cash_vat_scheme_indicator=0,
    paperless_indicator=1,
    system_entry_date=datetime.now(),
    line_summary=[
        InvoiceLineSummary(
            tax_point_date=date(2024, 1, 15),
            debit_credit_indicator="D",
            total_tax_base=Decimal("100.00"),
            tax=Tax(
                tax_type="IVA",
                tax_country_region="PT",
                tax_code="NOR",
                tax_percentage=Decimal("23.00"),
            ),
        )
    ],
    document_totals=DocumentTotals(
        tax_payable=Decimal("23.00"),
        net_total=Decimal("100.00"),
        gross_total=Decimal("123.00"),
    ),
)

response = fatcore.register_invoice(
    RegisterInvoiceInput(
        efatura_md_version="0.0.1",
        audit_file_version="1.04_01",
        tax_registration_number="599999993",
        tax_entity="Global",
        software_certificate_number=9999,
        invoice_data=invoice,
        canal_registo=ChannelInfo(sistema="MinhaApp", versao="1.0.0"),
    )
)

if not response.ok:
    raise RuntimeError(response.mensagem)
print("Fatura comunicada:", response.data_operacao)
```

Outros dataclasses (`ChangeInvoiceStatusInput`, `DeleteInvoiceInput`, `RegisterWorkInput`, etc.) seguem o mesmo padrão. Se preferires continuar a enviar dicionários, eles são transformados e validados automaticamente antes da serialização.

---

## 4. Testes e troubleshooting

- `test_connection(service="series")` ou `test_connection(service="faturas")` para validar certificados, UsernameToken e endpoint antes de chamar operações de negócio.
- O `OperationResponse` devolvido pelas operações do FatcoreWS inclui `codigo_resposta`, `mensagem` e `data_operacao`. Se `codigo_resposta` for diferente de zero, a mensagem costuma explicar o erro (por exemplo série inexistente, ATCUD inválido, etc.).
- As operações de séries devolvem `OperationResult` com o mesmo conceito de código/mensagem.
- Se quiseres validar o XML gerado face ao XSD oficial ativa `FaturasService(..., validate_xml=True)` e instala o extra `pip install "libefaturas[validation]"`.

---

## 5. CLI (opcional)

Podes usar a CLI integrada para validar conectividade rapidamente:

```bash
python -m libefaturas \
  --service series \
  --username 599999993/37 \
  --password SENHA_PORTAL \
  --public-key certs/at_public_key.cer \
  --client-cert certs/software.crt.pem \
  --client-key certs/software.key.pem
```

O comando acima executa `consultarSeries` sem filtros e devolve um resumo do pedido/resposta.

---

## 6. Referências

- `libefaturas/src/libefaturas/wsdl/`: WSDLs oficiais usados como referência.
- `libefaturas/security.py`: implementação da geração de UsernameToken (RSA + AES).
- `libefaturas/client.py`: construção do envelope SOAP, cabeçalho WS-Security e chamada HTTP.

Se precisares de adaptar os payloads ao teu domínio basta importar os dataclasses diretamente de `libefaturas.series` ou `libefaturas.faturas`. Tudo o resto (helpers internos) é considerado detalhe de implementação.
