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

--
-- Table for architectural patterns and best practices (RAG DB)
--
CREATE TABLE IF NOT EXISTS architectural_patterns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pattern_name TEXT UNIQUE NOT NULL,
    problem_description TEXT NOT NULL,
    solution_description TEXT NOT NULL,
    code_snippet TEXT,
    source_of_truth TEXT, -- e.g., URL to documentation or article
    tags TEXT, -- Comma-separated tags for searchability
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
);
