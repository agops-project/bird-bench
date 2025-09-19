# BIRD Text2SQL Benchmark

## Installation

**Downloading / unzipping the data:** If you don't have a data.zip file in the project root, [download it from here](https://1drv.ms/u/c/0a2bf91af9c5e93d/ES4NjfHfw_BBjv5-75n4kSUBK8JIacAVo4BNKwXRBS6vlw?e=ZkDCJ5). Unzip the folder in the project root (so, at `bird-bench/data`).

**Installing our tool:** In the VS Code marketplace, search for "agops agent copilot" and install the first extension: 

<img src="media_for_readme/marketplace.png" alt="VS Code Marketplace" width="300">

Then run `pip install agops-bird`. 

**Setting up API keys:** Text me at ferdi [dot] kossmann [at] gmail [dot] com. I can provide you with the needed API keys. 

## Using our tool

Our tool will show you runs of the evaluation set (Sample 0, Sample 1, ...). Correct samples will be shown with a green bar, incorrect ones with a red bar. You can click on samples and inspect the inputs and outputs of LLM calls and calls to the database and even modify them to see what would have happened if the input or output to/from an LLM were different.

If you have any questions, please reach out to me at `ferdi [dot] kossmann [at] gmail [dot] com`.

## Developing a workflow

> [!CAUTION]
> In the light of this user study, you may only invoke LLMs using the OpenAI `chat.completions.create` API call (also see `workflow/example.py`):
>
> ```
> from openai import OpenAI
> client = OpenAI()
> response = client.chat.completions.create(...)
> ```
> If you want to make a call to the database, you have to use the `utils.call_db(sql_str)` function (no need to create a connections or cursor). The function will return the same object as an actual call to the SQL DB would. 


### Run workflow and evaluation

When running our tool, the only difference is that you type `develop script.py` instead of `python script.py`. Practically, this means the following:

When you want to evaluate several samples, run `python run_and_evaluate.py --num_samples X`, which will run the first `X` samples of the benchmark. `run_and_evaluate.py` spawns the workflow runs using the `develop` command, so the actual runs run with our tool.

If you want to evaluate and run an individual sample `X`, do `develop workflow/main.py --sample_id X`.

**Look at the existing example workflow:** 
1. The code of the workflow is in `workflow/example.py`. It simply calls gpt-3.5 with the input.
2. The worflow is called from `workflow/main.py`. We recommend to leave much of the logic in `workflow/main.py` the same and use it to call your workflow.

**Understanding correctness**: In the list view at the left in the UI, samples that failed the benchmark test are shown through a red bar. The ones that passed through a green bar.