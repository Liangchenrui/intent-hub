import os
import json
import pandas as pd
import random
from pathlib import Path
from typing import List, Dict, Any

# 配置
SCRIPT_DIR = Path(__file__).parent
DATASETS = ["BANKING77", "HWU64"]
RAW_DATA_ROOT = SCRIPT_DIR / "raw_data"
PROCESSED_DATA_ROOT = SCRIPT_DIR / "processed_data"

def load_raw_data(dataset: str, split: str) -> pd.DataFrame:
    """加载原始数据 seq.in 和 label"""
    seq_path = RAW_DATA_ROOT / dataset / split / "seq.in"
    label_path = RAW_DATA_ROOT / dataset / split / "label"
    
    if not seq_path.exists() or not label_path.exists():
        print(f"警告: 找不到数据 {seq_path} 或 {label_path}")
        return pd.DataFrame()
    
    with open(seq_path, 'r', encoding='utf-8') as f:
        utterances = [line.strip() for line in f]
    
    with open(label_path, 'r', encoding='utf-8') as f:
        labels = [line.strip() for line in f]
    
    return pd.DataFrame({"utterance": utterances, "label": labels})

def save_for_intent_hub(df: pd.DataFrame, output_path: Path):
    """保存为 for_intent_hub 格式"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    grouped = df.groupby("label")
    data = []
    for i, (name, group) in enumerate(grouped):
        data.append({
            "id": i + 1,
            "name": name,
            "description": f"Intent for {name}",
            "utterances": group["utterance"].tolist(),
            "negative_samples": [],
            "score_threshold": 0.75,
            "negative_threshold": 0.95
        })
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def save_for_llm(test_df: pd.DataFrame, train_df: pd.DataFrame, output_dir: Path):
    """保存为 for_llm 格式: test.csv 和 few_shot.json"""
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 保存 test.csv
    test_df.to_csv(output_dir / "test.csv", index=False)
    
    # 生成 few_shot.json (每类 3 个样本)
    grouped = train_df.groupby("label")
    few_shot = []
    for name, group in grouped:
        samples = group.sample(n=min(3, len(group)), random_state=42)
        for _, row in samples.iterrows():
            few_shot.append({
                "utterance": row["utterance"],
                "label": row["label"]
            })
    
    with open(output_dir / "few_shot.json", 'w', encoding='utf-8') as f:
        json.dump(few_shot, f, indent=2, ensure_ascii=False)

def save_for_semantic_router(train_df: pd.DataFrame, test_df: pd.DataFrame, output_dir: Path):
    """保存为 for_semantic_router 格式"""
    train_dir = output_dir / "train"
    test_dir = output_dir / "test"
    train_dir.mkdir(parents=True, exist_ok=True)
    test_dir.mkdir(parents=True, exist_ok=True)
    
    # 生成 train/layer.json
    grouped = train_df.groupby("label")
    routes = []
    for name, group in grouped:
        routes.append({
            "name": name,
            "utterances": group["utterance"].tolist()
        })
    
    layer_config = {
        "encoder_type": "huggingface",
        "encoder_name": "Qwen/Qwen3-Embedding-0.6B",
        "routes": routes
    }
    
    with open(train_dir / "layer.json", 'w', encoding='utf-8') as f:
        json.dump(layer_config, f, indent=2, ensure_ascii=False)
    
    # 生成 test/utterances.txt 和 test/test_with_labels.csv
    with open(test_dir / "utterances.txt", 'w', encoding='utf-8') as f:
        for utt in test_df["utterance"]:
            f.write(f"{utt}\n")
    
    test_df.to_csv(test_dir / "test_with_labels.csv", index=False)

def process_dataset(dataset: str):
    print(f"正在处理数据集: {dataset}...")
    
    train_df = load_raw_data(dataset, "train")
    test_df = load_raw_data(dataset, "test")
    
    if train_df.empty or test_df.empty:
        print(f"跳过 {dataset}，因为数据不完整")
        return

    # 1. for_intent_hub
    save_for_intent_hub(train_df, PROCESSED_DATA_ROOT / dataset / "for_intent_hub" / "train.json")
    save_for_intent_hub(test_df, PROCESSED_DATA_ROOT / dataset / "for_intent_hub" / "test.json")
    
    # 2. for_llm
    save_for_llm(test_df, train_df, PROCESSED_DATA_ROOT / dataset / "for_llm")
    
    # 3. for_semantic_router
    save_for_semantic_router(train_df, test_df, PROCESSED_DATA_ROOT / dataset / "for_semantic_router")
    
    print(f"{dataset} 处理完成！")

def main():
    for dataset in DATASETS:
        process_dataset(dataset)

if __name__ == "__main__":
    main()
