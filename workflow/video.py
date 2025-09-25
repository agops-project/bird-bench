import time
import os
import sqlite3
from openai import OpenAI
from .utils import call_db, get_db_path

# Set up OpenAI client
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))


EXTRACT_SCHEMA_PROMPT = """Your given the following query:

{query}

You need to run this quuery against the {db_name} database with contains the following tables and schemas:

{schemas}

Output a list of all relevant columns and for each column, the table it belongs to. Don't output anything except the relevant tables and columns. Note that the query might go over multiple tables and require JOINs.
"""

GENERATE_SQL_PROMPT = """You need to write a SQL query to answer the following question:

{query}

Your SQL query is run against the {db_name} database, which contains the following relevant tables and columns.

{relevant_columns}

You are furthermore given the following hint:

{hint}

Generate the SQL query and don't output anything else. Consider if you need to JOIN tables.
"""

EXTRACT_SCHEMA_VERIFY_PROMPT = """You need to write a SQL query to answer the following question:

Which year recorded the most consumption of gas paid in CZK?

The query is run against the following database:

{schema}

The SQL query might contain JOINs, so think carefully which tables you all need to answer the question, there might be several.

Previously, someone suggested that those are all tables needed:

{prev_output}

Are they enough? Are some missing that need to be joined? Are there too many? First, reason about the existing tables and think carefully which ones are needed. Is the previous list correct? Justify your answer.
"""

FINAL_EXTRACT = """Ultimately, a user wants to answer the following question:

{query}

This question is asked against a database with the following tables and schemas:

{schema}

Your job is to output the columns and tables needed to answer this question. There has already been a discussion on the relevant tables and columns.

First, someone suggested this:

{first_answer}

Then, someone commented the following:

{second_answer}

You now need to combine these answers into a comprehensive list. What are the columns and tables needed to answer the query? Be clear and output all relevant columns and tables.
"""

REVISE_FINAL_OUTPUT = """There's a discussion on how to write a SQL query. The query should answer the following question:

{query}

First, someone ran this query against the {db_name} database using the following SQL statement:

{sql}

which renders this answer:

{answer}

Then, someone criticized this SQL statement as follows:

{sql_critique}

Given this discussion, your job is now to output the final SQL statement that should be run. Only output the right query and nothing else.
"""

JUDGE_ANSWER_PROMPT = """Your given the following query:

{query}

This query is run against the {db_name} database using the following SQL statement:

{sql}

which renders this answer:

{answer}

First assess whether this matches, the expected output of the question. Think step by step and explain why it matches the expected output or doesn't. Pay special attention to what columns are output as the question may be nuanced on what columns it asks for.

Then, based on your assessment, output the SQL query that you think is correct. Again, pay special attention to what columns you output."""


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
            _, col_name, col_type, not_null, default_val, pk = col
            pk_marker = " (PRIMARY KEY)" if pk else ""
            null_marker = " NOT NULL" if not_null else ""
            default_marker = f" DEFAULT {default_val}" if default_val is not None else ""
            
            schema_info.append(f"  - {col_name}: {col_type}{pk_marker}{null_marker}{default_marker}")
        
        # Get foreign key information for this table
        cursor.execute(f"PRAGMA foreign_key_list({table_name});")
        foreign_keys = cursor.fetchall()
        
        if foreign_keys:
            schema_info.append("  Foreign Keys:")
            for fk in foreign_keys:
                _, _, table_ref, from_col, to_col, _, _, _ = fk
                schema_info.append(f"    - {from_col} -> {table_ref}.{to_col}")
        
        # Get sample row for this table
        try:
            cursor.execute(f"SELECT * FROM {table_name} LIMIT 1;")
            sample_row = cursor.fetchone()
            if sample_row:
                schema_info.append("  Example row:")
                col_names = [desc[0] for desc in cursor.description]
                for col_name, value in zip(col_names, sample_row):
                    schema_info.append(f"    {col_name}: {value}")
        except Exception:
            schema_info.append("  Example row: No data available")
    
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

    prompt = EXTRACT_SCHEMA_VERIFY_PROMPT.format(query=question, schema=schemas, prev_output=relevant_columns)
    critic = call_llm(prompt)

    prompt = FINAL_EXTRACT.format(query=question, schema=schemas, first_answer=relevant_columns, second_answer=critic)
    final_schema = call_llm(prompt)

    prompt = GENERATE_SQL_PROMPT.format(query=question, db_name=db_id, hint=evidence, relevant_columns=final_schema)
    sql = call_llm(prompt)
    sql = fix_sql_syntax(sql)

    answer = call_db(sql, db_id, label="Test query")
    prompt = JUDGE_ANSWER_PROMPT.format(query=question, db_name=db_id, sql=sql, answer=answer)
    judge_sql = call_llm(prompt)
    
    prompt = REVISE_FINAL_OUTPUT.format(query=question, db_name=db_id, sql=sql, answer=answer, sql_critique=judge_sql)
    sql = call_llm(prompt)
    sql = fix_sql_syntax(sql)
    return sql
