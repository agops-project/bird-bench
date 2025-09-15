import time
import os
from openai import OpenAI

# Set up OpenAI client
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))


def generate_sql_with_openai(question, evidence, db_id):
    """Generate SQL using OpenAI API."""
    
    prompt = f"""Given the following natural language question and evidence, generate a SQL query.

Database ID: {db_id}
Question: {question}
Evidence: {evidence}

Generate only the SQL query without any additional text or explanation."""

    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": f"You are a SQL expert. Generate SQL queries based on natural language questions."},
            {"role": "user", "content": prompt}
        ],
        temperature=0
    )
    return response.choices[0].message.content.strip()
