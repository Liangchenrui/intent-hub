"""编码器模块 - 封装Qwen3-Embedding模型"""

import threading
from pathlib import Path
from typing import List, Optional

import numpy as np
import torch
from transformers import AutoModel, AutoTokenizer

from intent_hub.utils.logger import logger


class QwenEmbeddingEncoder:
    """Qwen3-Embedding编码器封装类"""

    # HuggingFace 镜像站点
    HF_MIRROR = "https://hf-mirror.com"

    def __init__(
        self,
        model_name: str = "Qwen/Qwen3-Embedding-0.6B",
        device: Optional[str] = None,
        batch_size: int = 32,
        local_model_dir: Optional[str] = None,
        huggingface_token: Optional[str] = None,
        huggingface_provider: Optional[str] = None,
        huggingface_timeout: int = 30,
    ):
        """初始化编码器

        Args:
            model_name: 模型名称 (如 Qwen/Qwen3-Embedding-0.6B)
            device: 设备类型 (cpu/cuda/mps)，None则自动检测
            batch_size: 批处理大小
            local_model_dir: 本地模型存储目录，默认为 intent_hub/models
            huggingface_token: HuggingFace Access Token (可选)
            huggingface_provider: HuggingFace 推理服务提供商 (可选，如 "nebius")
            huggingface_timeout: HuggingFace 验证超时时间 (秒)
        """
        self.model_name = model_name
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.batch_size = batch_size
        self.huggingface_token = huggingface_token
        self.huggingface_provider = huggingface_provider
        self.huggingface_timeout = huggingface_timeout
        self._tokenizer: Optional[AutoTokenizer] = None
        self._model: Optional[AutoModel] = None
        self._dimensions: Optional[int] = None
        self._inference_client = None  # HuggingFace InferenceClient

        # 是否使用远程 HuggingFace Inference API
        self.is_remote = False
        self._remote_validated = False

        # 确定本地模型目录
        if local_model_dir is None:
            current_dir = Path(__file__).parent
            self.local_model_dir = current_dir / "models"
        else:
            self.local_model_dir = Path(local_model_dir)

        # 确保模型目录存在
        self.local_model_dir.mkdir(parents=True, exist_ok=True)
        
        # 初始化线程锁
        self._lock = threading.Lock()

    def _validate_huggingface_token(self) -> bool:
        """验证 HuggingFace Token 是否有效

        Returns:
            如果 Token 有效且 Inference API 可用返回 True，否则返回 False
        """
        if not self.huggingface_token:
            logger.info("未配置 HuggingFace Access Token，将使用本地模型")
            return False

        try:
            from huggingface_hub import InferenceClient

            provider_info = (
                f" (provider: {self.huggingface_provider})"
                if self.huggingface_provider
                else ""
            )
            logger.info(
                f"正在验证 HuggingFace Token 并测试 Inference API{provider_info}..."
            )

            # 创建 InferenceClient
            client_kwargs = {"api_key": self.huggingface_token}
            if self.huggingface_provider:
                client_kwargs["provider"] = self.huggingface_provider

            client = InferenceClient(**client_kwargs)

            # 使用线程实现超时机制
            result_container = {"result": None, "exception": None}

            def api_call():
                """在独立线程中执行 API 调用"""
                try:
                    result_container["result"] = client.feature_extraction(
                        "test",
                        model=self.model_name,
                    )
                except Exception as e:
                    result_container["exception"] = e

            # 启动线程执行 API 调用
            thread = threading.Thread(target=api_call, daemon=True)
            thread.start()
            thread.join(timeout=self.huggingface_timeout)

            # 检查是否超时
            if thread.is_alive():
                logger.warning(
                    f"HuggingFace Inference API 验证超时（{self.huggingface_timeout}秒），将回退到本地模型"
                )
                return False

            # 检查是否有异常
            if result_container["exception"]:
                raise result_container["exception"]

            result = result_container["result"]
            if result is not None:
                self._inference_client = client
                logger.info("HuggingFace Inference API 验证成功，将使用远程服务")
                return True
            else:
                logger.warning("HuggingFace Inference API 返回空结果，将回退到本地模型")
                return False

        except ImportError:
            logger.warning("未安装 huggingface_hub 库，将使用本地模型")
            return False
        except Exception as e:
            # 获取详细错误信息
            error_msg = str(e).lower() if str(e) else ""
            error_type = type(e).__name__
            error_detail = repr(e) if not str(e) else str(e)

            if (
                "401" in error_msg
                or "unauthorized" in error_msg
                or "invalid" in error_msg
            ):
                logger.warning("HuggingFace Token 无效或已过期，将回退到本地模型")
            elif "503" in error_msg or "loading" in error_msg:
                # 模型正在加载中，也视为可用
                logger.info(
                    "HuggingFace 模型正在加载中，将使用远程服务 (首次请求可能较慢)"
                )
                try:
                    from huggingface_hub import InferenceClient

                    client_kwargs = {"api_key": self.huggingface_token}
                    if self.huggingface_provider:
                        client_kwargs["provider"] = self.huggingface_provider
                    self._inference_client = InferenceClient(**client_kwargs)
                    return True
                except Exception:
                    pass
            elif "not supported" in error_msg or "not available" in error_msg:
                logger.warning(
                    f"模型 {self.model_name} 不支持 HuggingFace Inference API，将回退到本地模型"
                )
            else:
                logger.warning(
                    f"HuggingFace Inference API 验证失败 [{error_type}]: {error_detail}，将回退到本地模型。"
                    f"提示: 该模型可能不在免费推理服务支持列表中。"
                )
            return False

    def _get_local_model_path(self) -> Path:
        """获取本地模型路径

        Returns:
            本地模型路径
        """
        # 将模型名称转换为安全的目录名（替换 / 为 _）
        safe_model_name = self.model_name.replace("/", "_")
        return self.local_model_dir / safe_model_name

    def _is_local_model_exists(self) -> bool:
        """检查本地模型是否存在

        Returns:
            如果本地模型存在返回 True，否则返回 False
        """
        local_path = self._get_local_model_path()
        # 检查关键文件是否存在（config.json 是 HuggingFace 模型的标准配置文件）
        config_file = local_path / "config.json"
        return local_path.exists() and config_file.exists()

    def _download_model_from_mirror(self):
        """从 HuggingFace 镜像下载模型到本地

        Raises:
            Exception: 如果下载失败
        """
        try:
            from huggingface_hub import snapshot_download
        except ImportError:
            raise ImportError(
                "需要安装 huggingface_hub 库来下载模型。"
                "请运行: pip install huggingface_hub"
            )

        local_path = self._get_local_model_path()

        try:
            logger.info(f"正在从 HuggingFace 镜像下载模型: {self.model_name}")
            logger.info(f"镜像地址: {self.HF_MIRROR}")
            logger.info(f"下载到: {local_path}")

            # 使用镜像站点下载模型
            snapshot_download(
                repo_id=self.model_name,
                local_dir=str(local_path),
                endpoint=self.HF_MIRROR,
                resume_download=True,
                # 降低并发，避免多线程下载/移动临时文件时与外部清理逻辑发生竞争
                max_workers=1,
                ignore_patterns=[
                    "*.DS_Store",
                    "*.git*",
                    "imgs/*",
                    "*.jpg",
                    "*.png",
                    "*.md",
                ],
            )

            logger.info(f"模型下载完成: {local_path}")
        except Exception as e:
            # 关键修复：
            # 不要在下载异常时 rmtree(local_path)，否则 huggingface_hub 的并发线程可能仍在
            # chmod/move *.incomplete，目录被删除会导致二次 FileNotFoundError 并进入错误循环。
            logger.error(
                f"从镜像下载模型失败（将保留现场以便断点续传）: {e}", exc_info=True
            )
            raise

    def _get_model_path(self) -> str:
        """获取模型路径（本地或远程）

        如果本地模型存在，返回本地路径；否则先下载，再返回本地路径。

        Returns:
            模型路径（字符串）
        """
        if self._is_local_model_exists():
            local_path = self._get_local_model_path()
            logger.info(f"使用本地模型: {local_path}")
            return str(local_path)
        else:
            logger.info(f"本地模型不存在，准备从镜像下载: {self.model_name}")
            self._download_model_from_mirror()
            local_path = self._get_local_model_path()
            return str(local_path)

    def _initialize(self):
        """延迟初始化编码器"""
        # 首先尝试验证 HuggingFace Token（如果配置了）
        if not self._remote_validated and self.huggingface_token:
            self.is_remote = self._validate_huggingface_token()
            self._remote_validated = True

        if self.is_remote:
            # 远程模式：尝试获取维度
            if self._dimensions is None:
                try:
                    test_embedding = self._remote_encode(["test"])
                    self._dimensions = len(test_embedding[0])
                    logger.info(f"远程编码器初始化完成，维度: {self._dimensions}")
                except Exception as e:
                    logger.warning(f"远程编码器获取维度失败: {e}，将回退到本地模型")
                    self.is_remote = False
                    self._initialize_local_model()
            return

        # 本地模式
        self._initialize_local_model()

    def _initialize_local_model(self):
        """初始化本地模型"""
        # 关键修复：加锁，避免多个请求同时触发下载/加载/清理造成竞争
        with self._lock:
            if self._model is None:
                model_path = None
                try:
                    # 获取模型路径（优先使用本地，不存在则下载）
                    model_path = self._get_model_path()
                    logger.info(f"正在加载本地编码器模型: {model_path}")

                    self._tokenizer = AutoTokenizer.from_pretrained(model_path)
                    self._model = AutoModel.from_pretrained(model_path)
                    self._model.to(self.device)
                    self._model.eval()

                    # 获取模型维度
                    test_embedding = self._local_encode(["test"])
                    self._dimensions = len(test_embedding[0])
                    logger.info(
                        f"本地编码器初始化完成，设备: {self.device}，维度: {self._dimensions}"
                    )
                except Exception as e:
                    logger.error(f"本地编码器初始化失败: {e}", exc_info=True)
                    # 关键修复：不要在这里删除模型目录
                    # 失败原因可能是下载中断/网络抖动/并发竞争；删除目录会破坏断点续传并放大故障面。
                    raise

    @property
    def dimensions(self) -> int:
        """获取向量维度"""
        if self._dimensions is None:
            self._initialize()
        if self._dimensions is None:
            raise ValueError("编码器维度未初始化")
        return self._dimensions

    def _remote_encode(self, texts: List[str]) -> List[List[float]]:
        """通过 HuggingFace Inference API 进行编码"""
        if not self._inference_client:
            raise ValueError("HuggingFace InferenceClient 未初始化")

        all_embeddings = []

        # 逐条处理（feature_extraction 接收单个文本）
        for text in texts:
            try:
                result = self._inference_client.feature_extraction(
                    text,
                    model=self.model_name,
                )

                # 处理返回结果
                if result is not None:
                    # 转换为 numpy 数组以便处理
                    result_array = np.array(result)

                    # 如果返回的是 2D (token-level embeddings)，做 mean pooling
                    if result_array.ndim == 2:
                        embedding = np.mean(result_array, axis=0).tolist()
                    else:
                        # 如果已经是 1D (sentence-level embedding)
                        embedding = result_array.tolist()
                    all_embeddings.append(embedding)
                else:
                    raise Exception("HuggingFace API 返回空结果")

            except Exception as e:
                error_msg = str(e).lower()
                if "503" in error_msg or "loading" in error_msg:
                    # 模型正在加载，等待后重试
                    import time

                    logger.info("HuggingFace 模型正在加载，等待 20 秒后重试...")
                    time.sleep(20)
                    return self._remote_encode(texts)
                else:
                    raise Exception(f"HuggingFace Inference API 调用失败: {e}")

        return all_embeddings

    def _local_encode(self, texts: List[str]) -> List[List[float]]:
        """使用本地模型进行编码"""
        all_embeddings = []

        for i in range(0, len(texts), self.batch_size):
            batch_texts = texts[i : i + self.batch_size]

            # 对输入进行编码
            inputs = self._tokenizer(
                batch_texts,
                padding=True,
                truncation=True,
                max_length=512,
                return_tensors="pt",
            )

            # 将输入移至对应设备
            inputs = {k: v.to(self.device) for k, v in inputs.items()}

            with torch.no_grad():
                outputs = self._model(**inputs)

                # 使用 mean pooling 获取句子向量
                attention_mask = inputs["attention_mask"]
                token_embeddings = outputs.last_hidden_state

                input_mask_expanded = (
                    attention_mask.unsqueeze(-1).expand(token_embeddings.size()).float()
                )
                sum_embeddings = torch.sum(token_embeddings * input_mask_expanded, 1)
                sum_mask = torch.clamp(input_mask_expanded.sum(1), min=1e-9)
                batch_embeddings = sum_embeddings / sum_mask

                all_embeddings.extend(batch_embeddings.cpu().numpy().tolist())

        return all_embeddings

    def encode(self, texts: List[str]) -> List[List[float]]:
        """编码文本列表为向量

        Args:
            texts: 文本列表

        Returns:
            向量列表
        """
        if not texts:
            return []

        # 确保已初始化（会自动判断远程/本地模式）
        if self._dimensions is None:
            self._initialize()

        try:
            if self.is_remote:
                return self._remote_encode(texts)
            else:
                return self._local_encode(texts)
        except Exception as e:
            logger.error(f"编码失败: {e}", exc_info=True)
            raise

    def encode_single(self, text: str) -> List[float]:
        """编码单个文本为向量

        Args:
            text: 文本字符串

        Returns:
            向量
        """
        return self.encode([text])[0]

    def encode_to_numpy(self, texts: List[str]) -> np.ndarray:
        """编码文本列表为numpy数组

        Args:
            texts: 文本列表

        Returns:
            numpy数组
        """
        embeddings = self.encode(texts)
        return np.array(embeddings)
