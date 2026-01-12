# 项目结构说明

## 目录结构

```
intent-hub-backend/
├── intent_hub/              # 主包目录
│   ├── __init__.py          # 包初始化，导出主要接口
│   ├── app.py               # Flask应用主文件，定义所有API路由
│   ├── config.py            # 配置管理，从环境变量和settings.json读取配置
│   ├── models.py            # 数据模型定义（Pydantic模型）
│   ├── encoder.py           # 编码器封装，处理文本向量化
│   ├── qdrant_wrapper.py   # Qdrant客户端封装，处理向量存储和检索
│   ├── route_manager.py     # 路由管理器，内存缓存和热加载
│   ├── auth.py              # 认证模块，API Key管理
│   ├── routes_config.json   # 路由配置文件
│   ├── settings.json        # 系统设置文件
│   ├── api/                 # API处理模块
│   │   ├── __init__.py
│   │   ├── auth.py          # 认证相关API
│   │   ├── health.py        # 健康检查API
│   │   ├── prediction.py    # 路由预测API
│   │   ├── routes.py        # 路由管理API
│   │   ├── reindex.py       # 重新索引API
│   │   └── settings.py      # 系统设置API
│   ├── core/                # 核心组件模块
│   │   ├── __init__.py
│   │   └── components.py    # 组件管理器，统一管理所有组件的初始化
│   ├── services/            # 业务逻辑服务层
│   │   ├── __init__.py
│   │   ├── route_service.py      # 路由服务，处理路由CRUD业务逻辑
│   │   ├── prediction_service.py # 预测服务，处理路由预测业务逻辑
│   │   ├── sync_service.py       # 同步服务，处理路由数据同步
│   │   └── llm_factory.py        # LLM工厂，根据provider创建LLM实例
│   ├── utils/               # 工具模块
│   │   ├── __init__.py
│   │   ├── error_handler.py # 错误处理工具
│   │   └── logger.py        # 日志工具
│   └── models/              # 模型文件目录
│       └── Qwen_Qwen3-Embedding-0.6B/  # 本地模型文件
├── tests/                   # 测试目录
│   ├── __init__.py
│   └── test_config.py      # 配置模块测试示例
├── docs/                    # 文档目录
│   ├── API.md              # API接口文档
│   ├── PRD_V1.0.md        # 需求规格说明书
│   └── STRUCTURE.md        # 本文件
├── requirements.txt         # Python依赖列表
├── setup.py                 # setuptools安装配置
├── Dockerfile              # Docker构建文件
├── .gitignore              # Git忽略文件
├── run.py                   # 应用启动脚本
└── README.md               # 项目说明文档
```

## 模块说明

### intent_hub.app
Flask应用主文件，定义所有API路由：
- `/health` - 健康检查
- `/auth/login` - 用户登录
- `/predict` - 路由预测
- `/routes` - 路由CRUD操作（GET, POST）
- `/routes/search` - 搜索路由
- `/routes/<id>` - 路由更新和删除（PUT, DELETE）
- `/routes/generate-utterances` - 生成例句
- `/reindex` - 重新索引
- `/settings` - 系统设置（GET, POST）

### intent_hub.config
配置管理模块，从环境变量和settings.json文件读取配置：
- Flask配置（host, port, debug）
- Qdrant配置（url, collection, api_key）
- Embedding模型配置（model_name, device）
- LLM配置（provider, api_key, base_url, model, temperature）
- 认证配置（auth_enabled, username, password, telestar_auth）
- 其他配置（batch_size, default_route等）

### intent_hub.models
数据模型定义，使用Pydantic进行验证：
- `RouteConfig` - 路由配置模型
- `PredictRequest/Response` - 预测请求/响应模型
- `ErrorResponse` - 错误响应模型
- `LoginRequest/Response` - 登录请求/响应模型
- `GenerateUtterancesRequest` - 生成例句请求模型

### intent_hub.encoder
编码器模块，封装Qwen3-Embedding模型：
- 支持本地模型和远程模型下载
- 批量编码和单文本编码
- 延迟初始化，提高启动速度
- 自动获取向量维度

### intent_hub.qdrant_wrapper
Qdrant客户端封装：
- Collection自动创建
- 路由向量点的增删改查
- 相似度搜索
- 路由ID集合获取
- 数据存在性检查

### intent_hub.route_manager
路由管理器：
- 从JSON文件加载路由配置
- 内存缓存路由数据
- 支持热加载（reload）
- 线程安全的CRUD操作
- 路由搜索功能

### intent_hub.auth
认证模块：
- API Key生成和验证
- 用户登录验证
- 认证装饰器（require_auth）
- 支持Bearer Token和X-API-Key两种方式
- 支持Telestar认证

### intent_hub.core.components
组件管理器，统一管理所有核心组件的初始化：
- 编码器（Encoder）初始化
- Qdrant客户端初始化
- 路由管理器初始化
- 自动同步路由数据到Qdrant
- 单例模式，确保全局唯一实例

### intent_hub.services
业务逻辑服务层，封装核心业务逻辑：

#### route_service.py
路由服务，处理路由的CRUD操作：
- 获取所有路由
- 搜索路由
- 创建/更新路由（含向量生成）
- 删除路由
- 使用LLM生成例句

#### prediction_service.py
预测服务，处理路由预测的核心业务逻辑：
- 文本向量化
- 相似度检索
- 阈值过滤
- 结果排序和返回

#### sync_service.py
同步服务，处理路由数据同步：
- 增量更新
- 全量重建

#### llm_factory.py
LLM工厂，根据provider创建对应的LLM实例：
- 支持多种LLM提供商（deepseek, openrouter, doubao, qwen, gemini）
- 自动配置默认参数
- 使用LangChain统一接口

### intent_hub.api
API处理模块，将HTTP请求路由到对应的服务层：
- `auth.py` - 认证相关API处理
- `health.py` - 健康检查API处理
- `prediction.py` - 路由预测API处理
- `routes.py` - 路由管理API处理
- `reindex.py` - 重新索引API处理
- `settings.py` - 系统设置API处理

### intent_hub.utils
工具模块：
- `error_handler.py` - 统一错误处理和请求验证
- `logger.py` - 日志工具，提供统一的日志接口

## 数据流

1. **启动流程**：
   - 通过`ComponentManager`统一初始化所有组件
   - 初始化编码器（加载模型，获取向量维度）
   - 初始化Qdrant客户端（连接数据库，创建Collection）
   - 初始化路由管理器（从JSON文件加载路由配置）
   - 如果Qdrant为空，自动同步路由数据到Qdrant

2. **预测流程**：
   - 接收文本输入（通过`PredictionService`）
   - 使用编码器生成向量
   - 在Qdrant中搜索Top-K最相似的向量
   - 按路由ID分组，取最高分
   - 根据每个路由的阈值判断是否匹配
   - 返回所有满足阈值的路由（按分数降序），如果没有则返回默认路由

3. **路由管理流程**：
   - 从JSON文件加载路由配置到内存缓存
   - 通过`RouteService`处理CRUD操作
   - 创建/更新路由时：
     - 更新内存缓存
     - 生成向量并同步到Qdrant
   - 删除路由时：
     - 从内存缓存删除
     - 从Qdrant删除对应向量点
   - 支持热加载重新索引（增量或全量）

4. **例句生成流程**：
   - 接收生成请求（路由ID、名称、描述等）
   - 如果路由已存在，获取现有例句作为参考
   - 使用LLM工厂创建LLM实例
   - 通过LangChain调用LLM生成新例句
   - 过滤重复例句，返回指定数量的新例句
   - 更新路由配置（如果路由已存在）

## 配置文件

### routes_config.json
路由配置文件，JSON格式：
```json
[
  {
    "id": 1,
    "name": "路由名称",
    "description": "路由描述信息",
    "utterances": ["示例1", "示例2"],
    "score_threshold": 0.75
  }
]
```

### settings.json
系统设置文件，存储系统配置（可通过API动态更新）：
```json
{
  "QDRANT_URL": "http://192.168.33.1:31853",
  "QDRANT_COLLECTION": "intent_hub_routes",
  "EMBEDDING_MODEL_NAME": "Qwen/Qwen3-Embedding-0.6B",
  "LLM_PROVIDER": "deepseek",
  "LLM_API_KEY": "sk-xxx",
  "LLM_MODEL": "deepseek-chat",
  "AUTH_ENABLED": true
}
```

### 环境变量
部分配置可通过环境变量设置，优先级高于settings.json：
- `FLASK_HOST` - Flask服务地址
- `FLASK_PORT` - Flask服务端口
- `FLASK_DEBUG` - 调试模式
- `API_KEYS` - API密钥（多个用逗号分隔）
- 其他配置详见`intent_hub/config.py`

## 扩展指南

### 添加新功能
1. 在`intent_hub`包中添加新模块
2. 在`intent_hub/api`中添加新的API处理函数
3. 在`app.py`中注册新的API路由
4. 在`models.py`中添加新的数据模型（如需要）
5. 在`services`中添加业务逻辑服务（如需要）
6. 更新`__init__.py`导出新接口（如需要）

### 添加新的LLM提供商
1. 在`intent_hub/services/llm_factory.py`中添加新的provider支持
2. 在`intent_hub/config.py`中添加对应的配置项
3. 更新`LLMFactory.SUPPORTED_PROVIDERS`列表
4. 更新API文档中的LLM配置说明

### 添加测试
1. 在`tests`目录下创建测试文件
2. 使用pytest编写测试用例
3. 运行`pytest`执行测试

### 添加文档
1. 在`docs`目录下添加文档文件
2. 更新`docs/API.md`中的接口文档（如添加新接口）
3. 更新`docs/STRUCTURE.md`中的项目结构说明
4. 更新README.md中的相关链接

