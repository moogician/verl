"""
Preprocess dataset for CWEval
"""

import re
import os
from datasets import Dataset, load_dataset
from random import randint, seed, choice
from typing import List, Tuple
from tqdm import tqdm
from verl.utils.hdfs_io import copy, makedirs
import argparse

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--cweval', default='/home/tony/resources/CWEval')
    parser.add_argument('--test_ratio', type=int, default=0.1)
    parser.add_argument('--ppt', type=str, default='direct')
    parser.add_argument('--local_dir', type=str, default='./dataset/')

    args = parser.parse_args()
    assert args.ppt in ['direct', 'cwe', 'secure']

    data_source = 'cweval'
    raw_dataset: Dataset = load_dataset('moogician/SecCodeGen', split='train') # type: ignore

    TEST_SIZE = int(len(raw_dataset) * args.test_ratio)
    TRAIN_SIZE = len(raw_dataset) - TEST_SIZE

    #save_path = tmp_dir / "generated_0" / ground_truth['file_path']
    # WARNING: the file_path originally looks like this
    #"benchmark/lang/c/cwe_119_0_c_task.c"
    # remember to remove the "benchmark/" prefix for RL to work properly

    #assert len(raw_dataset) > TRAIN_SIZE + TEST_SIZE
    train_dataset = raw_dataset.select(range(TRAIN_SIZE))
    test_dataset = raw_dataset.select(range(TRAIN_SIZE, TRAIN_SIZE + TEST_SIZE))

    def make_map_fn(split):
        ppt = args.ppt
        def process_fn(example, idx):
            question = example[ppt]
            solution = {
                "file_path": example['task_file_path'][10:]
            }
            data = {
                "data_source": data_source,
                "prompt": [{
                    "role": "user",
                    "content": question,
                }],
                "ability": "alignment",
                "reward_model": {
                    "style": "rule",
                    "ground_truth": solution
                },
                "extra_info": {
                    'split': split,
                    'index': idx,
                }
            }
            return data
        return process_fn
    
    train_dataset = train_dataset.map(function=make_map_fn('train'), with_indices=True)
    test_dataset = test_dataset.map(function=make_map_fn('test'), with_indices=True)

    local_dir = args.local_dir

    train_dataset.to_parquet(os.path.join(local_dir, 'train.parquet'))
    test_dataset.to_parquet(os.path.join(local_dir, 'test.parquet'))
