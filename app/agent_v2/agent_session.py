"""
Agent V2 会话状态管理与流式接口。
负责：
1. 维护内存会话存储（业务数据）；
2. 管理 ContextVar 供工具访问当前 thread_id；
3. 提供启动/继续对话的流式生成器。
"""

from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import AsyncGenerator

from langgraph.checkpoint.memory import MemorySaver

from app.agent_v2.agent_format import format_event


# ---------- 会话数据结构 ----------

@dataclass
class AgentSession:
    """单个会话的业务状态（区别于 LangGraph checkpointer 的对话历史）。"""
    thread_id: str
    document: str
    tech_structure: str = ""
    solutions: list = field(default_factory=list)
    current_solution: str = ""
    selected_index: int = -1
    evaluation_report: str = ""
    evaluation_passed: bool = False
    rejection_reason: str = ""
    revision_count: int = 0
    final_disclosure: str = ""
    searched_patents: list = field(default_factory=list)


# ---------- 模块级状态 ----------

_sessions: dict[str, AgentSession] = {}
_checkpointer = MemorySaver()

current_thread_id: ContextVar[str] = ContextVar("current_thread_id", default="")


# ---------- 会话 CRUD ----------

def create_session(thread_id: str, document: str) -> AgentSession:
    """创建新会话并存储。"""
    session = AgentSession(thread_id=thread_id, document=document)
    _sessions[thread_id] = session
    return session


def get_session() -> AgentSession:
    """从 ContextVar 获取当前线程的会话。工具内部调用。"""
    tid = current_thread_id.get()
    if tid not in _sessions:
        raise KeyError(f"会话 {tid} 不存在")
    return _sessions[tid]


def update_session_from_panel(thread_id: str, panel_action: dict) -> None:
    """根据前端面板操作更新会话状态。

    panel_action 格式:
      {"type": "confirm_features", "data": {"tech_structure": "..."}}
      {"type": "select_solution", "data": {"selected_index": 0, "intent": "disclosure"}}
      {"type": "regenerate", "data": {}}
    """
    if thread_id not in _sessions:
        return

    session = _sessions[thread_id]
    action_type = panel_action.get("type", "")
    action_data = panel_action.get("data", {})

    if action_type == "confirm_features":
        tech_structure = action_data.get("tech_structure", "")
        if tech_structure:
            session.tech_structure = tech_structure

    elif action_type == "select_solution":
        selected_index = action_data.get("selected_index", -1)
        intent = action_data.get("intent", "disclosure")
        if 0 <= selected_index < len(session.solutions):
            session.selected_index = selected_index
            session.current_solution = session.solutions[selected_index].get("content", "")

    elif action_type == "regenerate":
        # 无需改状态，agent 会重新调用 generate_solutions
        pass



def delete_session(thread_id: str) -> None:
    """删除会话。"""
    _sessions.pop(thread_id, None)


def get_checkpointer() -> MemorySaver:
    """获取共享 checkpointer 实例。"""
    return _checkpointer


# ---------- 核心流式接口 ----------

async def stream_agent_start(
    document: str,
    thread_id: str,
) -> AsyncGenerator[dict, None]:
    """启动新会话，流式返回所有事件。"""
    from app.agent_v2.agent_core import get_agent

    create_session(thread_id, document)
    current_thread_id.set(thread_id)

    agent = get_agent()
    config = {"configurable": {"thread_id": thread_id}}

    initial_message = (
        "请分析以下专利文档，提取技术特征并生成技术方案。\n\n"
        f"【专利文档内容】\n{document}"
    )

    yield {"type": "meta", "name": "thread_id", "data": {"thread_id": thread_id}}

    async for event in agent.astream_events(
        {"messages": [{"role": "user", "content": initial_message}]},
        config,
        version="v2",
    ):
        formatted = format_event(event)
        if formatted is not None:
            yield formatted


async def stream_agent_chat(
    thread_id: str,
    message: str,
    panel_action: dict | None = None,
) -> AsyncGenerator[dict, None]:
    """继续对话，流式返回所有事件。"""
    from app.agent_v2.agent_core import get_agent

    if panel_action:
        update_session_from_panel(thread_id, panel_action)

    # 防御：内存会话可能因服务重启丢失，提前给出友好提示
    if thread_id not in _sessions:
        yield {
            "type": "error",
            "name": "",
            "data": {"message": f"会话 {thread_id} 已过期，请返回首页重新上传文档开始分析。"},
        }
        return

    current_thread_id.set(thread_id)

    agent = get_agent()
    config = {"configurable": {"thread_id": thread_id}}

    async for event in agent.astream_events(
        {"messages": [{"role": "user", "content": message}]},
        config,
        version="v2",
    ):
        formatted = format_event(event)
        if formatted is not None:
            yield formatted
