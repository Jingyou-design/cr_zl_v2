"""
Agent V2 SSE 事件格式化。
将 astream_events 原始事件转换为标准 SSE payload。
与 V1 的 _format_event 类似，但用 panel 替代 interrupt，并增加 tool_start/tool_end。
只转发 V2 核心工具的事件，过滤内部 demo_agent 子工具的噪声。
"""

# V2 核心工具白名单 —— 只转发这些工具的 start/end 事件
_CORE_TOOLS = {
    "extract_tech_structure",
    "generate_solutions",
    "evaluate_all_solutions",
    "improve_solution",
    "evaluate_single_solution",
    "generate_disclosure",
}


def format_event(event: dict) -> dict | None:
    """将 astream_events 原生事件转换为标准 SSE payload。"""
    event_type = event.get("event", "")
    name = event.get("name", "")
    data = event.get("data", {})

    # ---- 过滤噪声 ----
    if event_type in ("on_chain_start", "on_chain_end"):
        return None

    # ---- Agent 文本 token 流式 ----
    if event_type == "on_chat_model_stream":
        chunk = data.get("chunk") if isinstance(data, dict) else None
        if chunk is None:
            return None
        # 跳过 tool_call 类型的 chunk
        tool_calls = getattr(chunk, "tool_calls", None)
        if tool_calls:
            return None
        token = getattr(chunk, "content", "")
        if not token:
            return None
        return {"type": "token", "name": "agent", "data": {"token": token}}

    # ---- 工具调用事件（仅转发核心工具） ----
    if event_type == "on_tool_start":
        if name in _CORE_TOOLS:
            return {"type": "tool_start", "name": name, "data": {}}
        return None

    if event_type == "on_tool_end":
        if name in _CORE_TOOLS:
            return {"type": "tool_end", "name": name, "data": {}}
        return None

    # ---- 自定义事件 ----
    if event_type == "on_custom_event":
        payload = data if isinstance(data, dict) else {}

        if name == "panel":
            panel_type = payload.get("panel_type", "unknown")
            return {"type": "panel", "name": panel_type, "data": payload}

        if name == "progress":
            return {"type": "progress", "name": payload.get("node", ""), "data": payload}

        if name == "token":
            return {
                "type": "token",
                "name": payload.get("node", "disclosure"),
                "data": {"token": payload.get("token", "")},
            }

        if name == "disclosure_done":
            return {"type": "disclosure_done", "name": "disclosure", "data": payload}

        return {"type": "custom", "name": name, "data": payload}

    return None
