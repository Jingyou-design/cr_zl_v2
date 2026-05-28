"""
Agent V2 工具定义。
6 个工具：extract_tech_structure, generate_solutions, evaluate_all_solutions,
improve_solution, evaluate_single_solution, generate_disclosure。
每个工具从 session 读取输入、写入结果、dispatch_custom_event 通知前端。
"""

import asyncio
import json
import re
import sys
import uuid
from pathlib import Path

from langchain_core.callbacks import dispatch_custom_event
from langchain_core.tools import tool
from langchain_deepseek import ChatDeepSeek
from dotenv import load_dotenv

load_dotenv()

# 确保项目根目录在路径中
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from app.agent_v2.agent_session import get_session, current_thread_id
from app.controller.report_parser import parse_evaluation_report

# ---------- LLM 实例 ----------

_llm = ChatDeepSeek(
    model="deepseek-v4-pro",
    extra_body={"thinking": {"type": "disabled"}},
    temperature=0.5,
)

_llm_creative = ChatDeepSeek(
    model="deepseek-v4-pro",
    extra_body={"thinking": {"type": "disabled"}},
    temperature=1,
)

_llm_zero = ChatDeepSeek(
    model="deepseek-v4-pro",
    extra_body={"thinking": {"type": "disabled"}},
    temperature=0,
)

OUTPUT_DIR = Path(__file__).resolve().parent.parent.parent / "files" / "disclosure_output"


# ---------- 工具函数 ----------

def _try_parse_json(text: str) -> str:
    """尝试从 LLM 输出中提取 JSON 字符串。"""
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        filtered = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(filtered).strip()
    try:
        obj = json.loads(text)
        return json.dumps(obj, ensure_ascii=False)
    except json.JSONDecodeError:
        return text


def _parse_solutions(text: str) -> list[dict]:
    """从 LLM 输出中解析方案列表。"""
    text = text.strip()
    try:
        obj = json.loads(text)
        if isinstance(obj, list):
            solutions = []
            for item in obj:
                if isinstance(item, dict) and "content" in item:
                    solutions.append({
                        "title": item.get("title", ""),
                        "content": item["content"],
                    })
                elif isinstance(item, str):
                    solutions.append({"title": "", "content": item})
            if solutions:
                return solutions
    except json.JSONDecodeError:
        pass
    # Fallback: 按 ### / ## 方案标题拆分
    headers = list(re.finditer(r"(?:###|##)\s*方案\s*\d*[：:]*", text))
    if headers:
        solutions = []
        for i, header in enumerate(headers):
            start = header.end()
            end = headers[i + 1].start() if i + 1 < len(headers) else len(text)
            content = text[start:end].strip()
            if content:
                solutions.append({"title": f"方案{i + 1}", "content": content})
        if solutions:
            return solutions
    if text:
        return [{"title": "方案1", "content": text}]
    return []


async def _stream_llm(prompt: str, llm=None) -> str:
    """调用 LLM 流式生成并收集完整输出。"""
    if llm is None:
        llm = _llm
    chunks = []
    async for chunk in llm.astream(prompt):
        content = getattr(chunk, "content", str(chunk))
        if content:
            chunks.append(content)
    return "".join(chunks)


# ---------- 工具 1: 提取技术特征 ----------

@tool
async def extract_tech_structure() -> str:
    """从专利文档中提取核心技术特征和辅助技术特征。
    调用后必须向用户展示提取结果并等待确认，不能自动调用 generate_solutions。"""
    session = get_session()
    document = session.document

    prompt = f"""请从以下专利文档中提取技术特征，以 JSON 格式输出。

文档内容：
{document}

请严格按以下 JSON 格式输出（不要加 markdown 代码块标记）：
{{
  "tech_features": ["核心技术特征1", "核心技术特征2", ...],
  "auxiliary_features": ["辅助技术特征1", ...]
}}

字段说明：
- tech_features：核心技术特征，指发明的关键结构、方法步骤、连接关系、控制逻辑等，是发明区别于现有技术的本质特征。必须提取。
- auxiliary_features：辅助技术特征，指对核心技术特征起支撑、优化作用的次级结构或步骤。如果没有明显可区分的辅助特征，填空数组 []。

注意：
- 只能写技术特征（结构/方法/关系），绝不能写效果或优点。
- auxiliary_features 可以为空数组，不要强行凑数。

只输出 JSON，不要有多余解释。"""

    raw = await _stream_llm(prompt)
    result = _try_parse_json(raw)
    session.tech_structure = result

    dispatch_custom_event("panel", {
        "panel_type": "extract_review",
        "content": result,
        "message": "请确认或修改提取的技术结构",
    })

    return "技术特征提取完成，请向用户展示结果并等待确认。绝不能在用户确认前自动调用 generate_solutions。"


# ---------- 工具 2: 生成技术方案 ----------

@tool
async def generate_solutions() -> str:
    """基于确认的技术结构生成多个技术方案。
    生成后应自动调用 evaluate_all_solutions 进行评估，不需要用户确认。"""
    session = get_session()
    tech_structure = session.tech_structure

    prompt = f"""你是一个专利工程师。请基于以下技术结构生成多个技术方案，方案必须紧扣 tech_features 中的核心技术特征，可适当利用 auxiliary_features 中的辅助特征。不要引入未列出的特征，只描述核心发明点和关键实现方式。

技术结构：
{tech_structure}

请严格按以下 JSON 格式输出（不要加 markdown 代码块标记）：
[
  {{"title": "方案1", "content": "方案1的详细描述..."}},
  {{"title": "方案2", "content": "方案2的详细描述..."}},
  {{"title": "方案3", "content": "方案3的详细描述..."}}
]

生成3-4个方案，每个方案的 content 应包含核心发明点和关键实现方式，200字以内。
只输出 JSON 数组，不要有多余解释。"""

    raw = await _stream_llm(prompt, llm=_llm_creative)
    parsed = _try_parse_json(raw)
    solutions = _parse_solutions(parsed)

    if not solutions:
        solutions = [{"title": "方案1", "content": parsed or "无方案"}]

    session.solutions = solutions
    session.current_solution = ""
    session.selected_index = -1

    return f"已生成 {len(solutions)} 个技术方案，请继续调用 evaluate_all_solutions 进行评估。"


# ---------- 工具 3: 并行评估所有方案 ----------

async def _eval_one(index: int, solution: str) -> dict:
    """评估单个方案（内部函数，供并行调用）。
    使用正式的 CompiledSubAgent（patent-evaluator）替代手动构建的 demo_agent。
    """
    from app.agent_v2.eval_subagent import build_eval_subagent_graph

    eval_thread_id = f"sub-eval-{uuid.uuid4().hex[:8]}"
    agent = build_eval_subagent_graph()
    config = {"configurable": {"thread_id": eval_thread_id}}

    eval_prompt = f"""请对以下技术方案进行专利审查检索和新颖性/创造性评估。
                请使用 patenthub 技能进行现有技术检索，使用专利审查检索技能评估 X/Y 类文献。

                待评估方案：
                {solution}

                请输出：
                1) 检索策略；
                2) 对比文件列表；
                3) 新颖性结论；
                4) 创造性结论。

                最后请明确给出：【评估结果：通过 / 不通过】，如果不通过请说明具体原因及改进方向。
                """

    result = await agent.ainvoke(
        {"messages": [{"role": "user", "content": eval_prompt}]},
        config=config,
    )

    messages = result.get("messages", [])
    assistant_msgs = [m for m in messages if getattr(m, "type", None) == "ai"]
    report = ""
    if assistant_msgs:
        report = getattr(assistant_msgs[-1], "content", str(assistant_msgs[-1]))
    else:
        report = str(result)

    return {"index": index, "report": report}


@tool
async def evaluate_all_solutions() -> str:
    """并行评估所有技术方案的专利新颖性和创造性。
    调用后必须向用户展示评估结果并等待选择，不能自动执行下一步。"""
    session = get_session()
    solutions = session.solutions
    thread_id = current_thread_id.get()

    if not solutions:
        return "错误：当前没有可评估的方案，请先调用 generate_solutions。"

    dispatch_custom_event("progress", {
        "node": "evaluate_solutions",
        "status": "started",
        "count": len(solutions),
    })

    # 并行评估所有方案
    results = await asyncio.gather(
        *[_eval_one(i + 1, sol.get("content", "")) for i, sol in enumerate(solutions)]
    )

    # 解析评估报告并更新 session
    for i, sol in enumerate(solutions):
        report = ""
        if i < len(results) and isinstance(results[i], dict):
            report = results[i].get("report", "")

        parsed = await parse_evaluation_report(report)

        sol["report"] = report
        sol["passed"] = parsed.get("passed", False)
        sol["reason"] = parsed.get("rejection_reason", "")

    dispatch_custom_event("progress", {
        "node": "evaluate_solutions",
        "status": "completed",
        "count": len(solutions),
    })

    dispatch_custom_event("panel", {
        "panel_type": "solution_review",
        "solutions_json": json.dumps(solutions, ensure_ascii=False),
        "message": "请查看各方案评估结果，选择一个方案进行下一步操作，或输入您的需求。",
    })

    return "所有方案评估完成，请向用户展示评估结果并等待选择。绝不能自动选择方案或生成交底书。"


# ---------- 工具 4: 改进方案 ----------

@tool
async def improve_solution() -> str:
    """根据评估反馈改进当前方案。
    改进后应自动调用 evaluate_single_solution 进行评估。"""
    session = get_session()
    document = session.document
    rejection_reason = session.rejection_reason
    current_solution = session.current_solution
    searched_patents = session.searched_patents

    # 构建检索到的专利对比提示（如有）
    patent_hint = ""
    if searched_patents:
        patent_summaries = []
        for i, p in enumerate(searched_patents, 1):
            summary = f"专利{i} [{p.get('patent_number', '')}]：{p.get('title', '')}\n摘要：{p.get('abstract', '')[:300]}\n"
            claims = p.get('claims', '')
            if claims:
                # 只取前3条权利要求，避免超出上下文
                claim_lines = claims.split('\n')[:3]
                summary += "权利要求（前3条）：\n" + "\n".join(claim_lines) + "\n"
            patent_summaries.append(summary)
        patent_hint = (
            "\n【检索到的对比专利】\n"
            + "\n".join(patent_summaries)
            + "\n请在分析技术缺陷和列举创新点时，主动与上述检索到的专利进行对比，"
            + "明确指出本方案与现有技术的差异点和改进空间。\n"
        )

    # Step 1: 提取技术点
    prompt1 = f"""请从以下文档中提取关键技术点或结构信息。只输出提取结果，不要有多余解释。

            文档内容：
            {document}

            提取的技术/结构："""
    tech_structure = await _stream_llm(prompt1, llm=_llm_zero)

    # Step 2: 分析技术缺陷
    prompt2 = f"""基于以下提取的技术/结构信息，分析技术缺陷，列举分析结果，不要有多余解释。{patent_hint}

            分析的技术/结构：
            {tech_structure}

            请输出列举分析结果："""
    issues = await _stream_llm(prompt2, llm=_llm_zero)

    # Step 3: 列举创新点
    feedback_hint = ""
    if rejection_reason:
        feedback_hint = (
            f"\n【特别说明】上一轮方案在专利评估中被指出存在以下问题，"
            f"请在创新点列举中重点关注并避免：\n{rejection_reason}\n"
        )
    prompt3 = f"""针对以下提取的技术缺陷/不足，列举出实用性的创新点，不要有多余解释。{patent_hint}{feedback_hint}

                提取的缺陷/不足：
                {issues}

                请输出列举出实用性的创新点："""
    innovation = await _stream_llm(prompt3, llm=_llm_creative)

    # Step 4: 生成改进方案（只输出发明内容，不输出完整交底书）
    prompt4 = f"""基于以下提取创新点，生成技术方案的"发明内容"部分。

            提取创新点：
            {innovation}

            要求：
            - 只输出发明内容，包括：要解决的技术问题、技术方案、有益效果
            - 不要输出技术领域、背景技术、具体实施方式、附图说明等其他章节
            - 保持简洁，突出核心创新点，500字以内

            请输出发明内容："""
    improved_solution = await _stream_llm(prompt4, llm=_llm_creative)

    session.current_solution = improved_solution
    session.revision_count += 1

    dispatch_custom_event("progress", {
        "node": "improve_solution",
        "status": "completed",
        "revision_count": session.revision_count,
    })

    return "方案已改进，请继续调用 evaluate_single_solution 评估改进后的方案。"


# ---------- 工具 5: 评估单个方案 ----------

@tool
async def evaluate_single_solution() -> str:
    """评估改进后的单个技术方案的专利新颖性和创造性。
    调用后必须向用户展示评估结果并等待决策。"""
    session = get_session()
    solution = session.current_solution
    thread_id = current_thread_id.get()

    if not solution:
        return "错误：当前没有可评估的方案，请先选择或改进方案。"

    from app.agent_v2.eval_subagent import build_eval_subagent_graph

    dispatch_custom_event("progress", {"node": "evaluate_single", "status": "started"})

    eval_thread_id = f"{thread_id}-eval-single"
    agent = build_eval_subagent_graph()
    config = {"configurable": {"thread_id": eval_thread_id}}

    eval_prompt = f"""请对以下技术方案进行专利审查检索和新颖性/创造性评估。
                请使用 patenthub 技能进行现有技术检索，使用专利审查检索技能评估 X/Y 类文献。

                待评估方案：
                {solution}

                请输出：
                1) 检索策略；
                2) 对比文件列表；
                3) 新颖性结论；
                4) 创造性结论。

                最后请明确给出：【评估结果：通过 / 不通过】，如果不通过请说明具体原因及改进方向。
                """

    result = await agent.ainvoke(
        {"messages": [{"role": "user", "content": eval_prompt}]},
        config=config,
    )

    messages = result.get("messages", [])
    assistant_msgs = [m for m in messages if getattr(m, "type", None) == "ai"]
    report = ""
    if assistant_msgs:
        report = getattr(assistant_msgs[-1], "content", str(assistant_msgs[-1]))
    else:
        report = str(result)

    parsed = await parse_evaluation_report(report)

    session.evaluation_report = report
    session.evaluation_passed = parsed.get("passed", False)
    session.rejection_reason = parsed.get("rejection_reason", "")

    dispatch_custom_event("progress", {
        "node": "evaluate_single",
        "status": "completed",
        "passed": parsed.get("passed", False),
    })

    passed = parsed.get("passed", False)
    reason = parsed.get("rejection_reason", "")

    dispatch_custom_event("panel", {
        "panel_type": "single_review",
        "current_solution": solution,
        "evaluation_passed": passed,
        "evaluation_report": report,
        "rejection_reason": reason,
        "message": (
            f"改进后方案评估结果：{'通过' if passed else '不通过'}。"
            + (f" 原因：{reason}" if reason else "")
        ),
    })

    return f"评估完成，结果为{'通过' if passed else '不通过'}。请向用户展示评估结果并等待决策。绝不能自动执行下一步。"


# ---------- 工具 6: 检索专利 ----------

@tool
async def search_patent(patent_number: str) -> str:
    """根据专利号检索专利信息。
    当用户要求查询某个具体专利号（如 CN114352908A）时使用此工具，
    返回专利的标题、摘要、权利要求、说明书等关键信息。"""
    skill_path = _PROJECT_ROOT / "skills" / "patenthub" / "scripts"
    if str(skill_path) not in sys.path:
        sys.path.insert(0, str(skill_path))

    from patenthub_client import api_get

    # Step 1: 搜索专利
    search_result = api_get("/api/s", {"q": f"number:{patent_number}", "ps": 1})
    if not search_result["success"]:
        return f"检索失败：{search_result.get('error', '未知错误')}"

    patents = search_result["data"].get("patents", [])
    if not patents:
        return f"未找到专利号 {patent_number} 的相关专利。"

    patent = patents[0]
    patent_id = patent.get("id")

    # Step 2: 获取基本信息
    base_result = api_get("/api/patent/base", {"id": patent_id})
    base_info = base_result["data"].get("patent", {}) if base_result["success"] else {}

    # Step 3: 获取权利要求
    claims_result = api_get("/api/patent/claims", {"id": patent_id})
    claims_info = claims_result["data"].get("patent", {}) if claims_result["success"] else {}
    if claims_info and "claims" in claims_info:
        claims_info["claims"] = claims_info["claims"].replace("<br/>", "\n")

    # Step 4: 获取说明书
    desc_result = api_get("/api/patent/desc", {"id": patent_id})
    desc_info = desc_result["data"].get("patent", {}) if desc_result["success"] else {}
    if desc_info and "description" in desc_info:
        desc_info["description"] = desc_info["description"].replace("<br/>", "\n")

    # 组装结果
    result = {
        "patent_number": patent_number,
        "title": base_info.get("title", ""),
        "abstract": base_info.get("abstract", ""),
        "applicant": base_info.get("applicant", ""),
        "inventor": base_info.get("inventor", ""),
        "application_number": base_info.get("applicationNumber", ""),
        "publication_number": base_info.get("publicationNumber", ""),
        "ipc": base_info.get("ipc", ""),
        "claims": claims_info.get("claims", ""),
        "description": desc_info.get("description", ""),
    }

    # 存入 session，供后续改进方案时参考
    session = get_session()
    session.searched_patents.append(result)

    return json.dumps(result, ensure_ascii=False, indent=2)


# ---------- 工具 7: 生成交底书 ----------

@tool
async def generate_disclosure() -> str:
    """基于当前技术方案生成专利交底书并保存为 MD 文件。"""
    session = get_session()
    solution = session.current_solution
    report = session.evaluation_report
    thread_id = current_thread_id.get()

    report_hint = ""
    if report:
        report_hint = (
            f"\n【评估报告摘要】\n{report}\n"
            "请在撰写交底书时，适当回应评估中指出的问题，突出本方案的创造性贡献。"
        )

    prompt = f"""你是一位资深专利代理师，请根据以下技术方案撰写一份完整的专利交底书。
            交底书应包含：技术领域、背景技术、发明内容（要解决的技术问题、技术方案、有益效果）、
            具体实施方式、附图说明、以及权利要求书草案。

            技术方案：
            {solution}
            {report_hint}

            请输出完整的交底书："""

    chunks = []
    async for chunk in _llm_creative.astream(prompt):
        content = getattr(chunk, "content", str(chunk))
        if content:
            chunks.append(content)
            dispatch_custom_event("token", {"node": "disclosure", "token": content})

    disclosure_text = "".join(chunks)

    # 保存 MD 文件
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    md_path = OUTPUT_DIR / f"{thread_id}.md"
    md_path.write_text(disclosure_text, encoding="utf-8")

    dispatch_custom_event("disclosure_done", {
        "file_path": str(md_path),
        "file_name": f"{thread_id}.md",
        "length": len(disclosure_text),
    })

    session.final_disclosure = disclosure_text

    return "交底书已生成并保存。请告知用户交底书已完成。"
