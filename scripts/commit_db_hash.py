import subprocess
import sys
import os
import hashlib

DB_PATH = "sigil_rag_cache.db"
HASH_FILE = "sigil_rag_cache.hash"


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
    if not os.path.exists(DB_PATH):
        print(f"Database file {DB_PATH} not found.")
        sys.exit(1)
    hash_val = compute_db_hash(DB_PATH)
    with open(HASH_FILE, "w") as f:
        f.write(hash_val + "\n")
    print(f"Wrote canonical hash to {HASH_FILE}: {hash_val}")
    # Stage and commit the hash file, bypassing .gitignore
    subprocess.run(["git", "add", "-f", HASH_FILE], check=True)
    subprocess.run(["git", "commit", "-m", f"Update canonical DB hash: {hash_val}"], check=True)
    subprocess.run(["git", "push"], check=True)


if __name__ == "__main__":
    main()
