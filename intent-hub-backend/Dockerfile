# ===========================================
# 轻量级 Docker 镜像构建
# - 不包含本地模型，使用远程 HuggingFace API
# - 纯 CPU 版本，无 GPU 依赖
# - 多阶段构建，最小化镜像体积
# ===========================================

# 第一阶段：构建阶段
FROM python:3.11-slim AS builder

WORKDIR /build

# 设置环境变量
ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1

# 复制依赖文件
COPY requirements.txt .

# 安装项目依赖到用户目录
RUN pip install --user --no-cache-dir \
    -i https://pypi.tuna.tsinghua.edu.cn/simple \
    --trusted-host pypi.tuna.tsinghua.edu.cn \
    -r requirements.txt

# ===========================================
# 第二阶段：运行阶段 (最终镜像)
# ===========================================
FROM python:3.11-slim

WORKDIR /app

# 设置环境变量
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/home/appuser/.local/bin:${PATH}" \
    # 禁用 HuggingFace 本地缓存
    HF_HOME="/tmp/hf_cache" \
    TRANSFORMERS_CACHE="/tmp/transformers_cache"

# 创建非 root 用户
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app

# 从构建阶段复制安装好的依赖
COPY --from=builder --chown=appuser:appuser /root/.local /home/appuser/.local

# 复制项目代码（.dockerignore 会排除模型和敏感文件）
COPY --chown=appuser:appuser . .

# 确保模型目录存在但为空（运行时使用远程 API）
RUN mkdir -p /app/intent_hub/models && \
    chown -R appuser:appuser /app/intent_hub/models

# 切换到非 root 用户
USER appuser

# 暴露端口
EXPOSE 5000

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/health')" || exit 1

# 启动命令
CMD ["python", "run.py"]
