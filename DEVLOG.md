# MaaNikke 开发日志（DEVLOG）

> 本文件记录对项目的每一次改动留痕，面向开发者。
> 用户向更新日志在 `resource/announcement/Changelog.md`，仅发版时由发版流程写入。
>
> **记录规则：**
> - 每次改动项目（代码 / pipeline / 配置 / 文档）后，在 `## [未发布]` 区追加一条，**新内容在上、旧内容在下**。
> - 条目格式：`- YYYY-MM-DD [类型] 简述（涉及：文件/模块）`；类型：新增 / 修复 / 优化 / 文档 / 调查。
> - 普通 push 不动本文件。
> - **仅在执行完整发版流程（push + Release）时**：把 `[未发布]` 区封存为 `## vX.Y.Z - 日期` 版本线，并在其上方重建空的 `[未发布]` 区（由 maanikke-release skill 执行）。
> - 发版时，未发布区条目会被过滤改写（剔除代码 / 文档 / 调查类内部条目，只保留用户可感知的内容）并与用户提供的 changelog 合并，按 Changelog.md 既有格式写入其顶部。

---

## [未发布]

---

## v2.2.8 - 2026-09-06

---

## v2.2.7 - 2026-09-02

- 2026-09-02 [修复] stage-1 框内重读新增否决规则：原始文本可严格解析的框跳过重读。实机案例（22:20，task 200002682）：粘连框 `CLEAR1-2` 在 stage-0 四档正确地未中 1-12，但 stage-1 紧裁剪送 otsu 提取图重读时横杠丢失读成纯数字 `"12"`，纯数字尾段档误中 1-12（旧 agent 进程问题修复后暴露的真实第二路径）。逻辑闭环：能严格解析却没在 stage-0 命中当前 expected ⇒ 解析值 ≠ expected ⇒ 框属于别的关卡，重读只会降信息引入歧义；`HII`/`H`/`-11`/裸 `"12"` 等解析不出的框不受影响，重读兜底行为不变。新增 1 条单测（整图 CLEAR1-2 + 重读 "12" 场景：1-12 不中、1-2/1-11 严格命中保持）先红后绿，并补对称用例（CLEAR1-1 重读丢横杠成 "11"：1-11 不中、1-1 严格命中）——否决规则为通用机制，1-1/1-11 粘连框同受保护，全量单测 + E2E 全绿（涉及：agent/custom/reco/stagenum.py、tools/stagenum_test/test_stagenum_units.py）
- 2026-09-02 [调查] 21:56 实机 1-2 被误报成 1-12（detail: matched=1-12, ocr_text='CLEAR1-2', source=整图）根因：**MPE 长驻 agent 进程持有的修复前旧代码**——旧版锚点尾段档 `_digits` 全串拼接把 "CLEAR1-2" 拼成 "12" 误中 1-12，该 bug 已于当日修复（取 `findall` 最后一个数字组）。硬时间线：agent 进程（socket e89e40cd，PID 15852）19:46:01 启动后贯穿全部 MPE 测试（maafw.log 全程仅此一个 socket）从未重载；修复落盘 ~20:30（test_stagepre_e2e.py mtime）；误中发生于 21:56——运行的即 19:46 前旧模块。离线逐档模拟实证当前代码不可能产出此匹配（CLEAR1-2×1-12 严格/宽松/锚点尾段/单H 全 False），同场景复现正确行为：1-12 未命中、1-2 严格档命中（parse_stage 从粘连框解析出 (1,2)）。注意：AGENTS.md"重启任务即生效"仅适用 MFAA GUI（每任务新启 agent）；MPE 编辑器 agent 长驻，改完 Python 代码需重启 MPE/agent 才生效；release 目录 C:\other\MaaNikke 的 stagenum.py 仍是旧版（发版时才同步）（涉及：无代码改动）
- 2026-09-02 [调查] stagematch `return` 参数（整轮皆空后 false=立即 error/true=循环到 timeout）试装后回退：实现依赖"analyze 抛异常使节点立即 Failed"，实机验证不成立——agent 是独立子进程，异常在 ctypes 回调层被吞（打印 "Exception ignored"），主进程只收到普通"未命中"（ret=false），框架按重试循环再调 analyze，表现为"action 执行完又识别"。MaaFW 源码（PipelineTask.cpp）实证：识别未命中→每隔上个节点 rate_limit（默认 1s）重试，直到**上个节点** timeout（默认 20000）耗尽→判负→走**上个节点**的 on_error；custom reco 无"立即判负"返回通道，post_stop() 会停整个 tasker 且任务记为成功。改动（stagenum.py 的 return 参数/StageMatchFailFast 异常类、3 条单测、docstring）已全部还原（涉及：agent/custom/reco/stagenum.py、tools/stagenum_test/test_stagenum_units.py）
- 2026-09-02 [新增] 锚点担保单字符 H≡1-1（锚点单H档）：斜体 `1-1` 三笔画形似 H，实机存在整串读作单 `H` 的形态；本帧锚点已检出时，映射后 strip 为单 `1` 且已通过锚点过滤（邻近锚点）的框允许中 1-1（expected 限 (1,1)）；无锚点/锚点未检出维持"单位数不认"防计数误中。用户拍板：`HI` 维持归 1-11 不动（纯数字 `-11` 路径与字母映射文本层不可分），单 H 仅在锚点检出时放开。顺带统一 stage-0/stage-1 匹配入口为 `full_match`（锚点尾段档对框内重读同样生效）。新增 3 条单测（邻近 H 中 1-1/无锚点 H 不认/非 1-1 字段不中）先红后绿，全量单测 + E2E 全绿（涉及：agent/custom/reco/stagenum.py、tools/stagenum_test/test_stagenum_units.py）
- 2026-09-02 [修复] 宽松匹配新增"映射后严格解析"档，消除 `H-1` 误中 1-11：斜体 `1` 误读字映射（H→1）后若文本可严格解析出关卡号（`H-1`→`1-1`→(1,1)），直接按解析结果与 expected 比对，不再落入尾段兜底档被数字串 `11` 抢去 1-11；真丢前导的 `-11`（映射后仍不可解析）维持尾段档不变。原 `parse_stage(candidate)` 冗余检查删除（candidate 可解析 ⇒ mapped 必可解析，上游已拦）。无分隔符的 `HI`/`HII` 文本层不可分，维持"归 1-11、点击位置兜底"取舍。新增 6 条单测（H-1 双向、H-11 双向、1-1 经映射档、-11 回归）先红后绿，全量单测 + E2E 全绿（涉及：agent/custom/reco/stagenum.py、tools/stagenum_test/test_stagenum_units.py）
- 2026-09-02 [修复] 锚点尾段拼接误中 + 全档混淆面梳理：实机 `CLEAR1-2`（CLEAR 标签与 1-2 粘连框）被锚点尾段档 `_digits` 全串拼接成 "12" 误中 1-12；修为取**最后一个数字组**（`re.findall(r"\d+")` 取末组）按 int==expected 尾段比对——`CLEAR1-2`→2 中 1-2、`EVENT 12`→12 中 1-12、`EVENT 1`→1 中 1-1。梳理全部档位的 1-2/1-12 混淆面（均有单测锁定）：严格档元组全等不互中；宽松全等仅 ≥3 位；宽松尾段能严格解析者直接出局；锚点尾段取末组；轮巡长号码优先。已知接受边界：`H-1`（1-1 艺术字映射）走尾段档中 1-11，但点击位置仍是 1-1 行框，业务后果正确。另修 E2E 依赖丢失：原旧蓝皮页截图被外部目录清理，case1/2/4 改用项目内 `live_220232.png`（Stage List 页，锚点防错配的杂散消歧已由单测 ANCHOR_PAGE 覆盖），新增 4 条防拼接用例先红后绿，全量单测 + E2E 全绿（涉及：agent/custom/reco/stagenum.py、tools/stagenum_test/test_stagenum_units.py、tools/stagenum_test/test_stagepre_e2e.py、DEVELOPMENT.md §10.2）
- 2026-09-02 [修复] absolute_checkeventpage/checkeventpage1 的 OCR ROI 由 [0,0,90,60] 加高为 [0,0,90,200]，修复链上识别不到"剧情活动"的问题：next 列表含多个 OCR 节点时框架走 batch OCR，合并区域由 ~1271×60 变为 ~1271×200；PaddleOCR 检测器归一化（长边 960）后条带高度从 ~45px 变为 ~150px，此前过窄条带使 DB 检测器 FPN 垂直分辨率退化、小字漏检（时灵时不灵），加高后链上稳定命中 score 0.9997（涉及：resource/base/pipeline/task/limitedevent/absolute.json）
- 2026-09-02 [优化] absolute.json 内 juveniledays 前缀批量改名为 absolute（213 处词边界替换：74 个节点 key、next/on_error/[JumpBack]/[Anchor] 引用、anchor 字段、`$__mpe_anchor_*`/`$__mpe_external_*`/`$__mpe_group_*`/`$__mpe_config_*` 键一并同步，config 的 filePath/filename 自动修正到 absolute.json；图片模板路径 `limitedevent/juveniledays/` 未动）；消除与 juveniledays.json 的全局重名，校验脚本全绿（涉及：resource/base/pipeline/task/limitedevent/absolute.json）
- 2026-09-02 [优化] absolute.json 内 p5 前缀批量改名为 absolute（234 处词边界替换 + claimp5→claimabsolute 9 处：节点 key、next/on_error/[JumpBack]/[Anchor] 引用、anchor 字段、`$__mpe_anchor_*`/`$__mpe_group_*`/`$__mpe_config_*` 键一并同步，config 的 filePath/filename 自动修正到 absolute.json；图片模板路径 `limitedevent/P5/` 未动）；消除与 p5.json 的全局重名，校验脚本全绿（涉及：resource/base/pipeline/task/limitedevent/absolute.json）

---

## v2.2.6 - 2026-08-31

---

## v2.2.5 - 2026-08-29

- 2026-08-27 [新增] 锚点框数字尾段匹配（EVENT x 关卡标题形态）：新活动页关卡标题为 `EVENT 1`（锚点字段与关卡号同框），原匹配层不认框内单位数（防 `5/5` 计数误中规则）致 1-1 全空。本帧锚点已检出时，含锚点字段的框同时作为关卡号候选——剥字母数字串按 int==expected 尾段匹配（1 位也认，锚点字段即担保；尾段比对自带消歧：`EVENT 1`→1≠11 不中 1-11、`EVENT 12`→12 中 1-12）；不配锚点/锚点未检出降级帧不启用此档，防误中规则不变。单测三用例（命中/消歧/无锚点不认）先红后绿，全量单测 + E2E 全绿；diag F 组实机 EVENT 1 页轮巡 1-12~1-2 全正确不中、1-1 第 1 试命中 `EVENT 1` score=0.82（新档位日志"整图/锚点尾段"）（涉及：agent/custom/reco/stagenum.py、tools/stagenum_test/test_stagenum_units.py、tools/stagenum_test/diag_stagelist.py、DEVELOPMENT.md §10.2）
- 2026-08-27 [修复] Stage List 活动页 stage 系列全灭根因与语义整合：①根因——p5_canintoevent_副本2 锚点字段在该页 OCR 全不可靠（CLEAR 小字整页 det 不出、花体 event 碎读 EAE/TEAE）触发 stagepre"锚点未检出即未命中"前置闸门，叠加节点 roi [395,160,496,488] 裁剪致 det 严重退化（同片像素整图可读 `-10`/`event1-11`，裁后全灭）；②语义整合（用户定调：stagepre 是叠加兜底而非推翻原识别）——锚点检出时启用过滤消歧（防错配，现状保留），全部未检出时降级为无过滤原流程（不再卡死）；节点不存在/非法仍直接未命中（防配置笔误）；③节点 roi 改为 [300,130,700,530] 卡片整带（用户拍板方案 1 只改 roi）。经 git 考古确认 v2.2.4 仓库版 stagenum.py 与 v2.2.0 逐字节相同（stage 全演进未提交），当前工作区对原主流程零删改、stagepre 纯叠加。验证：单测改断言（锚点未检出→降级命中）先红后绿，全量单测 + E2E 全绿；diag F 组实机同款配置（stagematch + stagepre=limitedevent_stagepre + 新 roi）对游戏实时画面 1-12 正确不中、1-11 第 1 试严格命中 `event1-11` score=0.99；新 roi 下该页 OCR 读数大幅改善（`1-8`/`-9`/`1-10`/`event`/`CLEAR`/`event1-11` 均可读）。工具：新增 `live_probe.py`（游戏窗口实时截图+全图 OCR 探针）、`diag_stagelist.py`（stagenum/stagematch/stagepre 多层对照诊断）（涉及：agent/custom/reco/stagenum.py、resource/base/pipeline/task/test.json、tools/stagenum_test/、DEVELOPMENT.md §10.2）
- 2026-08-27 [修复] stagepre 取参失败实机问题根因：limitedevent.json 的 `limitedevent_stagepre` 节点把 `custom_recognition_param` 误写成 JSON 字符串（且串内 `VENT`/`EVEN` 缺前引号、本身是非法 JSON）→ `_extract_stagepre_cfg` 只认 dict 直接判无效、安全未命中。修复两处：①该节点 param 改回对象格式（expected 12 个 CLEAR/EVENT 大小写截断变体保留用户意图）；②`_extract_stagepre_cfg` 新增 str→`json.loads` 兜底兼容字符串型 param，`_load_stagepre_cfg` 警告文案按"节点不存在"与"节点存在但 param 无有效 expected"分开打，避免再把配置格式问题误导成节点缺失。单测新增字符串型/非法 JSON 用例，全量单测 + 离线 E2E 全绿（涉及：agent/custom/reco/stagenum.py、resource/base/pipeline/task/example/limitedevent.json、tools/stagenum_test/test_stagenum_units.py）
- 2026-08-27 [新增] stagepre 锚点过滤体系：新增 custom reco `stagepre`（锚点字段识别器 + 锚点配置载体），stagenum/stagematch 的 param 写 `"stagepre": "<节点名>"` 即经 `context.get_node_data` 跨节点拉取其 `expected`/`max_dist`，启用"数字框必须邻近锚点框（横向行带 y 相交 / 纵向列带 x 相交，间距 ≤ max_dist 默认 300）"的空间过滤；同步收紧匹配——纯 2 位数字只按 int==尾段（`11`/`12`/`10` 不中 1-1、`12` 不中 1-2），数字串全等仅保留 ≥3 位（`HII`→`111`≡`1-11` 旧页兜底）；锚点未检出/节点不存在时直接未命中（宁漏勿错）。单测全绿 + 离线 E2E（`test_stagepre_e2e.py`：只 stub `maa.agent.agent_server` 保住真实框架，真实 OCR + 真实 get_node_data）双实机截图通过——实证无锚点时旧蓝皮页会误中解锁条件横幅的 `[1-12故事」` 文本，加锚点后正确命中 No. 列 `12` 行（涉及：agent/custom/reco/stagenum.py、tools/stagenum_test/test_stagenum_units.py、tools/stagenum_test/test_stagepre_e2e.py、DEVELOPMENT.md §10.2）
- 2026-08-27 [调查] p5_clickhard2 on_error 图根因：08-27 04:00 新活动（P5 联动）换皮，左上角"活动关卡"标签变小致 OCR det 只剩 35×5 碎条 → p5_swipe 锚点失效（非 stagenum 问题）；顺带实证 HARD 图标 OCR 读数为 "HaRD"/"HRD"、`EVENT 1` 大字可读（0.9+）可作为新锚点；产出离线 OCR 探针 `tools/stagenum_test/ocr_probe.py`（DbgController 缺 DLL 不可用，走 Win32Controller 任意窗口 + `post_recognition` 显式传图）；p5_swipe/p5_clickhard 用户确认无需修复（活动换皮属一次性事件，流程随活动维护），结项不挂起（涉及：tools/stagenum_test/ocr_probe.py）

---

## v2.2.4 - 2026-08-27

- 2026-08-25 [文档] 完善 README 使用文档：新增"程序组成"文件清单与启动链图解；autoMaaNikke.bat/.py、startnikke.ahk、DependencySetup bat 四个脚本逐一详解（流程、重试逻辑、launcher_cache.txt 缓存机制、ahk 可调参数表）；功能列表按 interface.json 展开为任务说明+可配置选项明细表；新增常见问题 FAQ（运行库缺失、路径缓存重建、WeGame 改版调按钮比例、加载期截图全黑等）（涉及：README.md）
- 2026-08-24 [新增] 合并 PR #5（ashi-koki）：新增 `autoMaaNikke.py`——`autoMaaNikke.bat` 的 Python 等价实现，供只接受 .py 的脚本调度器（如 OneDragon ScriptChainer）接入任务链；行为与 bat 一致：管理员校验 → startnikke.ahk 拉起游戏并轮询 nikke.exe → 守候 MaaNikke.exe 退出；进程名精确匹配，比 bat 的子串匹配更严谨；发版模板同步收录该文件，zip 顶层条目数 16→17（涉及：autoMaaNikke.py、F 盘发版模板、.kimi-code/skills/maanikke-release/SKILL.md）

---

## v2.2.3 - 2026-08-24

---

## v2.2.2 - 2026-08-22

- 2026-08-22 [优化] SubTask 默认参数调整为 `continue=true / strict=false`（尽力而为：子任务失败仍全部跑完、节点算成功走 next），与 M9A 原版默认（一败即停+整体失败）区分；失败判定等其余语义仍与 M9A 一致；limitedevent 节点既有显式参数与新默认相同，无需改动（涉及：agent/custom/action/my_actions.py、DEVELOPMENT.md）
- 2026-08-22 [优化] SubTask 还原为 M9A 原版语义（移植自 M9A `agent/custom/action/general.py`）：`sub` 改为必填非空列表，砍掉"缺省取本节点 next 当列表"的自动模式及配套 `override_next` 清空；默认参数回归原版——`continue` 默认 false（一败即停）、`strict` 默认 true（任一失败则节点整体失败走 on_error）；`run_task` 返回 None（任务不存在/启动失败）恢复为静默放过不计失败；砍掉 ▶/✅/❌ 边界日志与末尾汇总，只在出错时打 `[SubTask]`；limitedevent 节点同步适配：三个子任务挪入显式 `sub` 列表，显式写 `continue:true, strict:false` 保持原"尽力而为"行为，next 改指 `limitedevent_end` 收尾（涉及：agent/custom/action/my_actions.py、resource/base/pipeline/task/example/limitedevent.json、DEVELOPMENT.md）
- 2026-08-22 [调查] SubTask 子任务在 MaaLogAnalyzer 任务视图不可见的根因查明：`run_task` 内层任务有独立 task_id，节点级事件（PipelineNode/Recognition/Action，含完整 details JSON）照常全部进原生日志，但框架不为内层任务发 `Tasker.Task.Starting/Succeeded` 包装事件（实测 debug/maafw.log：task 200000001/200000003 有、内层 200000002 无）；MaaLogAnalyzer 按任务分段展示，内层节点事件归不进任何任务故不显示——框架原生行为，agent 侧无法补发。缓解路径：GUI 日志 `[Node]`/`[SubTask]` 行齐全；工具全文搜索视图可搜到子任务事件；要任务视图完整识别需把子流程改为 GUI 任务列表顺序勾选执行。后续查证：上游 issue MaaXYZ/MaaFramework#900（2025-11-30 起 open 无修复进展），main 分支（>5.13.0-beta.2）Context::run_task 源码仍无 Tasker 通知——**非版本锁定问题，升级 maafw 也解决不了**，且运行时原生库随 MFAA 发布非 pip 可升。§13 新增第 15 条坑点，§10.3 与 SubTask docstring 同步标注（涉及：DEVELOPMENT.md、agent/custom/action/my_actions.py）
- 2026-08-22 [优化] SubTask 增子任务边界日志：每个子任务开始（`▶ i/N`）/完成（`✅ +耗时`）/失败（`❌ +耗时`）逐条打印，末尾汇总"已执行 x/N，失败 y"——实测确认 `run_task` 子任务内部节点的 `[Node]` 日志经 context sink 照常完整输出（用户误以为不显示），但节点流里缺子任务归属边界，现 grep `[SubTask]` 即可定位每个子任务的结局；11 场景测试全过；DEVELOPMENT.md §10.3 同步补充 sink 覆盖事实（涉及：agent/custom/action/my_actions.py、DEVELOPMENT.md）
- 2026-08-22 [修复] SubTask 自动模式兼容框架规范化的 next 条目：`get_node_data` 返回的 `next` 实为 `[{"name": ..., "anchor": ..., "jump_back": ...}]` 对象列表（非字符串列表），此前全部判为"无效任务名"跳过 → 默认 continue/strict 下节点秒成功、清空 next，任务"刚点开始即结束"（limitedevent 实测暴露）；现复用 NextBurst 的 `_resolve_next_entry` 解析（字符串 / [JumpBack] / [Anchor] / 对象形式通吃），全解析不出才报错；测试补对象形式场景，11 场景全过（涉及：agent/custom/action/my_actions.py、temp/test_subtask.py、DEVELOPMENT.md）
- 2026-08-22 [修复] `parse_params` 兼容框架对缺省 custom param 传 JSON null（字符串 `"null"`）：此前 `json.loads("null")` 得 None，一律抛"参数必须是对象：NoneType"，导致**所有不写 param 的 custom 节点必败**（SubTask 挂 limitedevent 节点自动模式实测暴露，CheckWeekday 无参调用等同陷阱）；现 null 按无参返回 `{}`，必填键场景仍抛"缺少必填字段"；DEVELOPMENT.md §8.4/§13.2 同步补充该事实；测试补 `"null"` 场景，10 场景全过（涉及：agent/utils/params.py、temp/test_subtask.py、DEVELOPMENT.md）
- 2026-08-22 [优化] SubTask：`sub` 缺省时自动取本节点当前 `next` 作为子任务列表（兼容 str/list），跑完 `override_next` 清空本节点 next 防框架二次执行（自动模式下子任务跑完即任务线收尾）；默认参数翻转——`continue` 默认 true（失败后继续跑完）、`strict` 默认 false（有失败节点仍算成功走 next）；`run_task` 返回 None（任务不存在/启动失败）由静默放过改为计入失败；docstring 补失败判定与四组合效果说明；fake-context 单测 9 场景通过（涉及：agent/custom/action/my_actions.py、DEVELOPMENT.md、temp/test_subtask.py）
- 2026-08-22 [优化] NextBurst 截图失败兜底：某试 `post_screencap`/`cached_image` 抛 RuntimeError 时按当次未命中处理、`continue` 进下一试（循环自带重拍，瞬态截图故障不再掀桌）；同日删除 `multitry` custom reco（本日早些时候新增、未发版即撤——确定用不到，NextBurst 挂父节点的形态已覆盖其场景；其文档条目与单测一并移除，DEVLOG 原 [新增] multitry 条目同步撤下，防误进发版 changelog）（涉及：agent/custom/action/my_actions.py、agent/custom/reco/my_reco.py、DEVELOPMENT.md、temp/test_burst_screencap.py）
- 2026-08-22 [修复] NextBurst 重截图调用由 `controller.screencap()` 改为 `post_screencap().wait()`+`cached_image`——`Controller` 类本无 `screencap` 方法（那是 `CustomControllerAgent` 自定义控制器接口的抽象方法），原写法运行时会 AttributeError（Pylance reportAttributeAccessIssue 报错属实）；与 recodatebase/stagenum 既有写法对齐（涉及：agent/custom/action/my_actions.py）
- 2026-08-22 [新增] `NextBurst` custom action：挂在父节点 action 槽位的 next 候选突发扫描（候选节点零改动）——next1 连试 `tries` 次（默认 5，每次重截图）全空再扫 next2……；命中即 `override_next` 把命中者提到队首（其余候选保留）交还框架原生进入，一轮全空不 override、交还原生轮巡至 timeout→on_error；候选默认读 `get_node_data(本节点).next`（支持 [JumpBack]/[Anchor]/对象形式），也可用 `nodes` 参数指定；每试前查 `tasker.stopping`；fake-context 单测通过（涉及：agent/custom/action/my_actions.py、DEVELOPMENT.md）

---

## v2.2.1 - 2026-08-21

---

## v2.2.0 - 2026-08-20

- 2026-08-20 [优化] stagematch 临时数据库语义改为"确认删除制"（用户实机验证后提出）：命中字段标记为"最近待确认"——替换式单标记（新命中顶掉旧标记）且标记不妨碍识别（未删除字段每轮仍全扫，点击未生效/战斗未完成等未确认场景自动重试，根治原"标记即跳过"导致点击未生效时该关被永久跳过的问题）；仅后续节点明确确认未开放/已通关时 stagematchdel 才删除当前标记（至多一个，不再批量删）；db_remaining 语义变为未删除字段总数；DB 生命周期单测链重排并新增单标记替换断言，全绿（涉及：agent/custom/reco/stagenum.py、tools/stagenum_test/test_stagenum_units.py、DEVELOPMENT.md）
- 2026-08-20 [优化] 同步 juveniledays 的 OCR 词条：bigevent/smallevent/p5 三个文件的 `_12_have_end`、`_12_no_end` 节点 expected 末尾各补 `NONE`/`None`/`none` 三条（共 6 节点），校验脚本全绿（涉及：resource/base/pipeline/task/example/bigevent.json、example/smallevent.json、limitedevent/p5.json）
- 2026-08-20 [优化] stagenum 尾段兜底扩展纯数字无前缀形态（小活动页 STAGE LIST 关卡号显示 `01`~`12`，实机截图确认）：整框纯数字且 ≥2 位时按 int==expected 尾段命中（`01`≡`1-1`、`12`≡`1-12`，expected 仍统一写 `1-x`，无需开关，1-x 页与纯数字页通吃）；一位纯数字不认，防 `5/5`/`6天8小时` 类文本拆框误中；纯数字 `11`/`12` 与 `1-1`/`1-2` 丢分隔符形态存在文本层歧义，由 stagematch 长号码优先的既定顺序消解（旧断言同步改写）；单测加纯数字尾段断言组 + 小活动页读数集成用例，全绿（涉及：agent/custom/reco/stagenum.py、tools/stagenum_test/test_stagenum_units.py、DEVELOPMENT.md）
- 2026-08-20 [新增] tools/stagenum_test/grab_window.py：临时调试工具，maafw Win32Controller 直连游戏窗口截图（后台窗口可截），存 shots/game.png（涉及：tools/stagenum_test/）

---

## v2.1.9 - 2026-08-19

- 2026-08-19 [优化] juveniledays.json 内 smallevent 前缀批量改名为 juveniledays（179 处：节点 key、next/on_error/[JumpBack]/[Anchor] 引用、anchor 字段、`$__mpe_anchor_*`/`$__mpe_sticker_*` 键一并同步；图片模板路径未动，本就以 juveniledays 命名）；消除与 example/smallevent.json 的全局重名冲突，校验脚本全绿（涉及：resource/base/pipeline/task/limitedevent/juveniledays.json）

---

## v2.1.8 - 2026-08-16

- 2026-08-16 [修复] RotatedOCR 命中后点击位置偏移：`_map_to_original` 逆旋转方向取反，非 0° 命中坐标被镜像（±44° 偏差近百像素）；修正后合成图数值回归全角度误差 ≤1.4px。另修复 test.json 一处字符串式 `custom_recognition_param`（涉及：agent/custom/reco/my_reco.py、resource/base/pipeline/task/test.json）
- 2026-08-16 [新增] stagematch 进程内存态临时数据库（与 my_reco datebase 体系代码独立，供后续删除 recodatebase）：首次进入以本节点 expected 按序建库（去重，识别顺序=入库顺序）、命中字段只标记不删除（detail 增 db_remaining）、库存在时忽略各节点 expected 只按库顺序识别未标记字段、全部完成返回未命中作 pipeline 退出信号；新增 custom action `stagematchdel`（删除全部被标记字段，幂等）/ `stagematchclear`（整库清空，幂等；库随 agent 子进程退出自动销毁），均定义在 stagenum.py（reco 注册链导入即注册，注册文件零改动）；单测补 DB 生命周期 7 步用例（patch_recognize_one 加 reset_db 开关隔离模块级状态）（涉及：agent/custom/reco/stagenum.py、tools/stagenum_test/test_stagenum_units.py、DEVELOPMENT.md）
- 2026-08-16 [优化] stagenum 引擎重构为 det-first（根治新活动页全灭：该页 ROI 右侧角色立绘的深色像素把自建像素切割的行投影粘成 346px 巨带、词组全灭，且尺寸预筛按旧页小字体调的 w≤40/h≤24 误滤新页 55×25 大字体）：stage-0 整图 OCR 直配（det 框+rec 文本逐条归一匹配）+ stage-1 含数字框紧裁剪原图/提取图重读兜底；新增尾段匹配规则（`-11`≈`1-11`、`-09`≈`1-9`，能严格解析的候选不走尾段防 `1-1` 撞 `1-11`）；删除 `_runs`/`find_word_groups` 及 merge_gap/max_candidates/minmax 参数（variants 语义变为提取变体顺序，默认 otsu,dark,bright）；单测改用两页实机真实 OCR 读数回归，e2e 脚本标记待重写（FakeContext 无 det）（涉及：agent/custom/reco/stagenum.py、tools/stagenum_test/test_stagenum_units.py、tools/stagenum_test/test_stagenum_e2e.py、DEVELOPMENT.md）
- 2026-08-16 [优化] test.json 测试节点 `killthelord_into11_副本56_副本1` 从 stagenum 单字段改为 stagematch 全范围顺序识别：expected 1-12→1-1 降序（数组顺序即优先级）、tries_per_field=1（每试本就会重截图，12 字段 × 3 试会拖爆 timeout）、timeout 20s→60s（12 字段全扫一轮最坏约 25s）（涉及：resource/base/pipeline/task/test.json）
- 2026-08-15 [优化] stagenum `_ocr_texts` 子结果 box 改为 getattr 防御式取值（无 box 的子结果跳过）：消除 Pylance 对 RecognitionResult Union 类型（And/Or 成员无 box）的静态误报，运行时行为不变（涉及：agent/custom/reco/stagenum.py）
- 2026-08-15 [新增] stagematch custom reco：按 expected 数组顺序轮巡识别关卡字段（recodatebase 骨架 × stagenum 引擎）——每字段默认 3 试且每试重截图、一轮全空触发可选 action_node、全轮空返回未命中交框架重试；重构提取 `_recognize_one`/`_parse_engine_params`（stagenum 行为不变）；编排单测纯 python 覆盖；test.json 加 `stagematch_ordertest` 节点 + interface.json 加 `test2` 入口（涉及：agent/custom/reco/stagenum.py、tools/stagenum_test/test_stagenum_units.py、resource/base/pipeline/task/test.json、interface.json、DEVELOPMENT.md）
- 2026-08-15 [优化] stagenum 识别核心提取为模块级 `_recognize_one` / `_parse_engine_params`（供后续 StageMatch 复用），`StageNum.analyze` 改为 `_wrap` 委托，对外行为不变；新增 numpy-only 提取回归单测（合成图 + monkeypatch OCR）（涉及：agent/custom/reco/stagenum.py、tools/stagenum_test/test_stagenum_units.py）
- 2026-08-15 [修复] stagenum 实机不命中 1-11：本页艺术斜体 "1" 被 rec 整串误读（原图恒读 "HII"、提取图读 "11" 丢字形），宽松匹配升级为误读字归一（I/l/|/!/i/H→'1'）后比数字串，且原图枪同样启用；两道保险防误中——映射后残留其它字母直接出局（"EVEIT HI"→"111" 误中洞由新增单测抓住）、数字串须完全相等（"HI"≠"1-11"）；失败路径新增每组两枪读数日志（涉及：agent/custom/reco/stagenum.py、tools/stagenum_test/test_stagenum_units.py）
- 2026-08-15 [优化] 清理 digits 模型链路：删除 `tools/ocr_digits/` 训练工具链（9.2GB，含模型产物/合成数据/PaddleOCR/venv）、test.json `新建节点33`（digits 测试节点）、DEVELOPMENT.md §13 digits 条目；§13 新增第 14 条（识别子结果 box 是 list 的坑）；§10.2 登记 stagenum；stagenum 离线测试迁至 `tools/stagenum_test/`（自足化，不再依赖被删工具链；需 numpy+opencv-python+onnxruntime 环境）（涉及：tools/、DEVELOPMENT.md、resource/base/pipeline/task/test.json）
- 2026-08-15 [修复] stagenum 实机报错 `'list' object has no attribute 'x'`：绑定层 OCRResult.box 实为 list [x,y,w,h]（dataclass 不做类型转换），新增 `_box_xywh` 兼容取值；e2e fake 同步改为 list 形态防回归（涉及：agent/custom/reco/stagenum.py）
- 2026-08-15 [新增] stagenum custom reco：活动 STAGE LIST 关卡号（1-1~1-12）自动定位识别——前景掩码（bright/dark/otsu 级联）切词组 + 原图紧裁剪 OCR（默认模型）+ 归一化匹配（兼容 1-01；提取图兜底+宽松数字匹配救回连字符丢失场景；5/5 计数器不误中）；离线验收新图 1-6~1-11、旧图 1-1~1-3 全中；test.json 测试节点接入（涉及：agent/custom/reco/stagenum.py、agent/custom/reco/__init__.py、resource/base/pipeline/task/test.json、docs/superpowers/specs|plans）
- 2026-08-15 [调查] digits 自训数字 OCR 模型路线废弃：曾完成训练（SVTR_LCNet，黄底计数标签真实集 84/84）但从未真正接入仓库；在活动 STAGE LIST 艺术斜体关卡号上实测全误读，确认对本项目识别场景无用。教训：官方 PP-OCRv5 大模型 + 紧裁剪词组是更优路线（已由 stagenum 采用）（涉及：tools/ocr_digits（已删）、DEVELOPMENT.md）
- 2026-08-13 [文档] 补充原生多结果选择能力说明：同一字段多处命中时 `order_by: "Vertical"` + `index: 0/-1` 即取最上/最下一个，"字段多点选取"需求确认走原生方案、不做 custom reco（涉及：DEVELOPMENT.md §5）
- 2026-08-11 [文档] 文档体系重构：AGENTS.md 精简为常驻入口（速览/目录/按需读取规则/坑点速查/留痕规则），详细开发内容迁至 DEVELOPMENT.md，新增 DEVLOG.md 留痕机制（涉及：AGENTS.md、DEVELOPMENT.md、DEVLOG.md、.kimi-code/skills/maanikke-release/SKILL.md）
- 2026-08-11 [调查] "截图用时过长+截图全黑"排查结论：游戏手动重启后的加载期不产帧，FramePool 等满约 2s 帧超时返回残留黑帧并误触发 PseudoMinimizeHelper；游戏进大厅后自愈（23ms），非代码 bug，无需修复（已沉淀为 DEVELOPMENT.md §13 第 13 条）

---

## v2.1.7 - 2026-08-10

> 当前版本线。v2.1.7 及更早版本的改动记录见 `resource/announcement/Changelog.md` 与 git 历史；本文件自此线开始留痕。
