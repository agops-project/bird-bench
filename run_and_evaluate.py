import json
import os
import argparse
import concurrent.futures
import subprocess
import sys


def load_sample_questions(json_path, num_samples=5):
    """Load a subset of questions from the BIRD benchmark."""
    with open(json_path, 'r') as f:
        data = json.load(f)
    return data[:num_samples]

def generate_single_sql_subprocess(index, use_develop=True):
    """Generate SQL for a single question using subprocess."""
    try:
        # Use develop command to run workflow/main.py
        if use_develop:
            cmd = ["develop", "workflow/main.py", f"--sample_id={index}"]
        else:
            cmd = ["python", "-m", "workflow.main", f"--sample_id={index}"]
            
        # Prepare environment variables: copy current env and add session ID
        env = os.environ.copy()
        env["AGENT_COPILOT_SESSION_ID"] = str(index)
        
        # Run the subprocess with the modified environment
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300, env=env)
        
        if result.returncode != 0:
            raise Exception(f"Subprocess failed: {result.stderr}")
        
        # Parse the result
        output_lines = result.stdout.strip().split('\n')
        prediction_line = None
        evaluation_result = None
        
        for line in output_lines:
            if line.startswith("PREDICTION:"):
                prediction_line = line[11:]  # Remove "PREDICTION:" prefix
            elif line.startswith("EVALUATION_RESULT:"):
                evaluation_result = int(line[18:])  # Remove "EVALUATION_RESULT:" prefix
        
        if not prediction_line:
            raise Exception(f"No prediction found in output: {result.stdout}")
        
        return {
            'index': index, 
            'prediction': prediction_line,
            'evaluation_result': evaluation_result if evaluation_result is not None else 0
        }
    
    except Exception as e:
        print(f"Error in subprocess for sample {index}: {e}")
        raise


def main():
    parser = argparse.ArgumentParser(description='Generate SQL predictions for BIRD benchmark')
    parser.add_argument('--num_samples', type=int, default=5, help='Number of samples to process')
    parser.add_argument('--output_dir', type=str, default='predictions/', help='Output directory for predictions')
    parser.add_argument('--max_workers', type=int, default=8, help='Number of worker processes for parallel processing')
    parser.add_argument('--sample_id', type=int, default=-1, help='Run only the specific sample ID (0-indexed), or -1 for all samples')
    parser.add_argument('--use_python', action='store_true', help='Use python command instead of develop command')
    args = parser.parse_args()
        
    if not os.getenv('OPENAI_API_KEY'):
        print("Please set the OPENAI_API_KEY environment variable")
        return
    
    # Load sample questions to determine the range
    input_path = "data/mini_dev_sqlite.json"
    questions = load_sample_questions(input_path, num_samples=args.num_samples)
    
    # Determine which samples to process
    if args.sample_id >= 0:
        if args.sample_id >= len(questions):
            print(f"Error: sample_id {args.sample_id} is out of range (0-{len(questions)-1})")
            return
        sample_indices = [args.sample_id]
        print(f"Generating SQL for sample {args.sample_id} only...")
    else:
        sample_indices = list(range(len(questions)))
        print(f"Generating SQL for {len(questions)} questions using {args.max_workers} subprocess workers...")
    
    # Always use develop command by default, unless --use_python flag is passed
    use_develop = not args.use_python
    
    # Use subprocess approach with ThreadPoolExecutor to manage the subprocesses
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.max_workers) as executor:
        futures = [executor.submit(generate_single_sql_subprocess, idx, use_develop) for idx in sample_indices]
        results = [f.result() for f in futures]
    
    print(f"Successfully completed {len(results)} tasks using subprocess approach.")
    
    # Sort results by index and convert to expected format
    results.sort(key=lambda x: x['index'])
    final_predictions = {}
    evaluation_results = {}
    
    for result in results:
        final_predictions[str(result['index'])] = result['prediction']
        evaluation_results[str(result['index'])] = result['evaluation_result']
    
    # Calculate and display accuracy
    total_correct = sum(evaluation_results.values())
    total_queries = len(evaluation_results)
    accuracy = total_correct / total_queries * 100 if total_queries > 0 else 0
    
    print(f"\nEvaluation Results:")
    print(f"Total queries: {total_queries}")
    print(f"Correct: {total_correct}")
    print(f"Accuracy: {accuracy:.2f}%")
    
    # Ensure output directory exists
    os.makedirs(args.output_dir, exist_ok=True)
    
    # Save predictions
    output_path = os.path.join(args.output_dir, "predictions.json")
    with open(output_path, 'w') as f:
        json.dump(final_predictions, f, indent=2)
    
    # Save evaluation results
    eval_output_path = os.path.join(args.output_dir, "evaluation_results.json")
    with open(eval_output_path, 'w') as f:
        json.dump(evaluation_results, f, indent=2)
    
    print(f"\nSaved {len(final_predictions)} predictions to {output_path}")
    print(f"Saved evaluation results to {eval_output_path}")

if __name__ == "__main__":
    main()