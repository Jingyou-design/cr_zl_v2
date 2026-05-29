"""
专利评估子代理（CompiledSubAgent）。

封装专利审查检索、新颖性/创造性评估逻辑，供 V2 主 Agent 并行调用。
替代原来在 agent_tools.py 中手动 from demo_agent import build_agent 的方式。
"""

from pathlib import Path

from dotenv import load_dotenv
from langchain_deepseek import ChatDeepSeek
from langgraph.checkpoint.memory import MemorySaver

from deepagents import CompiledSubAgent
from deepagents.backends import LocalShellBackend
from deepagents.graph import create_agent
from deepagents.middleware import FilesystemMiddleware, SkillsMiddleware
from langchain.agents.middleware import TodoListMiddleware

load_dotenv()

_ROOT_DIR = Path(__file__).resolve().parent.parent.parent
_SKILLS_DIR = _ROOT_DIR / "skills"

_EVAL_SYSTEM_PROMPT = """您是一位专业的专利研究助理。
您能够使用文件系统工具（读取文件、写入文件、列出文件、通配符匹配、查找）和执行 shell 命令，此外还具备以下技能：
- 专利中心：通过 PatentHub API 搜索专利、获取专利信息以及查询法律状态。
- 国际专利分类搜索：从本地的 IPC 2026.01 树中查询国际专利分类号、层级结构和定义。
- 专利审查搜索：进行系统的专利审查搜索以评估新颖性和创造性步骤，并对检索到的文件进行分类（X、Y、A、E 等）。
当用户询问专利检索、专利详情或法律状态时，请使用 patenthub 技能。
当用户询问国际专利分类（IPC）分类、IPC 代码或技术主题与 IPC 符号的映射时，请使用 ipc-search 技能，访问 skills/ipc-search/references/IPC_Tree/。
当用户询问审查检索、新颖性评估、创造性步骤评估、现有技术策略或 X/Y 类文献检索时，请使用专利审查检索技能。
始终要简洁明了、条理清晰地回答问题。
重要提示：使用 glob 工具时，pattern 必须是相对路径（如 **/*.json），切勿使用绝对路径。
"""


def build_eval_subagent_graph():
    """构建并返回一个新的专利评估子代理 graph 实例。

    每次调用创建全新的实例（含独立 MemorySaver），支持并发安全评估。
    """
    backend = LocalShellBackend(
        root_dir=_ROOT_DIR, inherit_env=True, virtual_mode=False
    )
    fs_middleware = FilesystemMiddleware(backend=backend)
    skills_middleware = SkillsMiddleware(
        backend=backend,
        sources=[str(_SKILLS_DIR)],
    )

    agent = create_agent(
        model=ChatDeepSeek(
            model="deepseek-v4-flash",
            extra_body={"thinking": {"type": "disabled"}},
        ),
        system_prompt=_EVAL_SYSTEM_PROMPT,
        middleware=[fs_middleware, skills_middleware, TodoListMiddleware()],
        checkpointer=MemorySaver(),
        name="patent-evaluator",
    )
    return agent


# CompiledSubAgent 实例，供 create_deep_agent 注册使用
eval_subagent = CompiledSubAgent(
    name="patent-evaluator",
    description="Conducts patent examination search and evaluates novelty/creativity of a technical solution. Use when you need to assess whether a patent solution is novel and inventive.",
    runnable=build_eval_subagent_graph(),
)
