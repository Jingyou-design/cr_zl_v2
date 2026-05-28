---
name: patent-examination-search
description: "Use this skill when the user wants to perform a patent examination search to assess novelty and inventive step, or to find X/Y class prior art documents. Triggers include: patent search, examination search, novelty search, inventive step search, search report, X-class document retrieval, prior art search, 专利检索, 审查检索, 新颖性检索, 创造性检索, 检索报告, X类文件检索, 对比文件检索."
---

# Patent Examination Search Skill

## Overview

This skill guides the agent through a systematic patent search workflow: from claim deconstruction and search-element identification, to preliminary, conventional, and extended searches, all the way to the classification of retrieved documents (X, Y, A, E, etc.) and a preliminary assessment of novelty and inventive step.

When a patent number is provided, the skill leverages the `patenthub` tool to execute actual API queries. When no patent number is available, it works from the user's textual description of the invention.

## Pre-Search Preparation

Before executing any query, complete the following analytical steps:

1. **Read the application text** (claims + description + drawings).
   - If a patent number is known, retrieve the **claims** and **description** via `patenthub` (`claims` and `desc` commands).
   - Identify **all independent claims** and determine the one with the **broadest scope**.
   - Extract the **essential technical features** (not preferences or optional details).
   - Note the **core technical problem solved** and the **technical effect**.

2. **Verify the IPC/CPC classification**.
   - Use the classification numbers provided in the bibliographic data.
   - If they seem inaccurate for the invention's true subject matter, determine the correct class yourself using the IPC hierarchy: check the "Contents of the Section" to select possible divisions and classes; read subclass names to find the most appropriate one; consult the subclass index to select the main group; review one-dot subgroups, then multi-dot subgroups that still cover the subject matter. Also handle priority notes and the "last place rule" if applicable.
   - If skills such as `ipc-search` are available, read them to query the IPC hierarchy and definitions.

3. **Define the search technical field**.
   - Start with the field to which the claimed subject matter belongs.
   - Be prepared to extend the search to **functionally analogous** or **application-analogous** fields.

4. **Determine search elements**.
   - Break the broadest independent claim into **basic search elements** reflecting: technical field, technical problem, technical means, and technical effect.
   - Consider **equivalent features** (features that use substantially the same means, achieve substantially the same function, and produce substantially the same effect, and are obvious to a person skilled in the art).

## Search Process

Execute searches in three stages. **Document every query** and its result count.

### Stage 1 — Preliminary Search
Goal: Quickly locate highly relevant documents using non-technical clues and semantic similarity.

- **Applicant / Inventor tracing**: Search for co-pending applications, parent/divisional applications, and other patents by the same applicant or inventor in the same field.
  - Example: `applicant:"Tsinghua University" AND graphene`
- **Family & priority search**: Retrieve family members of the target patent.
- **Semantic / similar-patent search**: Use the `like` command with the target patent ID to find semantically close documents.
  - *Caution*: Filter out noisy results from unrelated industries.

### Stage 2 — Conventional Search
Goal: Search the **belonging technical field** thoroughly.

1. **Express each basic search element**:
   - **Classification symbols** (preferred): Start with the most accurate, lowest-level IPC/CPC group. If too few results, move up to the parent group, main group, or even subclass.
   - **Keywords**: Construct blocks for each element covering:
     - **Form**: different word forms, singular/plural, common misspellings.
     - **Meaning**: synonyms, near-synonyms, antonyms, broader/narrower concepts.
     - **Angle**: technical problem, technical effect, use case.

2. **Build query blocks**:
   - Combine expressions of the **same element** with `OR`.
   - Combine different element blocks with `AND`.
   - **Avoid over-ANDing**: A query returning 0 hits usually means the constraint is too tight, not that the invention is novel.

3. **Query patterns**:
   - **Full-element combination**: All basic search elements are present. Use this first for the broadest independent claim.
   - **Partial-element combination**: Remove one non-critical element block at a time to catch documents that disclose the core combination but use different wording for a secondary feature.
   - **Single-element search**: When the above fail, search each basic element individually to map the landscape and discover alternative keywords/classifications.

4. **Iterative adjustment**:
   - If result count is 0 or <5, **degrade** the query (broader classification, remove weakest AND term, add synonym ORs).
   - If results are too many and noisy, **upgrade** the query (add a second element block, use more specific classification symbols).

### Stage 3 — Extended Search
Goal: Search **functionally analogous** or **application-analogous** technical fields when the conventional search yields no damaging prior art.

- Example: If the invention is "silicone-based hydraulic oil in a printing press", extend the search to "general hydraulic systems with corrosion problems" or "hydraulic systems in other industrial applications".
- Use broader classification symbols or problem-centric keywords for this stage.

## Search Termination Conditions

You may terminate the search once **any** of the following is met:

1. **X/E class found**: A single document clearly discloses all technical features of the claimed subject matter, destroying novelty (or is an identical conflicting application).
2. **Y class combination found**: Two or more documents are found that, in combination, clearly render the claimed invention obvious to a person skilled in the art.
3. **Cost-benefit threshold**: Based on your knowledge and the quality of results already obtained, further search is unlikely to yield a better document and the cost is disproportionate.
4. **External discovery**: An X or Y class document is supplied by the applicant or the public.

## Document Classification & Preliminary Assessment

For every retrieved document that is relevant, classify it using the following symbols:

| Symbol | Meaning | When to assign |
|--------|---------|----------------|
| **X** | Document alone destroying novelty or inventive step | One document alone destroys novelty or renders the invention obvious. |
| **Y** | Document that in combination with other Y documents destroys inventive step | Must be combined with another Y document to destroy inventive step. |
| **A** | Background art | Reflects partial technical features or general prior art. |
| **E** | Conflicting application (identical invention filed earlier by same or different applicant) | Filed before the target's filing date and published after. |
| **R** | Document belonging to the same invention filed by the same applicant on the same day | Identical invention filed by same applicant on the same day. |
| **P** | Intermediate document | Published between the filing date and the priority date; append X/Y/E/A to indicate content relevance. |
| **T** | Document published on or after the filing/priority date | Can explain theory or show reasoning is flawed; not prior art for novelty. |
| **L** | Document cited for other reasons | For reasons other than X/Y/A/E/R/P/T. |

### Preliminary Novelty / Inventive-Step Assessment

- **Novelty**: If an X or E class document exists for an independent claim, the claim lacks novelty.
- **Inventive Step**: If no X/E exists, but a Y-class combination exists that a person skilled in the art could easily combine to reach the claimed solution, the claim lacks inventive step.
- If neither X/E nor Y combinations are found after a reasonable search, the claim **provisionally** appears to possess novelty and inventive step. Clearly state this is a provisional conclusion based on the searched databases.

## Common Pitfalls

- **Do not rely solely on abstracts**: Always retrieve full claims and description for candidate X-class documents.
- **Do not stop at the first close match**: Find the *earliest* document that fully discloses the claim.
- **Do not over-constrain queries**: A zero-result query is usually a sign of poor query construction, not novelty.
- **Do not skip extended search**: If the conventional field is "clean", the X-class document may be hiding in a functionally analogous field.
- **Do not confuse equivalence with disclosure**: A functionally equivalent material or step is not necessarily explicitly disclosed.

## Output Format

When reporting search results, structure the response as:

1. **Claim Deconstruction** — bullet list of the broadest independent claim's essential features and search elements.
2. **Search Strategy Log** — databases used, classification symbols, and a table of executed queries with result counts.
3. **Relevant Documents** — for each candidate: bibliographic data, publication date, assigned symbol (X/Y/A/etc.), and brief match assessment.
4. **Feature Mapping** — for X or strong Y candidates, a table mapping claim features to document disclosures.
5. **Conclusion** — provisional assessment of novelty and inventive step, and recommendation for any further search (e.g., non-patent literature, additional databases).
