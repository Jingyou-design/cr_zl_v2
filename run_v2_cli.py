#!/usr/bin/env python3
"""
专利方案分析助手 — 命令行交互式入口（V2）。

使用方式：
    source .venv/Scripts/activate
    python run_v2_cli.py

流程：
    输入文档 → 提取技术特征 → 生成并评估方案 → 生成交底书
"""

import asyncio
import json
import sys
import uuid
from pathlib import Path

# 确保项目根目录在路径中
_PROJECT_ROOT = Path(__file__).resolve().parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from app.agent_v2.agent_session import (
    stream_agent_start,
    stream_agent_chat,
    update_session_from_panel,
    get_session,
)


def print_section(title: str):
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def print_json_pretty(obj):
    print(json.dumps(obj, ensure_ascii=False, indent=2))


async def collect_events(gen):
    """收集异步生成器的所有事件。"""
    events = []
    async for ev in gen:
        events.append(ev)
        # 实时打印 token
        if ev.get("type") == "token":
            token = ev.get("data", {}).get("token", "")
            print(token, end="", flush=True)
        elif ev.get("type") == "tool_start":
            print(f"\n[工具启动: {ev.get('name', '')}]")
        elif ev.get("type") == "tool_end":
            print(f"\n[工具完成: {ev.get('name', '')}]")
    return events


def extract_panel(events, panel_name: str):
    """从事件列表中提取指定 panel。"""
    for ev in events:
        if ev.get("type") == "panel" and ev.get("name") == panel_name:
            return ev.get("data", {})
    return {}


async def main():
    print_section("专利方案分析助手 V2")
    print("请输入专利文档内容（多行输入，输入 END 结束）：")

    lines = []
    while True:
        try:
            line = input()
        except EOFError:
            break
        if line.strip() == "END":
            break
        lines.append(line)

    document = "\n".join(lines).strip()
    if not document:
        print("文档为空，退出。")
        return

    thread_id = f"cli-{uuid.uuid4().hex[:8]}"

    # ========== 步骤 1: 提取技术特征 ==========
    print_section("步骤 1：提取技术特征")
    print("正在分析文档，请稍候...\n")

    events = await collect_events(stream_agent_start(document, thread_id))

    panel = extract_panel(events, "extract_review")
    tech_structure = panel.get("content", "")

    if not tech_structure:
        # 兜底
        try:
            tech_structure = get_session().tech_structure
        except Exception:
            pass

    if not tech_structure:
        print("❌ 技术特征提取失败。")
        return

    print("\n提取结果：")
    print_json_pretty(json.loads(tech_structure))

    print("\n可编辑以上 JSON（确认直接回车，修改请输入完整 JSON）：")
    edited = input("> ").strip()
    if edited:
        try:
            json.loads(edited)
            tech_structure = edited
        except json.JSONDecodeError:
            print("输入不是合法 JSON，使用原始结果。")

    # ========== 步骤 2: 生成方案并评估 ==========
    print_section("步骤 2：生成技术方案并评估")
    print("正在生成方案，请稍候（可能需要几分钟）...\n")

    update_session_from_panel(
        thread_id,
        {"type": "confirm_features", "data": {"tech_structure": tech_structure}}
    )

    events = await collect_events(stream_agent_chat(
        thread_id,
        "请确认以上技术特征并生成技术方案。",
        panel_action={"type": "confirm_features", "data": {"tech_structure": tech_structure}},
    ))

    panel = extract_panel(events, "solution_review")
    solutions = []
    if panel:
        try:
            solutions = json.loads(panel.get("solutions_json", "[]"))
        except Exception:
            pass

    if not solutions:
        try:
            solutions = get_session().solutions
        except Exception:
            pass

    if not solutions:
        print("❌ 方案生成失败。")
        return

    print(f"\n✅ 已生成并评估 {len(solutions)} 个方案：\n")
    for idx, sol in enumerate(solutions):
        passed = sol.get("passed", False)
        status = "✅ 通过" if passed else "❌ 不通过"
        print(f"  方案 {idx + 1}: {sol.get('title', f'方案{idx+1}')} — {status}")
        print(f"    内容：{sol.get('content', '')[:120]}...")
        if sol.get("reason"):
            print(f"    原因：{sol['reason']}")
        print()

    # ========== 步骤 3: 选择操作 ==========
    while True:
        print_section("步骤 3：选择下一步操作")
        print("  1. 生成交底书")
        print("  2. 改进方案")
        print("  3. 重新生成方案")
        print("  4. 退出")

        choice = input("请选择 (1-4): ").strip()

        if choice == "4":
            print("再见！")
            break

        if choice == "3":
            print("\n正在重新生成方案...")
            events = await collect_events(stream_agent_chat(
                thread_id, "请重新生成技术方案。", panel_action={"type": "regenerate", "data": {}}
            ))
            panel = extract_panel(events, "solution_review")
            if panel:
                try:
                    solutions = json.loads(panel.get("solutions_json", "[]"))
                except Exception:
                    pass
            if not solutions:
                try:
                    solutions = get_session().solutions
                except Exception:
                    pass
            print(f"\n✅ 已重新生成 {len(solutions)} 个方案。")
            continue

        # 选择方案
        print(f"\n可用方案 (1-{len(solutions)}):")
        for idx, sol in enumerate(solutions):
            status = "✅" if sol.get("passed") else "❌"
            print(f"  {idx + 1}. {status} {sol.get('title', f'方案{idx+1}')}")

        idx_str = input(f"请选择方案编号 (1-{len(solutions)}): ").strip()
        try:
            selected = int(idx_str) - 1
            if not (0 <= selected < len(solutions)):
                print("无效编号。")
                continue
        except ValueError:
            print("无效输入。")
            continue

        # 同步 session 状态
        try:
            session = get_session()
            sol = session.solutions[selected]
            session.current_solution = sol.get("content", "")
            session.evaluation_report = sol.get("report", "")
            session.rejection_reason = sol.get("reason", "")
            session.selected_index = selected
        except Exception:
            pass

        update_session_from_panel(
            thread_id,
            {"type": "select_solution", "data": {"selected_index": selected, "intent": "disclosure" if choice == "1" else "improve"}}
        )

        if choice == "1":
            print_section("步骤 4：生成交底书")
            print("正在撰写交底书，请稍候...\n")

            events = await collect_events(stream_agent_chat(
                thread_id,
                f"请为方案{selected + 1}生成交底书。",
                panel_action={"type": "select_solution", "data": {"selected_index": selected, "intent": "disclosure"}},
            ))

            # 收集 disclosure_done
            disclosure_text = ""
            for ev in events:
                if ev.get("type") == "disclosure_done":
                    disclosure_text = ev["data"].get("file_path", "")
                if ev.get("type") == "token" and ev.get("name") == "disclosure":
                    disclosure_text += ev["data"].get("token", "")

            if not disclosure_text:
                try:
                    disclosure_text = get_session().final_disclosure
                except Exception:
                    pass

            if disclosure_text:
                print("\n✅ 交底书已生成！")
                print(f"\n{disclosure_text[:800]}...")
                print("\n完整内容已保存。")
            else:
                print("❌ 交底书生成失败。")

            break

        elif choice == "2":
            print(f"\n正在改进方案 {selected + 1}...")
            events = await collect_events(stream_agent_chat(
                thread_id,
                f"请改进方案{selected + 1}。",
                panel_action={"type": "select_solution", "data": {"selected_index": selected, "intent": "improve"}},
            ))

            try:
                session = get_session()
                if session.current_solution and 0 <= selected < len(session.solutions):
                    session.solutions[selected]["content"] = session.current_solution
                    session.solutions[selected]["report"] = session.evaluation_report
                    session.solutions[selected]["passed"] = session.evaluation_passed
                    session.solutions[selected]["reason"] = session.rejection_reason
                solutions = session.solutions
                print(f"\n✅ 方案 {selected + 1} 已改进并重新评估。")
                status = "通过" if solutions[selected].get("passed") else "不通过"
                print(f"   新评估结果：{status}")
            except Exception as e:
                print(f"改进完成，但状态同步异常：{e}")


if __name__ == "__main__":
    asyncio.run(main())
