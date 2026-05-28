#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Patent Analysis API 全接口测试脚本

运行方式:
    1. 确保服务已启动: uv run python -m uvicorn app.main:app --reload
    2. 运行测试: uv run python test_api.py

每个接口的输出均带有清晰的 [标注]，便于查看和定位。
"""

import json
import tempfile
import time
import uuid
from pathlib import Path

import requests

# ==================== 配置 ====================
BASE_URL = "http://127.0.0.1:8000"
AGENT_V2_URL = f"{BASE_URL}/agent"

# 测试用的专利文档内容
TEST_DOCUMENT = """本方案摒弃了传统多喷头、频繁换喷头、全程带纤维打印的老旧工艺，以极简的单喷头结构实现双模灵活切换，大幅简化设备整体结构、降低设备成本与运维成本。同时，独立双电机供料控制方式，彻底规避了连续纤维待机状态对喷头内部流场及打印稳定性的干扰，具备模式切换高效、控制逻辑简单、成型精度高、稳定性好的优势，可充分满足复杂复合材料构件分区增强、精细化成型的生产需求。"""

# 用于 SSE 流读取的超时设置
SSE_TIMEOUT = 60
SSE_READ_SECONDS = 15  # 每个 SSE 接口最多读取这么多秒的数据

# 存储测试过程中的状态变量
_state = {
    "thread_id": None,
    "file_path": None,
    "filename": None,
}


# ==================== 打印工具 ====================
def print_section(title: str):
    """打印大标题分隔线"""
    print()
    print("=" * 70)
    print(f"  【测试接口】{title}")
    print("=" * 70)


def print_label(label: str, content: str = ""):
    """打印带标签的内容"""
    if content:
        print(f"  [{label}] {content}")
    else:
        print(f"  [{label}]")


def print_json(label: str, data):
    """打印 JSON 格式的数据"""
    print(f"  [{label}]")
    for line in json.dumps(data, ensure_ascii=False, indent=4).splitlines():
        print(f"      {line}")


# ==================== 接口测试函数 ====================

def test_root():
    """测试 1: 首页重定向 /"""
    print_section("GET / — 首页重定向")
    url = f"{BASE_URL}/"
    print_label("请求", f"GET {url}")

    try:
        resp = requests.get(url, allow_redirects=False, timeout=10)
        print_label("HTTP 状态码", str(resp.status_code))
        print_label("响应头 Location", resp.headers.get("Location", "无"))
        if resp.status_code == 307:
            print_label("结果", "✅ 重定向成功，符合预期")
        else:
            print_label("结果", f"⚠️ 状态码异常，期望 307，实际 {resp.status_code}")
    except Exception as e:
        print_label("错误", str(e))


def test_health():
    """测试 2: 健康检查 /health"""
    print_section("GET /health — 健康检查")
    url = f"{BASE_URL}/health"
    print_label("请求", f"GET {url}")

    try:
        resp = requests.get(url, timeout=10)
        print_label("HTTP 状态码", str(resp.status_code))
        print_json("响应体", resp.json())
        if resp.status_code == 200 and resp.json().get("status") == "ok":
            print_label("结果", "✅ 服务健康，运行正常")
        else:
            print_label("结果", f"⚠️ 响应异常")
    except Exception as e:
        print_label("错误", str(e))


def test_upload():
    """测试 3: 文件上传 /agent/upload"""
    print_section("POST /agent/upload — 文件上传")
    url = f"{AGENT_V2_URL}/upload"
    print_label("请求", f"POST {url}")

    # 创建一个临时测试文件
    temp_file = tempfile.NamedTemporaryFile(
        suffix=".txt", delete=False, mode="w", encoding="utf-8"
    )
    temp_file.write(TEST_DOCUMENT)
    temp_file.close()
    file_path = Path(temp_file.name)

    print_label("上传文件", str(file_path))
    print_label("文件内容预览", TEST_DOCUMENT[:50] + "...")

    try:
        with open(file_path, "rb") as f:
            files = {"file": (file_path.name, f, "text/plain")}
            resp = requests.post(url, files=files, timeout=30)

        print_label("HTTP 状态码", str(resp.status_code))
        data = resp.json()
        print_json("响应体", data)

        if resp.status_code == 200:
            _state["thread_id"] = data.get("thread_id")
            _state["file_path"] = data.get("file_path")
            _state["filename"] = data.get("filename")
            print_label("结果", f"✅ 上传成功，thread_id = {_state['thread_id']}")
        else:
            print_label("结果", f"⚠️ 上传失败: {data}")
    except Exception as e:
        print_label("错误", str(e))
    finally:
        # 清理临时文件
        file_path.unlink(missing_ok=True)


def _read_sse(resp, max_seconds: float = SSE_READ_SECONDS, label_prefix: str = "SSE"):
    """辅助函数：从 Response 中读取 SSE 流数据"""
    start_time = time.time()
    buffer_lines = []
    event_count = 0
    heartbeat_count = 0

    for line in resp.iter_lines(decode_unicode=True):
        if time.time() - start_time > max_seconds:
            print_label(f"{label_prefix} 读取状态", f"⏱️ 已达到最大读取时间 {max_seconds}s，停止接收")
            break

        if line is None:
            continue

        # 心跳包
        if line.startswith(": keepalive"):
            heartbeat_count += 1
            continue

        # SSE 数据行
        if line.startswith("data: "):
            buffer_lines.append(line[6:])  # 去掉 "data: " 前缀

        # 空行表示一个事件结束
        if line == "" and buffer_lines:
            event_count += 1
            try:
                payload = json.loads("\n".join(buffer_lines))
                print_json(f"{label_prefix} 事件 #{event_count}", payload)
            except json.JSONDecodeError:
                raw = "\n".join(buffer_lines)
                print_label(f"{label_prefix} 事件 #{event_count} (原始非JSON)", raw[:200])
            buffer_lines = []

    print_label(f"{label_prefix} 统计", f"共接收 {event_count} 个事件，{heartbeat_count} 个心跳包")


def test_parse():
    """测试 4: MinerU 解析 /agent/parse"""
    print_section("POST /agent/parse — MinerU 文档解析 (SSE 流式)")
    url = f"{AGENT_V2_URL}/parse"
    print_label("请求", f"POST {url}")

    if not _state.get("thread_id"):
        print_label("跳过", "未获取到 thread_id，请先运行上传测试")
        return

    payload = {
        "thread_id": _state["thread_id"],
        "file_path": _state["file_path"],
        "filename": _state["filename"],
        "model_version": "vlm",
    }
    print_json("请求体", payload)

    try:
        resp = requests.post(
            url,
            json=payload,
            stream=True,
            timeout=(10, SSE_TIMEOUT),
            headers={"Accept": "text/event-stream"},
        )
        print_label("HTTP 状态码", str(resp.status_code))
        print_label("Content-Type", resp.headers.get("Content-Type", "未知"))

        if resp.status_code == 200:
            _read_sse(resp, label_prefix="解析")
            print_label("结果", "✅ 解析流读取完成")
        else:
            print_label("错误响应", resp.text[:500])
    except Exception as e:
        print_label("错误", str(e))


def test_start():
    """测试 5: 启动 Agent 会话 /agent/start"""
    print_section("POST /agent/start — 启动 Agent 会话 (SSE 流式)")
    url = f"{AGENT_V2_URL}/start"
    print_label("请求", f"POST {url}")

    payload = {
        "document": TEST_DOCUMENT,
        "thread_id": _state.get("thread_id"),
    }
    print_json("请求体", payload)

    try:
        resp = requests.post(
            url,
            json=payload,
            stream=True,
            timeout=(10, SSE_TIMEOUT),
            headers={"Accept": "text/event-stream"},
        )
        print_label("HTTP 状态码", str(resp.status_code))

        if resp.status_code == 200:
            _read_sse(resp, label_prefix="启动")
            print_label("结果", "✅ Agent 启动流读取完成")
        else:
            print_label("错误响应", resp.text[:500])
    except Exception as e:
        print_label("错误", str(e))


def test_chat():
    """测试 6: 继续对话 /agent/chat"""
    print_section("POST /agent/chat — 继续对话 (SSE 流式)")
    url = f"{AGENT_V2_URL}/chat"
    print_label("请求", f"POST {url}")

    if not _state.get("thread_id"):
        # 如果没有 thread_id，自动生成一个
        _state["thread_id"] = f"agent-{uuid.uuid4().hex[:12]}"
        print_label("注意", f"未获取到 thread_id，自动生成测试用 ID: {_state['thread_id']}")

    payload = {
        "thread_id": _state["thread_id"],
        "message": "请帮我分析一下这个方案的核心创新点。",
        "panel_action": None,
    }
    print_json("请求体", payload)

    try:
        resp = requests.post(
            url,
            json=payload,
            stream=True,
            timeout=(10, SSE_TIMEOUT),
            headers={"Accept": "text/event-stream"},
        )
        print_label("HTTP 状态码", str(resp.status_code))

        if resp.status_code == 200:
            _read_sse(resp, label_prefix="对话")
            print_label("结果", "✅ 对话流读取完成")
        else:
            print_label("错误响应", resp.text[:500])
    except Exception as e:
        print_label("错误", str(e))


def test_cleanup():
    """测试 7: 清理会话 /agent/cleanup"""
    print_section("POST /agent/cleanup — 清理会话资源")
    url = f"{AGENT_V2_URL}/cleanup"
    print_label("请求", f"POST {url}")

    if not _state.get("thread_id"):
        print_label("跳过", "未获取到 thread_id，无法执行清理")
        return

    payload = {"thread_id": _state["thread_id"]}
    print_json("请求体", payload)

    try:
        resp = requests.post(url, json=payload, timeout=10)
        print_label("HTTP 状态码", str(resp.status_code))
        print_json("响应体", resp.json())

        if resp.status_code == 200:
            cleaned = resp.json().get("cleaned", [])
            print_label("结果", f"✅ 清理完成，共清理 {len(cleaned)} 项资源: {cleaned}")
        else:
            print_label("结果", f"⚠️ 清理请求异常")
    except Exception as e:
        print_label("错误", str(e))


# ==================== 主流程 ====================
def main():
    print()
    print("╔" + "═" * 68 + "╗")
    print("║" + " " * 15 + "Patent Analysis API 全接口测试" + " " * 23 + "║")
    print("╚" + "═" * 68 + "╝")
    print(f"  服务地址: {BASE_URL}")
    print(f"  测试文档: {TEST_DOCUMENT[:40]}...")

    # 1. 根路径
    test_root()

    # 2. 健康检查
    test_health()

    # 3. 文件上传
    test_upload()

    # 4. MinerU 解析（SSE）
    test_parse()

    # 5. 启动 Agent（SSE）
    test_start()

    # 6. 继续对话（SSE）
    test_chat()

    # 7. 清理会话
    test_cleanup()

    # 总结
    print()
    print("=" * 70)
    print("  【测试完成】")
    print(f"  使用 thread_id: {_state.get('thread_id', '无')}")
    print("=" * 70)
    print()


if __name__ == "__main__":
    main()
