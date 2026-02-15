"""
使用 Semantic Router 方法对三个数据集进行实验
精简版本：不区分ID和OOD，只采集accuracy和latency指标
"""
import os
import json
import pandas as pd
import time
from tqdm import tqdm
from datetime import datetime
from pathlib import Path
from sklearn.metrics import accuracy_score

from semantic_router.index.qdrant import QdrantIndex
from semantic_router.routers import SemanticRouter
from semantic_router.routers.base import RouterConfig
from semantic_router.encoders import AutoEncoder

# 配置参数
DATASETS = ["ECOMMERCE_CONFLICT"]
# DATASETS = ["BANKING77", "HWU64", "ECOMMERCE_CONFLICT"]
QDRANT_URL = "http://192.168.33.1:31853"
COLLECTION_NAME = f"exp_semantic_router_{DATASETS[0]}"
THRESHOLD_VALUE = 0.75  # 阈值

# 获取脚本所在目录
SCRIPT_DIR = Path(__file__).parent
EXP_DIR = SCRIPT_DIR.parent.parent
DATA_DIR = EXP_DIR / "data" / "processed_data"
MODEL_DIR = EXP_DIR / "model" / "BAAI_bge-m3"
RESULT_DIR = SCRIPT_DIR / "result"


def normalize_label(label: str) -> str:
    """标准化标签名称，统一转换为小写"""
    if label is None:
        return None
    return label.lower().strip()


def load_test_data(dataset_name: str) -> pd.DataFrame:
    """从JSON格式加载测试数据并转换为DataFrame"""
    test_json_path = DATA_DIR / dataset_name / "for_intent_hub" / "test.json"
    
    if not test_json_path.exists():
        raise FileNotFoundError(f"测试数据文件不存在: {test_json_path}")
    
    with open(test_json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # 转换为DataFrame格式
    rows = []
    for intent in data:
        intent_name = intent["name"]
        for utterance in intent["utterances"]:
            rows.append({
                "utterance": utterance,
                "label": intent_name
            })
    
    return pd.DataFrame(rows)


def evaluate(router: SemanticRouter, test_df: pd.DataFrame, route_names: list):
    """
    简化评估函数，只计算accuracy和latency
    不区分ID和OOD，所有样本都参与准确率计算
    """
    total = len(test_df)
    
    # 预计算向量嵌入（不计入耗时统计）
    print(f"正在预计算 {total} 个样本的向量嵌入...")
    utterances = test_df['utterance'].tolist()
    embeddings = []
    batch_size = 100
    
    for i in range(0, len(utterances), batch_size):
        batch = utterances[i : i + batch_size]
        if batch:
            batch_embeddings = router.encoder(batch)
            embeddings.extend(batch_embeddings)
    
    print("向量嵌入预计算完成。")
    
    # 存储真实标签和预测标签
    y_true = []
    y_pred = []
    details = []  # 存储每个样本的详细信息
    
    # 累计纯推理（识别）时间
    total_inference_time = 0.0
    
    print(f"开始评估，共 {total} 个测试样本...")
    
    # 使用 zip 同时遍历 dataframe 和 embeddings
    for (idx, row), vector in tqdm(zip(test_df.iterrows(), embeddings), total=total, desc="评估中"):
        utterance = row['utterance']
        true_label = row['label']  # 保留原始标签
        true_label_normalized = normalize_label(true_label)
        
        # 使用路由器进行分类
        try:
            # 仅统计识别阶段的时间（排除编码时间）
            t0 = time.time()
            result = router(text=utterance, vector=vector)
            t1 = time.time()
            latency = t1 - t0
            total_inference_time += latency
            
            if result is None:
                predicted_label = None
                predicted_label_normalized = "unknown"
            else:
                predicted_route_name = result.name if hasattr(result, 'name') else None
                predicted_label = predicted_route_name
                predicted_label_normalized = normalize_label(predicted_route_name) if predicted_route_name else "unknown"
            
            # 判断是否正确
            is_correct = (predicted_label_normalized == true_label_normalized)
            
            # 记录预测结果
            y_true.append(true_label_normalized)
            y_pred.append(predicted_label_normalized)
            
            # 记录详细信息
            details.append({
                "id": idx,
                "utterance": utterance,
                "true_label": true_label,
                "pred_label": predicted_label if predicted_label else "unknown",
                "latency": latency,
                "correct": is_correct
            })
            
        except Exception as e:
            print(f"处理样本时出错 (id={idx}): {e}")
            # 出错时视为预测失败
            y_true.append(true_label_normalized)
            y_pred.append("unknown")
            details.append({
                "id": idx,
                "utterance": utterance,
                "true_label": true_label,
                "pred_label": "unknown",
                "latency": 0.0,
                "correct": False
            })
            continue
    
    # 计算准确率
    accuracy = accuracy_score(y_true, y_pred)
    
    # 计算平均延迟（秒）
    avg_latency = (total_inference_time / total) if total > 0 else 0.0
    
    return {
        "total": total,
        "accuracy": accuracy,
        "avg_latency": avg_latency,
        "total_inference_time": total_inference_time,
        "y_true": y_true,
        "y_pred": y_pred,
        "details": details
    }


def run_experiment(dataset_name: str):
    """对单个数据集运行实验"""
    print("=" * 80)
    print(f"数据集: {dataset_name}")
    print("=" * 80)
    
    # 1. 加载路由配置
    train_json_path = DATA_DIR / dataset_name / "for_semantic_router" / "train" / "layer.json"
    
    if not train_json_path.exists():
        print(f"警告: 训练数据文件不存在: {train_json_path}")
        return None
    
    print("正在加载路由配置...")
    config = RouterConfig.from_file(str(train_json_path))
    
    # 2. 创建编码器（使用本地模型路径）
    model_path = str(MODEL_DIR)
    print(f"正在加载本地编码器模型: {model_path}")
    
    # 检查模型路径是否存在
    if not os.path.exists(model_path):
        print(f"警告: 模型路径不存在: {model_path}")
        print("将使用模型名称而不是路径")
        model_path = "BAAI/bge-m3"
    
    encoder = AutoEncoder(type=config.encoder_type, name=model_path).model
    
    # 3. 创建Qdrant索引
    print("正在初始化 Qdrant 索引...")
    # 获取编码器维度
    test_embedding = encoder(["test"])
    encoder_dimensions = len(test_embedding[0])
    
    index = QdrantIndex(
        location=None,
        url=QDRANT_URL,
        api_key=None,  # 如果不需要API key
        collection_name=f"{COLLECTION_NAME}_{dataset_name.lower()}",
        dimensions=encoder_dimensions
    )
    
    # 4. 创建路由器
    print("正在创建路由器...")
    router = SemanticRouter(
        encoder=encoder,
        routes=config.routes,
        index=index,
        auto_sync="local",  # 启用自动同步，将本地路由数据添加到远程索引
    )
    
    # 设置阈值
    router.set_threshold(THRESHOLD_VALUE)
    
    print(f"编码器类型: {router.encoder.type}")
    print(f"编码器名称: {router.encoder.name}")
    print(f"路由数量: {len(router.routes)}")
    print("路由器初始化完成！\n")
    
    # 获取所有路由名称
    route_names = [route.name for route in router.routes]
    
    # 5. 加载测试数据
    print("正在加载测试数据...")
    test_df = load_test_data(dataset_name)
    print(f"测试样本数: {len(test_df)}")
    print(f"唯一标签数: {test_df['label'].nunique()}\n")
    
    # 6. 评估
    print("=" * 80)
    print("开始评估")
    print("=" * 80)
    
    results = evaluate(router, test_df, route_names)
    
    print("\n评估结果:")
    print(f"  总样本数: {results['total']}")
    print(f"  准确率 (Accuracy): {results['accuracy']:.4f} ({results['accuracy']*100:.2f}%)")
    print(f"  平均延迟 (Average Latency): {results['avg_latency']:.4f} s")
    print(f"  总推理时间: {results['total_inference_time']:.2f} 秒\n")
    
    # 保存单个数据集的结果
    save_single_result(dataset_name, router, results)
    
    return {
        "dataset": dataset_name,
        "router_info": {
            "encoder_type": router.encoder.type,
            "encoder_name": router.encoder.name,
            "route_count": len(router.routes)
        },
        "results": results
    }


def save_single_result(dataset_name: str, router: SemanticRouter, results: dict):
    """保存单个数据集的实验结果到文件（参考LLM脚本格式）"""
    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    
    # 准备保存的数据（参考LLM格式）
    save_data = {
        "config": {
            "model": f"{router.encoder.type}/{router.encoder.name}",
            "dataset": dataset_name,
            "encoder_type": router.encoder.type,
            "encoder_name": router.encoder.name,
            "route_count": len(router.routes),
            "threshold": THRESHOLD_VALUE,
            "qdrant_url": QDRANT_URL,
            "collection_name": f"{COLLECTION_NAME}_{dataset_name.lower()}"
        },
        "metrics": {
            "accuracy": results['accuracy'],
            "avg_latency": results['avg_latency'],
            "total_samples": results['total'],
            "correct_samples": sum(1 for d in results['details'] if d['correct'])
        },
        "details": results['details']
    }
    
    # 保存为JSON格式（文件名包含数据集名称）
    json_file = RESULT_DIR / f"test_results_{dataset_name}_{timestamp}.json"
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(save_data, f, indent=2, ensure_ascii=False)
    
    # 保存为文本报告（文件名包含数据集名称）
    report_file = RESULT_DIR / f"test_report_{dataset_name}_{timestamp}.txt"
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write("=" * 50 + "\n")
        f.write(f"SEMANTIC ROUTER INTENT CLASSIFICATION REPORT\n")
        f.write("=" * 50 + "\n")
        f.write(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Model: {router.encoder.type}/{router.encoder.name}\n")
        f.write(f"Dataset: {dataset_name}\n")
        f.write(f"Route Count: {len(router.routes)}\n")
        f.write(f"Threshold: {THRESHOLD_VALUE}\n")
        f.write("-" * 30 + "\n")
        f.write(f"Accuracy: {results['accuracy']:.2%}\n")
        f.write(f"Average Latency: {results['avg_latency']:.4f}s\n")
        f.write(f"Total Samples: {results['total']}\n")
        f.write("=" * 50 + "\n")
    
    print(f"\nResults saved to:\n- {json_file}\n- {report_file}")


def save_results(all_results: list):
    """保存所有实验结果到汇总文件（可选）"""
    if not all_results:
        return
    
    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    
    # 保存为JSON格式（汇总）
    json_path = RESULT_DIR / f"semantic_router_summary_{timestamp}.json"
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)
    print(f"\n汇总结果已保存为 JSON: {json_path}")


def main():
    """主函数：对三个数据集运行实验"""
    print("=" * 80)
    print("Semantic Router 实验")
    print("=" * 80)
    print(f"数据集列表: {DATASETS}")
    print(f"Qdrant URL: {QDRANT_URL}")
    print(f"集合名称: {COLLECTION_NAME}")
    print(f"阈值: {THRESHOLD_VALUE}")
    print(f"模型路径: {MODEL_DIR}")
    print("=" * 80 + "\n")
    
    all_results = []
    
    for dataset_name in DATASETS:
        try:
            result = run_experiment(dataset_name)
            if result:
                all_results.append(result)
        except Exception as e:
            print(f"数据集 {dataset_name} 实验失败: {e}")
            import traceback
            traceback.print_exc()
            continue
    
    # 保存汇总结果（可选）
    if all_results:
        save_results(all_results)
        print("\n" + "=" * 80)
        print("所有实验完成！")
        print("=" * 80)
        print(f"每个数据集的结果已单独保存到: {RESULT_DIR}")
    else:
        print("\n警告: 没有成功完成的实验")


if __name__ == "__main__":
    main()
