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
            如果 Token 有效返回 True，否则返回 False
        """
        if not self.huggingface_token:
            logger.info("HuggingFace Access Token not configured, using local model")
            return False

        try:
            from huggingface_hub import HfApi, InferenceClient

            # 兼容性处理：如果 provider 是 "hf-inference"，这通常意味着用户想用官方服务
            # 在这种情况下，InferenceClient 的 provider 应该为 None
            actual_provider = self.huggingface_provider
            if actual_provider == "hf-inference":
                actual_provider = None

            provider_info = (
                f" (provider: {actual_provider})"
                if actual_provider
                else " (official)"
            )
            logger.info(
                f"Validating HuggingFace Token{provider_info}..."
            )

            # 第一步：快速验证 Token 是否有效 (使用 whoami，非阻塞模型加载)
            api = HfApi(token=self.huggingface_token)
            
            # 使用较短的超时时间验证 Token
            result_container = {"valid": False, "error": None}
            def check_token():
                try:
                    api.whoami()
                    result_container["valid"] = True
                except Exception as e:
                    result_container["error"] = e

            thread = threading.Thread(target=check_token, daemon=True)
            thread.start()
            thread.join(timeout=10) # Token 验证不应超过 10 秒

            if thread.is_alive():
                logger.warning("HuggingFace Token validation timeout, network may be slow")
                return False

            if not result_container["valid"]:
                error_msg = str(result_container["error"]).lower()
                if "401" in error_msg or "unauthorized" in error_msg:
                    logger.warning("HuggingFace Token invalid or expired")
                else:
                    logger.warning(f"HuggingFace Token validation error: {result_container['error']}")
                return False

            # 第二步：初始化 Client (不立即测试推理，避免启动阻塞)
            client_kwargs = {
                "api_key": self.huggingface_token,
                "timeout": self.huggingface_timeout
            }
            if actual_provider:
                client_kwargs["provider"] = actual_provider

            self._inference_client = InferenceClient(**client_kwargs)
            logger.info("HuggingFace Token validated, using remote service")
            return True

        except ImportError:
            logger.warning("huggingface_hub not installed, using local model")
            return False
        except Exception as e:
            logger.warning(f"HuggingFace validation unexpected error: {e}")
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
                "huggingface_hub is required to download models. "
                "Run: pip install huggingface_hub"
            )

        local_path = self._get_local_model_path()

        try:
            logger.info(f"Downloading model from HuggingFace mirror: {self.model_name}")
            logger.info(f"Mirror: {self.HF_MIRROR}")
            logger.info(f"Target: {local_path}")

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

            logger.info(f"Model download complete: {local_path}")
        except Exception as e:
            # 关键修复：
            # 不要在下载异常时 rmtree(local_path)，否则 huggingface_hub 的并发线程可能仍在
            # chmod/move *.incomplete，目录被删除会导致二次 FileNotFoundError 并进入错误循环。
            logger.error(
                f"Model download from mirror failed (state kept for resume): {e}", exc_info=True
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
            logger.info(f"Using local model: {local_path}")
            return str(local_path)
        else:
            logger.info(f"Local model not found, downloading from mirror: {self.model_name}")
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
                    logger.info(f"Remote encoder initialized, dimensions: {self._dimensions}")
                except Exception as e:
                    logger.warning(f"Remote encoder dimension fetch failed: {e}, falling back to local model")
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
                    logger.info(f"Loading local encoder model: {model_path}")

                    self._tokenizer = AutoTokenizer.from_pretrained(model_path)
                    self._model = AutoModel.from_pretrained(model_path)
                    self._model.to(self.device)
                    self._model.eval()

                    # 获取模型维度
                    test_embedding = self._local_encode(["test"])
                    self._dimensions = len(test_embedding[0])
                    logger.info(
                        f"Local encoder initialized, device: {self.device}, dimensions: {self._dimensions}"
                    )
                except Exception as e:
                    logger.error(f"Local encoder initialization failed: {e}", exc_info=True)
                    # 关键修复：不要在这里删除模型目录
                    # 失败原因可能是下载中断/网络抖动/并发竞争；删除目录会破坏断点续传并放大故障面。
                    raise

    @property
    def dimensions(self) -> int:
        """获取向量维度"""
        if self._dimensions is None:
            self._initialize()
        if self._dimensions is None:
            raise ValueError("Encoder dimensions not initialized")
        return self._dimensions

    def _remote_encode(self, texts: List[str]) -> List[List[float]]:
        """通过 HuggingFace Inference API 进行编码"""
        if not self._inference_client:
            raise ValueError("HuggingFace InferenceClient not initialized")

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
                    raise Exception("HuggingFace API returned empty result")

            except Exception as e:
                error_msg = str(e).lower()
                if "503" in error_msg or "loading" in error_msg:
                    # 模型正在加载，等待后重试
                    import time

                    logger.info("HuggingFace model loading, waiting 20s then retry (Inference API may need minutes for cold start)...")
                    time.sleep(20)
                    return self._remote_encode(texts)
                else:
                    raise Exception(f"HuggingFace Inference API call failed: {e}")

        return all_embeddings

    def _local_encode(self, texts: List[str]) -> List[List[float]]:
        """Using local model进行编码"""
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
            logger.error(f"Encoding failed: {e}", exc_info=True)
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
