import argparse
import sqlite3
import hashlib
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.exceptions import InvalidSignature


def load_signature_from_db(db_path: str) -> bytes:
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT signature FROM provenance ORDER BY timestamp DESC LIMIT 1")
    row = cur.fetchone()
    conn.close()
    if not row:
        raise ValueError("No signature found in provenance table.")
    return row[0]

def load_db_hash(db_path: str) -> bytes:
    BUF_SIZE = 65536
    sha256 = hashlib.sha256()
    with open(db_path, "rb") as f:
        while True:
            data = f.read(BUF_SIZE)
            if not data:
                break
            sha256.update(data)
    return sha256.digest()

def verify_signature(db_path: str, public_key_path: str) -> bool:
    signature = load_signature_from_db(db_path)
    db_hash = load_db_hash(db_path)
    with open(public_key_path, "rb") as key_file:
        public_key = serialization.load_pem_public_key(key_file.read())
    try:
        public_key.verify(
            signature,
            db_hash,
            padding.PKCS1v15(),
            hashes.SHA256(),
        )
        return True
    except InvalidSignature:
        return False

def main():
    parser = argparse.ArgumentParser(description="Validate SQLite DB signature using public key.")
    parser.add_argument("--db", required=True, help="Path to the SQLite database.")
    parser.add_argument("--public-key", required=True, help="Path to the public PEM key.")
    args = parser.parse_args()
    if verify_signature(args.db, args.public_key):
        print("Signature validation: SUCCESS")
    else:
        print("Signature validation: FAILURE")
        exit(1)

if __name__ == "__main__":
    main()
