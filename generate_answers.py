import json
import os
import argparse
import concurrent.futures

from workflow.example import generate_sql_with_openai
import aco

def load_sample_questions(json_path, num_samples=5):
    """Load a subset of questions from the BIRD benchmark."""
    with open(json_path, 'r') as f:
        data = json.load(f)
    return data[:num_samples]

def generate_single_sql(item, index):
    """Generate SQL for a single question in its own context (threaded)."""
    question_id = item.get('question_id', f'q{index}')
    with aco.launch(run_name=f"Query {index}"):
        sql_query = generate_sql_with_openai(
            item['question'], 
            item['evidence'], 
            item['db_id']        
        )
    
    # Clean up any markdown formatting
    if sql_query.startswith('```sql'):
        sql_query = sql_query.replace('```sql\n', '').replace('```', '').strip()
    sql_query = sql_query.replace('\n', ' ').strip()
    
    # Format as expected by evaluation script: "SQL\t----- bird -----\tdb_id"
    formatted_prediction = f"{sql_query}\t----- bird -----\t{item['db_id']}"
    
    print(f"Generated SQL for question {index + 1}: {sql_query}")
    
    return {'index': index, 'prediction': formatted_prediction}

def main():
    parser = argparse.ArgumentParser(description='Generate SQL predictions for BIRD benchmark')
    parser.add_argument('--num_samples', type=int, default=5, help='Number of samples to process')
    parser.add_argument('--output_dir', type=str, default='predictions/', help='Output directory for predictions')
    parser.add_argument('--max_workers', type=int, default=8, help='Number of worker threads for parallel processing')
    args = parser.parse_args()
        
    if not os.getenv('OPENAI_API_KEY'):
        print("Please set the OPENAI_API_KEY environment variable")
        return
    
    # Load sample questions
    input_path = "data/mini_dev_sqlite.json"
    questions = load_sample_questions(input_path, num_samples=args.num_samples)
    
    print(f"Generating SQL for {len(questions)} questions using {args.max_workers} threads...")
    
    # Generate predictions in parallel using ThreadPoolExecutor
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.max_workers) as executor:
        futures = [executor.submit(generate_single_sql, item, i) for i, item in enumerate(questions)]
        results = [f.result() for f in futures]
    
    # Sort results by index and convert to expected format
    results.sort(key=lambda x: x['index'])
    final_predictions = {}
    for result in results:
        final_predictions[str(result['index'])] = result['prediction']
    
    # Ensure output directory exists
    os.makedirs(args.output_dir, exist_ok=True)
    
    # Save predictions
    output_path = os.path.join(args.output_dir, "predictions.json")
    with open(output_path, 'w') as f:
        json.dump(final_predictions, f, indent=2)
    
    print(f"\nSaved {len(final_predictions)} predictions to {output_path}")

if __name__ == "__main__":
    main()