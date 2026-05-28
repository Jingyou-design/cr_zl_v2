"""
Agent V2 核心模块。
创建 DeepAgents Agent 实例 + 系统提示词，注册专利评估子代理。
"""

import warnings

warnings.filterwarnings("ignore", category=DeprecationWarning, module="langgraph")

from dotenv import load_dotenv
from langchain_deepseek import ChatDeepSeek
from langgraph.checkpoint.memory import MemorySaver

load_dotenv()

from app.agent_v2.agent_tools import (
    extract_tech_structure,
    generate_solutions,
    evaluate_all_solutions,
    improve_solution,
    evaluate_single_solution,
    generate_disclosure,
)
from app.agent_v2.eval_subagent import eval_subagent


# ---------- 系统提示词 ----------

SYSTEM_PROMPT = """你是一位专业的专利方案分析助手，帮助用户从专利文档中提取技术特征、生成技术方案、评估方案并生成交底书。

## 可用工具

1. extract_tech_structure — 从专利文档中提取核心技术特征和辅助技术特征
2. generate_solutions — 基于确认的技术结构生成多个技术方案
3. evaluate_all_solutions — 并行评估所有方案的专利新颖性和创造性
4. improve_solution — 根据评估反馈改进当前方案
5. evaluate_single_solution — 评估改进后的单个方案
6. generate_disclosure — 生成专利交底书并保存

此外，你还可以通过 task() 工具委托专利评估子代理（patent-evaluator）进行专利审查检索。

## 标准工作流

当收到新的专利文档分析请求时，按以下顺序执行：

1. 调用 extract_tech_structure 提取技术特征
2. 【必须停止】向用户展示提取结果，等待用户确认或修改。绝不能在用户确认前调用 generate_solutions。
3. 用户确认后，调用 generate_solutions 生成方案
4. 立即自动调用 evaluate_all_solutions 评估所有方案（生成和评估之间不需要用户确认）
5. 【必须停止】向用户展示评估结果，等待用户选择操作。绝不能自动选择方案或生成交底书。
6. 根据用户选择：
   - 生成交底书：调用 generate_disclosure
   - 改进方案：调用 improve_solution，然后自动调用 evaluate_single_solution
   - 重新生成方案：调用 generate_solutions，然后自动调用 evaluate_all_solutions
7. evaluate_single_solution 评估完成后【必须停止】，等待用户决策。绝不能自动执行下一步。

## 关键规则

- 调用 extract_tech_structure 后，你必须向用户展示结果并等待确认。**绝不能**自动调用 generate_solutions。
- 调用 evaluate_all_solutions 后，你必须向用户展示评估结果并等待选择。**绝不能**自动选择方案或生成交底书。
- 调用 evaluate_single_solution 后，你必须展示评估结果并等待决策。**绝不能**自动执行下一步。
- 只有在用户明确要求时才执行下一步操作。
- generate_solutions 和 evaluate_all_solutions 应该连续调用，中间不需要用户确认。
- improve_solution 和 evaluate_single_solution 应该连续调用，中间不需要用户确认。

## 回复格式（极其重要）

- **绝不要**在回复中重复工具返回的原始数据（如 JSON 数组、技术特征列表、方案全文、评估报告原文等）。
- 你的回复应该是一两句简短的说明，例如：
  - "技术特征已提取，请确认或修改。"（不要重复列出特征内容）
  - "已生成方案并完成评估，请查看结果。"（不要重复列出方案和评估内容）
  - "改进方案评估完成，请查看结果。"（不要重复评估报告）
  - "交底书已生成。"（不要重复交底书全文）
- 前端会自动展示结构化的面板（特征编辑器、方案卡片等），你不需要在文本中重复这些信息。
- 保持回复极简，一两句话即可。
"""


# ---------- Agent 构建 ----------

_checkpointer = MemorySaver()


def build_patent_agent():
    """构建并返回 DeepAgents Agent 实例。"""
    llm = ChatDeepSeek(
        model="deepseek-v4-pro",
        extra_body={"thinking": {"type": "disabled"}},
        temperature=0.5,
    )

    tools = [
        extract_tech_structure,
        generate_solutions,
        evaluate_all_solutions,
        improve_solution,
        evaluate_single_solution,
        generate_disclosure,
    ]

    from deepagents import create_deep_agent

    agent = create_deep_agent(
        model=llm,
        tools=tools,
        system_prompt=SYSTEM_PROMPT,
        subagents=[eval_subagent],
        checkpointer=_checkpointer,
        name="patent-analysis-agent-v2",
    )
    return agent


# ---------- 单例 ----------

_agent = None


def get_agent():
    """获取 Agent 单例。"""
    global _agent
    if _agent is None:
        _agent = build_patent_agent()
    return _agent
