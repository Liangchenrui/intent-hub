import json
import random
import time
import os
from openai import OpenAI
from typing import List, Dict, Tuple, Optional
from datetime import datetime
from pathlib import Path

# ==========================================
# 配置参数 (统一硬编码管理)
# ==========================================

# DeepSeek 配置
DEEPSEEK_CONFIG = {
    "api_key": "sk-ed303aa95b28493b97fcedaf06265b81",
    "base_url": "https://api.deepseek.com",
    "model": "deepseek-chat"
}

# 当前生效配置
current_config = DEEPSEEK_CONFIG

LLM_API_KEY = current_config["api_key"]
LLM_BASE_URL = current_config["base_url"]
LLM_MODEL = current_config["model"]
LLM_TEMPERATURE = 0.0  # 测试准确率建议设为 0.0

DATASET_NAME = "HWU64"
# DATASET_NAME = "BANKING77"
# DATASET_NAME = "ECOMMERCE_CONFLICT"
DATA_DIR = f"/root/lcr/intent-hub/exp/data/processed_data/{DATASET_NAME}/for_intent_hub"
TRAIN_FILE = os.path.join(DATA_DIR, "train.json")
TEST_FILE = os.path.join(DATA_DIR, "test.json")

SAMPLING_RATE = 0.1  # 采样率
FEW_SHOT_COUNT = 3   # 3-shot

# ==========================================
# 工具函数
# ==========================================
client = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)


def load_data(file_path: str) -> List[Dict]:
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def flatten_data(data: List[Dict]) -> List[Tuple[str, str]]:
    flattened = []
    for item in data:
        intent_name = item["name"]
        for utterance in item["utterances"]:
            flattened.append((utterance, intent_name))
    return flattened


def build_prompt(utterance: str, intent_names: List[str], few_shot_examples: List[Tuple[str, str]]) -> str:
    """构建分类 Prompt"""
    intent_list = ", ".join(intent_names)

    few_shot_text = ""
    for i, (utt, label) in enumerate(few_shot_examples, 1):
        few_shot_text += f"Example {i}:\nUtterance: \"{utt}\"\nIntent: {label}\n\n"

    prompt = f"""You are an intent classification assistant. 
Identify the correct intent for the user utterance from the list below:

Possible Intents: {intent_list}

{few_shot_text}Now, classify the following:
Utterance: "{utterance}"
Intent:"""
    return prompt


def parse_response(response: str, intent_names: List[str]) -> str:
    """解析并清洗模型返回的标签"""
    clean_resp = response.strip().replace(
        '"', '').replace("'", "").split('\n')[0]
    # 尝试匹配已知意图列表
    for name in intent_names:
        if name.lower() == clean_resp.lower():
            return name
    return clean_resp


def save_results(results: Dict):
    """持久化测试结果到同路径下"""
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    base_path = Path(__file__).parent

    # 保存 JSON
    json_file = base_path / f"test_results_{timestamp}.json"
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    # 保存文本报告
    report_file = base_path / f"test_report_{timestamp}.txt"
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write("="*50 + "\n")
        f.write(f"LLM INTENT CLASSIFICATION REPORT\n")
        f.write("="*50 + "\n")
        f.write(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Model: {LLM_MODEL}\n")
        f.write(f"Dataset: {DATASET_NAME}\n")
        f.write(f"Sampling Rate: {SAMPLING_RATE*100}%\n")
        f.write(f"Few-shot: {FEW_SHOT_COUNT}\n")
        f.write("-" * 30 + "\n")
        f.write(f"Accuracy: {results['metrics']['accuracy']:.2%}\n")
        f.write("-" * 30 + "\n")
        f.write("Latency Metrics:\n")
        avg_latency_value = results['metrics']['avg_latency']
        avg_model_time_value = results['metrics']['avg_model_processing_time']

        f.write(f"  Average Total Latency: {avg_latency_value:.4f}s\n")
        f.write(f"    - 说明: 包含网络延迟的总延迟时间\n")
        f.write(f"    - 统计方式: 从请求发送开始到完整响应接收完成的总时间\n")
        f.write(f"    - 包含: 网络传输时间、服务器处理时间、响应传输时间\n")
        f.write(f"\n")
        f.write(
            f"  Average Model Processing Time: {avg_model_time_value:.4f}s\n")
        f.write(f"    - 说明: 排除网络延迟的模型处理时间\n")
        f.write(f"    - 统计方式: 使用流式响应测量，优先从响应头获取服务器处理时间，\n")
        f.write(f"               否则通过TTFT(Time to First Token)估算网络延迟后计算\n")
        f.write(f"    - 包含: prompt处理时间、token生成时间\n")
        f.write(f"    - 排除: 网络传输时间\n")
        f.write("-" * 30 + "\n")
        f.write(f"Total Samples: {results['metrics']['total_samples']}\n")
        f.write("="*50 + "\n")

    print(f"\nResults saved to:\n- {json_file}\n- {report_file}")


def get_model_processing_time_streaming(client, prompt: str, request_start_time: float) -> Tuple[str, float, float, Optional[float]]:
    """
    使用流式响应来精确测量模型处理时间（排除网络延迟）
    返回: (响应内容, 总延迟, 模型处理时间, 服务器处理时间(如果可用))
    """
    first_token_time = None
    last_token_time = None
    content_parts = []
    server_processing_ms = None

    try:
        # 使用流式响应
        stream = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=LLM_TEMPERATURE,
            max_tokens=20,
            stream=True
        )

        for chunk in stream:
            # 记录第一个 token 到达时间（Time to First Token）
            if first_token_time is None and chunk.choices[0].delta.content:
                first_token_time = time.time()
                # 尝试从响应头获取服务器处理时间
                try:
                    if hasattr(chunk, 'response') and hasattr(chunk.response, 'headers'):
                        headers = chunk.response.headers
                        for header_name in ['openai-processing-ms', 'x-processing-ms', 'processing-ms']:
                            if header_name in headers:
                                server_processing_ms = float(
                                    headers[header_name]) / 1000.0
                                break
                except Exception:
                    pass

            # 收集内容
            if chunk.choices[0].delta.content:
                content_parts.append(chunk.choices[0].delta.content)
                last_token_time = time.time()

        total_latency = time.time() - request_start_time
        raw_content = "".join(content_parts)

        # 计算模型处理时间
        if server_processing_ms is not None:
            # 方法1（最准确）：如果从响应头获取到了服务器处理时间，直接使用
            model_processing_time = server_processing_ms
        elif first_token_time is not None and last_token_time is not None:
            # 方法2：使用流式响应测量
            # 模型处理时间 = 从请求开始到最后一个 token 的时间 - 网络延迟估算
            # 网络延迟主要发生在：请求发送 + 第一个 token 返回
            # 估算：从请求开始到第一个 token 的时间中，网络延迟约占 50%
            ttft = first_token_time - request_start_time
            estimated_network_delay = ttft * 0.5  # 估算第一个 token 返回的网络延迟
            # 模型处理时间 = 总时间 - 网络延迟（请求发送 + 响应返回）
            # 更准确：从第一个 token 到最后一个 token 的时间 + prompt 处理时间（通过 TTFT 估算）
            token_generation_time = last_token_time - first_token_time
            prompt_processing_time = ttft - estimated_network_delay
            model_processing_time = prompt_processing_time + token_generation_time
        else:
            # 方法3（降级方案）：估算网络延迟（假设为总延迟的 15%）
            estimated_network_rtt = total_latency * 0.15
            model_processing_time = total_latency - estimated_network_rtt

        return raw_content, total_latency, model_processing_time, server_processing_ms

    except Exception as e:
        # 如果流式响应失败，降级到非流式
        print(f"Streaming failed, falling back to non-streaming: {e}")
        response = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=LLM_TEMPERATURE,
            max_tokens=20
        )
        total_latency = time.time() - request_start_time
        raw_content = response.choices[0].message.content

        # 尝试从响应头获取服务器处理时间
        try:
            if hasattr(response, 'response') and hasattr(response.response, 'headers'):
                headers = response.response.headers
                for header_name in ['openai-processing-ms', 'x-processing-ms', 'processing-ms']:
                    if header_name in headers:
                        server_processing_ms = float(
                            headers[header_name]) / 1000.0
                        break
        except Exception:
            pass

        if server_processing_ms is not None:
            model_processing_time = server_processing_ms
        else:
            # 估算网络延迟
            estimated_network_rtt = total_latency * 0.15
            model_processing_time = total_latency - estimated_network_rtt

        return raw_content, total_latency, model_processing_time, server_processing_ms


def main():
    print(f"Starting experiment on {DATASET_NAME} with {LLM_MODEL}...")

    # 1. 加载数据
    train_raw = load_data(TRAIN_FILE)
    test_raw = load_data(TEST_FILE)
    intent_names = [item["name"] for item in train_raw]

    # 2. 准备 Few-shot
    flattened_train = flatten_data(train_raw)
    few_shot_examples = random.sample(flattened_train, FEW_SHOT_COUNT)

    # 3. 采样测试集
    flattened_test = flatten_data(test_raw)
    sample_size = int(len(flattened_test) * SAMPLING_RATE)
    test_samples = random.sample(flattened_test, sample_size)

    print(
        f"Total Test Samples: {len(flattened_test)}, Processed Samples: {sample_size}")

    # 4. 执行测试
    results_detail = []
    correct_count = 0
    total_latency = 0
    total_model_time = 0  # 模型处理时间总和

    for i, (utterance, true_label) in enumerate(test_samples):
        prompt = build_prompt(utterance, intent_names, few_shot_examples)

        request_start_time = time.time()
        try:
            # 使用流式响应来精确测量模型处理时间
            raw_content, total_time, model_time, server_time = get_model_processing_time_streaming(
                client, prompt, request_start_time
            )

            pred_label = parse_response(raw_content, intent_names)

            is_correct = (pred_label.lower() == true_label.lower())
            if is_correct:
                correct_count += 1

            total_latency += total_time
            total_model_time += model_time

            results_detail.append({
                "id": i,
                "utterance": utterance,
                "true_label": true_label,
                "pred_label": pred_label,
                "latency": total_time,  # 总延迟（包含网络）
                "model_processing_time": model_time,  # 模型处理时间（排除网络）
                "server_processing_time": server_time,  # 服务器处理时间（如果可用）
                "correct": is_correct
            })

            if (i + 1) % 10 == 0:
                avg_total = total_latency / (i + 1)
                avg_model = total_model_time / (i + 1)
                print(f"[{i+1}/{sample_size}] Accuracy: {correct_count/(i+1):.2%}, "
                      f"Total Latency (含网络): {avg_total:.2f}s, Model Time (排除网络): {avg_model:.2f}s")

        except Exception as e:
            print(f"Error at index {i}: {e}")
            continue

    # 5. 汇总结果
    final_results = {
        "config": {
            "model": LLM_MODEL,
            "dataset": DATASET_NAME,
            "sampling_rate": SAMPLING_RATE,
            "few_shot": FEW_SHOT_COUNT,
            "temperature": LLM_TEMPERATURE,
            "latency_measurement": {
                "avg_latency": {
                    "description": "平均总延迟（包含网络延迟）",
                    "measurement_method": "从请求发送开始到完整响应接收完成的总时间",
                    "includes": ["网络传输时间", "服务器处理时间", "响应传输时间"],
                    "unit": "seconds"
                },
                "avg_model_processing_time": {
                    "description": "平均模型处理时间（排除网络延迟）",
                    "measurement_method": "使用流式响应测量，优先从响应头获取服务器处理时间，否则通过TTFT(Time to First Token)估算网络延迟后计算",
                    "excludes": ["网络传输时间"],
                    "includes": ["prompt处理时间", "token生成时间"],
                    "unit": "seconds"
                }
            }
        },
        "metrics": {
            "accuracy": correct_count / sample_size if sample_size > 0 else 0,
            "avg_latency": total_latency / sample_size if sample_size > 0 else 0,
            "avg_model_processing_time": total_model_time / sample_size if sample_size > 0 else 0,
            "total_samples": sample_size,
            "correct_samples": correct_count
        },
        "details": results_detail
    }

    # 6. 持久化
    save_results(final_results)


if __name__ == "__main__":
    main()
