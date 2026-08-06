# MaaNikke 开发文档（AI 速查版）

> 本文档面向 AI 助手与新开发者，目标是在不通读全部源码的前提下快速理解：
> MaaFramework 的运转流程、MFAA（MFAAvalonia）GUI 框架、官方 Python Agent 机制，
> 以及本项目 `agent/` 目录的工程化实现。
> 所有外部 API 签名均取自 MaaFramework 官方文档与 Python 绑定源码；本地行为均有代码或日志实证。

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
| interface.json | `interface_version: 2`，资源版本 2.1.4 | ProjectInterfaceV2 协议 |

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
│   │   ├── action/my_actions.py   # 9 个自定义 Action
│   │   ├── reco/my_reco.py        # RotatedOCR 自定义识别
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

- `parse_params(raw: str|None, *required_keys) -> dict`：解析 `custom_action_param` / `custom_recognition_param`。**注意绑定层传给 Python 的是 JSON 字符串**（pipeline 里写对象，到 Python 是 str），必须过 `parse_params`；空串/None 返回 `{}`（除非有必填键）；格式错误抛 `ValueError`。
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
| `get_anchor(name) -> str|None` / `set_anchor(name, node)` | 锚点 ↔ 节点名（v5.1+） |
| `get_node_data(name) -> dict|None` | 读节点当前定义 |
| `get_hit_count(name)` / `clear_hit_count(name)` | 节点命中计数读写（配合 max_hit） |
| `tasker.controller` | 直接控制设备，如 `context.tasker.controller.post_click(x, y).wait()` |

### 9.5 EventSink（事件监听）

四种 Sink 基类：`TaskerEventSink`（任务级，`Tasker.Task.*`）、`ControllerEventSink`（截图/点击等，极频繁）、`ResourceEventSink`（资源加载）、`ContextEventSink`（节点级，`Node.*`）。
每个都有兜底回调 `on_raw_notification(instance, msg, details)`；`msg` 后缀 `.Starting/.Succeeded/.Failed` 即通知类型。`details` 里可能带 `focus`（pipeline 节点可配 focus 文本用于通知展示）。

## 10. 本项目已注册 custom 组件清单

### 10.1 Actions（`custom/action/my_actions.py`，共 11 个）

| 名称 | 作用 | 关键参数 | 实际使用处 |
|---|---|---|---|
| `DisableNode` | 禁用指定节点 | `node_name` | climbtower / outpostdefense |
| `NodeOverride` | 批量 override 任意节点参数 | 整个 param 即 override 表 | — |
| `ResetCount` | 清除节点命中计数（配 max_hit 循环用） | `nodes: []`, `strict` | climbtower / smallevent1 |
| `SubTask` | 顺序执行多个子任务 | `sub: []`, `continue`, `strict` | — |
| `CheckWeekday` | 命中指定星期则掐断 next（0=周一） | `days: []` | interception（周一手操 boss） |
| `CheckDate` | 按日期列表决定继续/掐断（可 inverse） | `dates: []`, `inverse` | — |
| `RetryTask` | 子任务失败重试，每次 `context.clone()` 全新上下文 | `task`, `max_retry`, `fallback` | 文档内有完整接入教程（见该类 docstring） |
| `DisableAnchorNode` | 禁用锚点当前指向的节点 | `anchor` | climbtower |
| `LoopBack` | 循环回跳锚点 `_loopback` 标记的入口节点 N 次 | `max_loops` | smallevent1 |
| `addrecodatebase` | 日期临时字段日部分 +1（唯独 1-12 改为 -1 得 1-11；缺省视为 1-1，+1 得 1-2） | 无 | — |
| `clearrecodatebase` | 日期临时字段重置为默认值 1-1（重置非删除，不留空缺） | 无 | — |

共同约定：返回 `CustomAction.RunResult(success=...)`；掐断任务线统一用 `context.override_next(argv.node_name, [])`。

### 10.2 Recognition（`custom/reco/my_reco.py`）

**`RotatedOCR`**：倾斜文字识别。流程：裁剪 ROI → 0°/±step/±2step…交替旋转 → LANCZOS 上采样 → Unsharp Mask 锐化 → `context.run_recognition` 跑内置 OCR → 命中后把坐标经"逆缩放→逆旋转→加 ROI 偏移"映射回原图。
参数：`expected`（必填）/ `threshold`(0.8) / `angle_step`(3) / `angle_range`(±45) / `scale_factor`(2) / `sharpen_strength`(1.0)。依赖 Pillow（启动自检）。使用处：test.json。

**`recodatebase` / `userecodatebase`**：日期字段识别组合，经模块级"临时字段"（`_RECO_TEMP_STORE`，默认 `"1-1"`，模块加载即初始化、清除即重置为默认值，全程不留空缺）协作；+1 / 重置由 custom action `addrecodatebase` / `clearrecodatebase` 显式执行，三者共用 my_reco.py 的 `datebase_get/set/add/clear()` 辅助函数：
- `recodatebase`：分两轮在节点 roi 内 OCR 扫描，**第 1 轮 1-12→1-6、第 2 轮 1-7→1-1**（1-7/1-6 边界重叠属刻意双保险）；每个字段两段式：先用原图识别 `triesperimage` 次（默认 5），未命中再用处理后图识别同样次数；命中即停止扫描并写入临时字段。第 1 轮全未命中则 `context.run_action(action_node)` 手动执行一次独立动作节点（如滑动刷新），重新截图扫第 2 轮；第 2 轮后无论命中与否都返回成功。**跳过 action 采用"扫描节点与动作节点分离"方案：pipeline 中本节点 action 固定写 DoNothing，刷新动作放进 `action_node` 参数指向的独立节点（不进 next 链）——全程零 override_pipeline，节点可无限次循环重入**（旧方案 override 为 DoNothing 会污染整个任务，循环重入时刷新失效，已废弃）。未配 `action_node` 时第 2 轮沿用旧图。参数：`threshold` / `triesperimage` / `action_node` / `post_action_wait` / `preprocess` / `preprocess_scale` / `binarize`。
- `userecodatebase`：以临时字段为 expected 做 OCR，**只读不清除**（清除由 `clearrecodatebase` action 在 pipeline 显式执行）。**交替识别：每次 analyze 调用只用一张图识别一次，原图与处理后图逐次轮换；识别次数不设上限，未命中时由框架按节点 timeout 反复调用**（需自行在节点配置 timeout）。参数：`threshold` / `preprocess` / `preprocess_scale` / `binarize`。

两者共用 Pillow 前处理管线（`_preprocess_for_ocr`，默认开启）：**灰度 → LANCZOS 上采样 → autocontrast 对比度拉伸 → Otsu 二值化 + 自动反色**（深底浅字转黑字白底），目的是让数字/字母更醒目、抹掉背景干扰；每轮扫描只处理一次，命中 box 会 ÷缩放倍数映射回原图。Otsu 阈值为 numpy 实现（`_otsu_threshold`），不依赖 OpenCV。

实测调参建议（默认参数为通用取向）：OCR 反而变差（字体渐变/描边被二值化吃掉）先试 `binarize: false`；漏识别降 `threshold`（如 0.7）；字特别小把 `preprocess_scale` 提到 3。

### 10.3 Sinks（`custom/sink/my_sink.py`，4 个全注册）

`AppTaskerSink`（任务开始/完成/失败+耗时）、`AppControllerSink`（仅打印 Failed）、`AppResourceSink`（Starting/Failed）、`AppContextSink`（仅打印节点级 Starting/Failed，防刷屏）。输出全部走 print → 进 GUI 日志 `[src=Agent]` 通道。

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
2. **custom param 是字符串**：绑定层把 param 序列化成 JSON 字符串传给 Python，必须 `parse_params`；直接 `argv.custom_action_param["k"]` 会炸。
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
