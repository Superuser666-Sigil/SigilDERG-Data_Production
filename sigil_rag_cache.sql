--
-- Table for environment metadata
--
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
);
