import sqlite3
import os
from aco import untaint_if_needed, get_taint_origins, taint_wrap

def call_db(sql, db_name):
    """Execute a SQL query on the specified database and return results."""
    taint_origins = get_taint_origins(sql)
    sql = untaint_if_needed(sql)
    
    db_path = get_db_path(db_name)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(sql)
    results = cursor.fetchall()
    conn.close()

    return taint_wrap(results, taint_origins)

def get_db_path(db_name):
    """Construct the database path for a given database name."""
    # Get the directory containing this file (workflow/)
    current_dir = os.path.dirname(__file__)
    # Go up one level to the project root and then to data/dev_databases/
    db_root_path = os.path.join(current_dir, "..", "data", "dev_databases")
    return os.path.join(db_root_path, db_name, f"{db_name}.sqlite")