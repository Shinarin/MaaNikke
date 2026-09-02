# MaaNikke 开发文档（详细版）

> 本文档面向 AI 助手与新开发者，目标是在不通读全部源码的前提下快速理解：
> MaaFramework 的运转流程、MFAA（MFAAvalonia）GUI 框架、官方 Python Agent 机制，
> 以及本项目 `agent/` 目录的工程化实现。
> 所有外部 API 签名均取自 MaaFramework 官方文档与 Python 绑定源码；本地行为均有代码或日志实证。
>
> **按需按节阅读，不要一次全读**；任务类型与章节的对应关系见 AGENTS.md 的"按需读取规则"。

## 目录

- §1 项目概述
- §2 技术栈与版本基线
- §3 目录结构（开发相关部分）
- §4 端到端运转流程
- §5 MaaFramework 核心概念（主进程侧）
- §6 Agent 机制（MaaFramework 官方模型）
- §7 MFAA（MFAAvalonia）框架要点
- §8 本项目 agent 实现详解
- §9 Python Agent API 速查（官方绑定，maafw 5.x）
- §10 本项目已注册 custom 组件清单
- §11 新增 custom 组件开发流程
- §12 调试与日志
- §13 已知事实与坑（改动前必读）
- §14 参考资料

---

## 1. 项目概述

**MaaNikke** 是《胜利女神：NIKKE》（国服桌面端）的每日任务自动化工具，基于 MaaFramework 生态构建：

- **GUI 壳**：MFAAvalonia（MFAA，v2.12.1，Avalonia/.NET 10，通用 MaaFramework 图形界面），即根目录 `MaaNikke.exe`。
- **决策引擎**：MaaFramework 原生库 v5.10.2（`runtimes/win-x64/native` + `libs/`），负责截图、识别、点击、管线流转。
- **业务逻辑主体**：Pipeline JSON（`resource/base/pipeline/`），声明式节点图，覆盖 21 个日常任务。
- **自定义扩展**：Python Agent（`agent/`），承载 Pipeline 难以表达的自定义识别/动作，经 IPC 被主进程调用。
- **管线编辑器**：MaaPipelineEditor（`mpelb.exe`，`$__mpe_code` 元数据即其所写），见 `MPEsimple.txt`。

许可证 GPL-3.0，仅供学习交流。项目地址：https://github.com/Shinarin/MaaNikke

## 2. 技术栈与版本基线

| 组件 | 版本 | 说明 |
|---|---|---|
| MFAAvalonia (GUI) | v2.12.1（本地部署；上游最新 v2.13.x） | 日志 `logs/log-*.log` 中"程序版本" |
| MaaFramework（原生运行时） | **v5.10.2**（锁定） | GUI 加载的原生库版本 |
| Python 包 `maafw` | **==5.10.2**（锁定；已装任意 5.x 则复用） | `agent/main.py` 自动安装与校验 |
| Python | ≥ 3.10（代码使用 `str \| None` 等 3.10+ 语法） | 启动时强制检查 |
| Pillow | 任意近期版本 | 仅 RotatedOCR 使用，启动时自动装 |
| interface.json | `interface_version: 2`；资源版本以 `version` 字段为准（本文档不写死） | ProjectInterfaceV2 协议 |

## 3. 目录结构（开发相关部分）

```
MaaNikke_dev/
├── interface.json            # ★ 项目总线：controller/resource/task/option/agent 声明
├── MaaNikke.exe              # MFAAvalonia GUI（用户入口）
├── agent/                    # ★ Python Agent 子进程（本文档重点）
│   ├── main.py               #   启动入口：环境自检 → 依赖安装 → 参数解析 → run_agent()
│   ├── agent_runtime.py      #   核心编排：注册 custom 模块 → AgentServer 生命周期
│   ├── bootstrap.py          #   运行时路径初始化（薄封装）
│   ├── custom/               #   ★ 自定义组件（业务扩展写在这里）
│   │   ├── action/my_actions.py   # 自定义 Action（清单见 §10.1）
│   │   ├── reco/my_reco.py        # 自定义识别（清单见 §10.2）
│   │   └── sink/my_sink.py        # 4 类事件监听 Sink
│   └── utils/
│       ├── params.py         #   parse_params()：custom 参数 JSON 解析
│       └── runtime_paths.py  #   RuntimePaths：config/resource/debug 目录映射
├── resource/base/            # 资源包（interface.json "resource" 指向）
│   ├── pipeline/
│   │   ├── default_pipeline.json  # 全局默认（Default.post_wait_freezes=1000）
│   │   └── task/*.json       # 21 个任务的管线节点定义（与 interface.json task.entry 对应）
│   ├── image/                # 模板匹配图片资源
│   └── model/                # OCR 模型
├── config/
│   ├── config.json           # MFAA 全局配置
│   ├── instances/default.json# 实例配置（选中的控制器/资源/任务/option 状态）
│   └── maa_option.json       # MaaFramework 调试选项
├── logs/                     # MFAA 日志（log-*.log）+ maafw 原生日志
├── debug/                    # MaaFramework debug 输出
└── libs/, runtimes/, maafw/  # 原生库与运行时
```

## 4. 端到端运转流程

```
用户勾选任务 → MaaNikke.exe (MFAA)
  │  1. 读 interface.json：controller / resource / task / option / agent
  │  2. 按 option 选中项合并 pipeline_override JSON
  │  3. 创建 Resource（加载 resource/base 的 pipeline/image/model）
  │  4. 创建 Win32 Controller（FramePool 截图 + SendMessage 输入，绑定游戏窗口）
  │  5. 创建 Tasker = Controller + Resource
  │  6. 按 agent 配置启动 Python 子进程（见 §6）
  ▼
Tasker.AppendTask(entry, pipeline_override) 逐个任务入队执行
  │  管线节点循环：pre_delay → 执行 action → post_delay → 截图
  │    → 按序识别 next 列表 → 命中即跳入子节点；超时走 on_error；next 空则任务结束
  │
  ├─ 普通节点：原生引擎内完成（OCR/TemplateMatch/Click/Swipe…）
  └─ Custom 节点（type=Custom + custom_action/custom_recognition 名称）
       → MaaFramework 经 MaaAgentBinary IPC 转发给 Python AgentServer
       → Python 侧对应 @AgentServer.custom_action/reco 注册的类执行
       → 结果（success / box+detail）经 IPC 带回主流程继续流转
  ▼
节点事件（Node.* / Tasker.Task.*）经 Sink 回调：GUI 日志/focus 提示 + Python my_sink 打印
```

## 5. MaaFramework 核心概念（主进程侧）

- **Resource**：资源包加载器。递归加载目录下 `pipeline/*.json`（节点定义）、`image/`（模板图）、`model/`（OCR 模型）。支持运行期 `override_pipeline` 覆盖任意节点参数——interface.json 的 option、agent 的 `context.override_pipeline()` 都走这个机制。
- **Controller**：设备抽象。本项目只有 Win32 控制器：`class_regex=UnityWndClass`、`window_regex=胜利女神.*新的希望`，截图 FramePool，键鼠 SendMessageWithCursorPos（后台输入，不抢前台焦点）。
- **Tasker**：任务执行器。`AppendTask(入口节点名, pipeline_override)` 从入口节点开始跑节点图。
- **Pipeline 节点生命周期**（3.1 任务流水线协议）：
  `pre_wait_freezes → pre_delay → 执行本节点 action（可 repeat/max_hit 限制）→ post_delay → 截图 → 按序识别 next 列表 → 命中进入子节点`；识别超时进 `on_error`；`next` 为空/超时/外部停止时该任务线终止。`default_pipeline.json` 的 `Default` 节点给所有节点提供默认值（本项目设了 `post_wait_freezes: 1000`，即每节点执行后等待画面静止 1 秒）。
- **本项目 pipeline 使用新版嵌套格式**（非旧平铺式）：
  ```jsonc
  "节点名": {
      "recognition": { "type": "OCR", "param": { "expected": "确认", "roi": [...] } },
      "action":      { "type": "Click" },
      "next": ["下一节点"],
      "anchor": "锚点名",          // 可选，供 context.get_anchor() 查询
      "$__mpe_code": {...}         // MaaPipelineEditor 可视化编辑器元数据，框架忽略
  }
  ```
- **Custom 节点**：`recognition.type="Custom"` 时 `param.custom_recognition` 指定注册名；`action.type="Custom"` 时 `param.custom_action` 指定注册名，`param.custom_action_param` 为透传参数（任意 JSON 值）。
- **多结果选择（order_by + index，勿重复造 custom）**：OCR/TemplateMatch/ColorMatch 等一个 expected 命中多处时，原生即可排序后取第 N 个——`"param": {"order_by": "Vertical", "index": 0}` 取最上一个，`"index": -1` 取最下一个（`Vertical`=按 y 从上到下、y 同按 x；index 负数按类 Python 规则，-1=最末）。仅当原生 OCR 必须靠前处理才能识别时（如 recodatebase 场景），才值得为此写 custom reco。

## 6. Agent 机制（MaaFramework 官方模型）

### 6.1 双端架构

- **AgentClient**：住在主进程（MFAA）内。MFAA 调 `MaaAgentClientCreateV2(identifier)` 创建，identifier 即通信 socket 标识（未配置时随机生成 8 位字符串；多实例时追加 `_实例ID` 防冲突）。
- **AgentServer**：住在 Python 子进程（本项目 `agent/`），注册并执行 custom 代码。
- **IPC**：由独立的 `MaaAgentBinary` 原生库实现（Windows 上默认本地管道；identifier 传纯数字 1-65535 时退化为 TCP 127.0.0.1 端口模式）。**该二进制自 2024-04 起冻结**，因此 maafw 5.10~5.12 跨 minor 握手无碍——这是 `main.py` 版本验收放宽的依据。
- **握手方向**：Client 先监听 → 启动子进程并把 identifier 作为命令行参数传入 → 子进程 `AgentServer.start_up(socket_id)` 反向连接 Client。

### 6.2 interface.json 的 agent 字段（ProjectInterfaceV2）

```jsonc
"agent": {
    "child_exec": "python",              // 子进程可执行文件（CWD = interface.json 所在目录）
    "child_args": ["-u", "./agent/main.py"], // 固定参数，原样传递
    // "identifier": "..."               // 可选，固定 socket 标识；不配则每次随机
}
```
支持配置为数组以启动多个 Agent。

### 6.3 子进程实际收到的参数与环境变量（⚠ 与代码注释有出入，已实证）

MFAA 日志会打印 `Agent 启动命令：python -u "...main.py" 1uGqpjNp socket_id=1uGqpjNp instance_id=default instance_name=配置 1`，
**但实测 argv 只有位置参数 socket id**——agent 自身 stdout 日志为证：
`sys.argv = ['C:\\...\\agent\\main.py', '1uGqpjNp']`（见 `logs/log-20260801.log`）。
`socket_id=/instance_id=/instance_name=` 仅是 GUI 日志行的展示内容，不在 argv 中。
实例信息通过环境变量传递：`MFA_INSTANCE_ID` / `MFA_INSTANCE_NAME`（MFAA 私有），以及 PI v2.5.0 协议变量：
`PI_INTERFACE_VERSION` / `PI_CLIENT_NAME`(=MFAAvalonia) / `PI_CLIENT_VERSION` / `PI_CLIENT_LANGUAGE` / `PI_CLIENT_MAAFW_VERSION` / `PI_VERSION` / `PI_CONTROLLER` / `PI_RESOURCE`（后两个为当前选中控制器/资源包的单行 JSON 快照）。

> 本项目 `agent/main.py` 仍保留"优先解析 `socket_id=` 前缀参数"的兼容逻辑——防御性写法，无害，不必删。

### 6.4 子进程生命周期管理（MFAA 侧）

进程绑定 Windows Job Object（GUI 崩溃连带终止）；启动握手最多重试 3 次；任务停止/重连/更新前 `KillAllAgents`（杀整棵进程树）；Python 自动补 `-u` 无缓冲；stdout/stderr 重定向进 GUI 日志（`[src=Agent][op=Stdout]` 行）。

## 7. MFAA（MFAAvalonia）框架要点

> 仅供理解交互关系，本项目不改 MFAA 源码。仓库已迁移至 `MaaXYZ/MFAAvalonia`。

- **核心类 `MaaProcessor`**（`Extensions/MaaFW/MaaProcessor.cs`）：每实例一个，持有 MaaTasker + 任务队列，负责资源/控制器/Agent 初始化与任务执行。
- **interface.json 模型 `MaaInterface`**：Newtonsoft.Json 映射，支持 JSONC 注释与 import 递归；解析结果静态缓存，多实例共享。
- **任务调度**：勾选任务 → `CreateNodeAndParam`（按 option cases 合并所有选中项的 `pipeline_override`）→ 队列（Prescript 脚本 → Connection 建连 → 性能基准 → 各任务 entry → Postscript/CheckUpdate）→ 逐个 `MaaTasker.AppendTask(entry, override).Wait()`；失败默认中止队列。
- **option 机制**：interface.json `option` 节点的每个 case 带 `pipeline_override`，GUI 选择后合并进任务 override——**纯 JSON 层的节点参数覆盖，不需要 agent 参与**。switch/select 取单个 case，checkbox 合并多个，子 option 递归。
- **配置文件**：`config/config.json`（全局 KV）+ `config/instances/{id}.json`（每实例：CurrentTasks 用 `任务名<|||>entry` 分隔，option 选择态为嵌套 JSON）。
- **内置 C# custom 组件**：MFAA 自己还注册了 Countdown/TimedWait/CustomProgram 等 C# Action（与 Python agent 平行的另一扩展通道，本项目未用）。

## 8. 本项目 agent 实现详解

### 8.1 启动链路（main.py 四阶段）

```
MFAA: python -u ./agent/main.py <socket_id>
  └─ main.py
      阶段0: stdout 强制 UTF-8；Python≥3.10 检查；CWD 切到项目根（管线相对路径依赖 CWD）；
             agent/ 加入 sys.path
      阶段1: bootstrap.configure_initial_runtime_paths(project_root)
             → RuntimePaths{project_root, agent_dir, work_root, config_dir, resource_dir, debug_dir}
      阶段2: _ensure_maafw()：已装任意 5.x 直接复用；否则 pip 安装 maafw==5.10.2
             （直连→清华镜像→--user 兜底，300s 硬超时，装后子进程校验版本，清 maa.* 模块缓存）
      阶段3: _ensure_custom_deps()：预检 _CUSTOM_DEPS 表（目前仅 Pillow → RotatedOCR 用），
             缺失自动装。新增依赖在此表追加。
      阶段4: 解析 socket_id（优先 socket_id= 前缀参数，否则第一个位置参数）
             → agent_runtime.run_agent(project_root_dir, socket_id)
```

### 8.2 agent_runtime.run_agent()（极简三段式）

```python
from maa.agent.agent_server import AgentServer
import custom
custom.register_all()            # 动态 import custom/{action,reco,sink} 中登记的模块
AgentServer.start_up(socket_id)  # 与主进程 IPC 握手，False=失败
AgentServer.join()               # 阻塞，直到主进程断开
AgentServer.shut_down()
```

### 8.3 custom 注册机制（新增组件的入口）

`custom/__init__.py::register_all()` 依次调 `action/reco/sink.register_all()`；
各子包 `__init__.py` 内有模块名元组，**新增文件后必须把模块名加进对应元组**：

```python
# custom/action/__init__.py
ACTION_MODULES = ("my_actions", "你的新文件不含.py")
```

装饰器在模块 import 时执行注册（AgentServer 内部用 holder 防 GC），无需其他接线。

### 8.4 utils

- `parse_params(raw: str|None, *required_keys) -> dict`：解析 `custom_action_param` / `custom_recognition_param`。**注意绑定层传给 Python 的是 JSON 字符串**（pipeline 里写对象，到 Python 是 str），必须过 `parse_params`；空串/None 返回 `{}`（除非有必填键）；**框架对缺省的 param 会传 JSON null（字符串 `"null"`），同样按无参返回 `{}`**；格式错误抛 `ValueError`。
- `runtime_paths`：`get_runtime_paths()` 取 config/resource/debug 目录，冻结 dataclass，import 时即按文件位置初始化一次，`bootstrap` 再按真实项目根重配。

## 9. Python Agent API 速查（官方绑定，maafw 5.x）

### 9.1 AgentServer（全部 staticmethod）

| API | 说明 |
|---|---|
| `@AgentServer.custom_action(name)` | 装饰 CustomAction 子类并注册（name 对应 pipeline 的 `custom_action`） |
| `@AgentServer.custom_recognition(name)` | 装饰 CustomRecognition 子类并注册 |
| `@AgentServer.tasker_sink() / controller_sink() / resource_sink() / context_sink()` | 装饰对应 EventSink 子类并注册 |
| `AgentServer.start_up(identifier) -> bool` | 启动并连接主进程 |
| `AgentServer.join()` | 阻塞至服务结束 |
| `AgentServer.shut_down()` | 关闭 |
| `AgentServer.detach()` | 分离服务线程（本项目未用） |

⚠ AgentServer 进程内 `Toolkit` 不可用（调 `Library.toolkit()` 抛 `ValueError`）——不能照搬官方 boilerplate 的 `Toolkit.init_option()`。

### 9.2 CustomAction 模板

```python
from maa.agent.agent_server import AgentServer
from maa.custom_action import CustomAction
from maa.context import Context
from utils.params import parse_params

@AgentServer.custom_action("MyAction")   # 名字与 pipeline custom_action 一致
class MyAction(CustomAction):
    def run(self, context: Context, argv: CustomAction.RunArg) -> CustomAction.RunResult:
        params = parse_params(argv.custom_action_param)   # JSON 字符串 → dict
        # argv 其余字段: task_detail / node_name / custom_action_name / reco_detail / box
        return CustomAction.RunResult(success=True)       # 也可直接 return True / None
```

Pipeline 引用：
```jsonc
"some_node": {
    "action": { "type": "Custom", "param": {
        "custom_action": "MyAction",
        "custom_action_param": { "key": "value" }   // 写对象即可，到 Python 是 JSON 字符串
    }},
    "next": ["..."]
}
```

### 9.3 CustomRecognition 模板

```python
from maa.agent.agent_server import AgentServer
from maa.custom_recognition import CustomRecognition
from maa.context import Context

@AgentServer.custom_recognition("MyReco")
class MyReco(CustomRecognition):
    def analyze(self, context: Context, argv: CustomRecognition.AnalyzeArg) -> CustomRecognition.AnalyzeResult:
        # argv: task_detail / node_name / custom_recognition_name /
        #       custom_recognition_param(JSON str) / image(numpy, BGR) / roi(Rect)
        if hit:
            return CustomRecognition.AnalyzeResult(box=(x, y, w, h), detail={...})
        return CustomRecognition.AnalyzeResult(box=None, detail={})   # box=None 表示未命中
```

绑定层兼容：直接返回 4 元素 rect 也算命中，返回 None 算未命中；本项目统一用 AnalyzeResult。

### 9.4 Context（custom 代码的执行上下文）

| 方法 | 说明 |
|---|---|
| `run_task(entry, pipeline_override=None) -> TaskDetail` | 同步执行子任务（含 next 链）；用 `.status.failed` 判失败 |
| `run_recognition(entry, image, pipeline_override=None)` | 只识别不动作；`.hit` / `.box` |
| `run_action(entry, box, reco_detail, pipeline_override=None)` | 只动作不走 next |
| `override_pipeline({node: {k: v}})` | 覆盖节点参数；**影响整个任务**（context 是引用） |
| `override_next(name, [next...])` | 改节点后继；传 `[]` = 掐断任务线（条件终止的惯用手法） |
| `clone() -> Context` | 克隆独立上下文，override 只影响自身（重试场景关键） |
| `get_anchor(name) -> str|None` / `set_anchor(name, node)` | 锚点 ↔ 节点名（v5.1+）。锚点在节点执行动作后才注册（未执行不存在），同名锚点后执行的覆盖先执行的 |
| `get_node_data(name) -> dict|None` | 读节点当前定义 |
| `get_hit_count(name)` / `clear_hit_count(name)` | 节点命中计数读写（配合 max_hit） |
| `tasker.controller` | 直接控制设备，如 `context.tasker.controller.post_click(x, y).wait()` |

### 9.5 EventSink（事件监听）

四种 Sink 基类：`TaskerEventSink`（任务级，`Tasker.Task.*`）、`ControllerEventSink`（截图/点击等，极频繁）、`ResourceEventSink`（资源加载）、`ContextEventSink`（节点级，`Node.*`）。
每个都有兜底回调 `on_raw_notification(instance, msg, details)`；`msg` 后缀 `.Starting/.Succeeded/.Failed` 即通知类型。`details` 里可能带 `focus`（pipeline 节点可配 focus 文本用于通知展示）。

## 10. 本项目已注册 custom 组件清单

### 10.1 Actions（`custom/action/my_actions.py`，共 12 个）

| 名称 | 作用 | 关键参数 | 实际使用处 |
|---|---|---|---|
| `DisableNode` | 禁用指定节点 | `node_name` | climbtower / outpostdefense |
| `NodeOverride` | 批量 override 任意节点参数 | 整个 param 即 override 表 | — |
| `ResetCount` | 清除节点命中计数（配 max_hit 循环用） | `nodes: []`, `strict` | climbtower / smallevent1 |
| `SubTask` | 顺序执行多个子任务（移植自 M9A `agent/custom/action/general.py`；失败判定与原版一致——`run_task` 返回 None 静默放过不计失败、不触碰本节点 next，但默认参数不同：本项目默认尽力而为） | `sub: []`（必填）, `continue`（默认 true）, `strict`（默认 false） | limitedevent |
| `CheckWeekday` | 命中指定星期则掐断 next（0=周一） | `days: []` | interception（周一手操 boss） |
| `CheckDate` | 按日期列表决定继续/掐断（可 inverse） | `dates: []`, `inverse` | — |
| `RetryTask` | 子任务失败重试，每次 `context.clone()` 全新上下文 | `task`, `max_retry`, `fallback` | 文档内有完整接入教程（见该类 docstring） |
| `DisableAnchorNode` | 禁用锚点当前指向的节点 | `anchor` | climbtower |
| `LoopBack` | 固定次数循环闸门：前 `max_loops` 次经过回跳 `_loopback` 锚点入口，第 N+1 次恢复自身 next 放行（完整用法见该类 docstring） | `max_loops` | 未接线（smallevent1/killthelord 的 hard_return 节点挂名但无 next 链引用、无 `_loopback` 锚点声明，当前不生效） |
| `addrecodatebase` | 日期临时字段日部分 +1（唯独 1-12 改为 -1 得 1-11；缺省视为 1-1，+1 得 1-2） | 无 | — |
| `clearrecodatebase` | 日期临时字段重置为默认值 1-1（重置非删除，不留空缺） | 无 | — |
| `NextBurst` | 挂在父节点 action 槽位的 next 突发扫描：next1 连试 `tries` 次（每次重截图）全空再扫 next2…；命中即把命中者提到 next 队首交还框架原生进入，一轮全空不 override、交还原生轮巡 | `tries`(5), `delay`(200), `nodes`(可选，默认读本节点 next) | 某试截图抛 RuntimeError 按当次未命中 continue，不掀桌 |

共同约定：返回 `CustomAction.RunResult(success=...)`；掐断任务线统一用 `context.override_next(argv.node_name, [])`。

### 10.2 Recognition（`custom/reco/my_reco.py`、`custom/reco/stagenum.py`）

**`RotatedOCR`**：倾斜文字识别。流程：裁剪 ROI → 0°/±step/±2step…交替旋转 → LANCZOS 上采样 → Unsharp Mask 锐化 → `context.run_recognition` 跑内置 OCR → 命中后把坐标经"逆缩放→逆旋转→加 ROI 偏移"映射回原图。
参数：`expected`（必填）/ `threshold`(0.8) / `angle_step`(3) / `angle_range`(±45) / `scale_factor`(2) / `sharpen_strength`(1.0)。依赖 Pillow（启动自检）。使用处：test.json。

**`recodatebase` / `userecodatebase`**：日期字段识别组合，经模块级"临时字段"（`_RECO_TEMP_STORE`，默认 `"1-1"`，模块加载即初始化、清除即重置为默认值，全程不留空缺）协作；+1 / 重置由 custom action `addrecodatebase` / `clearrecodatebase` 显式执行，三者共用 my_reco.py 的 `datebase_get/set/add/clear()` 辅助函数：
- `recodatebase`：分两轮在节点 roi 内 OCR 扫描，**第 1 轮 1-12→1-6、第 2 轮 1-7→1-1**（1-7/1-6 边界重叠属刻意双保险）；每个字段两段式：先用原图识别 `triesperimage` 次（默认 5），未命中再用处理后图识别同样次数；命中即停止扫描并写入临时字段。第 1 轮全未命中则 `context.run_action(action_node)` 手动执行一次独立动作节点（如滑动刷新），重新截图扫第 2 轮；第 2 轮后无论命中与否都返回成功。**跳过 action 采用"扫描节点与动作节点分离"方案：pipeline 中本节点 action 固定写 DoNothing，刷新动作放进 `action_node` 参数指向的独立节点（不进 next 链）——全程零 override_pipeline，节点可无限次循环重入**（旧方案 override 为 DoNothing 会污染整个任务，循环重入时刷新失效，已废弃）。未配 `action_node` 时第 2 轮沿用旧图。参数：`threshold` / `triesperimage` / `action_node` / `post_action_wait` / `preprocess` / `preprocess_scale` / `binarize`。
- `userecodatebase`：以识别字段为 expected 做 OCR：参数 `targetnode` 写了就只识别该字段（与临时字段无关），不写用临时字段；**只读不清除**（清除由 `clearrecodatebase` action 在 pipeline 显式执行）。**交替识别：每次 analyze 调用只用一张图识别一次，原图与处理后图逐次轮换；识别次数不设上限，未命中时由框架按节点 timeout 反复调用**（需自行在节点配置 timeout）。参数：`targetnode` / `threshold` / `preprocess` / `preprocess_scale` / `binarize`。

两者共用 Pillow 前处理管线（`_preprocess_for_ocr`，默认开启）：**灰度 → LANCZOS 上采样 → autocontrast 对比度拉伸 → Otsu 二值化 + 自动反色**（深底浅字转黑字白底），目的是让数字/字母更醒目、抹掉背景干扰；每轮扫描只处理一次，命中 box 会 ÷缩放倍数映射回原图。Otsu 阈值为 numpy 实现（`_otsu_threshold`），不依赖 OpenCV。

实测调参建议（默认参数为通用取向）：OCR 反而变差（字体渐变/描边被二值化吃掉）先试 `binarize: false`；漏识别则再降 `threshold`（如 0.2）；字特别小把 `preprocess_scale` 提到 3。

**`stagenum`**（`custom/reco/stagenum.py`，2026-08-15 新增，2026-08-16 重构为 det-first，2026-08-20 尾段兜底扩展纯数字形态，2026-08-27 收紧防错配 + 支持 stagepre 锚点过滤）：活动 STAGE LIST 关卡号识别（expected 统一写 `1-1`~`1-12`，页面显示 `1-1`/`1-01`/纯数字 `01` 均自适应）。给定宽 roi（整个列表区域，不绑定行位置、列表滚动可用），定位完全交给框架 det 模型（与位置/字体/背景无关——旧版自建像素切割已被立绘/斜纹/字体大小淘汰并删除）。两级流程：stage-0 整图直配——roi 整图 OCR（不带 expected）后逐条文本做归一化匹配：严格（`parse_stage`，`1-04 √ Clear` 合并文本可抠出 `1-04`）→ 宽松（斜体 "1" 误读字归一，`HII`≈`1-11`）→ 尾段兜底（前导 "1" 被 det 丢失的选中行，`-11`≈`1-11`、`-09`≈`1-9`；以及整框纯数字且 ≥2 位的无前缀形态，`01`≡`1-1`、`12`≡`1-12`——小活动页 STAGE LIST 实测形态，一位纯数字不认、防 `5/5`/`6天8小时` 类计数文本拆框误中；能严格解析的候选不走尾段，防 `1-1` 撞 `1-11`；**2026-08-27 收紧**：数字串全等档仅保留 ≥3 位（`HII`→`111`≡`1-11` 旧页艺术字兜底），纯 2 位数字只按 int==尾段——`11`/`12`/`10` 不中 `1-1`、`12` 不中 `1-2`，丢分隔符歧义不再靠长号码优先消解，改由 stagepre 锚点空间过滤消歧）；stage-1 框内兜底——未匹配且含数字/形近字的框紧裁剪（pad 3px）先原图重读、再按 `variants` 顺序做黑字白底提取图重读。命中 box 映射回原图返回。参数：`expected`（必填）/ `stagepre`（可选，stagepre 节点名；填写后经 `context.get_node_data` 取该节点 `custom_recognition_param` 的 `expected`/`max_dist`，启用"数字框必须邻近锚点框"空间过滤——横向行带 y 相交或纵向列带 x 相交且间距 ≤ max_dist，默认 300；**锚点为叠加兜底而非前置闸门**：本帧锚点有检出时用它消歧，全部未检出时降级为无过滤原流程（锚点字段 OCR 不稳的页面不卡死）；且含锚点字段的框同时作为关卡号候选做"锚点尾段"匹配（取文本**最后一个数字组** int==expected 尾段，1 位也认——`EVENT 1`≡`1-1`、`EVENT 12`≡`1-12` 的关卡标题形态，尾段比对自带消歧：`EVENT 1` 不中 `1-11`；取最后组而非全串拼接，防 `CLEAR1-2` 粘连框拼出 `12` 误中 `1-12`）；仅当节点不存在/无有效字段时才直接未命中，防配置笔误静默退回无过滤）/ `threshold`(0.3) / `variants`（otsu,dark,bright，stage-1 提取变体顺序）/ `bright_min`(220) / `dark_max`(60)。无 Pillow 依赖。离线单测在 `tools/stagenum_test/`（numpy-only，OCR 用三页实机真实读数 monkeypatch；另有 `test_stagepre_e2e.py`——只 stub `maa.agent.agent_server` 保住真实框架库，真实 OCR + 真实 `get_node_data` 跑双实机截图）。使用处：test.json、limitedevent 各活动。

**`stagematch`**（`custom/reco/stagenum.py` 内第二个 reco）：关卡字段顺序轮巡（recodatebase 骨架 × stagenum 引擎）+ **进程内存态临时数据库**（`_STAGE_DB`，与 my_reco 的 datebase 体系代码完全独立）。库生命周期：首次进入以本节点 `expected` 按序建库（去重，识别顺序 = 入库顺序）→ 命中字段标记为"最近待确认"——**替换式单标记**（新命中顶掉旧标记）且**标记不妨碍识别**（未删除字段每轮仍全扫，点击未生效等未确认场景可自动重试）；detail 增 `db_remaining`（未删除字段总数）→ 仅当 pipeline 后续节点明确确认该关未开放/已通关（如"无法重复通关"弹窗）才用 custom action `stagematchdel` 删除当前标记字段（幂等，至多删一个）→ 库中字段全部删除后返回未命中（pipeline 退出信号）；`stagematchclear` 整库清空（幂等），下次进入重建，用于一轮刷完/流程收尾防残留（库随 agent 子进程退出即自动销毁）。（2026-08-20 语义变更：原为"标记即跳过、累积多个、del 批量删"，实机验证发现点击未生效时被标记关卡会永久跳过，改为确认删除制。）两个 action 定义在 stagenum.py 内（reco 注册链导入即注册），不在 my_actions.py。轮巡编排不变：每字段每轮识别 `tries_per_field` 次（默认 3，**每次识别前重新截图**——同图重试结果确定性相同，重截才有意义）；一轮全空执行 `action_node`（可选，滑动刷新类独立动作节点）并等 `post_action_wait` ms 后开下一轮（`rounds` 默认 2）；全轮皆空返回未命中由框架按 timeout 重试。detail：`matched`=命中字段、`ocr_text`=OCR 原文、`round`/`try`/`source`/`score`/`db_remaining`。与 `_recognize_one`/`_parse_engine_params` 共用 stagenum 引擎；参数增 `stagepre`（可选，同 stagenum 的锚点过滤，配置每次 analyze 重新经 `get_node_data` 拉取）；编排与库生命周期单测见 tools/stagenum_test/test_stagenum_units.py（monkeypatch `_recognize_one`，纯 python）。

**`stagepre`**（`custom/reco/stagenum.py` 内第三个 reco，2026-08-27 新增）：锚点字段识别器 + stage 系列的锚点配置载体。作为识别器：roi 整图 OCR 后 contains 匹配 `expected` 锚点字段（普通文字、大小写不敏感、不做关卡号解析），命中返回阅读顺序（y 主 x 次）首个锚点框。作为配置载体：stagenum/stagematch 的 param 写 `"stagepre": "<本节点名>"` 即引用其 `custom_recognition_param` 的 `expected`/`max_dist` 做锚点空间过滤（仅被引用时不需挂进 next 链）。**定位是叠加兜底，不取代原识别**：本帧锚点检出 → 启用过滤消歧；锚点全部未检出 → 降级为无过滤原流程（2026-08-27 语义修正：原为未检出即未命中的前置闸门，实测锚点字段 OCR 不稳的页面——Stage List 活动页 CLEAR 小字 det 不出、花体 event 碎读——会整页卡死，改为降级）；节点不存在/无有效字段仍直接未命中（防配置笔误）。另注意 **roi 裁剪对 OCR det 退化明显**（同片像素整图可读 `-10`/`event1-11`，裁小 roi 后全灭），stage 节点 roi 宜给整带/整图。锚点字段应选每张关卡卡片上重复出现的文字（锁定态 `NONE`、已通关 `CLEAR`、`Repeat` 等），随活动皮肤维护；锚点意为"关卡号必在锚点横向/纵向邻近处"，把文本层分不清的 `11`/`12` 纯数字歧义交给空间关系消歧（实测旧蓝皮页无锚点时会误中解锁条件横幅里的 `[1-12故事」` 文本，加锚点后正确命中 No. 列 `12` 行）。参数：`expected`（必填，字符串或数组）/ `max_dist`(300) / `threshold`(0.3)。

### 10.3 Sinks（`custom/sink/my_sink.py`，4 个全注册）

`AppTaskerSink`（任务开始/完成/失败+耗时）、`AppControllerSink`（仅打印 Failed）、`AppResourceSink`（Starting/Failed）、`AppContextSink`（仅打印节点级 Starting/Failed，防刷屏）。输出全部走 print → 进 GUI 日志 `[src=Agent]` 通道。**`context.run_task()` 子任务的内部节点同样触发 context sink**（`[Node] ▶` 流完整，实测验证），子任务归属定位靠该节点流；SubTask（M9A 版）本身只在子任务失败时打 `[SubTask]` 日志。但注意原生日志里 `run_task` 内层任务无 `Tasker.Task.*` 包装事件，MaaLogAnalyzer 任务视图归不进去（见 §13 第 15 条）。

## 11. 新增 custom 组件开发流程

1. **写类**：在 `custom/action/my_actions.py`（或新建文件）加 `@AgentServer.custom_action("XxxName")` 装饰的类，参数用 `parse_params` 解析，遵循 §9.2 模板。
2. **登记模块**：若新建了文件，把模块名加进对应子包 `__init__.py` 的 `*_MODULES` 元组。
3. **新依赖**：加进 `main.py` 的 `_CUSTOM_DEPS` 表（import 名/pip 名/用途），启动时自动装。
4. **pipeline 引用**：节点 `"action": {"type": "Custom", "param": {"custom_action": "XxxName", "custom_action_param": {...}}}`。
5. **自测**：用 interface.json 里的 `test` 任务（entry=`test`，default_check=false）挂你的节点，在 GUI 只勾选 test 运行；观察 GUI 日志中 `[Node] ▶`（context sink）与你的 print 输出。

## 12. 调试与日志

- **GUI 日志** `logs/log-YYYYMMDD.log`：MFAA 主日志；agent 的 stdout/stderr 以 `[src=Agent][op=Stdout/Stderr]` 混入。
- **原生日志** `logs/maafw.log`、`debug/maafw.log`：MaaFramework 引擎层细节（识别分数、节点流转）。
- **识别截图** `logs/vision/`、错误存档 `logs/on_error/`（由 `config/maa_option.json` 的 save_draw/save_on_error 控制）。
- 修改 Python custom 代码后**无需重装**，重启任务即可（agent 是每次任务前新启的子进程）。

## 13. 已知事实与坑（改动前必读）

1. **argv 真相**：子进程 argv 只有 `[脚本路径, socket_id]`；实例信息走 `MFA_INSTANCE_*` / `PI_*` 环境变量（§6.3）。`main.py` 兼容解析两种形式是防御性冗余。
2. **custom param 是字符串**：绑定层把 param 序列化成 JSON 字符串传给 Python，必须 `parse_params`；直接 `argv.custom_action_param["k"]` 会炸。缺省 param 时框架传的是 JSON null（字符串 `"null"`），`parse_params` 已兼容为 `{}`。
3. **内嵌字符串式 param 易出错**：pipeline 里 `custom_action_param` 也可以写成转义后的 JSON 字符串（而非对象），字符串里多一个逗号就是非法 JSON（smallevent1.json 曾因此导致 `ResetCount` 必败，已修复）。新增节点建议直接写对象形式。
4. **版本锁定**：`maafw==5.10.2` 与 GUI 原生库对齐；验收放宽到任意 5.x 是因为 MaaAgentBinary IPC 协议冻结。升 6.x 前必须重新评估。
5. **CWD 依赖**：MFAA 以项目根为 CWD 启动子进程，main.py 再次强制 `chdir` 到项目根；管线内相对路径、模板图加载都依赖这一点，不要在 agent 里再改 CWD。
6. **`$__mpe_code` 元数据**：pipeline JSON 里的 `$__mpe_*` 键是 MaaPipelineEditor 的画布数据，框架忽略，**不要删**（编辑器要用）；手写节点无需加。
7. **Toolkit 不可用**：AgentServer 进程内没有 Toolkit（§9.1）；日志、截图保存由主进程侧 `config/maa_option.json` 控制。
8. **LoopBack/RetryTask 的计数状态**：LoopBack 用类变量计数器，跨任务可能残留（重跑任务即新进程，实际无碍）；RetryTask 每次 clone 上下文，被包装任务内部靠 `override_next` 主动终止的不算失败、不会触发重试（设计如此）。
9. **Windows/管理员**：GUI 需管理员运行；游戏窗口标题须匹配 `胜利女神.*新的希望`，截图方式 FramePool 对画质设置敏感（README 有强制画质要求）。
10. **传给框架的图像必须是 3 通道 uint8**：`context.run_recognition` 的 image 经绑定层 `ImageBuffer.set` 传递，其硬编码类型 CV_8UC3（16）按 `宽×高×3` 字节读取——传 2D 单通道灰度图会让原生层越界读内存（ctypes 回调里报 `access violation`，表现为任务失败）。切片视图的非连续数组绑定层已自行转连续，无需担心；`_preprocess_for_ocr` 输出已统一为 3 通道。
11. **节点批量改名时锚点（重定向）相关名称一并替换**：除节点 key 和 `next`/`[JumpBack]` 引用外，`anchor` 字段、`[Anchor]` 引用、以及 `$__mpe_anchor_<锚点名>_<文件名>` 元数据键中的锚点名段也要同步改名——漏改 `$__mpe_anchor_*` 键会让 MPE 编辑器丢失锚点的画布位置记录；`[Anchor]` 引用必须与某节点的 `anchor` 字段对应，改名后注意检查锚点设置方与引用方仍然闭环（boomtheghost.json 曾出现 `[Anchor]smallevent1anchor` 悬空引用，靠入口节点锚点改名对齐修复）。
12. **节点批量改名时 MPE 便签（sticker）键名一并替换**：`$__mpe_sticker_<任务名>_便签N_<文件名>` 键中嵌入的任务名字段要同步改为新名，否则 MPE 编辑器里便签与原任务的对应关系丢失。
13. **游戏加载期"截图超时+全黑"是环境现象，不是代码 bug**（2026-08-07 实证）：游戏重启/启动后的加载阶段（黑屏、不 Present 新帧）被连接时，FramePool 拿不到新帧会等满约 2 秒帧超时并返回残留黑帧（MFAA 日志报 `截图用时过长：2008ms(FramePool)`），还可能误触发 PseudoMinimizeHelper 施加伪最小化；游戏加载完成后自愈（同一窗口恢复 23ms）。遇到时先确认游戏是否已进大厅再排查代码。另：不要多开 MaaNikke 实例（含 dev/release 两份同时跑），会造成热键互斥锁与配置文件锁冲突。
14. **识别子结果的 box 是 list 不是 Rect**（2026-08-15 实证）：`RecognitionDetail.filtered_results` / `all_results` / `best_result` 里的结果项（如 OCRResult）由绑定层 `ResultType(**raw_result)` 构造，dataclass 不做类型转换，JSON 原样透传——其 `box` 字段实为 list `[x,y,w,h]`，`.x/.y` 访问会炸 `AttributeError: 'list' object has no attribute 'x'`（在 ctypes 回调里变成 "Exception ignored" 静默吞栈）。取 box 用 `stagenum.py` 的 `_box_xywh()` 兼容写法（同时支持 list 与 Rect 对象）。
15. **`run_task` 内层任务不发 `Tasker.Task.*` 事件**（2026-08-22 实证）：`context.run_task` 启动的子任务有独立 task_id，节点级事件（PipelineNode/Recognition/Action，含完整 details JSON）照常全部进原生日志，但**没有 `Tasker.Task.Starting/Succeeded` 包装**（仅外层 posted 任务有；实测 debug/maafw.log 里 task 200000001/200000003 有、内层 200000002 无）。MaaLogAnalyzer 按任务分段展示，内层节点事件归不进任何任务 → 任务视图看不到子任务节点。这是**上游未实现的行为而非版本锁定问题**：上游 issue [MaaXYZ/MaaFramework#900](https://github.com/MaaXYZ/MaaFramework/issues/900)（2025-11-30 起 open，无修复进展）；main 分支（>5.13.0-beta.2）`Context::run_task` 源码仍无 Tasker 通知（注释自述"context 的子任务没有 Pending 状态，直接就是 Running"）。且运行时原生库随 MFAA 发布，非 pip 侧可升——即便上游修好也要等 MFAA 更新内置框架。排查子任务：用 GUI 日志 `[Node]`/`[SubTask]` 行（齐全），或 MaaLogAnalyzer 的全文搜索视图（全文索引不受任务分段影响）。要任务视图完整识别，子流程须改为 GUI 任务列表顺序勾选执行（每个都是完整 Tasker 任务）。

## 14. 参考资料

官方文档（MaaXYZ/MaaFramework，docs/zh_cn/）：
- 1.1-快速开始 / 1.3-Custom&Agent（Agent 概念与双端模型）
- 2.2-集成接口一览（MaaAgentClientAPI / MaaAgentServerAPI）
- 3.1-任务流水线协议（节点字段全集）
- 3.3-ProjectInterfaceV2协议（interface.json 字段、PI_* 环境变量）

API 签名以 Python 绑定源码为准：`source/binding/Python/maa/`（agent/agent_server.py、custom_action.py、custom_recognition.py、context.py、event_sink.py）。

相关仓库：
- https://github.com/MaaXYZ/MaaFramework
- https://github.com/MaaXYZ/MFAAvalonia（GUI 框架）
- https://github.com/MaaXYZ/MaaPracticeBoilerplate（官方 Python agent 极简示例；注意其无 custom/ 目录结构，本项目的 custom+utils 分层是演进形态）
