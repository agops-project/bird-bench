import json
import os
import argparse

from workflow.example import generate_sql_with_openai


def load_sample_questions(json_path, num_samples=5):
    """Load a subset of questions from the BIRD benchmark."""
    with open(json_path, 'r') as f:
        data = json.load(f)
    return data[:num_samples]

def main():
    parser = argparse.ArgumentParser(description='Generate SQL predictions for BIRD benchmark')
    parser.add_argument('--num_samples', type=int, default=5, help='Number of samples to process')
    parser.add_argument('--output_dir', type=str, default='predictions/', help='Output directory for predictions')
    args = parser.parse_args()
        
    if not os.getenv('OPENAI_API_KEY'):
        print("Please set the OPENAI_API_KEY environment variable")
        return
    
    # Load sample questions
    input_path = "data/mini_dev_sqlite.json"
    questions = load_sample_questions(input_path, num_samples=args.num_samples)
    
    # Generate predictions
    predictions = {}
    
    for i, item in enumerate(questions):
        print(f"Processing question {i+1}/{args.num_samples}...")
        
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
        predictions[str(i)] = formatted_prediction
        
        print(f"Generated SQL: {sql_query}")
    
    # Ensure output directory exists
    os.makedirs(args.output_dir, exist_ok=True)
    
    # Save predictions
    output_path = os.path.join(args.output_dir, "predictions.json")
    with open(output_path, 'w') as f:
        json.dump(predictions, f, indent=2)
    
    print(f"\nSaved {len(predictions)} predictions to {output_path}")

if __name__ == "__main__":
    main()