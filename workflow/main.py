import json
import os
import argparse
import sqlite3
from func_timeout import func_timeout, FunctionTimedOut
from workflow.example import generate_sql_with_openai
import aco

def load_sample_questions(json_path, num_samples=5):
    """Load a subset of questions from the BIRD benchmark."""
    with open(json_path, 'r') as f:
        data = json.load(f)
    return data[:num_samples]


def execute_sql(predicted_sql, ground_truth, db_path):
    """Execute SQL queries and compare results."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(predicted_sql)
    predicted_res = cursor.fetchall()
    cursor.execute(ground_truth)
    ground_truth_res = cursor.fetchall()
    conn.close()
    
    res = 0
    if set(predicted_res) == set(ground_truth_res):
        res = 1
    return res


def evaluate_single_query(predicted_sql, ground_truth, db_path, sample_id, meta_time_out=30.0):
    """Evaluate a single SQL query."""
    try:
        res = func_timeout(meta_time_out, execute_sql,
                          args=(predicted_sql, ground_truth, db_path))
        return res
    except FunctionTimedOut:
        print(f"Query timed out after {meta_time_out} seconds")
        return 0
    except Exception as e:
        print(f"Error evaluating query: {e}")
        return 0


def get_ground_truth_sql(sample_id, data_dir="data/"):
    """Get ground truth SQL for a given sample ID."""
    gold_sql_file = os.path.join(data_dir, "mini_dev_sqlite_gold.sql")
    with open(gold_sql_file, 'r') as f:
        lines = [line.strip() for line in f.readlines() if line.strip()]
    
    if sample_id >= len(lines):
        raise ValueError(f"Sample ID {sample_id} out of range (0-{len(lines)-1})")
    
    sql_line = lines[sample_id]
    sql, db_name = sql_line.split('\t')
    return sql, db_name


if __name__ == "__main__":

    parser = argparse.ArgumentParser(description='Process single SQL query and evaluate')
    parser.add_argument('--sample_id', type=int, required=True, help='Sample ID to process (0-indexed)')
    parser.add_argument('--data_dir', type=str, default='data/', help='Data directory')
    parser.add_argument('--db_root_path', type=str, default='data/dev_databases/', help='Database root path')
    parser.add_argument('--meta_time_out', type=float, default=30.0, help='Timeout for SQL execution')
    args = parser.parse_args()
    
    sample_id = args.sample_id

    try:
        # Load the specific question
        input_path = os.path.join(args.data_dir, "mini_dev_sqlite.json")
        questions = load_sample_questions(input_path, num_samples=1000)  # Load enough to get our sample
        
        if sample_id >= len(questions):
            print(f"Error: sample_id {sample_id} is out of range (0-{len(questions)-1})")
            exit(1)
        
        question_data = questions[sample_id]
        
        # Generate SQL using OpenAI
        sql_query = generate_sql_with_openai(
            question_data['question'], 
            question_data['evidence'], 
            question_data['db_id']        
        )
        
        # Clean up any markdown formatting
        if sql_query.startswith('```sql'):
            sql_query = sql_query.replace('```sql\n', '').replace('```', '').strip()
        sql_query = sql_query.replace('\n', ' ').strip()
        
        print(f"Generated SQL for question {sample_id}: {sql_query}")
        
        # Get ground truth SQL and database info
        ground_truth_sql, db_name = get_ground_truth_sql(sample_id, args.data_dir)
        db_path = os.path.join(args.db_root_path, db_name, f"{db_name}.sqlite")
        
        # Evaluate the query
        result = evaluate_single_query(sql_query, ground_truth_sql, db_path, sample_id, args.meta_time_out)
        
        # Log success/failure
        aco.log(success=bool(result))
        
        # Format prediction for output (compatible with existing format)
        formatted_prediction = f"{sql_query}\t----- bird -----\t{question_data['db_id']}"
        print(f"PREDICTION:{formatted_prediction}")
        print(f"EVALUATION_RESULT:{result}")
        
    except Exception as e:
        print(f"Error processing sample {sample_id}: {e}")
        exit(1)
