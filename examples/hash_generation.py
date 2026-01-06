#!/usr/bin/env python3
"""
Example: SAF-T Hash Generation for Portuguese Invoices

This example demonstrates how to generate the cryptographic hash
required for Portuguese SAF-T (Standard Audit File for Tax) invoices.

Requirements:
- RSA 1024-bit private key (as declared in Modelo 24 to AT)
- Invoice data in SAF-T format

The hash is signed using RSA-PKCS1v15-SHA1 as specified by AT.
"""
from libefaturas.security import gerar_hash_fatura


def main():
    # Path to your SAF-T private key (1024-bit RSA)
    # This key should match the public key declared in Modelo 24
    private_key_path = "path/to/your/saft_private_key.pem"
    private_key_password = None  # Or b"your_password" if encrypted

    # Invoice data from your billing system
    # All fields must match the SAF-T XML format exactly
    invoice_date = "2025-01-15"              # SAF-T InvoiceDate (YYYY-MM-DD)
    system_entry_date = "2025-01-15T10:30:00"  # SAF-T SystemEntryDate
    invoice_no = "FT FT2025/000001"          # SAF-T InvoiceNo (Type Series/Number)
    gross_total = "123.00"                   # SAF-T GrossTotal (decimal with 2 places)

    # For the FIRST document of a series/year, previous_hash is empty
    # For subsequent documents, use the hash of the previous document
    previous_hash = ""  # Empty for first document

    try:
        # Read the private key
        with open(private_key_path, "rb") as f:
            private_key_pem = f.read()

        # Generate the hash
        document_hash = gerar_hash_fatura(
            invoice_date=invoice_date,
            system_entry_date=system_entry_date,
            invoice_no=invoice_no,
            gross_total=gross_total,
            previous_hash=previous_hash,
            private_key_pem=private_key_pem,
            password=private_key_password,
        )

        print(f"Document: {invoice_no}")
        print(f"Hash: {document_hash}")
        print(f"Hash length: {len(document_hash)} characters")

        # The hash should be stored in your database and included in SAF-T
        # as field 4.1.4.3 <Hash>

        # For the QR code, extract characters at positions 1, 11, 21, 31
        # (0-indexed: 0, 10, 20, 30)
        hash_chars = "".join(document_hash[i] for i in [0, 10, 20, 30])
        print(f"QR code hash chars (Q field): {hash_chars}")

        # --- Chain to next document ---
        # The next document in this series should use this hash as previous_hash

        next_invoice_no = "FT FT2025/000002"
        next_hash = gerar_hash_fatura(
            invoice_date="2025-01-16",
            system_entry_date="2025-01-16T11:00:00",
            invoice_no=next_invoice_no,
            gross_total="456.00",
            previous_hash=document_hash,  # Chain from previous
            private_key_pem=private_key_pem,
            password=private_key_password,
        )

        print(f"\nNext document: {next_invoice_no}")
        print(f"Next hash: {next_hash}")

    except FileNotFoundError:
        print(f"Error: Private key not found at {private_key_path}")
        print("Please provide a valid path to your SAF-T private key.")
    except Exception as e:
        print(f"Error generating hash: {e}")


if __name__ == "__main__":
    main()
