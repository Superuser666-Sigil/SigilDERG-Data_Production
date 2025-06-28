from typing import Dict, List, Tuple, Optional, Any
import argparse
import sqlite3
import hashlib
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.exceptions import InvalidSignature


def load_signature_and_hash_from_db(db_path: str):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT db_hash, signature FROM provenance ORDER BY timestamp DESC LIMIT 1")
    row = cur.fetchone()
    conn.close()
    if not row:
        raise ValueError("No signature found in provenance table.")
    return row[0], row[1]


def verify_signature(db_path: str, public_key_path: str) -> bool:
    db_hash, signature = load_signature_and_hash_from_db(db_path)
    with open(public_key_path, "rb") as key_file:
        public_key = serialization.load_pem_public_key(key_file.read())
    key_type = type(public_key).__name__
    try:
        if key_type.startswith('Ed25519'):
            public_key.verify(signature, db_hash.encode())
        elif key_type.startswith('RSAPublicKey') or hasattr(public_key, 'public_numbers'):
            public_key.verify(
                signature,
                db_hash.encode(),
                padding.PKCS1v15(),
                hashes.SHA256(),
            )
        else:
            raise ValueError(f"Unsupported public key type: {key_type}")
        return True
    except InvalidSignature:
        return False


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate SQLite DB signature using public key."
    )
    parser.add_argument("--db", required=True, help="Path to the SQLite database.")
    parser.add_argument(
        "--public-key", required=True, help="Path to the public PEM key."
    )
    args = parser.parse_args()
    if verify_signature(args.db, args.public_key):
        print("Signature validation: SUCCESS")
    else:
        print("Signature validation: FAILURE")
        exit(1)


if __name__ == "__main__":
    main()
