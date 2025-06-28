import os
import subprocess
import sys
import logging
from typing import NoReturn

# Basic logging setup for the script itself
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    stream=sys.stdout,
)


def die(message: str) -> NoReturn:
    """Log a critical error and exit."""
    logging.critical(message)
    sys.exit(1)


def find_project_root() -> str:
    """Find the git project root robustly."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
            encoding="utf-8",
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        die(f"Failed to find project root. Is this a git repository? Error: {e}")


def main() -> None:
    """
    Orchestrates Rule Zero validation.
    1. Finds project root.
    2. Locates DB and hash files.
    3. Calls the core validation script.
    4. Exits with appropriate status code.
    """
    project_root = find_project_root()
    logging.info(f"Project root detected: {project_root}")

    db_path = os.path.join(project_root, "sigil_rag_cache.db")
    hash_path = os.path.join(project_root, "sigil_rag_cache.hash")
    validator_script = os.path.join(project_root, "scripts", "validate_db_hash.py")

    if not os.path.exists(validator_script):
        die(f"Core validation script not found: {validator_script}")
    if not os.path.exists(db_path):
        die(f"Database file not found: {db_path}")
    if not os.path.exists(hash_path):
        die(f"Hash file not found: {hash_path}")

    logging.info("Delegating to core validation script...")
    try:
        result = subprocess.run(
            [
                sys.executable,
                validator_script,
                "--db",
                db_path,
                "--expected-hash",
                hash_path,
            ],
            capture_output=True,
            text=True,
            check=False,
            encoding="utf-8",
        )

        if result.returncode == 0:
            logging.info("Rule Zero validation successful.")
            sys.exit(0)
        else:
            logging.error("Rule Zero validation FAILED.")
            # Output the failure reason for parent process to capture
            print(result.stdout, file=sys.stdout)
            print(result.stderr, file=sys.stderr)
            sys.exit(1)

    except Exception as e:
        die(f"An unexpected exception occurred during validation: {e}")


if __name__ == "__main__":
    main()
