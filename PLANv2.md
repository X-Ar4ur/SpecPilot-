# 4ga Boards 手册驱动 Web 测试智能体完整项目 Plan

## Summary

构建一个完整本地全栈系统：从 4ga Boards 帮助文档(user-manual + admin-manual 中 UI 操作部分)抽取功能点，生成 `step + expectation` 测试场景，由 LangGraph 编排 `browser-use` 执行网页测试，并用确定性校验和 `GLM-4.6V` 视觉校验判断结果。前端采用 `Next.js App Router + TypeScript`，做成完整产品级测试控制台，不是 Demo。

核心架构：

```text
Next.js 控制台
  ↓ REST + SSE
FastAPI 后端
  ↓
LangGraph Agent Worker
  ↓
browser-use Agent (DeepSeek V4 Pro by default, Browser Use hosted LLM optional) + BrowserSession
  ↓
DOM / 语义校验 + GLM-4.6V 视觉验证
  ↓
执行记录 / 报告 / 覆盖率 / 失败分类
```

## Key Design Decisions

本系统包含两个与传统 Web 测试范式不同的关键设计决策，作为创新点和工程取舍同时记录在此。

**决策一：零专用 Tool 设计**

不为 4ga Boards 封装任何领域专用 Tool。所有浏览器交互——包括 Board/List/Card 的创建编辑、视图切换、搜索筛选、以及拖拽——全部由 `browser-use` 通用能力承担，LLM 基于实时 DOM 观察自主决策。

依据：前期实验中，`browser-use + DeepSeek V4 Pro` 在 5 个核心场景（创建 board、创建 list、创建 card、编辑 card 标题、跨 list 拖拽 card）上均能完成，包括公认困难的拖拽操作。因此专用 Tool 封装属于过度工程，会损失 Agent 的自主决策价值，并使"失败分类"等评分点失去真实样本来源。

架构层面保留 `browser-use Tools` 的 `@tools.action` 注入接口作为逃生舱，当前实现中不注册任何 action。若后续遇到通用能力反复失败的特定交互，可低成本补充。

**决策二：零 locator 测试场景**

测试场景的 `step` 字段使用纯自然语言意图描述（如"在名为 'To Do' 的 List 中点击添加 Card 的入口"），不包含任何 DOM locator、selector、xpath 等定位信息。元素定位由 LLM Agent 在运行时基于 DOM 树观察完成。

依据：手册原文不包含 DOM 选择器，强制 LLM 生成 locator 等于强迫其脱离证据生成，违背 RAG-from-manual 的反幻觉初衷；且 `browser-use` 的执行模型基于运行时 index 分配，预先写入的 locator 在执行时被忽略，是死字段。纯意图描述还使场景具备跨 UI 实现的泛化能力——只要功能不变，UI 改版不会让场景失效。

**决策三：LangGraph 与 browser-use 的责任边界**

`browser-use` 自身已是一个完整的 Agent loop（LLM 观察 DOM → 选 action → 执行 → 循环）。LangGraph 不重做这一层，避免架构重叠。具体分工：

- `browser-use` 承担**单场景内部的 Plan/Execute 循环**：接收任务描述，自主决定每步动作，直到任务完成或达到 `max_steps`。
- LangGraph 承担**单场景外部的多阶段编排**：场景加载 → 调度 browser-use 执行 → trace 汇集 → 双通道验证 → 失败分类 → 修补决策 → 报告生成。这些是 `browser-use` 不做的事，也是测试系统的核心增量价值所在。

依据：在初版设计中，LangGraph 包含独立的 `PlannerNode` 与 `ExecutorNode`，与 `browser-use` 内部 loop 职责重叠，会导致"LangGraph 在此架构中具体做了什么"难以解释。本设计将 Plan/Execute 合并为单一 `BrowserUseRunNode`，使 LangGraph 的编排价值集中在执行**之后**的处理环节，分工清晰。

**决策四：依赖型场景的交互式前置数据绑定**

部分场景依赖既有数据（如"从 List View 打开标题为 X 的 Card"）。若目标实例无此数据，测试会假性失败——这是测试数据问题，非功能缺陷。解决方案：场景不再硬编码具体值，而在 `fixtures` 中声明所需数据槽（仍零 locator，仅领域属性）。运行依赖型场景时前端弹出绑定窗口，列出目标实例当前各类型元素（Project/Board/List/Card），由用户**选择既有元素或手动填写新建**；绑定时把操作目标与 `expectation` 断言值**一并重绑**为用户选定的已知值，从而保留确定性校验。绑定按 `target_app_url` 持久化，重跑/批量时元素仍在则跳过弹窗，实现无人值守。

数据来源：4ga Boards 为 Sails.js + React/Redux SPA，自带 JSON REST API（已实测：`POST /api/access-tokens` 登录、`GET /api/projects`、`GET /api/boards/:id`、`POST /api/lists/:listId/cards` 等）。后端 `FourgaApiClient` 复用既有 `fourga_username/password` 登录，**仅用于 Arrange 阶段**列举/创建数据；执行与判定仍全程走 browser-use 真实 UI + 双通道校验。该客户端是后端 infra、非 browser-use action，不违反决策一；零 locator（决策二）继续覆盖 `fixtures` 内部。前置数据无法建立时 run 判为 `error`(`precondition_setup_failure`)，排除在功能 pass/fail 指标外。完整设计见 `docs/FIXTURE_PROVISIONING.md`。

## Frontend Plan

前端采用 App Shell：

```text
顶部栏：项目名称、全局运行状态、模型状态、通知、系统设置入口
左侧栏：可收纳主导航
主内容区：当前页面
```

侧边栏导航固定为：

```text
工作台
功能点树
测试场景
执行过程
执行记录
```

系统设置不放在侧边栏，放在顶部栏右侧，使用齿轮图标入口。点击后打开设置抽屉或设置弹窗，符合常见后台系统习惯。

整体风格定位为"专业测试控制中心"：高信息密度、清晰状态反馈、偏工程工具感。使用浅色主界面配深色执行控制台局部区域，状态色固定为绿色通过、红色失败、琥珀色警告、蓝色运行中。使用 `Tailwind CSS + Radix UI + Lucide Icons + React Flow + TanStack Query + Zustand + Recharts + Framer Motion`。

前端路由：

```text
/                         工作台
/features                 功能点树
/scenarios                测试场景
/runs/live/[run_id]       执行过程
/runs                     执行记录
/runs/[run_id]            执行结果详情
```

工作台：

- 显示功能点数量、测试场景数量、已执行数量、通过率、失败率、平均执行时长。
- 展示最近执行记录、失败分类分布、功能覆盖率、场景难度分布。
- 提供快捷操作：爬取手册、生成场景、运行测试套件、查看最新报告。

功能点树：

- 左侧为功能点树，按 Project、Board、List、Card、Views、Settings 等模块分组。
- 右侧为详情面板，显示功能点摘要、手册证据、来源 URL、关联测试场景、覆盖状态。
- 支持搜索、按覆盖状态筛选、按证据可信度排序。
- 点击功能点可展开其关联场景，并可跳转到测试场景页。

测试场景：

- 主体是表格，列包括场景名称、所属功能点、优先级、难度、审核状态、证据数量、最近执行结果、操作。
- 点击行打开右侧详情抽屉，展示步骤、预期结果、手册证据、测试数据和完整 JSON。
- 每行提供运行按钮；点击后创建 run，并跳转到 `/runs/live/[run_id]` 实时显示执行过程。
- 支持筛选：功能点、优先级、难度、审核状态、是否可自动执行、最近运行结果。
- 支持批量选择运行测试套件。

执行过程：

页面采用左右分栏布局，左侧约 60% 宽度展示 Agent 编排与事件，右侧约 40% 宽度展示浏览器实时画面。布局支持折叠/全屏切换：右侧浏览器区可临时占满整个内容区，便于演示和调试。

**左侧上半部分：Agent 流程图（React Flow）**

- 节点固定为：`ScenarioLoader`、`BrowserUseRun`、`TraceCollector`、`DeterministicVerifier`、`GLM-4.6V VisionVerifier`、`FailureClassifier`、`RepairPlanner`、`Reporter`。
- 节点状态实时更新：pending、running、success、failed、skipped、retrying。
- 当前 running 节点高亮，边显示数据流动动画。

**左侧下半部分：实时事件流**

- 时间倒序展示事件：当前 step、Agent 当前思考、采取的 browser-use action、目标元素摘要（role + name + index）、返回结果、失败原因。
- browser-use action 子面板：每步的 action 类型（navigate、click、input、scroll、wait、screenshot、drag 等）、参数、执行结果。
- 执行结束后显示通过/失败、失败分类、GLM 判断摘要，并提供跳转到执行结果详情。

**右侧：浏览器实时画面**

- 顶部状态条：当前 URL、当前 step 编号、最新 action 文字摘要（如"点击 'Add Card' 按钮"）。
- 主显示区：渲染浏览器最新一帧截图。MVP 实现采用 per-step 截图——browser-use 每步执行时本来就会截图，通过 SSE 事件 `browser_frame` 推到前端，前端 `<img src="data:image/jpeg;base64,...">` 即时替换。帧率约等于"每个 action 一帧"（0.5–2 fps），呈现幻灯片节奏。
- 元素高亮覆盖层：在截图上叠加红色 bounding box，标记 LLM 当前操作的目标元素（坐标从 browser-use action 元数据获取）。这是"Agent 在思考什么"的可视化表达，对答辩演示有显著加分。
- 底部缩略时间线：所有历史帧的小图，可点击回看任一帧。

**进阶可选：CDP screencast 视频流**

如时间允许，可在 MVP 之上升级为接近视频的实时流：通过 browser-use 底层暴露的 `cdp-use` 调用 `Page.startScreencast`，以 JPEG quality 80 / 10–25 fps 通过独立 WebSocket 端点 `/api/runs/{run_id}/screencast` 推送二进制帧；前端用 `<canvas>` 或 `<img>` 渲染，并实现 CDP 帧 ack 背压。该方案是 Cypress、Browserless、Apify、Vercel agent-browser 的通用做法。**列为 P2 增强项，非核心交付**。

执行记录：

- 表格展示所有历史 run：场景名称、开始时间、耗时、状态、通过率、失败分类、模型、重试次数。
- 点击行进入 `/runs/[run_id]`，展示完整结果。
- 结果详情包含执行轨迹、每步截图、每步输入输出、验证结果、失败原因、手册证据、导出报告按钮。
- 支持按时间、状态、功能点、失败类型筛选。

顶部系统设置：

- 右上角齿轮图标打开设置抽屉。
- 配置文本模型 provider：默认 `openai_compatible`（Codex API / OpenAI-compatible endpoint，通过 `OPENAI_COMPATIBLE_BASE_URL` + `OPENAI_COMPATIBLE_API_KEY` + `OPENAI_COMPATIBLE_MODEL`），保留旧 `deepseek` 与 Browser Use 托管 LLM 配置读取兼容。
- Browser Use 托管 LLM 仅作为文本模型 provider / fallback 选项；不等于启用 Browser Use Cloud Browser。浏览器执行默认仍是本地 Managed Browser，除非后续非 MVP 明确新增云浏览器模式。
- 配置 `GLM-4.6V`、目标文档 URL、目标应用 URL。
- 配置浏览器模式、最大重试次数、截图频率、Agent 单场景最大步数上限。
- 配置 GLM-4.6V 验证置信度阈值 `τ_high`(默认 0.85)与 `τ_low`(默认 0.6),实时生效不需重启。两个阈值之间的判定进入 `needs_review`,详见 "Verification Pipeline" 章节。
- 配置验证快照采集延迟(默认 500ms)与 `networkidle` 等待上限(默认 3000ms)。
- 展示连接测试和 `doctor` 检查结果。

## Backend And Agent Plan

后端采用 `FastAPI + SQLite + SQLModel + ChromaDB`。本地文件系统保存 artifacts(截图、DOM 摘要、trace、报告、GLM 验证结果),目录布局与命名规则详见 "Artifact Storage" 章节。

核心 API：

```text
POST /api/ingestion/crawl
POST /api/ingestion/index
POST /api/features/extract
GET  /api/features
POST /api/scenarios/generate
GET  /api/scenarios
GET  /api/scenarios/{scenario_id}
POST /api/runs
GET  /api/runs
GET  /api/runs/{run_id}
GET  /api/runs/{run_id}/events           # SSE，含 browser_frame 事件
GET  /api/runs/{run_id}/trace
GET  /api/runs/{run_id}/artifacts
WS   /api/runs/{run_id}/screencast       # WebSocket，CDP 视频流，P2 可选
POST /api/mutations/generate
GET  /api/reports/{report_id}
GET  /api/settings                    # 返回运行时设置，密钥只返回 configured 状态
PATCH /api/settings                    # 更新 provider/model/非敏感配置；密钥字段只写不读
```

测试场景是系统核心产物，采用纯意图 schema：

```python
class TestStep:
    order: int
    action: str                       # 自然语言意图描述，不含 DOM 信息

class Expectation:
    type: Literal[
        "element_visible",            # 某语义元素出现/消失
        "text_present",               # 页面包含/不含某文本
        "url_match",                  # URL 满足某模式
        "element_state",              # 元素状态（选中/禁用/激活等）
        "containment",                # 元素 A 在元素 B 内
        "semantic",                   # 需视觉/语义判断（交给 GLM-4.6V）
    ]
    description: str                  # 自然语言描述，供 verifier 与 GLM 理解
    params: dict                      # 类型相关参数（如 text、pattern、target）

class TestScenario:
    scenario_id: str
    feature_id: str
    title: str
    priority: Literal["P0", "P1", "P2"]
    difficulty: Literal["simple", "medium", "hard"]
    source_urls: list[str]            # 手册证据来源
    evidence_quotes: list[str]        # 手册证据原文片段
    preconditions: list[str]          # 前置状态描述（自然语言）
    test_data: dict                   # 参数化数据，变异测试主入口
    steps: list[TestStep]
    expectations: list[Expectation]
    max_steps: int                    # Agent 执行步数上限
    requires_visual_check: bool       # 是否必须走 GLM-4.6V 验证
    review_status: Literal["auto_validated", "needs_review", "rejected"]
```

场景示例：

```json
{
  "scenario_id": "sc_create_card_001",
  "feature_id": "ft_card_creation",
  "title": "在指定 List 中创建新 Card",
  "priority": "P0",
  "difficulty": "simple",
  "preconditions": [
    "用户已进入一个 Board",
    "Board 中至少存在一个名为 'To Do' 的 List"
  ],
  "test_data": {
    "card_title": "完成季度报告",
    "target_list_name": "To Do"
  },
  "steps": [
    { "order": 1, "action": "在名为 'To Do' 的 List 中，点击添加 Card 的入口" },
    { "order": 2, "action": "输入 Card 标题 '完成季度报告'" },
    { "order": 3, "action": "确认创建" }
  ],
  "expectations": [
    {
      "type": "element_visible",
      "description": "标题为 '完成季度报告' 的 Card 出现在 'To Do' List 中",
      "params": { "text": "完成季度报告", "container_text": "To Do" }
    },
    {
      "type": "containment",
      "description": "新建 Card 位于 'To Do' List 内，而非其他 List",
      "params": { "child_text": "完成季度报告", "parent_label": "To Do" }
    }
  ],
  "evidence_quotes": [
    "在 List 中点击 + 号或 Add Card 按钮即可创建新的卡片"
  ],
  "source_urls": [
    "https://docs.4gaboards.com/cards/create"
  ],
  "max_steps": 10,
  "requires_visual_check": false,
  "review_status": "auto_validated"
}
```

`browser-use` 是唯一执行器：

- 所有交互均使用 browser-use 通用能力：navigate、click、input、scroll、wait、screenshot、drag 等。
- LLM（默认 DeepSeek V4 Pro；可选 Browser Use 托管 LLM）基于运行时 DOM 树观察自主选择目标元素与动作，不依赖场景中的预置 locator。
- `browser-use Tools` 使用默认实例，不通过 `@tools.action(...)` 装饰器注册任何 4ga 领域专用 action。架构上保留该扩展点用于未来低成本补丁，当前为空。
- 不引入 Playwright。前期实验已确认 browser-use 在 4ga 上能完成包括拖拽在内的全部核心交互，无需 fallback。
- 不修改 browser-use 核心源码，不 fork 仓库。通过 PyPI 标准方式集成（`pip install browser-use>=0.12.6,<0.13` 或 `uv add`），版本 pin 到 minor 以避免 API 漂移。
- 默认文本模型 DeepSeek V4 Pro 通过 `langchain-deepseek` 接入；Browser Use 托管 LLM 可作为显式可选 provider / fallback；GLM-4.6V 用于 VisionVerifier，独立调用，不进入 browser-use 决策循环。

LangGraph 节点：

```text
ScenarioLoader        加载场景与历史上下文
BrowserUseRunNode     将 steps 拼成自然语言任务交给 browser-use Agent 执行；
                      通过 hook（如 register_new_step_callback）实时收集 action、
                      截图、DOM、URL；接收完成事件后输出 history 与中间 trace
TraceCollectorNode    规整 BrowserUseRunNode 产出的原始 trace，写入 artifacts
DeterministicVerifierNode  按 expectation.type 分发到对应检查器
VisionVerifierNode    对 type=semantic 或 requires_visual_check=true 的场景调 GLM-4.6V
FailureClassifierNode 综合 trace + 验证结果输出失败类别与原因
RepairPlannerNode     针对可恢复失败生成单步修补计划，受全局重试预算约束
ReporterNode          产出 JSON/HTML 报告并写入执行记录
```

注：`BrowserUseRunNode` 内部不实现 LLM 决策循环——这一职责完全由 browser-use 自身的 Agent 承担。该节点的代码工作集中在三件事：(1) 把场景的 `steps` + `test_data` + `preconditions` 拼成 browser-use 可消费的自然语言任务字符串；(2) 配置 `Browser` / `Tools` / LLM 实例并调用 `await agent.run(max_steps=...)`；(3) 通过 hook 把每步的 action、截图、DOM、URL 推到 SSE 事件总线供前端实时显示。

验证器分发逻辑：

- `element_visible` / `text_present` / `containment` / `element_state` → DeterministicVerifier 直接通过 browser-use DOM 抓取判断。
- `url_match` → DeterministicVerifier 比对当前 URL。
- `semantic` 或场景显式标记 `requires_visual_check=true` → VisionVerifier 调用 GLM-4.6V，传入截图 + expectation.description，要求返回结构化判断。
- 仲裁规则：确定性通过即通过；确定性失败但视觉通过 → 标记 `dom_mismatch_visually_correct`（疑似 verifier 适配问题，进 needs_review，不计真失败）；两者都失败 → 真失败，进入失败分类。

失败分类（至少 6 类）：

```text
navigation_failure         页面/路由跳转未达预期
element_not_found          目标元素在 max_steps 内未定位到
interaction_failure        click/input/drag 等动作执行后无效
timing_issue               异步加载/动画导致状态判断过早
state_mismatch             功能执行成功但最终状态与 expectation 不符
visual_regression          DOM 通过但视觉验证失败（布局/样式问题）
agent_planning_error       LLM 规划错误（步骤顺序、误解意图）
dom_mismatch_visually_correct  确定性失败但视觉通过（疑似 verifier 适配问题）
```

## RAG Indexing & Retrieval

手册爬取、切分、索引、检索的完整流程。基于对 docs.4gaboards.com(Docusaurus v3.10、英文 + 波兰语双语、用户/管理员/开发者三层手册)的实际形态调研后定型。

### 爬取范围

仅爬取 **user-manual** 和 **admin-manual** 两个顶层 section。**完全排除 developer-manual**(API 引用、部署、数据库 schema、构建说明等开发者内容,与 UI 测试无关)、Additional Resources、其他非操作类页面。

只爬英文版本(默认 `en` locale,`/docs/...` 路径,跳过 `/pl/docs/...`)。

### Chunking 策略

二段式切分:

1. **`MarkdownHeaderTextSplitter`** 按 `#` / `##` / `###` 切分到逻辑块。手册典型结构是 1 个 H1 标题 + 多个 H2 小节 + 偶尔 H3 子节,自然块大小集中在 100-300 token。
2. **`RecursiveCharacterTextSplitter`** 仅作兜底:个别 H2 段落超过 chunk_size 时按段落/句子拆分。

参数:`chunk_size=400 tokens`、`overlap=50 tokens`。在该手册典型形态下,绝大多数 chunk 一个 H2 块,不会触发字符兜底切分。

### Metadata Schema

```python
chunk_metadata = {
    # 基础
    "source_url": "https://docs.4gaboards.com/docs/board#creating-a-new-board",  # 精确到 H2 anchor
    "page_url": "https://docs.4gaboards.com/docs/board",                          # 不带 anchor
    "page_title": "Board: General",                                              # sidebar 显示名
    "heading_path": "For Users / Board: General / Creating a new board",         # 完整面包屑
    "section_anchor": "creating-a-new-board",                                    # H2 anchor(可空)
    "content_hash": "sha256:...",                                                # 增量更新标识

    # 真实模块分类(基于 sidebar 真实结构)
    "manual_section": "user-manual",        # user-manual / admin-manual
    "module": "Board",                       # Project / Board / List / Card / Sidebar / Notifications /
                                             # Settings / Views / Shortcuts / Account / ImportExport /
                                             # Structure / ... admin 模块爬取后定型补入
    "module_variant": "general",             # Board 拆 general / board-view / list-view 三页时区分

    # UI 操作性标签(LLM 预分类,详见下文)
    "is_ui_operational": True,               # 仅 True 的 chunk 进入功能点抽取

    # 检索/调试
    "section_level": 2,                      # H1=1, H2=2, H3=3
    "chunk_index_in_page": 3,                # 该 page 内第 N 个 chunk
    "lang": "en",
    "crawled_at": "2026-05-04T..."
}
```

`source_url` 精确到 H2 anchor 是关键设计——场景的 `evidence_quotes` 引用证据时直接给 anchor URL,人工审核或前端展示可一键跳转到证据原文位置。

`module` 标准化映射首版以 user-manual sidebar 二级名称为主:`Project / Board / List / Card / Sidebar / Notifications / Settings / Views / Shortcuts / Account / ImportExport / Structure`。**admin-manual 的 module 名称在首次爬取后根据实际章节定型补入**,schema 开放。

### UI 操作性预分类

爬取并切分完成后、写入 ChromaDB 之前,对每个 chunk 调用当前配置的文本模型（默认 DeepSeek V4 Pro）打 `is_ui_operational: bool` 标签。该判断是语义判断,启发式规则在未知手册形态下容易误判,因此采用 LLM 一次性预分类。

**预分类 prompt**:

```text
你正在为一个 Web UI 测试系统准备语料。下面是 4ga Boards 帮助文档的一段内容。

判断这段内容是否描述"用户或管理员通过 4ga Boards Web 页面进行的 UI 操作"。

判定为 True 的情况:
- 描述用户/管理员在 Web 页面上点击、选择、拖拽、输入、切换视图等 UI 行为
- 描述某个 Web 页面、菜单、按钮、对话框的功能与用法
- 描述账号管理、权限设置等可通过 Web UI 完成的管理动作

判定为 False 的情况:
- 命令行操作(docker、npm、shell 命令等)
- API 端点、HTTP 请求、JSON schema 等开发者技术内容
- 安装、构建、部署、数据库迁移等运维内容
- 配置文件格式、环境变量等非 UI 配置
- 项目历史、贡献指南、许可证等元信息

输出严格 JSON,不要 markdown 代码块包装:
{"is_ui_operational": true|false, "reason": "1 句话说明"}

内容:
"""
{chunk_text}
"""
```

**实施细节**:
- 一次预分类涵盖所有爬取 chunks,作为索引建立的一次性成本(预估 user + admin 共 ~50 chunks,token 总量 < 30k,成本可忽略)
- 解析失败 / 字段缺失 → 默认 `is_ui_operational=False`(保守策略,宁可漏抽也不引入污染)
- `reason` 字段写入 ChromaDB metadata,供后期人工审核与调试

**功能点抽取阶段(阶段 1)拉取 chunks 时,只取 `is_ui_operational=True` 的部分**——这是 admin 内容进入抽取的唯一通道。dev manual 完全不爬,不需要在此再过滤。

### 检索策略

阶段 1 与阶段 2 检索方式不同,因为整个 user-manual + admin-manual UI 操作部分加起来才约 18-30k token,远小于 DeepSeek V4 Pro 的上下文窗口。

**阶段 1(功能点抽取)—— 不做向量检索,按 module 全量拉取**

```python
# 伪代码
for module in distinct_modules:
    chunks = chroma.get(
        where={"module": module, "is_ui_operational": True}
    )
    features = llm.extract_features(chunks)   # 全量传入,LLM 看到该 module 全部内容
```

理由:阶段 1 需要"完整理解一个 module 才能合理切分功能点",局部检索反而损失视野;且数据量小到可以全量传入,无需向量近似。ChromaDB 在此环节仅作 metadata 过滤的存储后端,不计算向量相似度。

**阶段 2(场景生成)—— 向量检索 + metadata 约束**

```python
chunks = chroma.query(
    query_text=feature.title + " " + feature.description,
    where={"module": feature.module, "is_ui_operational": True},
    n_results=8,
)
# 过滤 distance > 1.5 的低相关结果
```

`top_k=8`,distance 阈值 1.5(超过视为不相关,不传给 LLM)。该阈值在系统设置中可调。

### Embedding 模型

`sentence-transformers/all-MiniLM-L6-v2`,384 维。理由:手册英文(`meta-docsearch:language: en`),MiniLM-L6 是 ChromaDB 默认且对英文文档检索效果稳定,本地加载无需联网,模型小(~80MB)。

### Storage

ChromaDB **本地持久化模式**:

```python
client = chromadb.PersistentClient(path="./data/chroma_db")
collection = client.get_or_create_collection(
    name="4ga_manual_chunks",
    metadata={"hnsw:space": "cosine"},     # cosine 距离,语义检索惯例
)
```

### 增量更新

爬取调度支持手动触发("立即爬取")和定时触发(默认每周一次,系统设置可关闭)。每次爬取按 `content_hash` 比对:

- chunk 不存在 → 新增(含 LLM 预分类)
- chunk 存在且 hash 一致 → skip
- chunk 存在但 hash 变化 → 删旧加新(重新预分类)
- 旧 chunk 在新爬取中不再出现 → 删除

**预分类只对新增/变化 chunk 调用**——避免重复 LLM 成本。

### Pipeline 全景

```
[Crawl4AI 爬取 user-manual + admin-manual]
        ↓
[MarkdownHeaderTextSplitter 按 H1/H2/H3 切分]
        ↓
[RecursiveCharacterTextSplitter 兜底超长块]
        ↓
[Metadata 装配:source_url(含 anchor)/ heading_path / module / ...]
        ↓
[content_hash 比对,跳过未变化 chunk]
        ↓
[文本模型预分类 is_ui_operational（默认 DeepSeek V4 Pro）]
        ↓
[Embedding(MiniLM-L6)→ ChromaDB 写入]
        ↓
[等待功能点抽取 / 场景生成调用]
```

## Artifact Storage

每次 run 产生大量副产物——截图、DOM 快照、trace、报告。本节定义存储布局、文件命名、保留策略、数据库与文件系统的分工。

### 目录布局

```
./data/
├── chroma_db/                              # RAG 索引(详见 "RAG Indexing & Retrieval")
└── runs/
    └── {run_id}/                           # 每个 run 独立目录
        ├── meta.json                       # run 元信息(scenario_id / status / timing 等)
        ├── trace.jsonl                     # 完整事件流,JSON Lines
        ├── result.json                     # 最终验证结果与失败分类摘要
        ├── screenshots/
        │   ├── step_001_initial.jpg        # 起点截图(供 VisionVerifier 双帧对比)
        │   ├── step_001.jpg                # 第 1 步执行后
        │   ├── step_002.jpg
        │   ├── ...
        │   └── step_NNN_final.jpg          # 终点截图(供 verifier 与报告使用)
        ├── dom_snapshots/
        │   ├── step_001.json               # 每步的 DOM 抽象(含 clickable_elements)
        │   └── step_NNN_final.json         # 终态 DOM(verifier 输入)
        ├── verifications/
        │   ├── deterministic.json          # DeterministicVerifier 全部输出
        │   └── vision.json                 # VisionVerifier 全部输出(含 GLM thinking 痕迹)
        └── reports/
            ├── report.json                 # 结构化报告
            ├── report.html                 # 人类可读 HTML(内嵌相对路径截图)
            └── report.pdf                  # 可选 PDF 导出
```

`run_id` 格式:`run_{YYYYMMDD}_{HHMMSS}_{6 位随机字符}`,如 `run_20260504_143022_a3f9k2`。既能按时间排序,又避免冲突。

### 截图

- **命名**:`step_{NNN}_{suffix?}.jpg`,NNN 三位 0 padding;suffix 仅对特殊帧使用(`_initial` / `_final`)
- **格式**:JPEG,quality=80。在前端显示和 GLM 视觉判断的需求间取平衡——quality=100 体积大无明显视觉收益,quality=60 在文字密集场景下 GLM 会读不清
- **尺寸**:与 BrowserSession viewport 一致(1280×800),不缩放
- **存储与传输分离**:文件系统落盘原图;前端 SSE 推送 `browser_frame` 事件中的 base64 由后端按需压缩到 640×400,降低带宽

### Trace 格式:JSON Lines

每行一个事件,append-only 写入。该格式允许执行过程中**边写边被前端读取**(SSE 直接 tail 文件,不需等 run 结束),也方便后期用 jq / grep 离线分析。

```jsonl
{"ts": "2026-05-04T14:30:22.103Z", "type": "run_started", "run_id": "...", "scenario_id": "..."}
{"ts": "2026-05-04T14:30:23.512Z", "type": "browser_step", "step": 1, "url": "...", "action": "click", "target": "Add Card button", "screenshot": "screenshots/step_001.jpg"}
{"ts": "2026-05-04T14:30:24.821Z", "type": "model_thought", "step": 1, "thought": "..."}
{"ts": "2026-05-04T14:30:30.001Z", "type": "verification", "channel": "deterministic", "expectation_id": "exp_1", "verdict": "pass"}
{"ts": "2026-05-04T14:30:32.445Z", "type": "verification", "channel": "vision", "expectation_id": "exp_2", "verdict": "fail", "confidence": 0.91}
{"ts": "2026-05-04T14:30:32.890Z", "type": "classification", "primary": "visual_regression", "secondary": []}
{"ts": "2026-05-04T14:30:33.012Z", "type": "run_completed", "verdict": "fail"}
```

事件 `type` 集合固定:`run_started` / `browser_step` / `model_thought` / `verification` / `classification` / `repair_attempt` / `run_completed` / `error`。

### 保留策略

**永久保留**为默认。课程项目周期不长,几百 GB 也无所谓;运行记录是答辩关键素材,自动删除会丢失证据。

工作台显示总占用空间,提供两个**手动**清理按钮:"清理 30 天前 run" / "清理失败 run"。**不自动清理**。也支持从执行记录页选择性删除单个 run。

### 报告与 trace 的关系

报告引用 trace,**不内嵌**:

- `report.json` 含 run 概览 + 关键截图相对路径 + 验证结果摘要 + 失败分类 + 指向同目录其他文件的相对路径
- 完整 trace 在 `trace.jsonl`,报告中不重复
- `report.html` 是 `report.json` 的人类可读渲染,内嵌截图用相对路径——确保整个 `{run_id}/` 目录可拷贝、可压缩、可作为附件分享时报告不破图

这种设计让 `report.html` 文件本身只有几十 KB,邮件分享方便;需要深挖时再看 `trace.jsonl` 与 `screenshots/`。

### 数据库与文件系统的分工

- **SQLite(SQLModel)**:存 run 元信息(`run_id` / `scenario_id` / `status` / `started_at` / `duration` / `verdict` / `failure_primary` / `failure_secondary` 等)和**索引字段**,支持执行记录页的列表查询、筛选、聚合统计
- **文件系统(`./data/runs/{run_id}/`)**:存大对象——截图、DOM 快照、trace、报告

数据库不存截图二进制,文件系统不维护索引。两者通过 `run_id` 连接,SQLite 中保存 `artifact_dir` 字段记录 run 目录路径(默认 `./data/runs/{run_id}/`)。

### Artifacts API

```text
GET /api/runs/{run_id}/artifacts                          # 列出 run 目录文件树
GET /api/runs/{run_id}/artifacts/{path}                   # 下载具体文件(如 screenshots/step_001.jpg)
GET /api/runs/{run_id}/trace                              # 流式返回 trace.jsonl
GET /api/runs/{run_id}/report?format=json|html|pdf        # 报告导出(html/pdf 由 json 即时渲染)
```

artifacts 目录的访问由 FastAPI 静态文件挂载提供,所有路径限定在 `./data/runs/` 子树内,防止路径穿越攻击。

## Event Bus & SSE

执行过程页的实时性靠 Server-Sent Events 把后端事件推到前端。本节定义 SSE 实现选型、内部事件总线、前端订阅、断线重连、事件 schema 统一原则。

### 后端 SSE 实现:`sse-starlette`

PyPI 包 `sse-starlette`,FastAPI 官方推荐配套。使用其 `EventSourceResponse` 而非手写 `StreamingResponse`,避免心跳保活、连接关闭、客户端断开检测、缓冲控制等细节出错(这些写错会导致连接挂死、内存泄漏)。

```python
from sse_starlette.sse import EventSourceResponse

@router.get("/api/runs/{run_id}/events")
async def stream_run_events(run_id: str, request: Request):
    last_event_id = int(request.headers.get("Last-Event-ID", 0))

    async def event_generator():
        async for event in event_bus.subscribe(run_id, after_seq=last_event_id):
            yield {
                "event": event.type,
                "id": str(event.seq),
                "data": event.json(),
            }

    return EventSourceResponse(event_generator(), ping=15)  # 15s 心跳防代理切连
```

### 内部事件总线:per-run channel + broker

每个 run 一个 channel,channel 维护订阅者列表与事件历史,支持**多订阅者**(同 run 多 tab / 多次刷新)与**事件回放**(断线重连后从指定 seq 续传):

```python
class RunChannel:
    history: list[Event]
    subscribers: list[asyncio.Queue]

class EventBus:
    """每个 run 一个 channel,channel 支持多订阅者 + 历史回放。"""

    async def publish(self, run_id: str, event: Event):
        chan = self._channels.setdefault(run_id, RunChannel())
        chan.history.append(event)
        for queue in chan.subscribers:
            await queue.put(event)

    async def subscribe(self, run_id: str, after_seq: int = 0):
        chan = self._channels.setdefault(run_id, RunChannel())
        # 1. 先吐历史(支持断线重连)
        for event in chan.history:
            if event.seq > after_seq:
                yield event
        # 2. 再吐实时事件
        queue = asyncio.Queue()
        chan.subscribers.append(queue)
        try:
            while True:
                yield await queue.get()
        finally:
            chan.subscribers.remove(queue)
```

**事件源**:`BrowserUseRunNode` / `Verifier` / `FailureClassifier` 等 LangGraph 节点通过 `event_bus.publish(run_id, event)` 发布事件;事件**同时**写入 `trace.jsonl` 文件(P2 Artifact Storage 章节定义),保证文件记录与 SSE 推送是同一份数据,无双写不一致风险。

run 结束后保留 channel 历史 5 分钟,允许后续重连或刷新,之后回收;后续历史回放从 `trace.jsonl` 文件加载。

### 前端订阅:`@microsoft/fetch-event-source`

不使用浏览器原生 `EventSource`。原生 EventSource 有三个限制:

- 不能传 POST;不能传 headers(无法支持后续鉴权)
- 自动重连机制粗糙,无法精细控制重连间隔与 Last-Event-ID 处理

`@microsoft/fetch-event-source`(微软维护、基于 fetch streaming)解决全部上述问题,API 与 EventSource 几乎一致:

```typescript
import { fetchEventSource } from "@microsoft/fetch-event-source";

const ctrl = new AbortController();
fetchEventSource(`/api/runs/${runId}/events`, {
  signal: ctrl.signal,
  headers: { /* 留口子,首版可空 */ },
  onmessage(ev) {
    handleEvent(ev.event, JSON.parse(ev.data));
  },
  onclose() { /* 主动关闭 */ },
  onerror(err) {
    return 1000;  // 1s 后重连;Last-Event-ID 自动带上
  },
});
```

### 断线重连:Last-Event-ID 机制

每个事件分配单调递增 `seq`,作为 SSE 的 `id:` 字段。客户端断开后,`fetch-event-source` 自动在重连请求头 `Last-Event-ID` 携带最后收到的 seq;后端 `subscribe(run_id, after_seq=last_event_id)` 从断点续推。

该机制对演示场景关键——一个 5 分钟的 medium 场景中途网络抖动,无重连会导致前端从头看不到中间过程,有重连则无缝续上。`per-run channel + history` 模型天然支持,启用无额外成本。

### 事件 Schema:与 trace 完全统一

SSE 推送的事件类型与 `trace.jsonl` 写入的事件类型**完全同一套 schema**——这是单一来源原则,消除"前端看到的"与"文件记录的"不一致风险。

| 事件 type | trace.jsonl | SSE | 前端消费 |
| --- | --- | --- | --- |
| `run_started` | ✓ | ✓ | 流程图初始化 |
| `browser_step` | ✓ | ✓ | 流程图节点高亮、追加事件流 |
| `model_thought` | ✓ | ✓ | "Agent 当前思考"区域 |
| `verification` | ✓ | ✓ | Verifier 节点状态、详情区域 |
| `classification` | ✓ | ✓ | 失败分类显示 |
| `repair_attempt` | ✓ | ✓ | 流程图重试动画 |
| `run_completed` | ✓ | ✓ | 显示终态、跳转结果详情 |
| `error` | ✓ | ✓ | 异常提示 |
| `browser_frame` | ✗ | ✓ | 浏览器画面主区域 |

**`browser_frame` 是唯一 SSE-only 事件**——截图本体已在 `screenshots/step_NNN.jpg`,trace 中 `browser_step` 事件引用相对路径即可,不需要在 jsonl 里再 base64 一份(文件体积会爆炸)。

公共字段:`ts` / `type` / `run_id` / `seq`;事件特有 payload 在 `data` 子对象。

### CDP Screencast WebSocket(P2 增强项)

如启用 CDP screencast 视频流(详见 "Frontend Plan" 与 "browser-use Integration"),独立 WebSocket 端点 `WS /api/runs/{run_id}/screencast`,与 SSE 端点共享 run 生命周期但通道独立。两条通道关系:

- SSE 通道(`/events`):必须订阅,承载结构化事件、文字、状态、per-step 截图
- WebSocket 通道(`/screencast`):可选订阅,承载高频 JPEG 视频帧

`BrowserUseRunNode` 启动时检测 WebSocket 端点订阅者数量,有订阅者才调用 CDP `Page.startScreencast`,无订阅者不启,避免无人观看时浪费 CPU。

### Endpoint 总览

```text
GET /api/runs/{run_id}/events         # SSE,结构化事件流(MVP 必备)
WS  /api/runs/{run_id}/screencast     # WebSocket,CDP 视频流(P2 可选增强)
```

## browser-use Integration

集成方式为 PyPI 标准包依赖，**不 fork、不改源码**。依赖固定到 `browser-use>=0.12.6,<0.13`，避免下一个 minor 破坏 API（注意 0.12 已将 `Controller` 重命名为 `Tools`，未来仍可能调整）。

```bash
uv add browser-use python-dotenv langchain-deepseek
uvx browser-use install        # 装 chromium
```

### 浏览器模式选型

browser-use 支持三种浏览器接入方式：默认 Managed Browser（自动启动独立 Chromium）、Real Browser（连接系统 Chrome 复用日常会话）、Remote Browser（通过 CDP URL 连远程 Chrome 或 browser-use Cloud）。

**本项目固定使用默认 Managed Browser**，不使用 Real Browser、不使用 Remote Browser、不使用 browser-use Cloud。理由：

- **测试可重复性**：Real Browser 与用户日常 Chrome 共享 cookie / localStorage / 历史，会污染测试状态。Managed 模式每次启动使用独立临时 user_data_dir，状态从零开始，完美契合场景 `preconditions` 语义。
- **互斥代价**：Real Browser 要求每次跑测试前完全关闭本机 Chrome，破坏开发工作流。
- **复杂度匹配**：Remote Browser 主要服务于云端部署、并发、stealth 反检测等场景，对本地课程项目过重。
- **本地全栈**：Cloud 引入 SaaS 依赖与外部 API key，违背"本地全栈"假设。

### Browser 配置

`Browser` 类与 `BrowserSession` 是同一个类的别名。直接向 `Browser(...)` 传参为推荐用法，`BrowserProfile` 为向后兼容形式。项目固定参数：

```python
from browser_use import Browser

browser = Browser(
    headless=True,                              # 不弹窗，前端统一可视化
    window_size={'width': 1280, 'height': 800},
    viewport={'width': 1280, 'height': 800},
    user_data_dir=None,                         # 显式 incognito，每次干净
    allowed_domains=effective_allowed_domains,  # 默认 4ga 域；本地 target_app_url 额外加入对应 origin
    keep_alive=False,                           # 任务结束销毁
    highlight_elements=True,                    # 默认 True，辅助 LLM 视觉识别
    wait_between_actions=0.5,                   # SPA 抖动大可调到 1.0
    minimum_wait_page_load_time=0.25,
)
```

`allowed_domains` 是关键安全/聚焦约束：LLM 偶尔会"漫游"（如点击外链跳出 demo），这条限制保证 Agent 只在目标应用域名内活动，既保证测试聚焦，也避免污染外部环境。默认线上 demo 覆盖 `*.4gaboards.com`；当 `target_app_url` 指向本地部署（如 `http://localhost:3000/`）时，执行器必须把该 origin 追加到允许域与敏感数据作用域中。

### 认证策略

4ga demo 需要登录时，按以下两种路径处理，**不使用** Real Browser 模式做"复用日常 Chrome 登录态"。

**主路径：场景化登录 + `sensitive_data`**

注册一个专用测试账号，凭据写入 `.env`，通过 browser-use 的 `sensitive_data` 机制传入：占位符出现在 task / 提示词 / 日志中，真实值仅在 DOM 填入时替换，避免凭据泄漏到 LLM 上下文。

```python
agent = Agent(
    task=task,
    llm=llm,
    browser=browser,
    tools=tools,
    sensitive_data={
        '*.4gaboards.com': {
            'FOURGA_USERNAME': os.getenv('FOURGA_USERNAME'),
            'FOURGA_PASSWORD': os.getenv('FOURGA_PASSWORD'),
        },
    },
)
```

把"登录"作为一个独立的测试场景跑通，本身就是有价值的功能点测试。若任务过程中出现登录页，task 只提示使用 `<secret>FOURGA_USERNAME</secret>` 与 `<secret>FOURGA_PASSWORD</secret>`，真实值只通过 browser-use `sensitive_data` 在输入动作中替换。

**优化路径（可选）：`storage_state` 持久化登录态**

如果套件中大量场景需要已登录前置，每次都跑登录会拖慢整体执行。此时可手动登录一次后导出 `storage_state` JSON，后续场景直接挂载：

```python
browser = Browser(
    storage_state='./4ga_auth.json',  # 自动加载 + 周期保存 cookie / localStorage
    # ...其他参数同上
)
```

实际推进顺序：先做主路径，跑通后视性能再决定是否加 storage_state 优化。

### BrowserUseRunNode 调用骨架

```python
from browser_use import Agent, Browser, Tools
from browser_use import ChatBrowserUse

def build_text_llm(settings):
    if settings.TEXT_LLM_PROVIDER == "openai_compatible":
        return OpenAICompatibleBrowserUseModel(
            base_url=settings.OPENAI_COMPATIBLE_BASE_URL,
            api_key=settings.OPENAI_COMPATIBLE_API_KEY,
            model=settings.OPENAI_COMPATIBLE_MODEL,
        )

    if settings.TEXT_LLM_PROVIDER == "browser_use":
        # Requires BROWSER_USE_API_KEY. This changes only the LLM provider,
        # not the browser execution mode.
        return ChatBrowserUse(model=settings.BROWSER_USE_MODEL)

    return ChatDeepSeek(
        model=settings.DEEPSEEK_MODEL,  # default: deepseek-v4-pro
        api_key=settings.DEEPSEEK_API_KEY,
    )

async def run_browser_use(scenario, event_bus, run_id):
    llm = build_text_llm(settings)

    browser = Browser(
        headless=True,
        window_size={'width': 1280, 'height': 800},
        viewport={'width': 1280, 'height': 800},
        user_data_dir=None,
        allowed_domains=effective_allowed_domains,
        keep_alive=False,
    )

    tools = Tools()  # 默认实例，不注册任何 4ga 领域 action

    task = build_task_from_scenario(scenario)  # 拼 steps + test_data + preconditions

    def on_step(step):
        # 向 SSE 事件总线推送 browser_frame + action_event
        event_bus.publish(run_id, build_browser_frame_event(step))
        event_bus.publish(run_id, build_action_event(step))

    agent = Agent(
        task=task,
        llm=llm,
        browser=browser,
        tools=tools,
        sensitive_data=load_sensitive_data(),  # 仅当场景需要登录
        register_new_step_callback=on_step,    # 接口名以装到的版本为准
    )

    history = await agent.run(max_steps=effective_max_steps)
    return history  # 由 TraceCollectorNode 进一步处理
```

### 实时浏览器画面：SSE 事件设计

执行过程页右侧的浏览器画面通过 SSE 事件 `browser_frame` 推送，每个 browser-use step 推一帧（per-step 截图方案）。事件 schema：

```python
{
    "type": "browser_frame",
    "run_id": "run_abc123",
    "step": 7,                          # browser-use 步序号
    "url": "https://demo.4gaboards.com/board/xxx",
    "screenshot_b64": "<base64-jpeg>",  # browser-use 内置截图
    "action_summary": "点击 'Add Card' 按钮",
    "target_bbox": {                    # LLM 当前操作元素的 bounding box
        "x": 320, "y": 480, "w": 120, "h": 32
    },
    "timestamp": "2026-05-04T12:34:56Z",
}
```

前端订阅 `/api/runs/{run_id}/events` 的 SSE，把最新一帧渲染到右侧主显示区，并在画面上叠加红色 bbox 高亮当前操作元素。所有历史帧追加到底部缩略时间线，可点击回看。

**注意事项**：

- 单帧 base64 jpeg 约 50–200KB，本地全栈下网络不是瓶颈；前端应只渲染最新帧 + 缩略时间线，不要一次性渲染所有大图。
- 历史帧的原始数据写入 artifacts 目录（每个 run 一个文件夹），SSE 事件中只内联最新一帧的 base64，时间线缩略图按需懒加载。
- 截图频率与 browser-use step 频率绑定，不需要额外定时器。

**进阶可选（CDP screencast，P2 增强项）**：

如要升级到接近视频的体验，独立加一个 WebSocket 端点 `/api/runs/{run_id}/screencast`，从 browser-use 暴露的 CDP session 调用 `Page.startScreencast`（quality=80, format=jpeg, everyNthFrame 控制帧率），帧通过二进制 WebSocket 推送，前端用 `<canvas>` 或 `<img>` 渲染，并实现 CDP 帧 ack 机制做背压。该方案与 SSE 的 per-step 截图并存：核心数据走 SSE 不变，screencast 是纯视觉增强通道，失败不影响主流程。

### 约束清单

- `tools=Tools()` 显式传入空实例以表明设计意图，而非依赖默认行为。
- 默认 LLM 客户端选 OpenAI-compatible / Codex API，使用 `OPENAI_COMPATIBLE_BASE_URL` + `OPENAI_COMPATIBLE_MODEL`。
- `BROWSER_USE_API_KEY` 可以作为可替换方案：当前端设置 `TEXT_LLM_PROVIDER=browser_use` 时，后端使用 `ChatBrowserUse(model=BROWSER_USE_MODEL)` 作为 browser-use Agent 的 LLM。
- `BROWSER_USE_API_KEY` 的使用范围仅限 Browser Use 托管 LLM provider / fallback，不得自动启用 Browser Use Cloud Browser。
- MVP 不使用 Browser Use Cloud Browser：不使用 `@sandbox` 装饰器、不传 `use_cloud=True`、不连接 `cdp_url=`，全程本地 Managed Browser 模式。
- 不使用 `Browser.from_system_chrome()` 等 Real Browser API。
- callback hook 的具体接口名（如 `register_new_step_callback`）以所装版本的 docs 为准，集成时核对。
- 凭据始终通过 `sensitive_data` 机制注入，绝不写入 task 字符串或场景 JSON。

## Feature & Scenario Generation

任务一的核心环节。本节定义 Feature 与 Scenario 的语义边界、两阶段生成流程、反幻觉机制、粒度规则、prompt 设计要点。

### 语义边界:Feature 与 Scenario

清晰区分两个概念是后续 schema 设计与 prompt 编写的前提。

- **Feature(功能点)= 能力**。回答"系统支持什么"。例:"创建 Card"是一个 Feature——系统提供"创建 Card"这一种能力。
- **Scenario(测试场景)= 路径**。回答"如何验证它支持"。例:"通过 + 号按钮创建 Card"和"通过 'Add Card' 文字入口创建 Card"是同一个 Feature 的两个不同 Scenario。

**关键约束**:Feature 描述能力本身,**不绑定实现路径**;具体的入口、操作方式、UI 交互细节属于 Scenario,不进 Feature。这一约束的原因:

- 手册原文一般描述能力("用户可以创建卡片"),很少穷举所有 UI 入口。Feature 跟手册证据对得上,Scenario 跟可观察路径对得上,两层各司其职。
- 把"操作方式"塞进 Feature 会逼 LLM 编造手册中没有的路径细节,污染证据率。
- 增量友好:发现新的实现路径时,只需新增 Scenario,Feature 不变,schema 稳定。

层级关系:

```
Feature (能力, 来自手册 RAG)
  ├─ Scenario A (一种路径, steps + expectations)
  ├─ Scenario B (另一种路径)
  └─ Scenario C (...)
```

### Feature Schema

```python
class Feature:
    feature_id: str
    title: str                       # 简短能力名,如 "创建 Card"
    module: str                      # Project / Board / List / Card / Views / Settings
    description: str                 # 1-2 句能力描述,源自手册
    evidence_quotes: list[str]       # 来自手册的逐字片段,至少 1 条
    source_urls: list[str]           # 证据所在的手册 URL
```

注意:**没有 `steps`、`expectations`、`paths`、`operations` 字段**。Feature 是抽象能力描述,不含任何实现细节。

(Scenario schema 见上文 "Backend And Agent Plan" 章节,本章不重复。)

### 两阶段生成流程(路径 B)

**阶段 1:功能点抽取**

输入:手册 RAG 检索回的 chunks(覆盖一个手册章节或一组相关章节)
输出:该批 chunks 中可识别的 Feature 列表

prompt 要点:
- 明确告知 LLM "Feature 是能力,不是操作方式"
- 要求每个 Feature 至少给出 1 条 `evidence_quote`(逐字引用 chunk 内容)
- 要求 Feature 按系统模块归类(Project / Board / List / Card / Views / Settings)
- 禁止输出实现细节(按钮名、菜单路径、selector 等)

**阶段 2:场景生成**

输入:单个 Feature(含 evidence_quotes)+ 该 Feature 相关的手册 chunks +(可选)UI affordance 提示
输出:该 Feature 对应的 N 个 Scenario(N 由 LLM 根据手册证据决定,不强制下限)

阶段 2 的 prompt 在思考引导部分列出 **"路径变化轴"**,让 LLM 沿这些维度发现可独立测试的路径:

- **入口变化**:不同 UI 入口(+ 按钮 / 文字链接 / 快捷键 / 右键菜单)——只在手册或 affordance 明确提及时使用
- **前置变化**:不同前置状态下执行(空 List 创建 vs 已有多卡的 List 创建)
- **视角变化**:本人操作 vs 跨成员可见性(若 4ga 支持多人协作)
- **数据变化原则上不在生成阶段穷举**——边界数据、异常数据由变异测试覆盖,生成阶段只用一组典型数据

**约束**:每条变化轴必须有手册证据支撑或 affordance 提示支撑,无证据的路径不允许生成。如果某个 Feature 在手册中只能找到一种实现路径,就只生成一个 Scenario——**N 由内容决定,不强制凑数**。

### 反幻觉四重校验(全开)

每个生成的 Scenario / Feature 在写入数据库前必须通过以下四道校验,任一失败即标记为 `rejected`,不计入有效产出。

**校验 1:逐字 quote 校验**

`evidence_quotes` 中每条 quote 必须是输入 chunk 文本的子串(去除空白、标点归一化后比对)。LLM 编造的 paraphrase / 改写 / 拼接式引文一律拒绝。

**校验 2:source_urls 白名单校验**

`source_urls` 必须全部出现在该次生成时传入的 chunk metadata 中。LLM 编造的 URL(包括"看起来对"的 URL)一律拒绝。

**校验 3:DOM 词汇黑名单**

`step.action` 通过正则扫描以下关键词,命中即拒绝:`selector`、`xpath`、`querySelector`、`getElementById`、`class=`、`id=`、`#xxx`、`.xxx`(CSS 类语法)、`data-*`、`aria-*`、`<button>`、`<input>` 等 HTML 标签字面量。

**校验 4:JSON Schema 校验**

- 所有必填字段齐全且类型正确
- `expectation.type` 必须在枚举集合内(`element_visible` / `text_present` / `containment` / `element_state` / `url_match` / `semantic`)
- `priority` / `difficulty` / `review_status` 必须在枚举集合内
- `evidence_quotes` 至少 1 条,`source_urls` 至少 1 条

**rejected vs needs_review 的区别**:

- `rejected`:**结构性问题**(校验失败、引文编造、含 DOM 词汇),不可执行,不可修复后自动转正,需要重新生成
- `needs_review`:**软性问题**(场景看起来合理但需要人工确认),可执行可不执行,人工审核后转 `auto_validated`

工作台显示生成质量指标:`生成总数 / 通过校验数 / rejected 数 / 各校验失败的占比`,作为生成 prompt 迭代调优的反馈信号。

### 粒度规则与 difficulty 校准

**软约束**(写在 prompt 中):

- `difficulty=simple` → 1-3 步
- `difficulty=medium` → 4-6 步
- `difficulty=hard` → 7-15 步

**后处理校准**:LLM 标注的 `difficulty` 与实际 `len(steps)` 不一致时,**自动调整 `difficulty`**(不是拒绝重生成)。理由:LLM 对难度估计偏差比对步数控制偏差更常见,自动调整 difficulty 比浪费一次生成成本更合理。

校准规则:实际步数与标注 difficulty 落在不同 bucket 时,以实际步数对应的 bucket 为准,在 `metadata.difficulty_auto_calibrated=true` 标记原因。

### `max_steps` 推断

`max_steps` 是 browser-use Agent 在执行该场景时的**决策步数上限**(LLM 级别),与场景定义的 `steps` 数(意图步数)不是一个概念——一个意图步可能需要多个 browser-use 决策步(等待 / 滚动 / 重试 / 截图)。推断公式:

- `simple` → `max_steps=20`(场景 1-3 步,给约 13-17 步缓冲)
- `medium` → `max_steps=20`(场景 4-6 步,给约 12-15 步缓冲)
- `hard` → `max_steps=35`(场景 7-15 步,给约 18-25 步缓冲)

可在系统设置中全局覆盖。

### 输出格式与重试

- DeepSeek V4 Pro 调用使用 `response_format={"type": "json_object"}` 强制 JSON 输出；Browser Use 托管 LLM provider 也必须通过可用的结构化输出机制返回同等 JSON schema
- JSON 解析失败 / 反幻觉校验失败 → retry 1 次,把具体错误信息(哪条 quote 不在源文中、哪个字段缺失等)塞回 prompt
- 第 2 次仍失败 → 标记为 `rejected`,记录失败原因,不阻塞批次中其他 Feature/Scenario 的生成

**初版不放 few-shot 示例**:prompt 短、迭代成本低、Schema 约束 + 反幻觉校验已足够强。如后续质量评估显示证据率或路径覆盖度不足,再引入 few-shot 作为升级路径。

### 数量目标

- 阶段 1 至少抽取 8 个 Feature,覆盖 4ga 主要模块(Project / Board / List / Card / Views / Settings 各至少 1 个)
- 阶段 2 平均每个 Feature 生成 ≥ 2 个 Scenario,通过四重校验后总数 ≥ 16
- N=1 的 Feature(手册中只有单一实现路径)是合法情况,但全局 N=1 的 Feature 占比应 < 30%,否则提示生成 prompt 需调优


## Task String Construction

`build_task_from_scenario(scenario)` 是连接 Scenario 与 browser-use Agent 的桥梁:它把结构化场景 JSON 转成 `Agent(task=...)` 接受的自然语言任务字符串。本节定义其格式规范、注入策略、与 history 的衔接,所有设计决策对齐 [browser-use 官方 Prompting Guide](https://docs.browser-use.com/open-source/customize/agent/prompting-guide) 推荐实践。

### 设计原则

browser-use 官方推荐的 task 格式是 **"主题句 + 三引号字符串内的编号列表"**(可嵌套缩进),而非多 section markdown。实践上 LLM 在简单结构下注意力更集中,多 section header 反而稀释信号。本项目所有 task 字符串遵循该格式,**不使用** `## 目标` `## 当前状态` 等 markdown header 分块。

### 五项构造规则

**规则 1:格式——主题句 + 编号列表**

task 字符串结构固定为三段:目标主题句、合理前置条件段、任务步骤编号列表、失败处理短指引。各段之间空行分隔,不使用 markdown header。

**规则 2:数据注入——非敏感预实体化 + 敏感占位符**

- `test_data` 中的非敏感字段(标题、描述、URL、布尔标志等)在 `build_task_from_scenario` 内部**预先替换为字面值**,出现在 task 字符串里的就是真实数据。LLM 看到 `输入 Card 标题 "完成季度报告"`,而非 `输入 Card 标题 {card_title}`。
- 敏感字段(账号、密码等)**绝不**进入 `test_data`,而是通过 `Agent(sensitive_data=...)` 的占位符机制注入。LLM 上下文中始终是占位符(如 `<secret>FOURGA_USERNAME</secret>`、`<secret>FOURGA_PASSWORD</secret>`),真值仅在 DOM 填入时由 browser-use 替换。

**规则 3:不传 expectations**

task 字符串**完全不包含**场景的 `expectations` 字段——Agent 只负责执行,验证完全由外层 DeterministicVerifier 与 VisionVerifier 独立完成。该选择基于职责分离原则:Agent 不知道"通过判定"避免其为满足 expectation 而绕过 step 走捷径;Agent 何时停止由其自身根据任务完成度判断(browser-use 内置的 `done` 机制)。

**规则 4:preconditions 作为情境信息**

`preconditions` 写在主题句之后,以"合理前置条件"标题引出,后跟"如当前状态与前置条件不符,请先自主达成前置,再执行任务步骤"的短指引。**不写**"先做 X 再做 Y"这种硬流程指令——preconditions 是 Agent 自主达成的目标,不是 Agent 必须执行的指令。该设计避免 preconditions 干扰 Agent 对主任务的决策路径。

**规则 5:零 action 命名提示**

不强制 LLM 使用特定 action(如不写 "Use click action"、"Use drag_drop action")。所有 step 保持纯意图描述,由 LLM 自主决策映射到合适的 browser-use action。该约束适用于**所有场景**,**包括拖拽**——前期实验确认 browser-use 在 4ga 拖拽上能自主选对 action,无需提示。该决策与"零 locator 纯意图""零专用 Tool"哲学保持一致。

### task 字符串模板

以"在 To Do List 中创建一张 Card"场景为例,生成的 task:

```
在名为 "To Do" 的 List 中创建一张标题为 "完成季度报告" 的 Card。

执行该任务的合理前置条件:
- 已位于 https://demo.4gaboards.com/ 应用首页或某个 Board 内
- Board 中存在名为 "To Do" 的 List

如当前状态与前置条件不符,请先自主达成前置,再执行任务步骤。

任务步骤:
1. 进入 4ga Boards demo 应用 (https://demo.4gaboards.com/)
2. 在名为 "To Do" 的 List 中找到添加 Card 的入口并点击
3. 输入 Card 标题 "完成季度报告"
4. 确认创建(任一可行方式)

如合理尝试后仍无法推进某一步:
- 使用 done action 结束任务,success=false
- 在 done action 的结果中清楚说明卡在第几步、什么原因
  (找不到元素 / 元素无响应 / 状态不符 / 其他)
- 不要在不确定时反复盲目尝试同一动作
```

### `build_task_from_scenario` 函数签名

```python
def build_task_from_scenario(scenario: TestScenario) -> str:
    """
    将结构化场景转为 browser-use task 字符串。

    - 主题句由 scenario.title 派生,test_data 字段直接实体化嵌入
    - preconditions 列表作为情境信息,而非硬指令
    - steps[].action 已经是预实体化的纯意图描述
    - expectations 完全不传给 Agent
    - 失败处理短指引固定文本,引导 done action 报告
    """
    title_line = render_title(scenario.title, scenario.test_data)
    preconditions_block = render_preconditions(scenario.preconditions)
    steps_block = render_steps(scenario.steps, scenario.test_data)

    return f"""{title_line}

执行该任务的合理前置条件:
{preconditions_block}

如当前状态与前置条件不符,请先自主达成前置,再执行任务步骤。

任务步骤:
{steps_block}

如合理尝试后仍无法推进某一步:
- 使用 done action 结束任务,success=false
- 在 done action 的结果中清楚说明卡在第几步、什么原因
  (找不到元素 / 元素无响应 / 状态不符 / 其他)
- 不要在不确定时反复盲目尝试同一动作
""".strip()
```

`scenario_id` 等元数据**不写入 task 字符串**(对 LLM 是无用噪音),通过 BrowserUseRunNode 的 metadata 关联。

### Agent History 字段消费

`history = await agent.run(max_steps=...)` 返回的 `AgentHistoryList` 是 BrowserUseRunNode 的核心产出,后续节点按以下方式消费(参考 [Output Format 文档](https://docs.browser-use.com/open-source/customize/agent/output-format)):

| history 方法 | 消费方 | 用途 |
| --- | --- | --- |
| `is_done()` / `is_successful()` | DeterministicVerifier | Agent 自报成败的初判信号 |
| `last_action()` | FailureClassifier | 读取 `done(success=false, message=...)` 结构化失败原因 |
| `action_history()` | TraceCollector / 前端事件流 | 精简版 action 序列,显示给用户 |
| `screenshots()` | TraceCollector / 前端浏览器画面 | per-step 截图源,推 `browser_frame` SSE 事件 |
| `urls()` | DeterministicVerifier(`url_match`) | URL 变迁序列,验证导航类 expectation |
| `model_thoughts()` | TraceCollector / 前端事件流 | Agent 的推理过程,显示在事件流"Agent 当前思考"字段 |
| `errors()` | FailureClassifier | 执行过程中的异常事件 |
| `total_duration_seconds()` | Reporter / 评估指标 | 计入"平均执行时长"指标 |

注意:Agent 自报 `is_successful()=true` **不等于**测试通过——只表示 Agent 觉得自己完成了任务。最终通过判定由外层双通道 verifier 给出,这是"执行与验证职责分离"的体现。

## Verification Pipeline

执行结束后由 DeterministicVerifier 与 VisionVerifier 双通道独立判定,经仲裁规则汇总成单条 expectation 的最终结果,再综合成场景级结论。本节定义两条通道的实现、仲裁矩阵、低置信度处理、失败回填给 FailureClassifier 的数据契约。

### 验证快照采集时机

Agent `agent.run()` 返回后**不**立即抓 DOM。BrowserUseRunNode 显式做以下三步,产出 `VerificationSnapshot` 供两条 verifier 通道共享消费:

1. 等待 500ms(可在系统设置覆盖)——给 SPA 异步刷新、动画、toast 弹窗收尾时间
2. `await page.wait_for_load_state('networkidle', timeout=3000)`——避免无限等待
3. 抓取:DOM 树 + 全页面纯文本 + 当前 URL + 终态截图

理由:SPA 中"Agent 觉得任务完成"和"DOM 已稳定"经常错位 200-500ms,直接用 `history.dom_snapshots()[-1]` 容易抓到中间态,导致大量假失败。

`VerificationSnapshot` 字段:

```python
class VerificationSnapshot:
    dom_state: BrowserUseDomState        # 同 LLM 看到的 element 抽象,含 clickable_elements
    full_page_text: str                  # 整页纯文本
    current_url: str
    screenshot_final: bytes              # 终态截图(JPEG)
    screenshot_initial: bytes            # 执行**起点**截图(自 history.screenshots()[0])
    html_snapshot: str                   # browser-use/浏览器快照导出的静态 HTML 或可访问性摘要
```

### DeterministicVerifier 实现

主路径用 browser-use 的 DOM 抽象(与 LLM 看到的 element 视图一致,避免认知错位);需要 ARIA 属性 / 禁用态等抽象表达不出的检查时,基于 browser-use 可导出的 DOM/HTML/可访问性快照做只读解析。MVP 不引入 Playwright page 句柄、locator API、隐藏测试 runner 或任何 Playwright fallback。

各 expectation type 的检查实现:

```python
def check_element_visible(params, snapshot):
    """params: {text, container_text?}"""
    target = params['text']
    container = params.get('container_text')
    for el in snapshot.dom_state.clickable_elements:
        if target in el.visible_text:
            if container is None or is_descendant_of_text(el, container, snapshot.dom_state):
                return Pass()
    return Fail(f"未找到含文本 '{target}' 的可见元素")

def check_text_present(params, snapshot):
    """params: {text, not_present?}"""
    found = params['text'] in snapshot.full_page_text
    if params.get('not_present', False):
        return Pass() if not found else Fail(f"文本 '{params['text']}' 不应存在但找到了")
    return Pass() if found else Fail(f"未在页面中找到文本 '{params['text']}'")

def check_containment(params, snapshot):
    """params: {child_text, parent_label}"""
    return is_descendant_of_text(
        params['child_text'], params['parent_label'], snapshot.dom_state
    )

def check_element_state(params, snapshot):
    """params: {element_text, state}; 基于 DOM/HTML/可访问性快照判断
       state ∈ {disabled, enabled, checked, unchecked, expanded, collapsed, selected}"""
    element = find_element_by_visible_text(snapshot.dom_state, params['element_text'])
    if element is None:
        element = find_element_by_text_in_html(snapshot.html_snapshot, params['element_text'])
    return _eval_snapshot_state(element, params['state'])

def check_url_match(params, snapshot):
    """params: {pattern? | contains? | equals?}"""
    url = snapshot.current_url
    if 'pattern' in params: return Pass() if re.search(params['pattern'], url) else Fail(...)
    if 'contains' in params: return Pass() if params['contains'] in url else Fail(...)
    if 'equals' in params: return Pass() if url == params['equals'] else Fail(...)
```

每个检查返回 `Pass()` 或 `Fail(reason, evidence)`,evidence 含"实际值 vs 预期值"用于报告显示。

`expectation.type='semantic'` 不走 DeterministicVerifier。

### VisionVerifier (GLM-4.6V)

**调用接口**:Z.ai OpenAI 兼容 API `https://api.z.ai/api/paas/v4/chat/completions`,model=`glm-4.6v`,Bearer auth。

**输入**:执行**起点**截图 + **终态**截图(双帧对比)。利用 GLM 128K context 装得下两张大图的能力,前后对比对"创建/删除/更新"类语义判定显著更准。

**thinking 模式启用**(`"thinking": {"type": "enabled"}`):返回推理痕迹,延迟成本可接受,对答辩演示和失败定位有显著价值。

**Prompt 模板**:

```text
你是一个 Web 应用 UI 测试的视觉验证助手。系统已对 4ga Boards 应用执行了一项测试操作,
你需要判断该操作是否成功完成预期效果。

测试场景标题: {scenario.title}
预期描述: {expectation.description}

第一张截图是操作执行**前**的页面状态。
第二张截图是操作执行**完成后**的页面状态。

请基于这两张截图,判断"预期描述"是否成立。

判断时考虑:
- 该预期描述的核心可观察特征是什么(出现了什么 / 消失了什么 / 变成了什么)
- 在前后截图对比中,这些特征是否如预期出现
- 是否存在视觉异常:布局错乱、元素重叠、文本渲染异常、CSS 失效等

输出严格 JSON 格式,不要 markdown 代码块包装:
{"verdict": "pass" | "fail" | "uncertain",
 "confidence": 0.0-1.0,
 "reasoning": "1-3 句推理过程",
 "evidence": "在截图中观察到的具体视觉证据",
 "suggested_failure_type": "visual_regression" | "state_mismatch" | "agent_planning_error" | null}
```

**两类调用触发条件**:

- **逐条调用**:`expectation.type='semantic'` 时,该条 expectation 调用一次,prompt 中 `expectation.description` 填该条的描述
- **场景级总判**:场景 `requires_visual_check=true` 时,**额外**对终态截图做一次"整体视觉总判断",prompt 中 expectation.description 替换为"页面整体视觉与该测试场景的目标一致,无明显布局错乱、元素重叠、CSS 失效等视觉异常"

### 置信度阈值与三态结果

| 置信度区间 | 处理 |
| --- | --- |
| `confidence >= τ_high` | 信任 GLM 判断(pass / fail) |
| `τ_low <= confidence < τ_high` | 视为低置信度,该 expectation 进 `needs_review`,不计入真失败 |
| `confidence < τ_low` 或 `verdict='uncertain'` | 同上,进 `needs_review` |

**默认阈值**:`τ_high=0.85`,`τ_low=0.6`。**两个阈值在前端"系统设置"抽屉中可调**,实时覆盖默认值,无需重启。这给了答辩演示与实验调优的灵活性——演示时可临时调高阈值看严格判定的效果,实验时可调低看宽松判定下的通过率。

### 仲裁规则与判定矩阵

每条 expectation 独立判定,场景最终结果由所有 expectation 综合得出。

**单条 expectation 判定矩阵**:

| 配置 | DeterministicVerifier | VisionVerifier | 单条最终结果 |
| --- | --- | --- | --- |
| 非 semantic | pass | (不调用) | **pass** |
| 非 semantic | fail | (默认不补 GLM) | **fail**,记入失败分类 |
| 非 semantic + 场景 `requires_visual_check=true` | pass | pass | **pass** |
| 非 semantic + 场景 `requires_visual_check=true` | pass | fail(高置信) | **fail** → `visual_regression`(DOM 通过但视觉失败) |
| 非 semantic + 场景 `requires_visual_check=true` | fail | pass(高置信) | **fail-soft** → `dom_mismatch_visually_correct`,**进 needs_review**,**不计真失败** |
| 非 semantic + 场景 `requires_visual_check=true` | fail | fail | **fail**,失败分类按 GLM 的 `suggested_failure_type` 优先 |
| 任意 + GLM 置信度低或 uncertain | (按规则) | low-conf / uncertain | **needs_review**,不计真失败 |
| semantic | (不调用) | pass(高置信) | **pass** |
| semantic | (不调用) | fail(高置信) | **fail** |
| semantic | (不调用) | low-conf / uncertain | **needs_review**,不计真失败 |

**场景级综合**:

- 所有 expectation 都 pass → 场景 **pass**
- 任一 expectation fail → 场景 **fail**
- 无 fail 但有 needs_review → 场景 **needs_review**

**`dom_mismatch_visually_correct` 的设计意图**:这不是"成功"也不是"失败",而是"verifier 适配可能有问题"。在 verifier 还在持续调优阶段,这一类型避免把 verifier 自身 bug 错误归因到应用 bug,保持失败分类的准确性。后续若该类样本占比稳定低(<5%),说明 verifier 已成熟,可以考虑把它降级为普通 fail。

### 失败回填给 FailureClassifier 的 schema

verifier 输出失败/needs_review 时,把所有信号源**保留不合并**地传给下游 FailureClassifier。FailureClassifier 自行综合三源信号判断失败类别。

```python
class VerificationFailure:
    # 失败的具体 expectation
    expectation_id: str
    expectation_type: str               # element_visible / semantic / ...
    expectation_description: str

    # DeterministicVerifier 输出(None 表示未检查)
    deterministic_verdict: Optional[Literal["pass", "fail"]]
    deterministic_reason: Optional[str]
    deterministic_evidence: Optional[dict]   # 实际值 vs 预期值

    # VisionVerifier 输出(None 表示未检查)
    vision_verdict: Optional[Literal["pass", "fail", "uncertain"]]
    vision_confidence: Optional[float]
    vision_reasoning: Optional[str]
    vision_evidence: Optional[str]
    vision_suggested_failure_type: Optional[str]

    # Agent 自身信号(从 history 抽取)
    agent_self_reported_success: Optional[bool]
    agent_done_message: Optional[str]        # done(success=False, message=...) 内容
    agent_errors: list[str]                  # history.errors()

    # 上下文
    final_url: str
    screenshots: list[str]                   # 关键帧截图路径
    final_dom_summary: str                   # DOM 摘要,供 classifier 二次判断
    arbitration_label: Literal["fail", "fail_soft", "needs_review"]
```

**关键设计原则**:三源信号(deterministic / vision / agent self-report)**独立保留**,verifier 不合并、不预判分类。这给 FailureClassifier 留出充分判据空间——例如 Agent 自报成功 + DOM 失败 + 视觉成功的组合,可能指向"DOM 选择器漂移"而非应用 bug,这种细微判断只有 classifier 拿到全部信号才能做出。

## Failure Classification

FailureClassifierNode 消费 VerificationFailure 数据,将每次失败映射到 8 类有效失败类别之一(或 `unknown` 兜底)。同一次失败可能命中多类,以"主因 + 副因"结构表达。本节定义判定方式、各类触发规则、优先级、修补策略对应。

### 判定方式:规则引擎 + LLM-as-Judge 混合

混合架构,规则引擎跑在前,任一规则命中即返回结果;所有规则都不命中,再调 LLM-as-Judge 处理模糊类。

理由:8 类失败中至少 4 类有明确信号(URL 不匹配 / Agent 自报 + max_steps / 视觉仲裁结果等),if-else 决策树又快又准且课程项目可解释性强;但 `state_mismatch` 与 `agent_planning_error` 的边界模糊——Agent 完成所有步骤、DOM 有变化、但终态不对,到底是 LLM 想错还是状态语义错位,需要 LLM 看上下文综合判断。LLM-as-Judge 兜底而非主用,避免在 8 类间幻觉分类、节省 token。

LLM-as-Judge 用当前配置的文本模型（默认 DeepSeek V4 Pro）,prompt 中给出全部 VerificationFailure 信号 + 8 类定义 + 已有 action history,要求其指明类别 + 偏离的具体 step 序号 + 推理。**不强制返回 8 类之一**——若 LLM 也无法定位,返回 `unknown`。

### 8 类有效失败 + 1 类兜底:触发规则

每类触发条件如下,规则引擎按"决策点 3 优先级链"顺序判定。

**`navigation_failure`(规则)**

任一命中:
- `expectation.type == 'url_match'` 且 deterministic.verdict == 'fail'
- Agent done_message 含"页面打不开 / 导航失败 / 404 / 5xx"
- URL 序列中存在 4xx/5xx 响应(从 history.errors() 或 page response 检测)

**`element_not_found`(规则)**

任一命中:
- `expectation.type == 'element_visible'` 且 deterministic 与 vision 双通道一致认定缺元素
- Agent done(success=False) 且 done_message 含"找不到 / 无法定位 / 未发现"
- Agent 步数达 max_steps 且 last action 序列显示反复尝试同一目标(同一 element_text 连续 click ≥ 3 次)

**`interaction_failure`(规则)**

任一命中:
- Agent done_message 含"无响应 / 点击无效 / 输入无效"
- action_history 显示动作执行成功但前后帧 DOM 关键子树无 diff(URL 不变 + 关键 DOM 子树无变化)
- 拖拽场景特殊处理:drag 完成但 containment 检查失败

**`timing_issue`(规则,带主动重抓机制)**

任一命中:
- networkidle 等待超时(`wait_for_load_state` 触发 timeout)
- deterministic 第一次 fail 后,**主动延迟重抓机制**触发——再等 1.5s 重抓 DOM 二次验证,若第二次 pass 则归类此项
- GLM reasoning 中明确提到"页面似乎仍在加载 / loading 指示器存在"

**主动重抓**是用结果反推原因的兜底法:timing 与 element_not_found 信号上难分,通过"等久一点是否能通过"来识别。开销:每次"二次验证 deterministic.fail 是否为 timing"多 1.5s,但显著降低假 element_not_found 误判率,值得这个代价。

**`state_mismatch`(LLM-as-Judge)**

规则触发:
- Agent self_reported_success == True
- 部分 expectation 通过部分 fail
- DOM 上能看到操作"做了什么",但终态与预期不符

→ 转 LLM 判定。例:Agent 创建了卡但创建到错误的 List。Agent 觉得自己完成,DOM 也确实多了一张卡,但 containment 失败。

**`visual_regression`(规则,完全由仲裁决定)**

仲裁矩阵已映射:`deterministic.verdict == 'pass'` + `vision.verdict == 'fail'` 且置信度 ≥ τ_high。直接打标。

**`agent_planning_error`(LLM-as-Judge,严格)**

规则触发:
- Agent done(success=False) 且 done_message 体现"思路混乱"特征
- action_history 中有"做了又撤销"模式(执行 X 后立刻执行反向 X)

→ 转 LLM 判定。LLM **必须明确指出**偏离的 step 序号 + 偏离类型,否则**不归此类**——避免 agent_planning_error 沦为"不知道是啥"的垃圾桶。

**`dom_mismatch_visually_correct`(规则,完全由仲裁决定)**

仲裁结果 == 'fail_soft' 时直接打标,不再判别。该类进 needs_review,不计入真失败。

**`unknown`(兜底)**

所有规则都不命中,LLM-as-Judge 也未能定位到 8 类正常类别——记 `unknown`,保留原始 VerificationFailure 待人工分析。**该类不计入对外的"8 类有效失败分类"指标**,只作内部诊断。

### 多类命中:主因 + 副因结构

同一次失败可能命中多类(例:Agent 自报失败 + DOM 没找到元素 + step 间反复横跳 → 同时是 element_not_found 与 agent_planning_error)。FailureClassifier 输出双层结构:

```python
class FailureClassification:
    primary: FailureCategory          # 主因
    secondary: list[FailureCategory]  # 副因列表(可空)
    primary_reason: str               # 主因的诊断原因(LLM 类则附 LLM 推理)
    deviation_step: Optional[int]     # 仅 agent_planning_error / state_mismatch 必填
    raw_signals: VerificationFailure  # 原始三源信号留存供报告
```

**优先级链**(主因取命中类中最高优先级者):

1. **纯仲裁类**:`visual_regression` / `dom_mismatch_visually_correct`
2. **强信号规则类**:`navigation_failure` / `element_not_found` / `interaction_failure` / `timing_issue`
3. **LLM 类**:`state_mismatch` / `agent_planning_error`
4. **兜底**:`unknown`

**指标计算**:每次失败按主因计 1 类(用于"6 类失败分类"验收指标);副因不计入分类率,只在执行结果详情页展示。

### RepairPlannerNode:修补策略对应表

并非所有失败都进入修补——有些类修了也是浪费 token,有些是要报告的应用 bug,不应自动重试。

| 失败类 | 是否修补 | 修补策略 |
| --- | --- | --- |
| `navigation_failure` | 修 | 重新导航到 demo URL,从头执行 |
| `element_not_found` | 修 | 重启 Agent,把 done_message 反馈进 task("上次卡在 step X,因 Y,本次注意…") |
| `interaction_failure` | 条件修 | 仅疑似动画/异步原因时重试;元素根本无响应则放弃 |
| `timing_issue` | 修 | 重启 Agent,临时把 `wait_between_actions` 翻倍 |
| `state_mismatch` | **不修** | 修了也是同样的错误判断,不会改变结果 |
| `visual_regression` | **不修** | 视觉问题改不了,这是要报告的应用 bug |
| `agent_planning_error` | 修(LLM 引导) | 把"上次 action 序列 + LLM 指出的偏离 step"反馈进 task,让 Agent 重做 |
| `dom_mismatch_visually_correct` | **不修** | 这是 verifier 适配问题,要查的是 verifier 本身 |
| `unknown` | **不修** | 不知道哪错了修啥 |

**全局重试预算**:每 run 最多重试 2 次(系统设置可覆盖),触发任何修补类型都计入预算。预算用尽仍失败 → 封盘进入最终报告,不再尝试。这避免修补陷入死循环。

修补成功率作为评估指标:`修补后转通过的比例 / 触发修补的总次数`,在 Reporter 中计入。

## Core Workflow

1. 文档爬取与索引
   Crawl4AI 爬取 4ga Boards 的 user-manual 与 admin-manual(完全排除 developer-manual,仅 en 版本)。`MarkdownHeaderTextSplitter` 按 `#/##/###` 切分,`RecursiveCharacterTextSplitter` 兜底超长块。每个 chunk 装配 metadata(`source_url` 精确到 H2 anchor、`module`、`heading_path`、`content_hash` 等),当前配置的文本模型（默认 DeepSeek V4 Pro）预分类 `is_ui_operational` 标签,经 MiniLM-L6 embedding 后写入本地 ChromaDB。`content_hash` 实现增量更新,仅新增/变化 chunk 调用 LLM 预分类。详见 "RAG Indexing & Retrieval" 章节。

2. 功能点抽取与场景生成
   两阶段流程,详见 "Feature & Scenario Generation" 章节。阶段 1 从手册 chunks 抽取 Feature(纯能力描述);阶段 2 为每个 Feature 沿"路径变化轴"生成多个 Scenario。所有产出经反幻觉四重校验(逐字 quote / URL 白名单 / DOM 词汇黑名单 / JSON Schema),失败标记为 `rejected`。

3. （可选）UI Affordance 提示生成
   离线访问 demo，提取页面级别的语义信息（"该页面有 Add Card 文字入口""卡片支持拖拽到其他 List"），作为场景生成时的软提示提供给 LLM，帮助其确认手册描述的功能在实现中存在。**该信息只用于场景生成阶段，不进入运行时执行路径，不作为定位信息**。如实验显示无明显增益，可不实施。

4. 场景执行
   前端点击运行后创建 run,跳转执行过程页。LangGraph 加载场景。对依赖型场景(`fixtures` 非空),`FixtureResolverNode` 先解析绑定与占位符:有有效绑定且元素仍在则直接复用,否则前端弹窗由用户选择既有元素或新建(经 `FourgaApiClient` 调 4ga REST API),并把绑定值注入 `steps`/`test_data`/`expectations`;前置数据无法建立时 run 以 `error`(`precondition_setup_failure`) 结束、不进入 browser-use(详见 "Key Design Decisions" 决策四与 `docs/FIXTURE_PROVISIONING.md`)。随后 `BrowserUseRunNode` 将场景 `steps` + `test_data` + `preconditions` 拼成自然语言任务字符串交给 browser-use Agent,由 LLM 自主选择 DOM 元素与 action 完成整段交互。执行期间通过 hook 向 SSE 事件总线推送 action、截图、DOM、URL 变迁,前端实时显示。`max_steps` 由场景的 difficulty 推断(simple=20、medium=20、hard=35,详见 "Feature & Scenario Generation" 章节),可在系统设置中覆盖。

5. 结果验证
   BrowserUseRunNode 完成后等待 500ms + `networkidle` 后采集 `VerificationSnapshot`(DOM/纯文本/URL/起终态截图)。DeterministicVerifier 按 expectation.type 分发结构化检查;`semantic` 类与 `requires_visual_check=true` 触发 VisionVerifier 调 GLM-4.6V(双帧对比 + thinking 模式)。两条通道结果经仲裁矩阵综合,低置信度进 `needs_review`,DOM/视觉冲突进 `dom_mismatch_visually_correct`。详见 "Verification Pipeline" 章节。

6. 失败分类与修补
   FailureClassifierNode 用规则引擎 + LLM-as-Judge 混合方式,把 VerificationFailure 映射到 8 类有效失败之一(或 `unknown` 兜底),输出主因 + 副因双层结构。规则命中即返回,LLM 仅处理 `state_mismatch` / `agent_planning_error` 等模糊类。RepairPlannerNode 按修补策略表对部分类别(navigation/element_not_found/timing/agent_planning_error 等)生成修补尝试,全局重试预算 2 次,用尽后封盘。详见 "Failure Classification" 章节。

7. 报告与记录
   每次运行保存为执行记录，生成 JSON/HTML 报告，包含步骤轨迹、每步截图、action 序列、验证结果、失败分类、手册证据和覆盖率。PDF 报告作为可选导出。

## Mutation Testing

变异测试目标是评估系统识别"典型应用错误"的能力。**首版仅实现接口与数据结构 stub,具体生成算法作为后续版本开发**——核心系统(场景生成 → 执行 → 验证 → 失败分类)主链路打通后再补完。本节定义 stub 边界与未来实现的接入契约。

### 三类变异语义

- **数据变异(`data`)**:替换 `test_data` 字段值——超长标题、空字符串、特殊字符、SQL/HTML 注入字面量、Unicode 边界——保持 steps 与 expectations 不变,观察应用是否正确处理边界数据
- **流程变异(`flow`)**:对 steps 序列做删除某步 / 调换两步顺序 / 插入冗余步骤,观察 Agent 是否检测到流程偏离与 expectations 不符
- **预期反转(`expectation_inversion`)**:将 expectation 反向(如 `element_visible` 改为期望"不出现"),保持 steps 不变,验证 verifier 能正确报告"功能正确执行但与变异预期不符"——区分"应用 bug"与"测试预期 bug"

### 数据结构

变异 Scenario 与普通 Scenario 共享同一执行流(BrowserUseRunNode → Verifier → FailureClassifier),因此**复用 scenarios 表**,不开独立表。普通 Scenario 表新增两个字段:

- `is_mutation: bool` (DEFAULT FALSE)
- `source_scenario_id: Optional[str]` (普通 Scenario 为 NULL)

`MutatedScenario` 继承 `TestScenario` 全部字段,额外承载变异元数据:

```python
class MutatedScenario(TestScenario):
    mutation_id: str                              # 变异 id,与 scenario_id 不同
    source_scenario_id: str                       # 关联原 Scenario
    mutation_type: Literal["data", "flow", "expectation_inversion"]
    mutation_description: str                     # 自然语言描述变异内容
                                                  # 例:"将 card_title 替换为 5000 字符长字符串"
    mutation_params: dict                         # 变异参数,具体内容由 type 决定
    expected_detection: bool                      # 期望分类器能否检测到此变异
    detection_outcome: Optional[Literal[          # 运行后回填:实际检测结果
        "detected_correctly",                     # 检测到且预期为检测到
        "missed",                                 # 没检测到但预期检测到
        "false_positive",                         # 检测到但预期不检测到
        "true_negative"                           # 没检测到且预期不检测到
    ]] = None
```

`expected_detection` 与 `detection_outcome` 是变异检出率指标的算盘:

```
mutation_score = count(detection_outcome == "detected_correctly")
               / count(expected_detection == True)
```

各类变异的 `expected_detection` 默认值:
- `data`:依变异内容定——若是合法但极端的边界数据(如 5000 字符标题),期望应用兼容(`expected_detection=False`,unexpected 失败才计 bug);若是非法数据(如空标题),期望应用拒绝(`expected_detection=True`)
- `flow`:依流程修改类型定——删除关键步骤通常 `True`(应破坏功能),调换无依赖步骤可能 `False`(不应破坏)
- `expectation_inversion`:**必为 `True`**——反转预期必然与执行结果不符,verifier 必须能识别

### Stub API

```text
POST /api/mutations/generate
请求体:
{
  "scenario_ids": ["sc_xxx", "sc_yyy"],
  "mutation_types": ["data", "flow", "expectation_inversion"],   # 可选,默认全 3 类
  "max_per_scenario": 3                                          # 可选,默认 3
}
响应:
{
  "mutations": [...]   # MutatedScenario[]
}
```

**首版 stub 行为**:接口存在并返回有效 schema,内部生成器返回空数组或写死示例 1-2 条用于打通前端展示。完整生成算法作为后续版本实现。

### 与运行流的关系

变异 Scenario 走与普通 Scenario 完全相同的执行链:点击运行 → BrowserUseRunNode → 双通道 verifier → FailureClassifier。区别仅在 FailureClassifier 输出后多一步:**根据 `expected_detection` 与实际是否被分类为失败,回填 `detection_outcome`**。该回填逻辑是变异专属增量,代码量不大,放在 ReporterNode 或 FailureClassifierNode 末尾均可。

前端测试场景表格用 `is_mutation` 字段做筛选(默认隐藏变异 / 仅看变异 / 全部),不需要新建独立页面。

### 未来实现要点(留作后续开发参考)

- 数据变异生成器:维护一个变异规则库(空值/超长/特殊字符/注入字面量/Unicode 边界等),按 `test_data` 字段类型选适用规则
- 流程变异生成器:基于 steps 顺序的图算法(删除非首尾步、对换无依赖相邻步、插入空操作步)
- 预期反转生成器:对 `expectation.type` 与 `params` 应用确定性反转规则(`element_visible` ↔ `not_present`,`url_match.contains` 改为不含,etc.)
- 每条变异生成时同步推断 `expected_detection` 默认值并允许覆盖

## Evaluation Metrics

任务一（场景生成）：

- 功能点覆盖数与手册章节覆盖率。
- 场景证据率：携带 `evidence_quotes` 的场景占比。
- 证据对齐度：随机抽样场景，由独立 LLM-as-Judge 评估 step+expectation 是否真实反映 evidence_quotes 的语义（5 分制）。
- 场景粒度合理性：人工抽查 + 自动指标（步数中位数、复杂场景比例）。

任务二（执行与验证）：

- 简单场景通过率（目标 ≥ 80%）。
- 中等场景通过率（目标 ≥ 60%）。
- 困难场景尝试率与通过率。
- 平均执行步数与时长。
- Verifier 精确率/召回率：人工标注 N 个 run 的真实成败，对比 verifier 判断。
- 失败分类准确率：人工标注失败原因，对比 FailureClassifier 输出。
- 变异检出率：注入 N 个变异，FailureClassifier 正确识别的比例。
- 重试有效性：RepairPlanner 修补后转通过的比例。

附加观测：

- 无领域封装通过率：本系统全程不使用专用 Tool，所获通过率即"通用 Web Agent 在 4ga 上的开箱通过率"，作为创新档观察值汇报。

## Test Plan

单元测试：

- TestScenario schema 校验：拒绝包含 `locator` / `selector` / `xpath` 字段的输入。
- 无 evidence_quotes 或 quote 不在源 chunk 中的场景自动标记为 `rejected`(反幻觉校验失败)。
- expectation.type 分发逻辑：每种 type 路由到正确的 verifier 实现。
- GLM-4.6V verifier 输出 JSON 解析、低置信度阈值处理、超时回退。
- `MutatedScenario` schema 校验、`POST /api/mutations/generate` 接口可访问、返回符合 schema(stub 阶段允许返回空数组或固定示例)。

集成测试：

- 成功爬取并索引 user-manual 与 admin-manual,LLM 预分类 `is_ui_operational` 标签覆盖率 100%。
- 至少抽取 8 个 Feature,覆盖 4ga 主要模块(Project / Board / List / Card / Views / Settings 各至少 1 个)。
- 平均每个 Feature 通过四重校验的 Scenario ≥ 2 个,Scenario 总数 ≥ 16,全部 schema 合法且不含 DOM 字段。
- 反幻觉校验拒绝率(`rejected` 占比)< 40%,否则提示生成 prompt 需调优。
- 场景表格、详情抽屉、JSON 查看、运行跳转完整可用。
- 执行过程页能实时更新 Agent 节点、action 历史和截图。
- 执行记录能展示历史 run 和结果详情。

E2E 验收（全部由 browser-use 通用能力完成，无专用 Tool）：

- 创建 board 并验证名称可见。
- 创建 list 并验证 list 可见。
- 创建 card 并验证 card 出现在目标 list。
- 编辑 card 标题和描述并验证内容更新。
- 拖拽 card 到另一个 list，DOM 包含关系与 GLM-4.6V 双通道验证通过。
- 切换 Board/List 视图并验证视觉状态。
- (可选,后续版本)运行三类变异场景并通过 `detection_outcome` 回填正确反映检出结果。首版仅验证 stub 接口与 `is_mutation` 字段筛选可用。

验收标准：

- 完整覆盖"爬取、索引、功能点、场景、执行、验证、记录、报告、前端可视化"流程。
- 简单场景通过率 ≥ 80%。
- 中等场景通过率 ≥ 60%。
- 至少 6 类有效失败分类被实际触发并各有 ≥ 1 个真实样本(系统实现 8 类 + unknown 兜底,详见 "Failure Classification" 章节)。
- 变异测试接口与 schema 在首版中保留 stub,具体生成算法的实现作为后续版本(详见 "Mutation Testing" 章节)。
- 测试场景全部为零 locator 设计。
- 执行器全程不使用专用 Tool 与 Playwright。
- 前端必须包含完整 App Shell、顶部设置入口、可收纳侧边栏、仪表盘、功能点树、场景表格、实时执行图、历史记录详情。

## Assumptions

- 前端使用 `Next.js App Router + TypeScript`。
- 运行方式为本地全栈。
- UI 默认中文。
- 系统设置入口放在顶部栏右侧，不放入侧边栏。
- 视觉模型固定为 `GLM-4.6V`。
- 文本模型默认使用 OpenAI-compatible / Codex API，默认模型 ID 为 `gpt-5.5`；`DeepSeek V4 Pro` 作为兼容路径保留。
- 不修改 browser-use 核心源码，不 fork 仓库。通过 PyPI 标准依赖集成，版本 pin 到 `browser-use>=0.12.6,<0.13`。
- LangGraph 不重做 browser-use 的 Agent 内部 loop。Plan/Execute 由 browser-use 承担，LangGraph 编排 trace 收集、双通道验证、失败分类、修补、报告等执行**之后**的环节。
- 不引入 Playwright；browser-use 通用能力（含拖拽）经实测足以覆盖 4ga 全部核心交互。
- 不封装任何 4ga 领域专用 action；`browser-use Tools` 使用默认实例，仅在架构上预留 `@tools.action` 扩展点。
- 测试场景采用纯意图描述，不含 DOM locator、selector、xpath、element index 等定位信息；定位由 LLM Agent 在运行时基于 DOM 观察完成。
- 浏览器使用 browser-use 的默认 Managed 模式（独立临时 Chromium 实例），不使用 Real Browser 模式（`Browser.from_system_chrome()`）、不使用 Remote Browser 模式（`cdp_url=`）、不使用 Browser Use Cloud Browser（`@sandbox` / `use_cloud=True`）。
- 浏览器始终以 `headless=True` + `user_data_dir=None` 启动，确保每次执行环境干净；通过默认 `*.4gaboards.com` 加当前 `target_app_url` origin 的有效允许域限制 Agent 漫游。
- 执行过程页右侧的浏览器实时画面 MVP 采用 per-step 截图方案，复用 browser-use 内置截图，通过 SSE `browser_frame` 事件推送；CDP screencast 视频流为 P2 增强项，独立 WebSocket 端点 `/api/runs/{run_id}/screencast`，与 SSE 通道并存且互不依赖。
- 凭据通过 `.env` 配置并经 browser-use `sensitive_data` 机制注入；先走"场景化登录"主路径，必要时升级为 `storage_state` 持久化。绝不在 task 字符串或场景 JSON 中明文写入凭据。
- 默认 LLM 通过 OpenAI-compatible / Codex API adapter 接入；旧 DeepSeek 与 Browser Use hosted LLM 设置仅作为显式兼容路径，但仍保持本地 Managed Browser 执行。
