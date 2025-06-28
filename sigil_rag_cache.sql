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

--
-- Enhanced Hardware Profile Table
--
CREATE TABLE IF NOT EXISTS hardware_profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_name TEXT NOT NULL,
    cpu_model TEXT,
    cpu_cores INTEGER,
    cpu_threads INTEGER,
    ram_total_gb REAL,
    gpu_model TEXT,
    gpu_vram_gb INTEGER,
    storage_type TEXT, -- SSD, HDD, NVMe
    storage_capacity_gb REAL,
    network_speed_mbps INTEGER,
    os_platform TEXT,
    os_version TEXT,
    python_version TEXT,
    available_models TEXT, -- JSON array of available model paths
    performance_benchmarks TEXT, -- JSON object with benchmark results
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
);

--
-- Code Index Table for Fast File/Function Lookup
--
CREATE TABLE IF NOT EXISTS code_index (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path TEXT NOT NULL,
    file_name TEXT NOT NULL,
    file_extension TEXT,
    function_name TEXT,
    class_name TEXT,
    module_name TEXT,
    code_snippet TEXT,
    docstring TEXT,
    imports TEXT, -- JSON array of imports
    dependencies TEXT, -- JSON array of dependencies
    complexity_score REAL,
    lines_of_code INTEGER,
    last_modified DATETIME,
    git_hash TEXT,
    tags TEXT, -- Comma-separated tags for searchability
    content_hash TEXT, -- Hash of actual content for change detection
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
);

--
-- Documentation Cache Table
--
CREATE TABLE IF NOT EXISTS documentation_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_type TEXT NOT NULL, -- 'api', 'readme', 'tutorial', 'reference'
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    source_url TEXT,
    source_file TEXT,
    package_name TEXT,
    version TEXT,
    language TEXT, -- 'python', 'rust', 'javascript', etc.
    tags TEXT, -- Comma-separated tags
    relevance_score REAL, -- 0.0 to 1.0
    last_accessed DATETIME,
    access_count INTEGER DEFAULT 0,
    content_hash TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
);

--
-- Code Changes History Table
--
CREATE TABLE IF NOT EXISTS code_changes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path TEXT NOT NULL,
    change_type TEXT NOT NULL, -- 'added', 'modified', 'deleted', 'renamed'
    old_content TEXT,
    new_content TEXT,
    diff_summary TEXT,
    commit_hash TEXT,
    commit_message TEXT,
    author TEXT,
    timestamp DATETIME,
    impact_score REAL, -- 0.0 to 1.0 based on change significance
    affected_functions TEXT, -- JSON array of affected function names
    breaking_changes BOOLEAN DEFAULT FALSE,
    tags TEXT, -- Comma-separated tags
    recorded_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

--
-- Project Context Table
--
CREATE TABLE IF NOT EXISTS project_context (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_name TEXT NOT NULL,
    project_path TEXT NOT NULL,
    description TEXT,
    tech_stack TEXT, -- JSON array of technologies
    dependencies TEXT, -- JSON object of dependencies
    configuration TEXT, -- JSON object of config files
    environment_vars TEXT, -- JSON object of environment variables
    build_commands TEXT, -- JSON array of build/run commands
    test_commands TEXT, -- JSON array of test commands
    deployment_info TEXT, -- JSON object of deployment details
    last_updated DATETIME,
    active BOOLEAN DEFAULT TRUE,
    tags TEXT, -- Comma-separated tags
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
);

--
-- Agent Session Context Table
--
CREATE TABLE IF NOT EXISTS agent_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT UNIQUE NOT NULL,
    user_id TEXT,
    context_summary TEXT,
    current_task TEXT,
    relevant_files TEXT, -- JSON array of relevant file paths
    conversation_history TEXT, -- JSON array of conversation turns
    memory_context TEXT, -- JSON object of important context
    performance_metrics TEXT, -- JSON object of session metrics
    start_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_activity DATETIME DEFAULT CURRENT_TIMESTAMP,
    active BOOLEAN DEFAULT TRUE
);

--
-- Search Index for Fast Retrieval
--
CREATE VIRTUAL TABLE IF NOT EXISTS search_index USING fts5(
    content,
    title,
    tags,
    doc_type,
    file_path,
    timestamp
);

--
-- Indexes for Performance
--
CREATE INDEX IF NOT EXISTS idx_code_index_file_path ON code_index(file_path);
CREATE INDEX IF NOT EXISTS idx_code_index_function ON code_index(function_name);
CREATE INDEX IF NOT EXISTS idx_code_index_class ON code_index(class_name);
CREATE INDEX IF NOT EXISTS idx_docs_package ON documentation_cache(package_name);
CREATE INDEX IF NOT EXISTS idx_docs_type ON documentation_cache(doc_type);
CREATE INDEX IF NOT EXISTS idx_changes_file ON code_changes(file_path);
CREATE INDEX IF NOT EXISTS idx_changes_timestamp ON code_changes(timestamp);
CREATE INDEX IF NOT EXISTS idx_projects_active ON project_context(active);
CREATE INDEX IF NOT EXISTS idx_sessions_active ON agent_sessions(active);
