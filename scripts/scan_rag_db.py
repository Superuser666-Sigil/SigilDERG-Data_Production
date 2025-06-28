import sqlite3

DB_PATH = 'sigil_rag_cache.db'

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

tables = [r[0] for r in cursor.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()]

for t in tables:
    print(f'--- {t} ---')
    # Get column names
    cursor.execute(f'PRAGMA table_info({t})')
    columns = [col[1] for col in cursor.fetchall()]
    print('Columns:', columns)
    # Get up to 3 rows
    cursor.execute(f'SELECT * FROM {t} LIMIT 3')
    rows = cursor.fetchall()
    for row in rows:
        print(row)
    if not rows:
        print('(no rows)')
    print()

conn.close() 