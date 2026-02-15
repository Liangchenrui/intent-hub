"""
使用 Intent Hub 方法对数据集进行实验
采集指标：accuracy 和 latency
参考代码：baseline/LLM/llm.py 和 baseline/semantic_router/sr.py
"""
import os
import json
import random
import time
import shutil
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from datetime import datetime
from tqdm import tqdm

# 设置环境变量（在导入intent-hub之前）
import sys

# 获取脚本所在目录
SCRIPT_DIR = Path(__file__).parent
EXP_DIR = SCRIPT_DIR.parent
# 将 intent-hub-backend 目录添加到 Python 路径，以便导入 intent_hub 模块
INTENT_HUB_BACKEND_DIR = EXP_DIR.parent / "intent-hub-backend"
if INTENT_HUB_BACKEND_DIR.exists() and str(INTENT_HUB_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(INTENT_HUB_BACKEND_DIR))

# 配置参数
DATASETS = ["ECOMMERCE_CONFLICT_SOLVED"]
# DATASETS = ["BANKING77", "HWU64", "ECOMMERCE_CONFLICT"]
SAMPLING_RATE = 1  # 采样率，可以根据需要调整
QDRANT_URL = os.getenv("QDRANT_URL", "http://192.168.33.1:31853")
QDRANT_COLLECTION_PREFIX = f"intent_hub_exp_{DATASETS[0]}"
MODEL_DIR = EXP_DIR / "model" / "BAAI_bge-m3"
DATA_DIR = EXP_DIR / "data" / "processed_data"
RESULT_DIR = SCRIPT_DIR / "result"
RESULT_DIR.mkdir(parents=True, exist_ok=True)

# 是否启用详细的时间统计（显示正语料和负语料搜索耗时）
ENABLE_DETAILED_TIMING = os.getenv("INTENT_HUB_ENABLE_DETAILED_TIMING", "True").lower() in ("true", "1", "yes")

# 临时路由配置文件目录
TEMP_CONFIG_DIR = SCRIPT_DIR / "temp_configs"
TEMP_CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def normalize_label(label: str) -> str:
    """标准化标签名称，统一转换为小写"""
    if label is None:
        return None
    return label.lower().strip()


def load_data(file_path: Path) -> List[Dict]:
    """加载JSON格式的数据"""
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def flatten_data(data: List[Dict]) -> List[Tuple[str, str]]:
    """将数据展平为(utterance, label)列表"""
    flattened = []
    for item in data:
        intent_name = item["name"]
        for utterance in item["utterances"]:
            flattened.append((utterance, intent_name))
    return flattened


def prepare_routes_config(train_data: List[Dict], config_path: Path):
    """准备路由配置文件"""
    # 训练数据已经是intent-hub需要的格式，直接保存
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(train_data, f, indent=2, ensure_ascii=False)
    print(f"路由配置文件已保存到: {config_path}")


def setup_environment(dataset_name: str, routes_config_path: Path):
    """设置环境变量"""
    # 为每个数据集使用不同的collection名称
    collection_name = f"{QDRANT_COLLECTION_PREFIX}_{dataset_name.lower()}"
    
    # 设置环境变量
    os.environ["QDRANT_URL"] = QDRANT_URL
    os.environ["QDRANT_COLLECTION"] = collection_name
    os.environ["ROUTES_CONFIG_PATH"] = str(routes_config_path)
    os.environ["INTENT_HUB_PREDICT_TOP_K"] = "5"
    os.environ["INTENT_HUB_ENABLE_NEGATIVE_SEARCH"] = "True"
    
    # 设置编码器模型路径（使用本地模型）
    model_path = str(MODEL_DIR)
    if os.path.exists(model_path):
        # 如果本地模型路径存在，使用本地路径
        # 注意：QwenEmbeddingEncoder 会将模型名称转换为目录名
        # 所以我们需要将模型名称设置为目录名，并设置 local_model_dir 为父目录
        model_name = MODEL_DIR.name  # "BAAI_bge-m3"
        os.environ["EMBEDDING_MODEL_NAME"] = model_name
        # 设置本地模型目录为模型所在目录的父目录
        os.environ["EMBEDDING_LOCAL_MODEL_DIR"] = str(MODEL_DIR.parent)
        print(f"使用本地编码器模型: {model_path}")
    else:
        print(f"警告: 本地模型路径不存在: {model_path}")
        print("将使用默认模型配置")
        # 如果本地模型不存在，使用默认配置
        if "EMBEDDING_MODEL_NAME" not in os.environ:
            os.environ["EMBEDDING_MODEL_NAME"] = "BAAI/bge-m3"
    
    # 设置其他必要的环境变量（使用默认值或从环境获取）
    if "HUGGINGFACE_ACCESS_TOKEN" not in os.environ:
        # 如果需要使用本地模型，可以设置这些
        pass
    
    print(f"环境变量已设置:")
    print(f"  QDRANT_URL: {QDRANT_URL}")
    print(f"  QDRANT_COLLECTION: {collection_name}")
    print(f"  ROUTES_CONFIG_PATH: {routes_config_path}")
    print(f"  EMBEDDING_MODEL_NAME: {os.environ.get('EMBEDDING_MODEL_NAME', '未设置')}")
    if "EMBEDDING_LOCAL_MODEL_DIR" in os.environ:
        print(f"  EMBEDDING_LOCAL_MODEL_DIR: {os.environ.get('EMBEDDING_LOCAL_MODEL_DIR')}")


def sync_collection_data(dataset_name: str):
    """
    检查并同步向量数据库collection
    如果collection不为空，则清空并同步所有数据
    """
    # 延迟导入，确保环境变量已设置
    from intent_hub.core.components import get_component_manager
    from intent_hub.services.sync_service import SyncService
    from intent_hub.config import Config
    
    # 验证配置文件是否存在且非空（直接从环境变量读取，因为Config类可能在环境变量设置前已导入）
    config_path = os.getenv("ROUTES_CONFIG_PATH")
    if not config_path:
        print(f"错误: 环境变量 ROUTES_CONFIG_PATH 未设置")
        return
    
    if not os.path.exists(config_path):
        print(f"错误: 路由配置文件不存在: {config_path}")
        return
    
    # 检查文件是否为空
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config_data = json.load(f)
            if not config_data or len(config_data) == 0:
                print(f"错误: 路由配置文件为空: {config_path}")
                return
            print(f"验证配置文件: {config_path}，包含 {len(config_data)} 个路由")
    except Exception as e:
        print(f"错误: 无法读取路由配置文件 {config_path}: {e}")
        return
    
    # 获取组件管理器并初始化（跳过自动同步，统一使用 sync_service.reindex()）
    print("正在初始化Intent Hub组件...")
    component_manager = get_component_manager()
    # 跳过自动同步，因为我们要统一使用 sync_service.reindex() 来同步数据
    # 这样可以确保数据完整性（包括正例和负例向量）
    component_manager.init_components(skip_auto_sync=True)
    
    # 确保路由管理器重新加载配置文件（因为配置文件可能在路由管理器初始化后才创建）
    route_manager = component_manager.route_manager
    print("正在重新加载路由配置...")
    route_manager.reload()
    
    # 验证路由配置是否已加载
    routes = route_manager.get_all_routes()
    if len(routes) == 0:
        print(f"警告: 路由配置为空，请检查配置文件: {route_manager.config_path}")
        print(f"配置文件路径: {config_path}")
        return
    
    print(f"已加载 {len(routes)} 个路由配置")
    
    # 检查collection是否有数据
    qdrant_client = component_manager.qdrant_client
    has_existing_data = qdrant_client.has_data()
    
    if has_existing_data:
        print(f"检测到collection '{qdrant_client.collection_name}' 中已有数据，将清空并重新同步...")
    else:
        print(f"collection '{qdrant_client.collection_name}' 为空，开始同步数据...")
    
    # 统一使用同步服务执行全量重建（force_full=True 会清空并重新同步所有数据）
    # 这样可以确保数据完整性（包括正例和负例向量），避免 init_components() 的自动同步只处理正例向量
    sync_service = SyncService(component_manager)
    sync_result = sync_service.reindex(force_full=True, skip_diagnostics=True)
    print(f"数据同步完成:")
    print(f"  路由数: {sync_result.get('routes_count', 0)}")
    print(f"  正例向量点数: {sync_result.get('total_points', 0)}")
    print(f"  负例向量点数: {sync_result.get('total_negative_points', 0)}")
    print()


def evaluate_intent_hub(test_samples: List[Tuple[str, str]], dataset_name: str):
    """
    使用Intent Hub进行评估
    返回accuracy和latency指标
    """
    # 延迟导入，确保环境变量已设置
    from intent_hub.core.components import get_component_manager
    from intent_hub.services.prediction_service import PredictionService
    from intent_hub.utils.logger import logger as intent_hub_logger
    
    # 获取组件管理器并初始化（复用已初始化的组件，避免重复同步）
    print("正在初始化Intent Hub组件...")
    component_manager = get_component_manager()
    # 如果组件已初始化，直接使用；否则初始化但不自动同步（因为 sync_collection_data 已经同步过了）
    # 这样可以避免重复同步向量数据库
    if not component_manager.is_ready():
        component_manager.init_components(skip_auto_sync=True)
    else:
        # 组件已初始化，确保路由管理器重新加载配置（如果需要）
        component_manager.route_manager.reload()

    # 基准测试场景：默认把 intent-hub 的日志压到 WARNING，避免 INFO 日志在循环中成为噪声开销
    # 如需更细粒度分段耗时，请设置：INTENT_HUB_PROFILE_PREDICT=true 并将日志级别调回 DEBUG
    try:
        import logging

        intent_hub_logger.setLevel(logging.WARNING)
    except Exception:
        pass
    
    # 创建预测服务
    prediction_service = PredictionService(component_manager)
    encoder = component_manager.encoder
    
    print(f"开始评估，共 {len(test_samples)} 个测试样本...")
    
    # 存储结果
    y_true = []
    y_pred = []
    details = []
    total_inference_latency = 0.0
    total_negative_search_time = 0.0
    total_positive_search_time = 0.0

    # 预计算向量嵌入（用于和 semantic-router 的 latency 口径对齐：排除 embedding）
    utterances = [u for (u, _) in test_samples]
    print(f"正在预计算 {len(utterances)} 个样本的向量嵌入（不计入 no-embed latency）...")
    vectors = encoder.encode(utterances)
    print("向量嵌入预计算完成。")
    
    # 遍历测试样本
    for i, ((utterance, true_label), vector) in enumerate(
        tqdm(list(zip(test_samples, vectors)), desc="评估中")
    ):
        true_label_normalized = normalize_label(true_label)
        
        try:
            # 仅统计检索/过滤阶段（排除 embedding）——与 semantic-router 统计口径对齐
            if ENABLE_DETAILED_TIMING:
                # 使用 return_timing=True 获取详细的时间统计
                results, timing_info = prediction_service.predict_with_vector(
                    text=utterance, query_vector=vector, return_timing=True
                )
                latency = timing_info["total_time"]
                negative_search_time = timing_info["negative_search_time"]
                positive_search_time = timing_info["positive_search_time"]
                total_negative_search_time += negative_search_time
                total_positive_search_time += positive_search_time
            else:
                # 使用传统方式统计总延迟
                start_time = time.time()
                results = prediction_service.predict_with_vector(
                    text=utterance, query_vector=vector
                )
                latency = time.time() - start_time
                negative_search_time = None
                positive_search_time = None
            
            total_inference_latency += latency
            
            # 获取预测结果（取第一个匹配的路由，如果没有则使用默认路由）
            if results and len(results) > 0:
                pred_result = results[0]
                predicted_label = pred_result.name
                predicted_label_normalized = normalize_label(predicted_label)
            else:
                predicted_label = "none"
                predicted_label_normalized = "none"
            
            # 判断是否正确
            is_correct = (predicted_label_normalized == true_label_normalized)
            
            # 记录结果
            y_true.append(true_label_normalized)
            y_pred.append(predicted_label_normalized)
            detail = {
                "id": i,
                "utterance": utterance,
                "true_label": true_label,
                "pred_label": predicted_label,
                "latency": latency,
                "correct": is_correct,
                "score": results[0].score if results and len(results) > 0 and results[0].score else None
            }
            # 如果启用了详细时间统计，添加时间信息
            if ENABLE_DETAILED_TIMING:
                detail["negative_search_time"] = negative_search_time
                detail["positive_search_time"] = positive_search_time
            details.append(detail)
            
        except Exception as e:
            print(f"处理样本时出错 (id={i}): {e}")
            # 出错时视为预测失败
            y_true.append(true_label_normalized)
            y_pred.append("none")
            detail = {
                "id": i,
                "utterance": utterance,
                "true_label": true_label,
                "pred_label": "none",
                "latency": 0.0,
                "correct": False,
                "score": None
            }
            if ENABLE_DETAILED_TIMING:
                detail["negative_search_time"] = 0.0
                detail["positive_search_time"] = 0.0
            details.append(detail)
            continue
    
    # 计算准确率
    correct_count = sum(1 for d in details if d['correct'])
    accuracy = correct_count / len(test_samples) if len(test_samples) > 0 else 0.0
    
    # 计算平均延迟
    avg_latency = (
        total_inference_latency / len(test_samples) if len(test_samples) > 0 else 0.0
    )
    
    result = {
        "total": len(test_samples),
        "accuracy": accuracy,
        "avg_latency": avg_latency,
        "total_latency": total_inference_latency,
        "correct_samples": correct_count,
        "details": details
    }
    
    # 如果启用了详细时间统计，添加平均时间信息
    if ENABLE_DETAILED_TIMING:
        avg_negative_search_time = (
            total_negative_search_time / len(test_samples) if len(test_samples) > 0 else 0.0
        )
        avg_positive_search_time = (
            total_positive_search_time / len(test_samples) if len(test_samples) > 0 else 0.0
        )
        result["avg_negative_search_time"] = avg_negative_search_time
        result["avg_positive_search_time"] = avg_positive_search_time
        result["total_negative_search_time"] = total_negative_search_time
        result["total_positive_search_time"] = total_positive_search_time
    
    return result


def run_experiment(dataset_name: str):
    """对单个数据集运行实验"""
    print("=" * 80)
    print(f"数据集: {dataset_name}")
    print("=" * 80)
    
    # 1. 加载数据
    train_file = DATA_DIR / dataset_name / "for_intent_hub" / "train.json"
    test_file = DATA_DIR / dataset_name / "for_intent_hub" / "test.json"
    
    if not train_file.exists():
        print(f"警告: 训练数据文件不存在: {train_file}")
        return None
    
    if not test_file.exists():
        print(f"警告: 测试数据文件不存在: {test_file}")
        return None
    
    print("正在加载数据...")
    train_data = load_data(train_file)
    test_data = load_data(test_file)
    
    print(f"训练路由数: {len(train_data)}")
    print(f"测试意图数: {len(test_data)}")
    
    # 2. 准备路由配置文件
    routes_config_path = TEMP_CONFIG_DIR / f"routes_config_{dataset_name}.json"
    prepare_routes_config(train_data, routes_config_path)
    
    # 3. 设置环境变量
    setup_environment(dataset_name, routes_config_path)
    
    # 4. 检查并清空collection（如果非空），然后同步数据
    print("=" * 80)
    print("检查并同步向量数据库")
    print("=" * 80)
    sync_collection_data(dataset_name)
    
    # 5. 采样测试数据
    flattened_test = flatten_data(test_data)
    sample_size = max(1, int(len(flattened_test) * SAMPLING_RATE))
    test_samples = random.sample(flattened_test, sample_size)
    
    print(f"测试样本总数: {len(flattened_test)}, 采样数量: {sample_size}")
    
    # 6. 评估
    print("=" * 80)
    print("开始评估")
    print("=" * 80)
    
    results = evaluate_intent_hub(test_samples, dataset_name)
    
    print("\n评估结果:")
    print(f"  总样本数: {results['total']}")
    print(f"  准确率 (Accuracy): {results['accuracy']:.4f} ({results['accuracy']*100:.2f}%)")
    print(f"  平均延迟 (Average Latency): {results['avg_latency']:.4f} s")
    print(f"  总延迟时间: {results['total_latency']:.2f} 秒")
    if ENABLE_DETAILED_TIMING and 'avg_negative_search_time' in results:
        print(f"  平均负语料搜索耗时: {results['avg_negative_search_time']:.4f} s ({results['avg_negative_search_time']/results['avg_latency']*100:.2f}%)" if results['avg_latency'] > 0 else "  平均负语料搜索耗时: 0.0000 s")
        print(f"  平均正语料搜索耗时: {results['avg_positive_search_time']:.4f} s ({results['avg_positive_search_time']/results['avg_latency']*100:.2f}%)" if results['avg_latency'] > 0 else "  平均正语料搜索耗时: 0.0000 s")
    print()
    
    # 6. 保存结果
    save_single_result(dataset_name, results)
    
    return {
        "dataset": dataset_name,
        "results": results
    }


def save_single_result(dataset_name: str, results: dict):
    """保存单个数据集的实验结果到文件（参考LLM脚本格式）"""
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    
    # 提取错误样本
    error_samples = [d for d in results['details'] if not d['correct']]
    
    # 准备保存的数据（参考LLM格式）
    save_data = {
        "config": {
            "model": "intent-hub",
            "dataset": dataset_name,
            "sampling_rate": SAMPLING_RATE,
            "qdrant_url": QDRANT_URL,
            "collection_name": f"{QDRANT_COLLECTION_PREFIX}_{dataset_name.lower()}",
            "enable_detailed_timing": ENABLE_DETAILED_TIMING
        },
        "metrics": {
            "accuracy": results['accuracy'],
            "avg_latency": results['avg_latency'],
            "total_samples": results['total'],
            "correct_samples": results['correct_samples'],
            "error_samples_count": len(error_samples)
        },
        "details": results['details'],
        "error_samples": error_samples
    }
    
    # 如果启用了详细时间统计，添加到 metrics 中
    if ENABLE_DETAILED_TIMING and 'avg_negative_search_time' in results:
        save_data["metrics"]["avg_negative_search_time"] = results['avg_negative_search_time']
        save_data["metrics"]["avg_positive_search_time"] = results['avg_positive_search_time']
        save_data["metrics"]["total_negative_search_time"] = results['total_negative_search_time']
        save_data["metrics"]["total_positive_search_time"] = results['total_positive_search_time']
    
    # 保存为JSON格式
    json_file = RESULT_DIR / f"test_results_{dataset_name}_{timestamp}.json"
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(save_data, f, indent=2, ensure_ascii=False)
    
    # 保存为文本报告
    report_file = RESULT_DIR / f"test_report_{dataset_name}_{timestamp}.txt"
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write("=" * 50 + "\n")
        f.write(f"INTENT HUB INTENT CLASSIFICATION REPORT\n")
        f.write("=" * 50 + "\n")
        f.write(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Model: intent-hub\n")
        f.write(f"Dataset: {dataset_name}\n")
        f.write(f"Sampling Rate: {SAMPLING_RATE*100}%\n")
        f.write(f"Qdrant URL: {QDRANT_URL}\n")
        f.write("-" * 30 + "\n")
        f.write(f"Accuracy: {results['accuracy']:.2%}\n")
        f.write(f"Average Latency: {results['avg_latency']:.4f}s\n")
        if ENABLE_DETAILED_TIMING and 'avg_negative_search_time' in results:
            f.write(f"Average Negative Search Time: {results['avg_negative_search_time']:.4f}s")
            if results['avg_latency'] > 0:
                f.write(f" ({results['avg_negative_search_time']/results['avg_latency']*100:.2f}%)\n")
            else:
                f.write("\n")
            f.write(f"Average Positive Search Time: {results['avg_positive_search_time']:.4f}s")
            if results['avg_latency'] > 0:
                f.write(f" ({results['avg_positive_search_time']/results['avg_latency']*100:.2f}%)\n")
            else:
                f.write("\n")
        f.write(f"Total Samples: {results['total']}\n")
        f.write(f"Correct Samples: {results['correct_samples']}\n")
        f.write(f"Error Samples: {len(error_samples)}\n")
        f.write("=" * 50 + "\n")
        
        # 添加错误样本详情
        if error_samples:
            f.write("\n" + "=" * 50 + "\n")
            f.write("ERROR SAMPLES (判断错误的样本)\n")
            f.write("=" * 50 + "\n")
            for idx, error in enumerate(error_samples, 1):
                f.write(f"\n[{idx}] 样本 ID: {error['id']}\n")
                f.write(f"    句子: {error['utterance']}\n")
                f.write(f"    正确标签: {error['true_label']}\n")
                f.write(f"    预测标签: {error['pred_label']}\n")
                if error.get('score') is not None:
                    f.write(f"    预测分数: {error['score']:.4f}\n")
                f.write(f"    延迟: {error['latency']:.4f}s\n")
            f.write("\n" + "=" * 50 + "\n")
        else:
            f.write("\n没有判断错误的样本。\n")
    
    print(f"\n结果已保存到:\n- {json_file}\n- {report_file}")
    if error_samples:
        print(f"共 {len(error_samples)} 个判断错误的样本，详情已记录在报告中。")


def save_results(all_results: list):
    """保存所有实验结果到汇总文件（可选）"""
    if not all_results:
        return
    
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    
    # 保存为JSON格式（汇总）
    json_path = RESULT_DIR / f"intent_hub_summary_{timestamp}.json"
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)
    print(f"\n汇总结果已保存为 JSON: {json_path}")


def cleanup_temp_configs():
    """清理临时配置文件"""
    if TEMP_CONFIG_DIR.exists():
        try:
            shutil.rmtree(TEMP_CONFIG_DIR)
            print(f"已清理临时配置文件目录: {TEMP_CONFIG_DIR}")
        except Exception as e:
            print(f"清理临时配置文件失败: {e}")


def main():
    """主函数：对所有数据集运行实验"""
    print("=" * 80)
    print("Intent Hub 实验")
    print("=" * 80)
    print(f"数据集列表: {DATASETS}")
    print(f"采样率: {SAMPLING_RATE*100}%")
    print(f"Qdrant URL: {QDRANT_URL}")
    print("=" * 80 + "\n")
    
    all_results = []
    
    try:
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
    finally:
        # 清理临时配置文件
        cleanup_temp_configs()
    
    # 保存汇总结果
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
