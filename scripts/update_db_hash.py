from typing import Dict, List, Tuple, Optional, Any
import hashlib
import os


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


def main() -> None:
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    db_path = os.path.join(repo_root, "sigil_rag_cache.db")
    hash_path = os.path.join(repo_root, "sigil_rag_cache.hash")
    new_hash = compute_db_hash(db_path)
    with open(hash_path, "w") as f:
        f.write(new_hash + "\n")
    print(f"Updated {hash_path} with hash: {new_hash}")


if __name__ == "__main__":
    main()
