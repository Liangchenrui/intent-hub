import os
import json
import pandas as pd
from pathlib import Path
from typing import List, Dict, Any

# 配置
SCRIPT_DIR = Path(__file__).parent
PROCESSED_DATA_ROOT = SCRIPT_DIR / "processed_data"
ECOMMERCE_DIR = PROCESSED_DATA_ROOT / "ECOMMERCE_CONFLICT"

def load_intent_hub_data(split: str) -> List[Dict]:
    """从 for_intent_hub 格式加载数据"""
    file_path = ECOMMERCE_DIR / "for_intent_hub" / f"{split}.json"
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def convert_to_dataframe(data: List[Dict]) -> pd.DataFrame:
    """将 for_intent_hub 格式转换为 DataFrame"""
    rows = []
    for intent in data:
        name = intent["name"]
        for utterance in intent["utterances"]:
            rows.append({
                "utterance": utterance,
                "label": name
            })
    return pd.DataFrame(rows)

def save_for_intent_hub(df: pd.DataFrame, output_path: Path):
    """保存为 for_intent_hub 格式（已存在，但保留函数以保持一致性）"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    grouped = df.groupby("label")
    data = []
    for i, (name, group) in enumerate(grouped):
        data.append({
            "id": i + 1,
            "name": name,
            "description": f"Intent for {name}",
            "utterances": group["utterance"].tolist()
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

def process_ecommerce_conflict():
    """处理 ECOMMERCE_CONFLICT 数据集"""
    print("正在处理数据集: ECOMMERCE_CONFLICT...")
    
    # 从 for_intent_hub 格式加载数据
    train_data = load_intent_hub_data("train")
    test_data = load_intent_hub_data("test")
    
    # 转换为 DataFrame
    train_df = convert_to_dataframe(train_data)
    test_df = convert_to_dataframe(test_data)
    
    if train_df.empty or test_df.empty:
        print("警告: 数据为空")
        return
    
    print(f"训练集: {len(train_df)} 条样本, {train_df['label'].nunique()} 个意图")
    print(f"测试集: {len(test_df)} 条样本, {test_df['label'].nunique()} 个意图")
    
    # 1. for_intent_hub (已存在，跳过或重新生成以保持一致性)
    # save_for_intent_hub(train_df, ECOMMERCE_DIR / "for_intent_hub" / "train.json")
    # save_for_intent_hub(test_df, ECOMMERCE_DIR / "for_intent_hub" / "test.json")
    print("✓ for_intent_hub 格式已存在，跳过")
    
    # 2. for_llm
    save_for_llm(test_df, train_df, ECOMMERCE_DIR / "for_llm")
    print("✓ for_llm 格式已生成")
    
    # 3. for_semantic_router
    save_for_semantic_router(train_df, test_df, ECOMMERCE_DIR / "for_semantic_router")
    print("✓ for_semantic_router 格式已生成")
    
    print("ECOMMERCE_CONFLICT 处理完成！")

if __name__ == "__main__":
    process_ecommerce_conflict()
