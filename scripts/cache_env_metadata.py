import sqlite3
from datetime import datetime, timezone

# Non-PII system info for dev environment
ENV_INFO = {
    "label": "dev",
    "os_name": "Microsoft Windows 11 Pro",
    "os_version": "10.0.26100 N/A Build 26100",
    "system_type": "x64-based PC",
    "processor": "1 Processor(s) Installed.",
    "bios_version": "AMI F.23, 1/17/2025",
    "enforcement_rank": 10,  # Highest for dev enforcement
    "timestamp": datetime.now(timezone.utc).isoformat(),
}


def cache_env_metadata(db_path: str = "sigil_rag_cache.db"):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute(
        """
    CREATE TABLE IF NOT EXISTS environment_metadata (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        label TEXT NOT NULL,
        os_name TEXT,
        os_version TEXT,
        system_type TEXT,
        processor TEXT,
        bios_version TEXT,
        enforcement_rank INTEGER NOT NULL,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """
    )
    cur.execute(
        """
        INSERT INTO environment_metadata (label, os_name, os_version, system_type, processor, bios_version, enforcement_rank, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            ENV_INFO["label"],
            ENV_INFO["os_name"],
            ENV_INFO["os_version"],
            ENV_INFO["system_type"],
            ENV_INFO["processor"],
            ENV_INFO["bios_version"],
            ENV_INFO["enforcement_rank"],
            ENV_INFO["timestamp"],
        ),
    )
    conn.commit()
    conn.close()
    print("Dev environment metadata cached to DB.")


if __name__ == "__main__":
    cache_env_metadata()
