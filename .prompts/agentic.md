# Kernel Agentic 改造方案（含 `kernel_api.py` 调度与限流）

## 摘要
- v1 只把 `kernel` 路线完整 agent 化，保留现有 legacy `Wrapper`/脚本入口用于对照实验。
- kernel 数据获取改为“两阶段”：
  1. `kernel_api.py` 预取并缓存 commit 相关上下文；
  2. Agent 只消费缓存后的分层切片，默认不直接在线拉 GitHub。
- 目标不是把全量文件塞进窗口，而是让 Digestor/Reasoner 在 patch、函数级上下文、文件级摘要之间逐级升级视野。
- 工具调用采用代码控 JSON，流程状态和证据记录放到代码层，不再靠长 prompt 维持。

## 核心改造
- 运行时与兼容层：
  - 保留 `Wrapper.chat(id)` 入口，新增 `mode="legacy"|"agentic"`。
  - 新增 agentic orchestrator，固定流程为 `cache_prepare -> digestor -> iterative_reasoner -> judge -> persist`。
  - 新增共享 `RunState`，统一保存原始 commit、缓存路径、切片结果、检索记录、证据账本、最终裁决。

- Agent 分工：
  - `DigestorAgent`：先读 commit message、patch、缓存后的局部上下文，输出 `DigestBundle`。
  - `LibrarianAgent`：包装现有 `rag/`，回答概念问题并返回带引用的简短答复。
  - `ReasonerAgent`：每轮只输出一个 JSON 动作，允许查看某段切片、查询 Librarian、记录证据、回答一个子问题或提交 Judge。
  - `JudgeAgent`：只接收结构化证据和子问题结论，生成稳定的最终报告；正例时按临时模板生成 `_spec.md`。

- Prompt 重写原则：
  - 角色 prompt 拆成 `Digestor / Librarian / Reasoner / Judge` 四份。
  - 流程控制、步数限制、工具权限、终止条件全部上移到 Python。
  - Reasoner prompt 只保留 CISB 最小约束和“遇到概念不确定必须问 Librarian”的规则。
  - Judge 报告继续沿用当前 `Title / Issue / Tag / Purpose / Step-by-Step Analysis / 5个yes-no / CISB Status` 结构。

## `kernel_api.py` 调度与上下文分层
- 数据获取策略固定为“先缓存后分析”：
  - 分析开始前先用 `kernel_api.py` 获取 commit 基础信息并写入本地缓存。
  - Agent 运行过程中只读缓存，不直接访问 GitHub API。
  - 若缓存缺失或字段不足，由预取器补拉并更新缓存，然后重新进入 agent 流程。

- `kernel_api.py` 的职责调整：
  - 保留现有 commit 元信息、message、patch 获取能力。
  - 扩展为面向 commit 的上下文预取器，而不是只产出一个 `patches` 字典。
  - 新增面向缓存的函数接口，而不是只保留脚本式 `main()`。
  - 推荐最小接口：
    - `fetch_commit_bundle(commit_sha)`: 返回 message、file list、patches、提交时间等。
    - `fetch_file_snapshot(commit_sha, file_path)`: 拉取该提交版本的整文件内容。
    - `build_file_focus_slice(commit_sha, file_path, patch_text, line_budget)`: 基于 patch 生成函数级/邻域级切片。
    - `prepare_commit_cache(commit_sha, policy)`: 按预取策略生成完整缓存对象。

- 上下文分层策略：
  - `L0`：commit message + file list + patch hunk。
  - `L1`：每个被修改文件的 hunk 邻域切片。
    - 以 hunk 为中心向前后各扩固定窗口。
    - 若能识别函数签名，则扩到完整函数边界。
  - `L2`：文件级结构摘要。
    - 不给全文，只给函数/宏/关键符号目录、被改动符号列表、与 patch 关联的局部摘要。
  - `L3`：整文件全文。
    - 默认不进入 prompt。
    - 只缓存到磁盘，供切片器二次生成更小片段。
  - Agent 默认只看 `L0 + L1`，当证据不足时再申请 `L2`；禁止直接把 `L3` 送进模型。

- 切片与窗口控制规则：
  - 每个文件先只暴露与 patch 对应的 1 个主切片和最多 2 个补充切片。
  - 单切片按字符或行数设硬预算，超出则二次压缩成“签名 + 关键分支 + 关键变量使用点”。
  - 多文件 commit 先按 message 命中的文件和 patch 规模排序，Digestor 只处理前 `N` 个高优先级文件。
  - 若 Reasoner 仍不确定，只允许请求“某个具体符号的补充上下文”，不允许请求整仓库漫游。

- 限流与缓存策略：
  - 所有 GitHub 请求统一走一个 `KernelApiScheduler`。
  - 调度器按串行队列执行请求，默认插入固定 sleep，并根据响应头动态退避。
  - 必须读取并利用 `X-RateLimit-Remaining` 和 `X-RateLimit-Reset` 做 backoff，不在代码里写死某个阈值。
  - 本地缓存键使用 `commit_sha + file_path + context_level`，命中缓存时不再访问网络。
  - 预取阶段按 commit 批量跑时，采用“commit 间限速 + 文件内复用”的策略，避免同一 commit 重复拉取同一文件快照。

## 工具、接口与输出契约
- 新工具集：
  - `get_commit_overview`
  - `list_changed_files`
  - `get_patch_for_file`
  - `get_focus_slice`
  - `get_file_outline`
  - `query_librarian`
  - `record_evidence`
- 所有工具都只返回短文本和可引用元数据：
  - `source_type`, `file_path`, `commit_sha`, `line_hint`, `slice_id`, `content`
- 新内部结构：
  - `KernelCommitCache`：commit message、patches、file snapshots、focus slices、file outlines、rate-limit metadata。
  - `DigestBundle`：`previous_issue`、`patching_purpose`、`compiler_behavior`、`focused_contexts`、`uncertainties`。
  - `EvidenceLedger`：按子问题累计代码证据、知识证据、缺口说明。
  - `JudgeDecision`：最终 markdown、yes/no 矩阵、CISB 结论、可选 spec 草稿。
- 输出文件：
  - `<id>_analysis.md`：主报告。
  - `<id>_trace.json`：agent 动作、工具调用、切片使用、Librarian 交互、终止原因。
  - `<id>_spec.md`：仅正例生成，先用临时模板。

## 测试与验收
- 单元测试：
  - `kernel_api.py` 的缓存命中、限流退避、空 patch/多文件 patch 处理。
  - hunk 邻域切片、函数边界扩展、超预算压缩。
  - JSON 动作解析、非法动作拒绝、步数上限终止。
  - Librarian 空检索和 Judge 证据不足场景。
- 集成测试：
  - 选 1 个 kernel 正例、1 个反例，对比 `legacy` 与 `agentic`。
  - 验证 agentic 在只读缓存、不联网的阶段也能完整跑完。
  - 验证大文件场景不会把整文件直接喂给模型。
  - 验证 `_trace.json` 能回放“用了哪些切片、为何升级上下文”。
- 验收标准：
  - legacy 模式可继续运行。
  - agentic 模式下，核心判断都能追溯到 patch/focus slice/Librarian 引用。
  - `kernel_api.py` 预取在批处理下不会因重复请求或缺少退避而打爆速率限制。
  - 当全文过长时，系统会降级为更小切片而不是直接失败或塞爆窗口。

## 默认假设
- v1 完整覆盖 kernel；Bugzilla/LLVM 只保留抽象接口和后续接入点。
- 默认存在 GitHub Token；若没有，则调度器仍可运行，但批处理速度会明显降低。
- `kernel_api.py` 可以被重构为“脚本入口 + 可复用函数接口”双形态。
- 整文件快照允许缓存到本地，但默认不直接进入模型上下文。
- `_spec.md` 这一版只预留接口和临时模板，正式 spec 结构后续再替换。
