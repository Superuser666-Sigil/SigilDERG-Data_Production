import argparse
import hashlib
import sys

def compute_db_hash(db_path: str) -> str:
    BUF_SIZE = 65536
    sha256 = hashlib.sha256()
    with open(db_path, "rb") as f:
        while True:
            data = f.read(BUF_SIZE)
            if not data:
                break
            sha256.update(data)
    return sha256.hexdigest()

def main():
    parser = argparse.ArgumentParser(description="Validate SQLite DB hash against canonical value.")
    parser.add_argument("--db", required=True, help="Path to the SQLite database.")
    parser.add_argument("--expected-hash", required=True, help="Expected canonical SHA256 hash.")
    args = parser.parse_args()
    actual_hash = compute_db_hash(args.db)
    print(f"Computed hash:   {actual_hash}")
    print(f"Expected hash:   {args.expected_hash}")
    if actual_hash.lower() == args.expected_hash.lower():
        print("DB hash validation: SUCCESS")
    else:
        print("DB hash validation: FAILURE")
        sys.exit(1)

if __name__ == "__main__":
    main()
