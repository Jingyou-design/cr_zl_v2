# 专利方案分析助手

基于 **DeepSeek** + **LangGraph** 的专利交底书自动生成系统。

支持从专利文档中提取技术特征、生成多种技术方案、进行新颖性/创造性评估，并最终输出完整专利交底书。

---

## 🏗️ 架构概览

| 模块 | 说明 |
|------|------|
| **V2 Agent** (`app/agent_v2/`) | ReAct Agent，驱动 6 步专利分析工作流 |
| **V1 Agent** (`demo_agent.py`) | DeepAgents 框架，专利检索与审查评估 |
| **FastAPI** (`app/main.py`) | HTTP API 服务，SSE 流式响应 |
| **CLI** (`run_v2_cli.py`) | 命令行交互入口 |
| **MinerU** (`app/services/`) | PDF/文档转 Markdown 服务 |

---

## ⚙️ 环境准备

### 1. 安装依赖

```bash
# 使用 uv（推荐）
uv sync

# 或使用 pip
pip install -e .
```

### 2. 配置 API Key

在项目根目录创建 `.env` 文件：

```env
DEEPSEEK_API_KEY=your_deepseek_api_key
MINERU_TOKEN=your_mineru_token
```

> - DeepSeek API Key: https://platform.deepseek.com/
> - MinerU Token: https://mineru.net/

---

## 🚀 运行方式

### 方式一：FastAPI 后端服务

```bash
source .venv/Scripts/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

**API 端点：**

| 方法 | 端点 | 说明 |
|------|------|------|
| POST | `/agent/upload` | 上传文件（PDF/DOC/图片等） |
| POST | `/agent/parse` | MinerU 解析（SSE 流式） |
| POST | `/agent/start` | 启动 Agent 会话（SSE） |
| POST | `/agent/chat` | 继续对话（SSE） |
| POST | `/agent/cleanup` | 清理会话与文件 |
| GET | `/health` | 健康检查 |

文档地址：`http://localhost:8000/docs`

---

### 方式二：命令行交互（V2）

```bash
source .venv/Scripts/activate
python run_v2_cli.py
```

按提示输入专利文档，支持完整的交互式分析流程。

---

### 方式三：V1 专利研究助手

```bash
source .venv/Scripts/activate
python demo_agent.py
```

支持专利检索、IPC 分类查询、X/Y 类文献评估。

---

## 🔄 V2 工作流

```
输入文档
   │
   ▼
┌─────────────────────┐
│ extract_tech_structure │  ← 提取核心/辅助技术特征
└─────────────────────┘
   │
   ▼
用户确认/编辑特征
   │
   ▼
┌─────────────────────┐     ┌─────────────────────┐
│  generate_solutions  │ ──▶ │ evaluate_all_solutions │  ← 并行评估
└─────────────────────┘     └─────────────────────┘
   │
   ▼
用户选择方案
   │
   ├──▶ 生成交底书 ──▶ generate_disclosure
   │
   ├──▶ 改进方案 ──▶ improve_solution ──▶ evaluate_single_solution
   │
   └──▶ 重新生成 ──▶ generate_solutions
```

---

## 📁 项目结构

```
zl_demo_v2/
├── app/
│   ├── agent_v2/           # V2 核心引擎
│   │   ├── agent_core.py     # ReAct Agent + 系统提示词
│   │   ├── agent_tools.py    # 6 个专利分析工具
│   │   ├── agent_session.py  # 会话管理 + 流式接口
│   │   └── agent_format.py   # SSE 事件格式化
│   ├── api/
│   │   └── routes/
│   │       └── agent_v2.py   # FastAPI 路由
│   ├── controller/
│   │   └── report_parser.py  # 评估报告解析
│   ├── services/
│   │   └── mineru_service.py # MinerU 文档解析
│   └── main.py             # FastAPI 入口
├── skills/                 # V1 Agent Skills
│   ├── patenthub/            # 专利检索
│   ├── ipc-search/           # IPC 分类查询
│   └── patent-examination-search/ # 审查评估
├── files/                  # 输出目录
│   ├── mineru_output/
│   └── disclosure_output/
├── demo_agent.py           # V1 入口
├── run_v2_cli.py           # CLI 入口
├── pyproject.toml
└── README.md
```

---

## ⚠️ 注意事项

1. **API 消耗**：`evaluate_all_solutions` 会为每个方案启动子 Agent 调用 DeepSeek API，评估 3 个方案约消耗 3 次对话额度。
2. **内存会话**：当前会话状态保存在内存中，服务重启后丢失。
3. **文件大小**：上传文件限制 50MB。
4. **Python 版本**：要求 Python ≥ 3.12。

---

## 📝 License

MIT
