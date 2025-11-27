# libefaturas

Biblioteca Python para comunicar com os webservices oficiais da AT (e‑Fatura / SeriesWS) com uma API mínima: um único cliente e resultados uniformes.

- Geração automática de UsernameToken / WS-Security.
- Comunicação de séries (SeriesWS) e de faturas/obras/pagamentos (FatcoreWS).
- Assinaturas simples com tipos built‑in (`str`, `int`, `date`, `dict`, `list`).
- Resposta sempre no mesmo formato (`EFaturasResult`: `ok`, `code`, `message`, `data`).

## Instalação rápida

```bash
pip install libefaturas
```

Pré‑requisitos:

- Python 3.9+
- Certificado de produtor de software emitido pela AT (`.crt/.pem` + chave privada)
- Credenciais de utilizador/subutilizador com permissões WSE
- Chave pública do Sistema de Autenticação (`.cer` ou `.pem`)

## API de alto nível

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

### Resultado padrão

Todas as operações devolvem um `EFaturasResult`:

- `ok`: `True` se a AT aceitou a operação
- `code`: código numérico da AT (quando existe)
- `message`: mensagem humana
- `data`: payload útil (por exemplo, lista de séries)

### Testar ligação

```python
result = client.test_connection(service="faturas")  # ou "series"
if not result.ok:
    print(result.message, result.data)
```

### Comunicar faturas / obras / pagamentos (FatcoreWS)

Os métodos aceitam dicionários equivalentes aos campos do manual da AT. A biblioteca valida, converte para os payloads exigidos e trata de SOAP/TLS.

```python
from datetime import date, datetime
from decimal import Decimal

invoice_data = {
    "InvoiceNo": "FT A/2024/1",
    "ATCUD": "ATCUD-EXEMPLO",
    "InvoiceDate": date(2024, 1, 15),
    "InvoiceType": "FT",
    "SelfBillingIndicator": 0,
    "CustomerTaxID": "999999990",
    "CustomerTaxIDCountry": "PT",
    "DocumentStatus": {"InvoiceStatus": "N", "InvoiceStatusDate": datetime.now()},
    "HashCharacters": "ABCD",
    "CashVATSchemeIndicator": 0,
    "PaperlessIndicator": 1,
    "SystemEntryDate": datetime.now(),
    "LineSummary": [
        {
            "TaxPointDate": date(2024, 1, 15),
            "DebitCreditIndicator": "D",
            "TotalTaxBase": Decimal("100.00"),
            "Tax": {
                "TaxType": "IVA",
                "TaxCountryRegion": "PT",
                "TaxCode": "NOR",
                "TaxPercentage": Decimal("23.00"),
            },
        }
    ],
    "DocumentTotals": {
        "TaxPayable": Decimal("23.00"),
        "NetTotal": Decimal("100.00"),
        "GrossTotal": Decimal("123.00"),
    },
}

result = client.register_invoice(
    efatura_md_version="0.0.1",
    audit_file_version="1.04_01",
    tax_registration_number="599999993",
    tax_entity="Global",
    software_certificate_number=9999,
    invoice_data=invoice_data,
    canal_registo={"Sistema": "MinhaApp", "Versao": "1.0.0"},
)

if not result.ok:
    print(result.code, result.message)
```

Métodos disponíveis (todos devolvem `EFaturasResult`): `register_invoice`, `change_invoice_status`, `delete_invoice`, `register_work`, `change_work_status`, `delete_work`, `register_payment`, `change_payment_status`, `delete_payment`.

### Comunicar séries (SeriesWS)

```python
from datetime import date

create = client.create_series(
    serie="A",
    tipo_serie="N",
    classe_doc="FT",
    tipo_doc="FT",
    num_inicial_seq=1,
    data_inicio=date(2024, 1, 1),
    num_cert_sw="9999",            # certificado do software ou "0"
    meio_processamento="PI",       # conforme manual AT
)
print(create.ok, create.code, create.message, create.data)  # data contém a série criada

series_list = client.list_series(estado="A", tipo_doc="FT")
for serie in series_list.data or []:
    print(serie.serie, serie.estado, serie.codigo_validacao)

finalize = client.finalize_series(
    serie="A",
    classe_doc="FT",
    tipo_doc="FT",
    codigo_validacao="X1Y2Z3A4",
    seq_ultimo_doc_emitido=120,
    justificacao="Série substituída",
)
print(finalize.ok, finalize.message)
```

Outros métodos: `cancel_series`.

## Notas

- Em condições normais a biblioteca não lança exceções: erros são devolvidos como `EFaturasResult(ok=False, ...)`.
- As validações de campos seguem as regras do manual da AT; mensagens de validação aparecem em `result.message`.
- Se precisares de depuração aprofundada, as implementações internas continuam disponíveis nos módulos `faturas` e `series`, mas não são parte da API pública.
