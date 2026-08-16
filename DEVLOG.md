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
