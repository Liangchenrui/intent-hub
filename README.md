# Intent Hub 🚀

一个基于向量相似度的静态路由系统，通过语义匹配将用户请求精准分发至对应的 AI Agent。

---

## 🗺️ 导航与快速开始

### ⚡ 快速一键运行 (推荐)
项目已深度容器化。确保你已安装 Docker 和 Docker Compose，然后在根目录运行：

```shell
docker-compose up -d
```
或
```shell
docker compose --env-file .env.china up -d --build
```

启动后：
- **管理后台 (Frontend):** `http://localhost` (默认 80 端口)
- **API 服务 (Backend):** `http://localhost:8000`
- **向量数据库 (Qdrant):** `http://localhost:6333/dashboard`

> **注意**：首次启动会自动拉取/构建镜像，并下载必要的 Embedding 模型，请确保网络畅通。

---

## 🏗️ 项目架构

本项目采用前后端分离架构，通过向量检索实现毫秒级意图分发。

### 🔹 后端 (Python / FastAPI)
- **核心框架:** [Python 3.9+](https://www.python.org/) + [FastAPI](https://fastapi.tiangolo.com/)
- **向量检索:** [Qdrant](https://qdrant.tech/) (高性能向量数据库)
- **模型能力:** 
  - Embedding: Qwen-Embedding-0.6B (支持 HuggingFace / 本地加载)
  - LLM: 通过 LangChain 集成 DeepSeek, OpenAI, 通义千问等
- **主要职责:** 意图识别、向量同步、自动语料增强生成、路由管理 API。

### 🔹 前端 (Vue / Vite)
- **核心框架:** [Vue 3](https://vuejs.org/) + [Vite](https://vitejs.dev/)
- **UI 组件库:** [Element Plus](https://element-plus.org/)
- **主要职责:** 路由 CRUD 可视化、语料生成交互、系统配置、向量匹配效果测试。

---

## 📂 目录结构

```text
intenthub/
├── intent-hub-backend/    # 后端源代码 (Python/FastAPI)
│   ├── intent_hub/        # 核心逻辑 (编码、检索、服务层)
│   ├── tests/             # 单元测试
│   └── run.py             # 服务启动入口
├── intent-hub-frontend/   # 前端源代码 (Vue/Vite)
│   ├── src/               # 页面、组件、状态管理
│   └── vite.config.ts     # 构建配置
├── docker-compose.yml     # 全栈容器化编排
└── README.md              # 本说明文件 (项目导航)
```

---

## 📄 License
Distributed under the MIT License. See `LICENSE` for more information.
