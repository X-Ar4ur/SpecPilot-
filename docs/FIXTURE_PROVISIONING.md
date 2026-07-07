# SpecPilot 依赖型场景的交互式前置数据绑定（Fixture Binding）设计提案

> **状态：已同步进契约（Ratified），待实现。**
> 已落进 `PLANv2.md`（决策四 + Core Workflow 第 4 步）与 `docs/{SPEC,SCHEMAS,API,PROMPTS,TESTING}.md`；本文为配套详细设计。可行性已在本地实例实测通过（§3）。尚未编写实现代码。

## 1. 背景与问题

部分生成的测试场景对**预先存在的特定数据**有硬依赖，但目标 4gaboards 实例不一定有这条数据，于是测试判 `fail`——这并非功能缺陷，而是**测试数据/夹具（fixture）依赖问题**。

典型例子 `SC_LIST_VIEW_CARD_OPEN_001`（"从 List View 打开对应 Card"，`is_mutation: false`）：

- 生成阶段把 `test_data.card_title` 和 `expectations[].params.text` 都填成具体值 `"完成季度报告"`。
- 执行阶段 `agent/task_builder.py` 拼 browser-use 任务（**expectations 不下发**）。
- 校验阶段 `verification/deterministic.py` 的 `check_element_visible` 对页面文本做**字面子串匹配**。

只要实例里没有这张卡：browser-use 找不到 → 字面量匹配失败 → 判 `fail`，但功能本身完好。

**只读型**（打开/查看/搜索/筛选，`is_mutation: false`）受此影响最大；**自给自足型**（创建/编辑，测试自己造数据再校验）不受影响。

## 2. 方案演进与最终决策（已与用户确认）

| 轮次 | 方案 | 结论 |
| --- | --- | --- |
| 1 | 后端 API/DB 自动播种已知 fixture | 用户初选，后因"以为没有 API"放弃 |
| 2 | 手动预置固定 fixture Board（静态） | 因复位/污染负担大放弃 |
| 3 | **交互式前置数据绑定 + 记住绑定** | **最终采纳** |

**关键事实纠正**：4ga Boards 后端是 Sails.js，前端是 React/Redux-Saga SPA，**确实存在一套 JSON REST API**（前端本身就靠它运行）。"没有 API"的假设不成立。由此第 3 版得以干净落地。

最终决策：

1. **数据来源**：复用 4ga REST API（见 §3），既用于**列举现有元素清单**，也用于**创建缺失元素**。
2. **交互方式**：点击运行依赖型场景时弹窗，列出当前实例各类型元素，由用户**选择**目标，或**手动填写并创建**。
3. **自动化模式**：**交互式 + 记住绑定**——首次手动选/填，绑定持久化到场景；重跑/批量时若元素仍在则跳过弹窗。
4. **断言**：保留**确定性 oracle**——用户选/填的是已知具体值，沿用现有 `DeterministicVerifier`，零改动。
5. **目标实例**：**用户自己部署的实例**（可写、可控、可清理，必要时可 DB 快照复位）。`target_app_url` 指向它。

## 3. 数据来源：已核实的 4ga REST API

> **已在本地自托管实例（`http://localhost:1337`，demo/demo）实测通过**，以下结构来自真实响应，非推测。

复用配置里**已有的** `fourga_username` / `fourga_password`（`config.py`）登录，**无需新增密钥**：

```text
登录拿 token：  POST   /api/access-tokens        {emailOrUsername, password} → {item: "<jwt>"}
列项目：        GET    /api/projects             Bearer 鉴权
看 board 详情： GET    /api/boards/:id
建 board：      POST   /api/projects/:projectId/boards
建 list：       POST   /api/boards/:boardId/lists
建 card：       POST   /api/lists/:listId/cards  {name, position} → {item:{id,...}}
看/改/删 card： GET / PATCH / DELETE /api/cards/:id
```

实测响应结构（Planka 风格 `included` 扁平数组）：

```text
GET /api/projects
  { items: [ {id, name} ],
    included: { users, projectManagers, boards[ {id, name, projectId} ], boardMemberships } }

GET /api/boards/:id
  { item: { id, name, projectId },
    included: { lists[ {id, name, boardId} ], cards[ {id, name, listId} ],
                labels, tasks, cardLabels, cardMemberships, attachments, ... } }
```

清单组装逻辑（`list_inventory`）：登录 → `GET /api/projects` 取 projects + `included.boards` → 逐 board `GET /api/boards/:id` 取 `included.lists` / `included.cards` → 按 `projectId`/`boardId`/`listId` 拼成 Project→Board→List→Card 树。

**实现注意**：请求体必须按 **UTF-8** 编码（Python `httpx` 默认即是，无需特殊处理）。中文标题（如"完成季度报告"）的 create→读回往返已实测无损。鉴权用 `Authorization: Bearer <token>`。Token 为 JWT，按既有密钥规则处理。

## 4. 架构总览

```text
┌─ 前端（Next.js 控制台）────────────────────────────────┐
│  运行依赖型场景 → 前置绑定弹窗                          │
│   · 渲染 Project→Board→List→Card 树（按场景所需类型过滤）│
│   · 选择既有元素 / 手动填写新元素                        │
│   · 展示已记住的绑定，可改可清                           │
└───────────────┬────────────────────────────────────────┘
                │ REST
┌─ 后端（FastAPI）───────────────────────────────────────┐
│  FourgaApiClient（新增）                                │
│   · login() → token（用 fourga_username/password）      │
│   · list_inventory() → 组装实体树                       │
│   · create_element(kind, parent, attrs) → 实体 id       │
│  GET  /fixtures/inventory        列当前实例元素树        │
│  POST /fixtures/bind             保存/创建并绑定         │
│  绑定持久化（SQLite）：scenario_id → 解析后的具体值      │
└───────────────┬────────────────────────────────────────┘
                │ /api/...（仅 Arrange 用，不碰执行/判定）
        ┌───────▼────────┐
        │  4ga Boards     │ 用户自托管实例
        └─────────────────┘
```

**职责边界**：4ga API 客户端**只在 Arrange 阶段**用于"列清单/建元素/校验存在"。测试的**执行仍走 browser-use 真实 UI，判定仍走确定性/视觉校验**——API 不碰执行和判定，测试保真度不变。

## 5. Schema 改动

### 5.1 场景声明"需要什么数据槽"（`fixtures`）

```python
class FixtureSlot:
    ref: str                                  # 槽句柄，如 "target_card"；被 test_data/steps/expectations 引用
    kind: Literal["project", "board", "list", "card"]  # MVP 实体集合
    parent_ref: str | None                    # 归属，如 card 属于某 list 槽
    required_attrs: list[str] = ["title"]     # 绑定时需确定的属性
    allow_create: bool = True                 # 是否允许"手动填写并创建"

class TestScenario:
    ...
    fixtures: list[FixtureSlot] = []          # 新增；空=无数据依赖，直接运行
    data_dependency: Literal["none", "interactive"] = "none"  # 是否需要绑定弹窗
```

**零定位器合规**：`fixtures` 只含领域属性（标题、归属），不含 `selector/locator/xpath/element_id/element_index/css`，现有禁止字段规则继续覆盖其内部。

占位符贯穿引用：生成产物里 `test_data` / `steps.action` / `expectations[].params` 用 `{{fixture.target_card.title}}`，绑定后由后端解析成真实值。

### 5.2 绑定持久化（新增表）

```python
class ScenarioFixtureBinding:
    scenario_id: str
    target_app_url: str                       # 绑定属于哪个实例
    ref: str                                  # 对应 FixtureSlot.ref
    entity_kind: str                          # card/list/...
    entity_id: str                            # 4ga 实体 id（用于 pre-run 存在性校验）
    resolved_values: dict[str, object]        # 如 {"title": "买菜清单"}
    created_by_specpilot: bool                # 是否本工具创建（影响是否可清理）
    bound_at: str
```

## 6. 运行时流程（交互式 + 记住绑定）

```text
点击运行依赖型场景（fixtures 非空）
  │
  ├─ 对每个 FixtureSlot：查 ScenarioFixtureBinding
  │     ├─ 有绑定 → GET /api/<kind>/:id 校验仍存在？
  │     │     ├─ 存在 → 直接复用，跳过弹窗
  │     │     └─ 已删/不存在 → 进入弹窗（标记"原绑定已失效"）
  │     └─ 无绑定 → 进入弹窗
  │
  ├─ 弹窗（仅未解析的槽）：
  │     · GET /fixtures/inventory，按 slot.kind 过滤渲染树
  │     · 用户【选择既有元素】 → 记录 entity_id + 值
  │     · 或【手动填写新元素】（选父级）→ POST /api/.../create → 记录
  │     · 保存 ScenarioFixtureBinding
  │
  ├─ 解析占位符：把绑定值注入 test_data / steps.action / expectations.params
  ├─ build_browser_use_task → BrowserUseRun（真实 UI）
  └─ DeterministicVerifier 对已知值字面匹配 → pass/fail（确定性）
```

重跑/批量：所有槽都有有效绑定 → **全程跳过弹窗，无人值守**。这就是"记住绑定"带来的批量能力。

## 7. 绑定必须连"断言"一起改（保确定性）

绑定时不仅重绑**操作目标**，还要同步重绑**断言值**：

```text
用户选了 Card "买菜清单"
  → step 动作   重绑为 "打开 买菜清单"
  → expectation 重绑为 {text: "买菜清单"}   ← 关键，否则仍拿旧值判，照样失败
```

因为是用户**显式选了已知值**，绑定后仍是确定性校验。`fixtures`/`ref` 槽机制保证"被绑定的值"与"被断言的值"始终同一。

## 8. 失败状态：前置阻塞 ≠ 功能失败

当前置数据**确实无法建立**（实例 API 不可达、登录失败、用户取消绑定且无可用元素）时，run 判为**"前置条件未满足 / 环境阻塞"**，**不算功能 `fail`**——这正是问题的根。

- 复用 `Run.status = error`，`failure_primary = "precondition_setup_failure"`，排除在功能 pass/fail 指标外。
- 附带收益：数据被绑定保证存在后，browser-use 还找不到元素，那才是**真**功能失败（`element_not_found`）——播种把噪声变成了有效信号。

## 9. LangGraph 流水线改动

```text
ScenarioLoader
  → FixtureResolver   (新增, Arrange)  解析绑定/占位符；缺绑定则中断等待前端弹窗回填
  → BrowserUseRun
  → TraceCollector → DeterministicVerifier / VisionVerifier → FailureClassifier
  → RepairPlanner → Reporter
```

- 无需 Teardown 节点：被绑定/创建的元素是**持久 fixture**，留着供下次复用（符合"记住绑定"）。
- 可选 DB 快照复位（自托管）单独提供给变更类场景，不在主流程。

## 10. 合规与安全

- `FourgaApiClient` 是**后端 setup/infra，不是 browser-use action** → 不违反"禁止 4ga 专属 browser action"。
- 测试**执行与判定全程走 browser-use + 确定性/视觉校验**，API 仅 Arrange。
- 登录 token 按现有密钥规则：不进 prompt / 日志 / trace / 截图元数据 / 报告 / 前端（只暴露"已配置/为空"）。
- 复用既有 `fourga_username` / `fourga_password`，无新增密钥面。

## 11. MVP 范围

- 实体类型：**Project / Board / List / Card**（覆盖绝大多数依赖型场景）。Label / Comment / Attachment / 成员权限延后。
- 先做 **list_inventory + 既有元素选择 + 手动创建 card + 记住绑定**；其余创建类型按需补。

## 12. 受影响契约文件清单（批准后再同步）

| 文件 | 改动 |
| --- | --- |
| `PLANv2.md` | 架构权威：登记 FourgaApiClient、FixtureResolver 节点、交互式绑定数据流 |
| `docs/SPEC.md` | LangGraph 节点加 `FixtureResolver`；前端加"前置绑定弹窗"交互 |
| `docs/SCHEMAS.md` | `TestScenario` 增 `fixtures` / `data_dependency`；新增 `ScenarioFixtureBinding`；失败语义增 `precondition_setup_failure`；零定位器规则覆盖 `fixtures` |
| `docs/API.md` | 新增 `GET /fixtures/inventory`、`POST /fixtures/bind`；run 状态语义 |
| `docs/PROMPTS.md` | Scenario Generation 产出 `fixtures` + 占位符；区分依赖型/自给自足型 |
| `docs/TESTING.md` | 新增：API 客户端登录/列举/创建、占位符解析、绑定持久化与 pre-run 存在性校验、前置阻塞分类 |

## 13. 待核实 / 开放问题

1. ~~目标实例 API 字段核实~~ — **已核实**（§3）：登录/列举/创建/读回/删除全通，响应为 `included` 扁平数组，中文 UTF-8 往返无损。
2. ~~创建最小必填字段~~ — **已核实**：`POST /api/lists/:listId/cards` 仅需 `{name, position}`，`position` 为排序数（如 65535/71000）。
3. **变更类场景复位**：是否需要 DB 快照复位作为可选项？（自托管 + 已确认 PostgreSQL/5432，可行；非 MVP 必需）
4. **弹窗范围**：清单是否需要分页/搜索（demo board 已有 31 张卡，真实实例 Card 会更多）。
5. **绑定与实例耦合**：绑定按 `target_app_url` 隔离，切换实例时绑定失效并重新弹窗——确认这是期望行为。
6. **登录端点指向**：实测后端在 `:1337`（Sails），前端 dev server 在 `:3000` 代理 `/api`。`FourgaApiClient` 应直连后端端口（避免依赖前端代理）；该端口建议作为独立配置项（如 `FOURGA_API_BASE_URL`，默认从 `target_app_url` 推导）。
