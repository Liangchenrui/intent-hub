# Intent Hub API 接口文档

## 基础信息

- **Base URL**: `http://localhost:5000` (根据实际部署环境调整)
- **认证方式**: 
  1. **API Key 认证** (适用于管理接口):
     - 请求头: `Authorization: Bearer <api_key>` 或 `X-API-Key: <api_key>`
     - 获取方式: 通过 `/auth/login` 接口登录获取
  2. **Telestar 认证** (适用于预测接口):
     - 请求头: `Authorization: <telestar_key>`
     - Telestar 密钥需要在 `settings.json` 中配置 `TELESTAR_AUTH_KEY` 字段
     - 建议首次部署后立即修改默认密钥

## 接口列表

### 1. 健康检查

**接口**: `GET /health`

**鉴权**: 否

**响应**:
```json
{
  "status": "ok",
  "qdrant_ready": true,
  "encoder_ready": true,
  "route_manager_ready": true,
  "auth_enabled": true
}
```

---

### 2. 登录

**接口**: `POST /auth/login`

**鉴权**: 否

**请求体**:
```json
{
  "username": "admin",
  "password": "your_password"
}
```

**说明**：
- 默认用户名：`admin`
- 默认密码需要在 `settings.json` 中配置 `DEFAULT_PASSWORD` 字段
- 建议首次部署后立即修改默认密码

**响应** (200):
```json
{
  "api_key": "your-api-key-here",
  "message": "请妥善保管此API key，后续请求需要在请求头中提供 Authorization: Bearer <key> 或 X-API-Key: <key>"
}
```

**错误响应** (401):
```json
{
  "error": "认证失败",
  "detail": "用户名或密码错误"
}
```

---

### 3. 路由预测

**接口**: `POST /predict`

**鉴权**: 是 (Telestar认证)

**请求头**:
```
Authorization: <your_telestar_key>
```

**说明**：
- `your_telestar_key` 需要在 `settings.json` 中配置 `TELESTAR_AUTH_KEY` 字段
- 如果 `TELESTAR_AUTH_ENABLED=false`，则无需认证

**请求体**:
```json
{
  "text": "北京今天天气如何？"
}
```

**响应** (200):
返回所有相似度大于设定阈值的路由列表，按相似度分数降序排列。如果没有路由满足阈值，则返回默认路由（id: 0, name: "none"）。

```json
[
  {
    "id": 1,
    "name": "天气查询助手",
    "score": 0.85
  },
  {
    "id": 2,
    "name": "技术支持",
    "score": 0.78
  }
]
```

**说明**:
- 系统会在Qdrant中检索Top-K结果（默认K=20），然后按路由ID分组，每个路由取最高分
- 只有相似度分数大于等于该路由的`score_threshold`的路由才会被返回
- 结果按分数降序排列
- 如果没有路由满足阈值，返回：`[{"id": 0, "name": "none", "score": null}]`

---

### 4. 获取所有路由

**接口**: `GET /routes`

**鉴权**: 是

**响应** (200):
```json
[
  {
    "id": 1,
    "name": "天气查询助手",
    "description": "提供全球城市天气查询服务，包括温度、湿度、降水概率等详细信息，支持多城市对比和未来天气预报",
    "utterances": [
      "如何查询某个城市的天气？",
      "北京今天天气如何？"
    ],
    "score_threshold": 0.7
  },
  {
    "id": 2,
    "name": "技术支持",
    "description": "提供系统技术支持服务，帮助用户解决技术问题、系统错误和bug修复",
    "utterances": [
      "我需要技术支持",
      "系统出现错误"
    ],
    "score_threshold": 0.70
  }
]
```

---

### 5. 搜索路由

**接口**: `GET /routes/search`

**鉴权**: 是

**查询参数**:
- `q` (string, 可选): 搜索关键词，会在路由名称、描述和例句中搜索。如果为空，返回所有路由。

**响应** (200):
```json
[
  {
    "id": 1,
    "name": "天气查询助手",
    "description": "提供全球城市天气查询服务，包括温度、湿度、降水概率等详细信息，支持多城市对比和未来天气预报",
    "utterances": [
      "如何查询某个城市的天气？",
      "北京今天天气如何？"
    ],
    "score_threshold": 0.7
  }
]
```

**示例请求**:
- `GET /routes/search?q=天气` - 搜索包含"天气"的路由
- `GET /routes/search?q=技术支持` - 搜索包含"技术支持"的路由
- `GET /routes/search?q=` - 返回所有路由（等同于 `/routes`）

---

### 6. 创建路由

**接口**: `POST /routes`

**鉴权**: 是

**请求体**:
```json
{
  "id": 4,
  "name": "订单查询",
  "description": "提供订单查询服务，帮助用户查找订单信息和订单状态",
  "utterances": [
    "查询订单",
    "我的订单在哪里",
    "订单状态"
  ],
  "score_threshold": 0.75
}
```

**参数说明**:
- `id` (int): 路由ID。如果设置为 `0`，系统会自动分配一个新的ID（取现有最大ID+1）。如果指定了非0的ID且该ID已存在，则执行更新操作；如果ID不存在，会返回错误。
- `name` (string, 必填): 路由名称
- `description` (string, 可选): 路由描述，默认为空字符串
- `utterances` (string[], 必填): 示例语句列表，至少包含一条语句
- `score_threshold` (float, 可选): 相似度阈值，范围0.0-1.0，默认0.75

**响应** (201):
```json
{
  "id": 4,
  "name": "订单查询",
  "description": "提供订单查询服务，帮助用户查找订单信息和订单状态",
  "utterances": [
    "查询订单",
    "我的订单在哪里",
    "订单状态"
  ],
  "score_threshold": 0.75
}
```

**说明**:
- 创建路由时，系统会自动为路由的所有utterances生成向量并存储到Qdrant
- 如果ID为0，系统会自动分配新ID；如果指定了已存在的ID，会执行更新操作

---

### 7. 更新路由

**接口**: `PUT /routes/<route_id>`

**鉴权**: 是

**路径参数**:
- `route_id` (int): 路由ID

**请求体**:
```json
{
  "id": 1,
  "name": "天气查询助手（更新）",
  "description": "提供全球城市天气查询服务，包括温度、湿度、降水概率等详细信息，支持多城市对比和未来天气预报",
  "utterances": [
    "如何查询某个城市的天气？",
    "北京今天天气如何？",
    "新增的示例语句"
  ],
  "score_threshold": 0.8
}
```

**响应** (200):
```json
{
  "id": 1,
  "name": "天气查询助手（更新）",
  "description": "提供全球城市天气查询服务，包括温度、湿度、降水概率等详细信息，支持多城市对比和未来天气预报",
  "utterances": [
    "如何查询某个城市的天气？",
    "北京今天天气如何？",
    "新增的示例语句"
  ],
  "score_threshold": 0.8
}
```

**错误响应** (404):
```json
{
  "error": "路由不存在",
  "detail": "路由ID不存在"
}
```

---

### 8. 删除路由

**接口**: `DELETE /routes/<route_id>`

**鉴权**: 是

**路径参数**:
- `route_id` (int): 路由ID

**响应** (200):
```json
{
  "message": "路由 1 已删除"
}
```

**错误响应** (404):
```json
{
  "error": "路由不存在",
  "detail": "路由ID不存在"
}
```

---

### 9. 重新索引

**接口**: `POST /reindex`

**鉴权**: 是

**请求体** (可选):
```json
{
  "force_full": false
}
```

**参数说明**:
- `force_full` (boolean, 可选): 默认为 `false`，执行增量更新；设置为 `true` 时执行全量重建

**响应** (200):
```json
{ 
  "message": "重新索引完成",
  "updated_count": 2,
  "total_count": 3
}
```

---

### 10. 生成例句 (LLM)

**接口**: `POST /routes/generate-utterances`

**鉴权**: 是

**请求体**:
```json
{
  "id": 1,
  "name": "天气查询助手",
  "description": "提供全球城市天气查询服务，包括温度、湿度、降水概率等详细信息",
  "count": 5,
  "utterances": [
    "如何查询某个城市的天气？",
    "北京今天天气如何？"
  ]
}
```

**参数说明**:
- `id` (int, 必填): 路由ID
- `name` (string, 必填): 路由名称
- `description` (string, 可选): 路由描述，LLM 将根据此描述生成更相关的例句
- `count` (int, 可选): 需要**新生成**的例句数量（不包含示例utterances），默认为 5，范围 1-50
- `utterances` (string[], 可选): 参考的例句列表（仅当路由不存在时使用，如果路由已存在则从现有路由获取示例）

**行为说明**:
1. **示例utterances获取**：
   - 如果路由ID已存在，自动从现有路由获取所有utterances作为示例
   - 如果路由ID不存在，使用请求中的`utterances`字段作为示例（如果有）
2. **生成逻辑**：
   - LLM会参考示例utterances的风格生成新的utterances
   - 实际生成数量 = 示例数量 + `count`参数（用于确保有足够的候选）
   - 但最终只返回`count`条新生成的utterances（过滤掉与示例重复的）
3. **返回结果**：
   - 返回的utterances列表 = 示例utterances（最前面） + 新生成的`count`条utterances

**响应** (200):
返回更新后的路由配置对象：
```json
{
  "id": 1,
  "name": "天气查询助手",
  "description": "提供全球城市天气查询服务，包括温度、湿度、降水概率等详细信息",
  "utterances": [
    "如何查询某个城市的天气？",
    "北京今天天气如何？",
    "上海明天的降水概率是多少？",
    "帮我查询一下广州的气温",
    "现在的天气适合出门吗？",
    "查询温度",
    "明天会下雨吗"
  ],
  "score_threshold": 0.75
}
```
注意：返回的utterances列表中，前N条是原有的示例utterances（如果路由已存在），后面是 newly 生成的`count`条。

---

### 11. 获取系统设置

**接口**: `GET /settings`

**鉴权**: 是

**响应** (200):
```json
{
  "QDRANT_URL": "http://localhost:6333",
  "QDRANT_COLLECTION": "intent_hub_routes",
  "QDRANT_API_KEY": null,
  "HUGGINGFACE_ACCESS_TOKEN": null,
  "HUGGINGFACE_PROVIDER": null,
  "EMBEDDING_MODEL_NAME": "Qwen/Qwen3-Embedding-0.6B",
  "EMBEDDING_DEVICE": "cpu",
  "LLM_PROVIDER": "deepseek",
  "LLM_API_KEY": null,
  "LLM_BASE_URL": null,
  "LLM_MODEL": null,
  "LLM_TEMPERATURE": 0.7,
  "DEEPSEEK_API_KEY": null,
  "DEEPSEEK_BASE_URL": "https://api.deepseek.com",
  "DEEPSEEK_MODEL": "deepseek-chat",
  "UTTERANCE_GENERATION_PROMPT": "...",
  "AUTH_ENABLED": true,
  "TELESTAR_AUTH_ENABLED": true,
  "BATCH_SIZE": 32,
  "DEFAULT_ROUTE_ID": 0,
  "DEFAULT_ROUTE_NAME": "none"
}
```

**配置说明**：

**Qdrant配置**：
- `QDRANT_URL`: Qdrant服务地址（本地/自建或云端）
- `QDRANT_COLLECTION`: Collection名称
- `QDRANT_API_KEY`: Qdrant API密钥（云端部署时需要）

**Embedding模型配置**：
- `HUGGINGFACE_ACCESS_TOKEN`: HuggingFace Access Token（可选）
  - 如果配置，系统会尝试使用 HuggingFace Inference API
  - 如果为空或验证失败，将从 hf-mirror 下载模型到本地
- `HUGGINGFACE_PROVIDER`: 推理服务提供商（可选）
  - 支持的值：`nebius`、`hf-inference` 等
  - 某些模型（如 Qwen3-Embedding-4B/8B）需要特定 provider（如 `nebius`）
- `EMBEDDING_MODEL_NAME`: 模型名称（如 `Qwen/Qwen3-Embedding-0.6B`）
- `EMBEDDING_DEVICE`: 本地模型使用的设备（`cpu`/`cuda`/`mps`）

**LLM配置**：
- `LLM_PROVIDER`: LLM提供商，支持的值：`deepseek`、`openrouter`、`doubao`、`qwen`、`gemini`
- `LLM_API_KEY`: LLM API密钥（如果为null，将使用对应provider的默认配置）
- `LLM_BASE_URL`: LLM API基础URL（Gemini不需要此配置）
- `LLM_MODEL`: 模型名称（如果为null，将使用对应provider的默认模型）
- `LLM_TEMPERATURE`: 温度参数，控制输出的随机性（0.0-2.0）
- `DEEPSEEK_*`: DeepSeek配置（向后兼容，当LLM_PROVIDER=deepseek时自动使用）

---

### 12. 更新系统设置

**接口**: `POST /settings`

**鉴权**: 是

**说明**：
- 更新配置后，系统会自动重新初始化核心组件（编码器、Qdrant客户端等）
- 可以只更新部分配置项，未提供的配置项保持不变
- 所有配置项都会保存到 `settings.json` 文件中

**请求体**:
```json
{
  "LLM_PROVIDER": "gemini",
  "LLM_API_KEY": "your-gemini-api-key",
  "LLM_MODEL": "gemini-pro",
  "LLM_TEMPERATURE": 0.8
}
```

**配置示例**：

**1. 配置 Embedding 使用 HuggingFace Inference API**:
```json
{
  "HUGGINGFACE_ACCESS_TOKEN": "hf_your_token_here",
  "HUGGINGFACE_PROVIDER": "nebius",
  "EMBEDDING_MODEL_NAME": "Qwen/Qwen3-Embedding-4B"
}
```
说明：如果 Token 验证成功，将使用远程 API；否则回退到本地模型。

**2. 配置 Embedding 使用本地模型**:
```json
{
  "HUGGINGFACE_ACCESS_TOKEN": null,
  "EMBEDDING_MODEL_NAME": "Qwen/Qwen3-Embedding-0.6B",
  "EMBEDDING_DEVICE": "cpu"
}
```
说明：系统会从 hf-mirror 下载模型到本地。

**3. 配置 Qdrant 云端服务**:
```json
{
  "QDRANT_URL": "https://your-qdrant-cloud.tech",
  "QDRANT_API_KEY": "your-qdrant-api-key",
  "QDRANT_COLLECTION": "intent_hub_routes"
}
```

**4. 切换到 Gemini LLM**:
```json
{
  "LLM_PROVIDER": "gemini",
  "LLM_API_KEY": "your-gemini-api-key",
  "LLM_MODEL": "gemini-pro"
}
```

**5. 切换到 OpenRouter LLM**:
```json
{
  "LLM_PROVIDER": "openrouter",
  "LLM_API_KEY": "your-openrouter-api-key",
  "LLM_BASE_URL": "https://openrouter.ai/api/v1",
  "LLM_MODEL": "openai/gpt-4"
}
```

**6. 切换到豆包(Doubao) LLM**:
```json
{
  "LLM_PROVIDER": "doubao",
  "LLM_API_KEY": "your-doubao-api-key",
  "LLM_BASE_URL": "https://ark.cn-beijing.volces.com/api/v3",
  "LLM_MODEL": "ep-20241208123456-xxxxx"
}
```

**7. 切换到通义千问(Qwen) LLM**:
```json
{
  "LLM_PROVIDER": "qwen",
  "LLM_API_KEY": "your-qwen-api-key",
  "LLM_BASE_URL": "https://dashscope.aliyuncs.com/compatible-mode/v1",
  "LLM_MODEL": "qwen-turbo"
}
```

**8. 切换回 DeepSeek LLM**:
```json
{
  "LLM_PROVIDER": "deepseek",
  "LLM_API_KEY": "your-deepseek-api-key",
  "LLM_BASE_URL": "https://api.deepseek.com",
  "LLM_MODEL": "deepseek-chat"
}
```

**响应** (200):
```json
{
  "message": "配置更新成功，组件已重新加载",
  "settings": {
    "QDRANT_URL": "http://localhost:6333",
    "HUGGINGFACE_ACCESS_TOKEN": "hf_***",
    "LLM_PROVIDER": "gemini",
    "LLM_TEMPERATURE": 0.8,
    "...": "..."
  }
}
```

**错误响应** (500):
```json
{
  "error": "配置保存失败",
  "detail": "详细错误信息"
}
```

---

## 错误响应格式

所有接口在出错时可能返回以下格式：

```json
{
  "error": "错误类型",
  "detail": "详细错误信息"
}
```

**常见HTTP状态码**:
- `200`: 成功
- `201`: 创建成功
- `400`: 请求参数错误
- `401`: 认证失败
- `404`: 资源不存在
- `500`: 服务器内部错误

---

## 数据模型

### RouteConfig (路由配置)
```typescript
{
  id: number;              // 路由ID
  name: string;            // 路由名称
  description: string;     // 路由描述，默认为空字符串
  utterances: string[];    // 示例语句列表
  score_threshold: number; // 相似度阈值 (0.0-1.0)，默认0.75
}
```

### PredictRequest (预测请求)
```typescript
{
  text: string;  // 待匹配的文本，至少1个字符
}
```

### PredictResponse (预测响应)
```typescript
{
  id: number;        // 匹配到的路由ID
  name: string;      // 匹配到的路由名称
  score?: number;    // 相似度分数（可选）
}
```

### LoginRequest (登录请求)
```typescript
{
  username: string;  // 用户名，至少1个字符
  password: string;  // 密码，至少1个字符
}
```

### LoginResponse (登录响应)
```typescript
{
  api_key: string;  // API密钥
  message: string;  // 提示信息
}
```

### GenerateUtterancesRequest (生成例句请求)
```typescript
{
  id: number;              // Agent (路由) ID
  name: string;            // Agent (路由) 名称
  description?: string;    // Agent 描述，用于引导生成
  count?: number;          // 生成数量 (1-50)，默认 5
  utterances?: string[];   // 参考例句列表
}
```

### Settings (系统设置)
```typescript
{
  // Qdrant配置
  QDRANT_URL: string;
  QDRANT_COLLECTION: string;
  QDRANT_API_KEY?: string | null;
  
  // Embedding模型配置
  HUGGINGFACE_ACCESS_TOKEN?: string | null;  // HuggingFace Access Token（可选）
  HUGGINGFACE_PROVIDER?: string | null;      // 推理服务提供商（可选，如 "nebius"）
  EMBEDDING_MODEL_NAME: string;              // 模型名称
  EMBEDDING_DEVICE: "cpu" | "cuda" | "mps"; // 本地模型使用的设备
  
  // LLM配置（通用）
  LLM_PROVIDER: "deepseek" | "openrouter" | "doubao" | "qwen" | "gemini";
  LLM_API_KEY?: string | null;  // 如果为null，将使用对应provider的默认配置
  LLM_BASE_URL?: string | null;  // Gemini不需要此配置
  LLM_MODEL?: string | null;     // 如果为null，将使用对应provider的默认模型
  LLM_TEMPERATURE: number;       // 温度参数 (0.0-2.0)
  
  // DeepSeek配置（向后兼容）
  DEEPSEEK_API_KEY?: string | null;
  DEEPSEEK_BASE_URL?: string;
  DEEPSEEK_MODEL?: string;
  
  // 提示词配置
  UTTERANCE_GENERATION_PROMPT: string;
  
  // 认证配置
  AUTH_ENABLED: boolean;
  TELESTAR_AUTH_ENABLED: boolean;
  
  // 其他配置
  BATCH_SIZE: number;
  DEFAULT_ROUTE_ID: number;
  DEFAULT_ROUTE_NAME: string;
}
```

