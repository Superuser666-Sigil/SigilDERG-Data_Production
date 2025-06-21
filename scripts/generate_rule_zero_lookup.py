"""
Script to generate a Rule Zero runtime lookup table from the canonical DB for dev environments.
- Reads policy/enforcement data from the canonical SQLite DB.
- Outputs a JSON lookup table for fast runtime access by agents or future models.
- Ensures the lookup table is always up-to-date and traceable.
"""
import sqlite3
import json
import os

DB_PATH = os.path.abspath("sigil_rag_cache.db")
LOOKUP_PATH = os.path.abspath("rule_zero_lookup.json")

# Example: fetch all environment metadata and enforcement rules
def fetch_rule_zero_data(conn):
    data = {}
    # Fetch environment metadata
    try:
        cur = conn.execute("SELECT * FROM environment_metadata ORDER BY timestamp DESC")
        data['environment_metadata'] = [dict(row) for row in cur.fetchall()]
    except Exception as e:
        data['environment_metadata'] = f"Error: {e}"
    # Fetch Rule Zero policies
    try:
        cur = conn.execute("SELECT * FROM rule_zero_policies ORDER BY enforcement_rank DESC, last_updated DESC")
        data['rule_zero_policies'] = [dict(row) for row in cur.fetchall()]
    except Exception as e:
        data['rule_zero_policies'] = f"Error: {e}"
    # Add more tables/logic as needed for other Rule Zero rigor
    return data

def main():
    if not os.path.exists(DB_PATH):
        print(f"Canonical DB not found: {DB_PATH}")
        return
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    data = fetch_rule_zero_data(conn)
    conn.close()
    # Write lookup table as JSON
    with open(LOOKUP_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)
    print(f"Rule Zero lookup table generated: {LOOKUP_PATH}")
    # Validate JSON after writing
    try:
        with open(LOOKUP_PATH, "r", encoding="utf-8") as f:
            json.load(f)
        print("JSON validation successful.")
    except Exception as e:
        print(f"JSON validation failed: {e}")
        raise

if __name__ == "__main__":
    main()
