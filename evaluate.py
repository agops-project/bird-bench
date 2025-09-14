import sys
import json
import argparse
import sqlite3
import multiprocessing as mp
import tempfile
import os
import shutil
# from runner.context_manager import aco_launch
from func_timeout import func_timeout, FunctionTimedOut

def load_json(dir):
    with open(dir, 'r') as j:
        contents = json.loads(j.read())
    return contents

def result_callback(result):
    exec_result.append(result)


def execute_sql(predicted_sql,ground_truth, db_path):
    conn = sqlite3.connect(db_path)
    # Connect to the database
    cursor = conn.cursor()
    cursor.execute(predicted_sql)
    predicted_res = cursor.fetchall()
    cursor.execute(ground_truth)
    ground_truth_res = cursor.fetchall()
    res = 0
    if set(predicted_res) == set(ground_truth_res):
        res = 1
    return res



def execute_model(predicted_sql,ground_truth, db_place, idx, meta_time_out):
    try:
        res = func_timeout(meta_time_out, execute_sql,
                                  args=(predicted_sql, ground_truth, db_place))
    except KeyboardInterrupt:
        sys.exit(0)
    except FunctionTimedOut:
        result = [(f'timeout',)]
        res = 0
    except Exception as e:
        result = [(f'error',)]  # possibly len(query) > 512 or not executable
        res = 0
    # print(result)
    # result = str(set([ret[0] for ret in result]))
    result = {'sql_idx': idx, 'res': res}
    # print(result)
    return result


def package_sqls(sql_path, db_root_path, mode='gpt', data_mode='dev'):
    clean_sqls = []
    db_path_list = []
    if mode == 'gpt':
        sql_data = json.load(open(sql_path + 'predictions.json', 'r'))
        for idx, sql_str in sql_data.items():
            if type(sql_str) == str:
                sql, db_name = sql_str.split('\t----- bird -----\t')
            else:
                sql, db_name = " ", "financial"
            clean_sqls.append(sql)
            db_path_list.append(db_root_path + db_name + '/' + db_name + '.sqlite')

    elif mode == 'gt':
        sqls = open(sql_path + data_mode + '_gold.sql')
        sql_txt = sqls.readlines()
        # sql_txt = [sql.split('\t')[0] for sql in sql_txt]
        for idx, sql_str in enumerate(sql_txt):
            sql, db_name = sql_str.strip().split('\t')
            clean_sqls.append(sql)
            db_path_list.append(db_root_path + db_name + '/' + db_name + '.sqlite')

    return clean_sqls, db_path_list

def run_sqls_parallel(sqls, db_places, num_cpus=1, meta_time_out=30.0):
    pool = mp.Pool(processes=num_cpus)
    for i,sql_pair in enumerate(sqls):
        # with aco_launch("bird-run"):  # Removed ACO dependency
        predicted_sql, ground_truth = sql_pair
        pool.apply_async(execute_model, args=(predicted_sql, ground_truth, db_places[i], i, meta_time_out), callback=result_callback)
    pool.close()
    pool.join()

def sort_results(list_of_dicts):
  return sorted(list_of_dicts, key=lambda x: x['sql_idx'])

def compute_acc_by_diff(exec_results,diff_json_path):
    num_queries = len(exec_results)
    results = [res['res'] for res in exec_results]
    contents = load_json(diff_json_path)
    simple_results, moderate_results, challenging_results = [], [], []

    for i,content in enumerate(contents):
        if content['difficulty'] == 'simple':
            simple_results.append(exec_results[i])

        if content['difficulty'] == 'moderate':
            moderate_results.append(exec_results[i])

        if content['difficulty'] == 'challenging':
            challenging_results.append(exec_results[i])

    simple_acc = sum([res['res'] for res in simple_results])/len(simple_results) if simple_results else 0
    moderate_acc = sum([res['res'] for res in moderate_results])/len(moderate_results) if moderate_results else 0
    challenging_acc = sum([res['res'] for res in challenging_results])/len(challenging_results) if challenging_results else 0
    all_acc = sum(results)/num_queries
    count_lists = [len(simple_results), len(moderate_results), len(challenging_results), num_queries]
    return simple_acc * 100, moderate_acc * 100, challenging_acc * 100, all_acc * 100, count_lists



def print_data(score_lists,count_lists):
    levels = ['simple', 'moderate', 'challenging', 'total']
    print("{:20} {:20} {:20} {:20} {:20}".format("", *levels))
    print("{:20} {:<20} {:<20} {:<20} {:<20}".format('count', *count_lists))

    print('======================================    ACCURACY    =====================================')
    print("{:20} {:<20.2f} {:<20.2f} {:<20.2f} {:<20.2f}".format('accuracy', *score_lists))


if __name__ == '__main__':
    args_parser = argparse.ArgumentParser()
    args_parser.add_argument('--predicted_sql_path', type=str, default='predictions/')
    args_parser.add_argument('--ground_truth_path', type=str, default='data/')
    args_parser.add_argument('--data_mode', type=str, default='dev')
    args_parser.add_argument('--db_root_path', type=str, default='data/dev_databases/')
    args_parser.add_argument('--num_cpus', type=int, default=1)
    args_parser.add_argument('--meta_time_out', type=float, default=30.0)
    args_parser.add_argument('--mode_gt', type=str, default='gt')
    args_parser.add_argument('--mode_predict', type=str, default='gpt')
    args_parser.add_argument('--difficulty',type=str,default='simple')
    args_parser.add_argument('--diff_json_path',type=str,default='data/mini_dev_sqlite.json')
    args_parser.add_argument('--num_samples', type=int, default=5, help='Number of samples to evaluate')
    args = args_parser.parse_args()
    exec_result = []

    # Create temporary files with limited samples if num_samples is specified
    temp_dir = None
    original_diff_json_path = args.diff_json_path
    original_ground_truth_path = args.ground_truth_path
    
    if args.num_samples and args.num_samples > 0:
        print(f"Creating temporary files for {args.num_samples} samples...")
        
        # Create temporary directory
        temp_dir = tempfile.mkdtemp()
        
        # Load and limit questions
        with open(original_diff_json_path, 'r') as f:
            questions = json.load(f)
        limited_questions = questions[:args.num_samples]
        
        # Save limited questions
        temp_questions_file = os.path.join(temp_dir, 'dev.json')
        with open(temp_questions_file, 'w') as f:
            json.dump(limited_questions, f, indent=2)
        args.diff_json_path = temp_questions_file
        
        # Load and limit gold SQL
        gold_sql_file = original_ground_truth_path + 'mini_dev_sqlite_gold.sql'
        with open(gold_sql_file, 'r') as f:
            gold_lines = [line.strip() for line in f.readlines() if line.strip()]
        limited_gold_lines = gold_lines[:args.num_samples]
        
        # Save limited gold SQL
        temp_gold_file = os.path.join(temp_dir, 'dev_gold.sql')
        with open(temp_gold_file, 'w') as f:
            for line in limited_gold_lines:
                f.write(line + '\n')
        args.ground_truth_path = temp_dir + '/'

    try:
        pred_queries, db_paths = package_sqls(args.predicted_sql_path, args.db_root_path, mode=args.mode_predict,
                                              data_mode=args.data_mode)
        
        # Limit predictions to num_samples if specified
        if args.num_samples and args.num_samples > 0:
            pred_queries = pred_queries[:args.num_samples]
            db_paths = db_paths[:args.num_samples]
        
        # generate gt sqls:
        gt_queries, db_paths_gt = package_sqls(args.ground_truth_path, args.db_root_path, mode='gt',
                                               data_mode=args.data_mode)

        query_pairs = list(zip(pred_queries,gt_queries))
        run_sqls_parallel(query_pairs, db_places=db_paths, num_cpus=args.num_cpus, meta_time_out=args.meta_time_out)
        exec_result = sort_results(exec_result)
        
        print('start calculate')
        simple_acc, moderate_acc, challenging_acc, acc, count_lists = \
            compute_acc_by_diff(exec_result,args.diff_json_path)
        score_lists = [simple_acc, moderate_acc, challenging_acc, acc]
        print_data(score_lists,count_lists)
        print('===========================================================================================')
        print("Finished evaluation")
        
    finally:
        # Clean up temporary files
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
    