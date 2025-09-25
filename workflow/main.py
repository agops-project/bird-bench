import json
import os
import argparse
import sqlite3
from .example import example1
from .video import video_example
from .utils import call_db
import aco

def load_sample_questions(json_path, num_samples=5):
    """Load a subset of questions from the BIRD benchmark."""
    with open(json_path, 'r') as f:
        data = json.load(f)
    return data[:num_samples]


def execute_sql(predicted_sql, ground_truth, db_name):
    """Execute SQL queries and compare results using call_db function."""
    predicted_res = None
    ground_truth_res = None
    
    # Execute ground truth SQL and label it as "DB gold" - always execute regardless of predicted result
    try:
        ground_truth_res = call_db(ground_truth, db_name, "DB gold")
    except Exception as e:
        print(f"Ground truth SQL failed: {e}")
    

    # Execute predicted SQL and label it as "DB predicted" 
    try:
        predicted_res = call_db(predicted_sql, db_name, "DB predicted")
    except Exception as e:
        print(f"Predicted SQL failed: {e}")
    
    # Compare results only if both succeeded
    res = 0
    if predicted_res is not None and ground_truth_res is not None:
        if set(predicted_res) == set(ground_truth_res):
            res = 1
    
    return res


def evaluate_single_query(predicted_sql, ground_truth, db_name, sample_id, meta_time_out=30.0):
    """Evaluate a single SQL query."""
    try:
        res = execute_sql(predicted_sql, ground_truth, db_name)
        return res
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

    # Load the specific question
    input_path = os.path.join(args.data_dir, "mini_dev_sqlite.json")
    questions = load_sample_questions(input_path, num_samples=1000)  # Load enough to get our sample
    
    if sample_id >= len(questions):
        print(f"Error: sample_id {sample_id} is out of range (0-{len(questions)-1})")
        exit(1)
    
    question_data = questions[sample_id]
    
    # Generate SQL using OpenAI
    sql_query = video_example(
        question_data['question'], 
        question_data['evidence'], 
        question_data['db_id']        
    )
    
    # Clean up any markdown formatting
    if sql_query.startswith('```sql'):
        sql_query = sql_query.replace('```sql\n', '').replace('```', '').strip()
    sql_query = sql_query.replace('\n', ' ').strip()
        
    # Get ground truth SQL and database info
    ground_truth_sql, db_name = get_ground_truth_sql(sample_id, args.data_dir)
    
    # Evaluate the query
    result = evaluate_single_query(sql_query, ground_truth_sql, db_name, sample_id, args.meta_time_out)
    
    # Log success/failure
    aco.log(success=bool(result))
