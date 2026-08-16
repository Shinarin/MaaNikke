# MaaNikke 项目说明（AI 常驻入口）

> 本文档每次会话都会加载，刻意保持精简。
> 详细开发文档在 **DEVELOPMENT.md**（按需按节阅读，不要一次全读）；
> 每次改动项目后必须在 **DEVLOG.md** 留痕（规则见 §5）。

## 1. 项目速览

**MaaNikke** 是《胜利女神：NIKKE》（国服桌面端）的每日任务自动化工具，GPL-3.0，仅供学习交流。
仓库：https://github.com/Shinarin/MaaNikke

四个组成部分：

- **GUI 壳**：MFAAvalonia（MFAA v2.12.1，Avalonia/.NET 10），即根目录 `MaaNikke.exe`；本项目不改其源码。
- **决策引擎**：MaaFramework 原生库 **v5.10.2（锁定）**，`runtimes/win-x64/native` + `libs/`。
- **业务主体**：Pipeline JSON，`resource/base/pipeline/`，21 个日常任务的声明式节点图。
- **自定义扩展**：Python Agent（`agent/`），custom action/reco/sink 经 IPC 被主进程调用。

版本基线：Python ≥ 3.10；pip 包 `maafw==5.10.2`（已装任意 5.x 则复用）；Pillow 任意近期版本。
资源版本号以 `interface.json` 的 `version` 字段为准（文档不写死）。

## 2. 目录结构速览

```
MaaNikke_dev/
├── interface.json      # ★ 项目总线：controller/resource/task/option/agent 声明
├── MaaNikke.exe        # MFAA GUI（用户入口）
├── agent/              # ★ Python Agent 子进程（main.py 入口；custom/ 写业务扩展）
├── resource/base/      # 资源包：pipeline/（节点 JSON）、image/（模板图）、model/（OCR 模型）
├── config/             # MFAA 全局/实例配置 + maa_option.json（调试开关）
├── logs/               # GUI 日志（log-*.log）、maafw 原生日志、vision/ 识别截图
├── debug/              # MaaFramework debug 输出
└── libs/, runtimes/, maafw/  # 原生库与运行时（勿动）
```

## 3. 按需读取规则（改什么，读什么）

| 任务类型 | 必读内容 |
|---|---|
| 修改/新增 pipeline 节点 | DEVELOPMENT.md §5（节点协议）；pipeline-guide skill；批量改名前另读 §13 第 11/12 条 |
| 新增/修改 custom action/reco/sink | DEVELOPMENT.md §9（API 模板）、§8.3（注册机制）、§11（开发流程）；现有组件清单见 §10 |
| 排查 agent 启动/依赖/参数问题 | DEVELOPMENT.md §8.1（启动链路）、§6.3（argv/环境变量真相）、§6.4（生命周期） |
| 排查截图/识别/点击问题 | DEVELOPMENT.md §12（日志位置）、§13（坑点）；先排除 §13 第 13 条的环境现象 |
| 理解 option 合并/任务调度/override | DEVELOPMENT.md §7（MFAA 要点）、§5（核心概念） |
| 发版（push + Release） | `.kimi-code/skills/maanikke-release/SKILL.md`，严格按流程，不要自由发挥 |
| 写改动留痕 | DEVLOG.md 头部规则（§5 有摘要） |

## 4. 坑点速查（论证与细节见 DEVELOPMENT.md §13）

1. agent 子进程 argv 只有 `[脚本路径, socket_id]`；实例信息走 `MFA_INSTANCE_*` / `PI_*` 环境变量。
2. custom param 到 Python 是 JSON 字符串，必须过 `parse_params`，直接当 dict 用会炸。
3. pipeline 里 `custom_action_param` 直接写对象，不要写转义字符串（多一个逗号即非法 JSON）。
4. `maafw==5.10.2` 锁定，与 GUI 原生库对齐；升 6.x 前必须重新评估。
5. CWD 必须是项目根（截图/模板/相对路径都依赖），agent 里不要再 chdir。
6. pipeline JSON 里的 `$__mpe_*` 键是 MPE 编辑器画布数据，框架忽略，**不要删**。
7. AgentServer 进程内 Toolkit 不可用；日志/截图保存由主进程侧 `config/maa_option.json` 控制。
8. LoopBack 用类变量计数、RetryTask 每次 clone 上下文，行为边界见 §13 第 8 条（设计如此）。
9. GUI 需管理员运行；窗口标题须匹配 `胜利女神.*新的希望`；FramePool 对游戏画质设置敏感。
10. 传给 `run_recognition` 的图像必须是 3 通道 uint8，否则原生层越界崩溃（access violation）。
11. 节点批量改名：`anchor` 字段、`[Anchor]` 引用、`$__mpe_anchor_*` 键名一并改，且锚点设置方与引用方须闭环。
12. 节点批量改名：`$__mpe_sticker_*` 键中嵌入的任务名也要一并改。
13. 游戏重启/加载期连接会出现"截图用时过长（约2s）+截图全黑"——加载期不产帧的环境现象，进大厅后自愈，非代码 bug；先确认游戏状态再排查。不要多开 MaaNikke 实例（dev/release 同时跑会互踩锁）。

## 5. 改动留痕规则（DEVLOG.md）

- **每次改动项目**（代码 / pipeline / 配置 / 文档）后，在 `DEVLOG.md` 的 `## [未发布]` 区追加一条：
  `- YYYY-MM-DD [类型] 简述（涉及：文件/模块）`，类型：新增 / 修复 / 优化 / 文档 / 调查。
- 新内容在上、旧内容在下；普通 push 不动 DEVLOG。
- **仅执行完整发版流程时**（maanikke-release skill）：未发布区封存为新版本线，并把条目过滤改写成用户向内容、与用户提供的 changelog 合并写入 `resource/announcement/Changelog.md`（格式与旧条目一致；代码/文档/调查类内部条目不写入）。
- `Changelog.md` 是用户向（仅发版时写），`DEVLOG.md` 是开发向（每次改动就写），两者不要混。

## 6. 调试日志速查

- GUI 日志：`logs/log-YYYYMMDD.log`（agent 输出混在 `[src=Agent]` 行）
- 原生日志：`logs/maafw.log`、`debug/maafw.log`（识别分数、节点流转、截图细节）
- 识别截图：`logs/vision/`；错误存档：`logs/on_error/`
- 改 Python custom 代码后无需重装，重启任务即生效（agent 是每次任务新启的子进程）
