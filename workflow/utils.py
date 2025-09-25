import sqlite3
import os
import uuid
from aco import untaint_if_needed, get_taint_origins, taint_wrap
from aco.common.utils import send_to_server
from aco.runner.context_manager import get_session_id
from aco.common.constants import CERTAINTY_YELLOW

def call_db(sql, db_name, label="SQLite Query"):
    print("CALL DB", label)
    """Execute a SQL query on the specified database and return results."""
    taint_origins = get_taint_origins(sql)
    sql_clean = untaint_if_needed(sql)    
    
    node_id = str(uuid.uuid4())
    results = None
    output_text = ""
    
    try:
        db_path = get_db_path(db_name)
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(sql_clean)
        results = cursor.fetchall()
        conn.close()
        
        # Format successful results
        output_preview = results[:5] if results else []
        output_text = str(output_preview)
        
    except Exception as e:
        # Format exception as output
        output_text = str(e)
        print(f"SQL execution failed: {e}")
    
    # Always send to server regardless of success/failure
    session_id = get_session_id()
    print(f"Session ID: {session_id}")
    
    node_msg = {
        "type": "add_node",
        "session_id": session_id,
        "node": {
            "id": node_id,
            "input": sql_clean,
            "output": output_text,
            "border_color": CERTAINTY_YELLOW,
            "label": label,
            "codeLocation": f"{__file__}:call_db",
            "model": "sqlite3",
        },
        "incoming_edges": list(taint_origins),
    }
    
    try:
        print(f"Sending node message: {node_msg}")
        send_to_server(node_msg)
        print("Successfully sent to server")
    except Exception as e:
        print(f"Failed to send to server: {e}")
        import traceback
        traceback.print_exc()

    # Re-raise the original exception if SQL failed
    if results is None:
        raise Exception(output_text)
    
    return taint_wrap(results, [node_id])

def get_db_path(db_name):
    """Construct the database path for a given database name."""
    # Get the directory containing this file (workflow/)
    current_dir = os.path.dirname(__file__)
    # Go up one level to the project root and then to data/dev_databases/
    db_root_path = os.path.join(current_dir, "..", "data", "dev_databases")
    return os.path.join(db_root_path, db_name, f"{db_name}.sqlite")