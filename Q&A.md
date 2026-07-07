# SpecPilot 智能体层答辩问答

## 高频必问

### 1. 你们的智能体层具体由哪些部分组成？

智能体层由 `LangGraph` 外部编排、`browser-use` 执行器、任务构造器、Trace 采集、确定性验证器、视觉验证器和失败分类器组成。

其中，`browser-use` 负责单个测试场景内部的网页观察、动作规划和浏览器交互；`LangGraph` 负责编排一次测试运行的完整生命周期。

### 2. 为什么要同时使用 `LangGraph` 和 `browser-use`？它们会不会职责重复？

不会重复。`browser-use` 本身负责单场景内部的 Agent loop，也就是观察页面、选择动作、执行动作、判断是否继续。

`LangGraph` 负责场景外部的测试流程编排，例如加载场景、调用执行器、收集 Trace、执行验证、分类失败和生成报告。两者是内外分工关系。

### 3. `browser-use` 已经是一个 Agent 了，LangGraph 在项目里到底起什么作用？

LangGraph 的作用不是再写一个浏览器 Agent，而是把一次测试运行变成可编排、可追踪、可扩展的流程。

它负责把 `ScenarioLoader`、`BrowserUseRun`、`TraceCollector`、`DeterministicVerifier`、`VisionVerifier`、`FailureClassifier`、`Reporter` 等阶段组织起来。

### 4. 你们的 Agent 是怎么根据测试场景执行网页操作的？

系统先把测试场景中的标题、前置条件、非敏感测试数据和自然语言步骤拼成 `browser-use` 可消费的 task。

然后 `browser-use` Agent 根据当前页面 DOM、URL、可交互元素和历史动作，自主选择点击、输入、滚动、等待、拖拽等动作。

### 5. 测试场景里为什么不保存 selector、xpath、locator？

因为项目的测试场景来源是用户手册，而手册本身不会提供 DOM selector 或 xpath。

如果强行生成 locator，容易变成模型幻觉，也会让测试脚本绑定具体 UI 实现。UI 一改版，locator 就容易失效。零 locator 场景更接近用户真实意图。

### 6. 没有 locator，Agent 怎么知道要点击哪个按钮？

`browser-use` 会在运行时观察页面结构和可访问性信息，LLM 根据当前任务语义和页面内容判断哪个元素最符合操作目标。

也就是说，元素定位不是预先写死在场景里，而是在执行时由 Agent 根据实时页面状态决定。

### 7. 为什么选择 `browser-use`，而不是 Playwright、Selenium 这类传统自动化测试工具？

Playwright 和 Selenium 更适合提前写好脚本、明确 selector 的传统 E2E 测试。

本项目的目标是“自然语言测试场景 -> 自主 Web 测试智能体”，场景来自手册，不包含 locator。因此 `browser-use` 更适合这种基于页面观察和语义理解的自主执行任务。

### 8. 你们有没有为 4ga Boards 写专用 action 或专用工具？为什么不写？

没有。项目没有为 4ga Boards 封装创建 Board、创建 List、拖拽 Card 这类领域专用 action。

这样做是为了保留 Web Agent 的通用自主决策能力。如果把业务操作都封装成专用工具，Agent 实际上就不再真正理解网页，而是调用人为写好的快捷接口。

### 9. Agent 执行失败时，怎么区分是网页功能有 bug，还是 Agent 自己没操作好？

系统会结合 Trace、action 错误、URL 轨迹、最终页面状态、DOM 验证结果和视觉验证结果进行判断。

如果是页面没跳转，可能是 `navigation_failure`；如果找不到目标元素，可能是 `element_not_found`；如果点了但没生效，可能是 `interaction_failure`；如果 Agent 理解错任务顺序，则可能是 `agent_planning_error`。

### 10. `browser-use` 返回 success，就能说明测试通过吗？为什么？

不能。Agent 自报 success 只能说明它认为任务完成了，不能等同于测试通过。

最终是否通过必须由独立验证层判断，也就是确定性验证和 GLM-4.6V 视觉验证。执行者不能自己当裁判。

## LangGraph 编排相关

### 11. 你们的 LangGraph 工作流有哪些节点？

主要节点包括：

- `ScenarioLoader`
- `BrowserUseRun`
- `TraceCollector`
- `DeterministicVerifier`
- `VisionVerifier`
- `FailureClassifier`
- `RepairPlanner`
- `Reporter`

这些节点覆盖了从场景加载到执行、验证、失败诊断和报告生成的完整过程。

### 12. `ScenarioLoader`、`BrowserUseRun`、`TraceCollector`、`Verifier`、`FailureClassifier` 分别负责什么？

`ScenarioLoader` 负责加载测试场景。

`BrowserUseRun` 负责把场景交给 `browser-use` 执行。

`TraceCollector` 负责整理执行过程中的 action、URL、截图、错误和日志。

`DeterministicVerifier` 和 `VisionVerifier` 负责判断最终页面状态是否满足预期。

`FailureClassifier` 负责把失败结果归类，解释失败原因。

### 13. 为什么不在 LangGraph 里再写一个 PlannerNode？

因为 `browser-use` 内部已经有完整的 LLM planning loop。

如果 LangGraph 再写一个 PlannerNode，就会出现两套规划逻辑：外层规划一次，内层又重新规划一次，容易职责重叠甚至互相冲突。

### 14. LangGraph 是控制 Agent 每一步点击，还是控制一次测试运行的阶段？

LangGraph 控制的是一次测试运行的阶段，不控制每一次点击。

每一步具体点击、输入、滚动、拖拽由 `browser-use` 内部 Agent loop 决定。

### 15. 如果后续要加入自动修复、二次验证、人工审核，LangGraph 怎么扩展？

可以在现有工作流中插入新节点，例如 `RepairPlanner`、`RetryRunner`、`HumanReview` 或 `SecondVerifier`。

这种扩展不需要修改 `browser-use` 内部执行循环，只需要调整 LangGraph 的外部流程。

### 16. 实时执行页上展示的 Agent 流程图，和 LangGraph 节点是什么关系？

前端实时执行页用 React Flow 展示 LangGraph 节点状态。

后端通过 SSE 推送 `node_status`、`browser_step`、`verification`、`classification` 等事件，前端据此展示每个节点的 pending、running、success、failed 或 needs_review 状态。

### 17. 当前系统中 LangGraph 是完整执行主链路，还是部分节点已经模块化、主流程还在逐步串联？

当前系统已经定义了 LangGraph 节点骨架，也实现了 browser-use 执行、Trace、截图、报告、验证器和失败分类等模块。

主执行链路目前以 `run_executor` 调度 browser-use、写入 Trace 和生成报告为主，验证和分类模块已经具备独立能力，后续会按里程碑继续深度串联到完整运行链路中。

## browser-use 执行相关

### 18. 一个测试场景是怎么转成 `browser-use` task 的？

`task_builder` 会读取 `TestScenario` 的标题、前置条件、测试数据和步骤。

它会过滤敏感字段，只把非敏感信息和自然语言步骤拼成任务字符串，交给 `browser-use` Agent 执行。

### 19. 为什么 task 里放 steps，但不把 expectations 放进去？

因为 steps 是执行指导，expectations 是验证标准。

如果把 expectations 也放进 Agent task，Agent 可能会倾向于迎合答案，甚至自报完成。项目要求执行和验证分离，所以 expectations 只给后置验证器使用。

### 20. Agent 执行时能看到哪些信息？DOM、页面截图、URL、历史动作分别有什么用？

Agent 可以看到当前页面结构、可交互元素、URL、页面状态和历史动作。

DOM 和可访问性信息用于理解页面元素；URL 用于判断当前页面位置；历史动作用于避免重复操作；截图可用于辅助观察页面状态。

### 21. `max_steps` 的作用是什么？如果超过步数还没完成怎么办？

`max_steps` 用于限制 Agent 的最大操作步数，防止无限循环。

如果超过步数仍未完成，系统会把该 run 标记为失败或未完成，并在 Trace 和报告中保留过程证据。

### 22. 对拖拽、视图切换这类复杂交互，`browser-use` 怎么处理？

这些操作仍然交给 `browser-use` 的通用浏览器 action 处理，例如 click、drag、scroll、wait 等。

项目不为 4ga Boards 写专用拖拽工具，而是让 Agent 基于运行时页面观察自主完成。

### 23. 你们如何限制 Agent 不乱跳到无关网站？

执行器创建浏览器会话时会配置 `allowed_domains`，限制 Agent 只能访问允许的目标域名。

这样可以减少错误跳转，也能降低安全风险。

### 24. 登录账号、密码、API key 这些敏感信息怎么传给 Agent？会不会进日志？

敏感信息通过 `browser-use` 的 sensitive data 机制注入，不直接写进 task 文本。

系统在日志、Trace 和报告生成时也会进行脱敏，避免账号、密码、token、api key 等内容被保存。

### 25. 为什么不能直接把测试账号密码写进 prompt？

因为 prompt、Trace、日志和报告都有可能被持久化。

如果把密码直接写进 prompt，就可能进入运行记录和报告，造成泄漏风险。

## 验证与判定相关

### 26. 你们怎么判断 Agent 真的完成了测试目标？

系统不看 Agent 自己说没说完成，而是看最终页面状态是否满足 scenario 中的 expectations。

判断方式包括确定性验证、视觉验证和两者之间的仲裁。

### 27. 确定性验证器检查哪些内容？

确定性验证器主要检查：

- `element_visible`：目标文本或元素是否可见
- `text_present`：页面文本是否存在
- `url_match`：当前 URL 是否符合预期
- `element_state`：元素状态是否正确
- `containment`：子对象是否位于目标容器中

### 28. 哪些情况必须交给 GLM-4.6V 做视觉验证？

`semantic` 类型 expectation、`requires_visual_check=true` 的场景，以及布局、视图切换、视觉状态、拖拽呈现等 DOM 难以准确判断的情况，会交给 GLM-4.6V 做视觉验证。

### 29. DOM 判断和视觉判断冲突时怎么办？

系统会进入仲裁逻辑。

如果 DOM 失败但视觉通过，可能说明 DOM 验证器适配不够好，会标记为软失败或 `needs_review`。

如果 DOM 通过但视觉失败，可能说明页面功能数据正确但视觉呈现异常，会倾向于判为真实失败或视觉回归。

### 30. 为什么不能完全依赖视觉模型？

视觉模型有成本、延迟和不确定性，而且对一些结构化条件不如程序化判断稳定。

例如 URL 是否匹配、文本是否存在、元素状态是否 checked，这些更适合确定性验证。

### 31. 为什么也不能完全依赖 DOM 判断？

DOM 判断可能看不出布局错乱、视觉遮挡、拖拽后的实际呈现效果和视图切换状态。

因此需要 GLM-4.6V 作为视觉和语义判断的补充。

### 32. `needs_review` 是什么状态？为什么要有它？

`needs_review` 表示系统证据不足、模型置信度不够，或 DOM 与视觉判断发生冲突。

它的作用是避免系统在不确定时强行判定 pass 或 fail。

### 33. GLM-4.6V 的置信度阈值怎么设计？

默认高置信度阈值是 `0.85`，低置信度阈值是 `0.60`。

高于高阈值的结果可以参与明确判定；低于低阈值或模型返回 uncertain 的结果进入 `needs_review`；中间区域通常也需要谨慎处理。

### 34. 对于“卡片被拖到另一个列表”这种结果，你们用 DOM 还是视觉验证？

优先用确定性验证中的 `containment` 判断卡片文本是否出现在目标列表范围内。

如果 DOM 结构无法可靠判断，或者需要确认视觉位置，再调用 GLM-4.6V 做视觉验证。

### 35. Agent 自己说成功、DOM 失败、视觉成功，这种情况怎么判？

Agent 自己说成功不能直接作为通过依据。

DOM 失败但视觉成功时，一般会标记为 `dom_mismatch_visually_correct` 或 `needs_review`，说明可能是 DOM 验证器没有适配好，但视觉上结果看起来正确。

## 失败分类相关

### 36. 你们有哪些失败类型？

主要失败类型包括：

- `navigation_failure`
- `element_not_found`
- `interaction_failure`
- `timing_issue`
- `state_mismatch`
- `visual_regression`
- `agent_planning_error`
- `dom_mismatch_visually_correct`
- `unknown`

### 37. `navigation_failure` 和 `element_not_found` 怎么区分？

`navigation_failure` 指页面没有成功进入目标页面或目标 URL。

`element_not_found` 指页面已经到达相关位置，但 Agent 或验证器找不到目标元素。

### 38. `interaction_failure` 和 `agent_planning_error` 怎么区分？

`interaction_failure` 指 Agent 选择了看似正确的动作，例如点击、输入或拖拽，但动作没有生效。

`agent_planning_error` 指 Agent 从任务理解或步骤规划上就错了，例如顺序错误、目标误解或操作了错误对象。

### 39. 什么情况下会判为 `state_mismatch`？

当 Agent 完成了一系列操作，但最终页面状态与 expectation 不一致时，会判为 `state_mismatch`。

例如预期卡片标题被修改成 A，但最终页面仍显示旧标题。

### 40. 什么是 `dom_mismatch_visually_correct`？

它表示确定性 DOM 验证失败，但视觉验证认为页面结果是正确的。

这种情况通常说明验证器的 DOM 规则可能不够适配，或者页面结构和视觉呈现存在差异。

### 41. 失败分类是模型判断，还是规则判断？

当前主要是规则优先。

系统会根据 VerificationFailure、action 错误、URL 轨迹、DOM summary、Agent self-report 和视觉 reasoning 等信号映射到失败类别。

### 42. 失败分类对项目有什么价值？只是展示好看吗？

不是。失败分类可以帮助判断下一步应该改哪里。

如果是 `agent_planning_error`，需要优化任务描述或 Agent 设置；如果是 `state_mismatch`，可能是应用功能问题；如果是 `dom_mismatch_visually_correct`，可能要改验证器。

### 43. 如果失败原因分类错了，会不会影响最终测试结论？

一般不会直接影响 pass/fail 的基本结论。

最终结论来自验证和仲裁，失败分类主要用于诊断、解释和报告。

## 零 locator 与智能性相关

### 44. 零 locator 场景相比传统自动化测试有什么优势？

零 locator 场景表达的是用户意图，而不是具体 DOM 实现。

它更贴近手册内容，也更能适应 UI 小幅改版，避免 selector 变化导致测试脚本大面积失效。

### 45. 零 locator 会不会导致执行不稳定？

会带来一定不确定性，因为执行依赖 Agent 的页面理解。

所以系统通过 `max_steps`、allowed domains、Trace 采集、双通道验证和失败分类来控制风险。

### 46. 如果 UI 改版了，你们的测试场景还能用吗？

如果功能语义没变，零 locator 场景通常仍然可以复用。

传统 selector 脚本可能因为按钮 class、DOM 层级或 id 变化而失效，但自然语言意图场景对这类变化更不敏感。

### 47. 场景步骤是自然语言，会不会太模糊？

所以场景步骤需要控制粒度，既不能过细到绑定 UI 细节，也不能过粗到 Agent 无法执行。

项目还通过 schema、review_status、evidence quotes 和 source URLs 约束场景质量。

### 48. 怎么保证模型生成的步骤不是幻觉？

功能点和场景必须带 source URLs 和 evidence quotes。

后端会校验证据 quote 是否来自手册 chunk，也会校验场景中不能出现禁止的 DOM locator 字段，从而减少幻觉。

### 49. 手册证据和 Agent 执行之间是怎么衔接的？

手册 chunk 先生成 Feature，Feature 再生成 Scenario。

Scenario 中的 steps 被转换为 `browser-use` task，expectations 则交给后置验证器判断执行结果。

### 50. 你们如何防止场景里偷偷出现 `selector`、`xpath`、`element_id` 这类字段？

后端在 scenario schema 和 generation validator 中都做了递归检查。

如果 payload 中出现 `selector`、`locator`、`xpath`、`element_id`、`element_index` 等字段，会直接拒绝入库。

## 老师可能会追得比较尖锐的问题

### 51. 你们项目的“智能体”创新点是什么？是不是只是调用了一个现成 browser-use？

创新点不是重新发明浏览器 Agent，而是把 `browser-use` 放进一个完整的智能测试闭环中。

系统从手册证据生成零 locator 场景，再由 Agent 执行，并通过 Trace、确定性验证、视觉验证、失败分类和报告完成测试闭环。

### 52. 如果 browser-use 本身已经能执行任务，你们系统相比直接使用 browser-use 多了什么？

直接使用 `browser-use` 只能执行一个自然语言任务。

SpecPilot 还提供手册驱动的场景生成、证据约束、零 locator 校验、运行记录、实时可视化、双通道验证、失败分类和报告归档。

### 53. 你们怎么证明这是“测试系统”，而不只是“网页自动操作 demo”？

关键区别是系统有独立的 expectations、验证器、失败分类和报告。

普通 demo 关注 Agent 能不能操作网页；测试系统关注操作后功能是否真的满足预期，并且能留下可复查证据。

### 54. 如果 Agent 操作错了，但最后页面状态碰巧对了，系统怎么判断？

最终 pass/fail 主要看页面结果是否满足 expectation。

但 Trace 会保留完整操作过程，报告中也会记录 action 序列和错误信息。如果需要分析偶然通过，可以回看 Trace 和截图。

### 55. 如果页面状态对了，但视觉布局坏了，系统能发现吗？

可以。DOM 或文本验证通过后，如果场景需要视觉检查，GLM-4.6V 仍会检查最终截图。

如果视觉模型判断布局或呈现异常，系统可以判为 `visual_regression` 或进入失败处理。

### 56. 你们的验证器和 Agent 是独立的吗？为什么独立很重要？

是独立的。

独立很重要，因为执行者不能自己当裁判。如果只听 Agent 自己说成功，就无法区分“真的完成”和“Agent 误判完成”。

### 57. 失败分类有没有真实样本验证准确率？

当前失败分类模块已有规则和测试覆盖，可以处理主要失败类型。

真实失败样本的规模化评估是后续优化方向，需要通过更多真实 E2E run 积累样本。

### 58. 这个系统目前的短板是什么？

短板主要是真实 E2E 运行依赖外部条件，包括 4ga 测试账号、网络环境、文本模型和视觉模型 API。

另外，复杂场景的通过率、失败分类准确率和验证链路深度串联还需要持续优化。

### 59. 真实 E2E 测试依赖哪些外部条件？

需要 4ga demo 测试账号、可访问 4ga 的网络环境、文本模型 API key。

如果场景需要视觉验证，还需要 GLM-4.6V API key。

### 60. 你们后续最应该优化智能体层的哪一块？

优先优化验证闭环和失败分类准确率。

其次是提高复杂交互场景的稳定性，例如拖拽、视图切换、多步骤编辑，以及增强每一步 action 的目标元素可视化。

## 核心背诵句

`browser-use` 负责“怎么操作网页”，`LangGraph` 负责“怎么组织一次测试运行”；最终是否通过不听 Agent 自己说，而由确定性验证和视觉验证共同裁决。
