# BIRD Text2SQL Benchmark

## Developing a workflow

### Plain runs with Python

**Downloading / unzipping the data:** If you don't have a data.zip file in the project root, [download it from here](https://1drv.ms/u/c/0a2bf91af9c5e93d/ES4NjfHfw_BBjv5-75n4kSUBK8JIacAVo4BNKwXRBS6vlw?e=ZkDCJ5). Unzip the folder in the project root (so, at `bird-bench/data`).

**Look at the existing example workflow:** 
1. The code of the workflow is in `workflow/example.py`. It is a `predict` function that simply calls GPT-3.5 on each sample.
2. The predict function is called from `generate_answers.py`, which TODO.
3. You can run the workflow like so:

```
python generate_answers.py --num_samples 5
```

You can then evaluate the accuracy of those answers like so:

```
python evaluate.py --num_samples 5
```

If this works, you should see 5% accuracy as in the following output:

```
                     simple               moderate             challenging          total               
count                3                    4                    3                    10                  
======================================    ACCURACY    =====================================
accuracy             0.00                 0.00                 0.00                 0.00                
===========================================================================================
```

You can inspect your predictions at `prediction/predictions.json` or inside the tool.

### Runs using agent-copilot


