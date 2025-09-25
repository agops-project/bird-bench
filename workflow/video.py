import time
import os
import sqlite3
from openai import OpenAI
from .utils import get_db_path

# Set up OpenAI client
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))


EXTRACT_SCHEMA_PROMPT = """Your given the following query:

{query}

You need to run this quuery against the {db_name} database with contains the following tables and schemas:

{schemas}

Output a list of all relevant columns and for each column, the table it belongs to. Don't output anything except the relevant tables and columns.
"""

GENERATE_SQL_PROMPT = """You need to write a SQL query to answer the following question:

{query}

Your SQL query is run against the {db_name} database, which contains the following relevant tables and columns.

{relevant_columns}

You are furthermore given the following hint:

{hint}

Generate the SQL query and don't output anything else.
"""

def fix_sql_syntax(sql_query):
    """Fix if LLM misformatted the SQL query."""
    # Remove code block markers (```sql and ```)
    cleaned = sql_query.strip()
    if cleaned.startswith('```sql'):
        cleaned = cleaned[6:]  # Remove ```sql
    elif cleaned.startswith('```'):
        cleaned = cleaned[3:]   # Remove ```
    
    if cleaned.endswith('```'):
        cleaned = cleaned[:-3]  # Remove trailing ```
    
    # Remove trailing semicolon if present
    cleaned = cleaned.strip()
    if cleaned.endswith(';'):
        cleaned = cleaned[:-1]
    
    return cleaned.strip()


def get_database_schema(db_name):
    """Extract all tables and their schemas from the given database."""
    db_path = get_db_path(db_name)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    schema_info = []
    
    # Get all table names
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    
    for table in tables:
        table_name = table[0]
        schema_info.append(f"\nTable: {table_name}")
        
        # Get column information for this table
        cursor.execute(f"PRAGMA table_info({table_name});")
        columns = cursor.fetchall()
        
        for col in columns:
            col_id, col_name, col_type, not_null, default_val, pk = col
            pk_marker = " (PRIMARY KEY)" if pk else ""
            null_marker = " NOT NULL" if not_null else ""
            default_marker = f" DEFAULT {default_val}" if default_val is not None else ""
            
            schema_info.append(f"  - {col_name}: {col_type}{pk_marker}{null_marker}{default_marker}")
    
    conn.close()
    
    return "\n".join(schema_info)


def call_llm(prompt):
    """Generate SQL using OpenAI API.""" 
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "user", "content": prompt}
        ],
        temperature=0
    )

    return response.choices[0].message.content.strip()


def video_example(question, evidence, db_id):
    """Generate SQL using OpenAI API.""" 

    schemas = get_database_schema(db_id)
    extract_schema_prompt = EXTRACT_SCHEMA_PROMPT.format(query=question, db_name=db_id, schemas=schemas)
    relevant_columns = call_llm(extract_schema_prompt)

    generate_sql_prompt = GENERATE_SQL_PROMPT.format(query=question, db_name=db_id, hint=evidence, relevant_columns=relevant_columns)
    sql = call_llm(generate_sql_prompt)
    sql = fix_sql_syntax(sql)
    return sql
