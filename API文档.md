# Patent Analysis API 接口文档

> **版本**: 0.1.0  
> **基础地址**: `/`  
> **描述**: AI 驱动的专利方案分析与交底书生成系统

---

## 目录

- [通用说明](#通用说明)
- [接口列表](#接口列表)
  - [1. 首页重定向](#1-首页重定向)
  - [2. 健康检查](#2-健康检查)
  - [3. 文件上传](#3-文件上传)
  - [4. MinerU 解析](#4-mineru-解析)
  - [5. 启动 Agent 会话](#5-启动-agent-会话)
  - [6. 继续对话](#6-继续对话)
  - [7. 清理会话](#7-清理会话)
- [数据模型](#数据模型)
- [SSE 流式响应说明](#sse-流式响应说明)
- [错误码](#错误码)

---

## 通用说明

### CORS

服务已开启跨域支持，允许所有来源访问：
- `allow_origins: ["*"]`
- `allow_methods: ["*"]`
- `allow_headers: ["*"]`

### 静态资源

| 路径 | 说明 |
|------|------|
| `/static/*` | 前端静态页面 |
| `/files/*` | 上传的文件及生成结果 |

---

## 接口列表

### 1. 首页重定向

**请求方式**: `GET`

**请求路径**: `/`

**功能说明**: 将请求重定向到前端页面 `/static/agent_v2.html`。

**响应示例**:
```http
HTTP/1.1 307 Temporary Redirect
Location: /static/agent_v2.html
```

---

### 2. 健康检查

**请求方式**: `GET`

**请求路径**: `/health`

**功能说明**: 检查服务运行状态。

**响应参数**:

| 字段 | 类型 | 说明 |
|------|------|------|
| status | string | 服务状态，正常返回 `"ok"` |

**响应示例**:
```json
{
  "status": "ok"
}
```

---

### 3. 文件上传

**请求方式**: `POST`

**请求路径**: `/agent/upload`

**Content-Type**: `multipart/form-data`

**功能说明**: 上传文件到服务器，返回线程 ID 和文件路径。

**请求参数**:

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| file | File | 是 | 要上传的文件 |

**支持文件类型**:

`.pdf`, `.doc`, `.docx`, `.ppt`, `.pptx`, `.xls`, `.xlsx`, `.png`, `.jpg`, `.jpeg`, `.gif`, `.bmp`, `.webp`

**文件大小限制**: 最大 `50MB`

**响应参数**:

| 字段 | 类型 | 说明 |
|------|------|------|
| thread_id | string | 会话线程 ID，格式为 `agent-{12位十六进制}` |
| filename | string | 原始文件名 |
| file_path | string | 文件在服务器上的绝对路径 |
| file_size | integer | 文件大小（字节） |

**响应示例**:
```json
{
  "thread_id": "agent-04cb1b4d487f",
  "filename": "patent.pdf",
  "file_path": "F:/python-ai/zl_demo_v2/files/agent-04cb1b4d487f/patent.pdf",
  "file_size": 1024576
}
```

**错误响应**:

| HTTP 状态码 | 说明 |
|-------------|------|
| 400 | 不支持的文件类型 |
| 413 | 文件大小超过 50MB 限制 |

---

### 4. MinerU 解析

**请求方式**: `POST`

**请求路径**: `/agent/parse`

**Content-Type**: `application/json`

**功能说明**: 提交文件到 MinerU 服务进行 Markdown 转换，以 **SSE（Server-Sent Events）** 形式流式返回解析进度和结果。

**请求参数**:

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| thread_id | string | 是 | 会话线程 ID |
| file_path | string | 是 | 要解析的文件路径 |
| filename | string | 是 | 文件名 |
| model_version | string | 否 | 模型版本，默认 `"vlm"` |

**请求示例**:
```json
{
  "thread_id": "agent-04cb1b4d487f",
  "file_path": "F:/python-ai/zl_demo_v2/files/agent-04cb1b4d487f/patent.pdf",
  "filename": "patent.pdf",
  "model_version": "vlm"
}
```

**响应格式**: `text/event-stream`

SSE 数据流格式参见 [SSE 流式响应说明](#sse-流式响应说明)。

**响应头**:
```http
Content-Type: text/event-stream
Cache-Control: no-cache
Connection: keep-alive
X-Accel-Buffering: no
```

---

### 5. 启动 Agent 会话

**请求方式**: `POST`

**请求路径**: `/agent/start`

**Content-Type**: `application/json`

**功能说明**: 启动 Agent 会话，以 **SSE** 形式流式返回分析事件。

**请求参数**:

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| document | string | 是 | 待分析的文档内容（Markdown 文本） |
| thread_id | string | 否 | 指定会话线程 ID；不传则自动生成 |

**请求示例**:
```json
{
  "document": "# 专利说明\n\n本发明涉及一种...",
  "thread_id": "agent-04cb1b4d487f"
}
```

**响应格式**: `text/event-stream`

SSE 数据流格式参见 [SSE 流式响应说明](#sse-流式响应说明)。

**响应头**:
```http
Content-Type: text/event-stream
Cache-Control: no-cache
Connection: keep-alive
X-Accel-Buffering: no
```

---

### 6. 继续对话

**请求方式**: `POST`

**请求路径**: `/agent/chat`

**Content-Type**: `application/json`

**功能说明**: 在已有会话中继续对话，以 **SSE** 形式流式返回事件。

**请求参数**:

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| thread_id | string | 是 | 会话线程 ID |
| message | string | 是 | 用户发送的消息内容 |
| panel_action | PanelAction | 否 | 面板操作指令 |

**PanelAction 结构**:

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| type | string | 是 | 操作类型：`"confirm_features"` / `"select_solution"` / `"regenerate"` |
| data | object | 否 | 操作附加数据，默认为 `{}` |

**请求示例**:
```json
{
  "thread_id": "agent-04cb1b4d487f",
  "message": "请帮我生成交底书",
  "panel_action": {
    "type": "confirm_features",
    "data": {
      "features": ["特征A", "特征B"]
    }
  }
}
```

**错误响应**:

| HTTP 状态码 | 说明 |
|-------------|------|
| 400 | `thread_id` 不能为空 |

**响应格式**: `text/event-stream`

SSE 数据流格式参见 [SSE 流式响应说明](#sse-流式响应说明)。

---

### 7. 清理会话

**请求方式**: `POST`

**请求路径**: `/agent/cleanup`

**Content-Type**: `application/json`

**功能说明**: 清理会话相关资源，包括上传文件、MinerU 输出、交底书输出、Agent 会话状态。

**请求参数**:

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| thread_id | string | 是 | 要清理的会话线程 ID |

**请求示例**:
```json
{
  "thread_id": "agent-04cb1b4d487f"
}
```

**响应参数**:

| 字段 | 类型 | 说明 |
|------|------|------|
| thread_id | string | 被清理的会话线程 ID |
| cleaned | string[] | 已清理的资源类型列表 |

**cleaned 取值说明**:

| 值 | 说明 |
|----|------|
| `upload` | 上传的原始文件目录 |
| `mineru_output` | MinerU 解析输出目录 |
| `disclosure_output` | 生成的交底书文件 |
| `agent_session` | Agent 会话状态 |

**响应示例**:
```json
{
  "thread_id": "agent-04cb1b4d487f",
  "cleaned": ["upload", "mineru_output", "disclosure_output", "agent_session"]
}
```

**错误响应**:

| HTTP 状态码 | 说明 |
|-------------|------|
| 400 | 无效的 `thread_id`（必须以 `agent-` 开头） |

---

## 数据模型

### StartRequest

```json
{
  "document": "string",   // 必填，文档内容
  "thread_id": "string"   // 可选，会话线程 ID
}
```

### ChatRequest

```json
{
  "thread_id": "string",      // 必填
  "message": "string",        // 必填，用户消息
  "panel_action": {            // 可选
    "type": "string",         // confirm_features / select_solution / regenerate
    "data": {}                // 可选，附加数据
  }
}
```

### ParseRequest

```json
{
  "thread_id": "string",      // 必填
  "file_path": "string",      // 必填
  "filename": "string",       // 必填
  "model_version": "string"   // 可选，默认 "vlm"
}
```

### CleanupRequest

```json
{
  "thread_id": "string"       // 必填
}
```

---

## SSE 流式响应说明

以下接口使用 **Server-Sent Events (SSE)** 返回流式数据：

- `POST /agent/parse`
- `POST /agent/start`
- `POST /agent/chat`

### 数据格式

每条消息以 `data:` 开头，以两个换行符 `\n\n` 结束：

```
data: {"type": "...", "name": "...", "data": {...}}\n\n
```

### 通用 Payload 结构

```json
{
  "type": "string",
  "name": "string",
  "data": {}
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| type | string | 事件类型，如 `thought`, `tool_call`, `panel`, `error` 等 |
| name | string | 事件名称/标识 |
| data | object | 事件具体数据 |

### 心跳包

在 `/agent/parse` 接口中，服务端会发送心跳包以保持连接：

```
: keepalive\n\n
```

### 错误事件

当流式处理发生异常时，会返回 `type` 为 `error` 的事件：

```json
{
  "type": "error",
  "name": "",
  "data": {
    "message": "错误描述信息"
  }
}
```

---

## 错误码

| HTTP 状态码 | 含义 | 常见场景 |
|-------------|------|----------|
| 200 | 成功 | 请求正常处理 |
| 307 | 临时重定向 | 访问 `/` 重定向到前端页面 |
| 400 | 请求参数错误 | 文件类型不支持、thread_id 无效、缺少必填参数 |
| 413 | 请求实体过大 | 上传文件超过 50MB |

---

## 接口调用流程示例

### 典型使用流程

```
1. POST /agent/upload      → 上传专利文件，获取 thread_id
2. POST /agent/parse       → 解析文件为 Markdown（SSE 流式返回）
3. POST /agent/start       → 启动 Agent 分析（SSE 流式返回）
4. POST /agent/chat        → 用户交互、确认方案（SSE 流式返回）
5. POST /agent/cleanup     → 分析完成，清理资源
```

---

*文档生成时间: 2026-05-28*
