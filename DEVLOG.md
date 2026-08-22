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
