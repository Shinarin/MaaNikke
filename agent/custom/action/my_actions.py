"""
============================================================
  ★ 在此文件中编写你的自定义 Action ★
============================================================

所有 Action 通过 @AgentServer.custom_action("名称") 注册，
名称需与 Pipeline JSON 中的 custom_action 字段一致。

⚠️ 在 Pipeline JSON 中调用自定义 Action 必须同时写:
    "action": "Custom",
    "custom_action": "你的Action名"

上下文对象 context 的常用方法：
  - context.override_pipeline({...})    覆盖管线节点参数
  - context.override_next("节点", [...])  跳转到指定后续节点
  - context.run_task("任务名")           执行子任务，返回 TaskDetail
  - context.run_action("入口", ...)      直接执行一个动作（不触发后续 next）
  - context.run_recognition("识别名", img, pipeline)  执行识别
  - context.clear_hit_count("节点名")    重置节点的命中计数
  - context.clone()                     克隆一个新上下文（独立覆盖管线）
  - context.tasker.controller           游戏控制器（截图/点击等）
============================================================
"""

from maa.agent.agent_server import AgentServer
from maa.context import Context
from maa.custom_action import CustomAction
from utils.params import parse_params
from custom.reco.my_reco import datebase_add, datebase_clear, datebase_get

import datetime
import time


# =====================================================================
# Action 1: DisableNode —— 禁用指定管线节点
# =====================================================================
@AgentServer.custom_action("DisableNode")
class DisableNode(CustomAction):
    """
    将特定 node 设置为 disable 状态。

    参数格式:
    {
        "node_name": "结点名称"
    }

    Pipeline JSON 引用示例:
    {
        "action": "Custom",
        "custom_action": "DisableNode",
        "custom_action_param": {
            "node_name": "要禁用的节点名"
        }
    }
    """

    def run(
        self,
        context: Context,
        argv: CustomAction.RunArg,
    ) -> CustomAction.RunResult:
        # 解析必填参数 node_name
        node_name = parse_params(argv.custom_action_param, "node_name")["node_name"]
        # 覆盖管线：将该节点的 enabled 设为 False
        context.override_pipeline({f"{node_name}": {"enabled": False}})
        return CustomAction.RunResult(success=True)


# =====================================================================
# Action 2: NodeOverride —— 批量覆盖管线节点参数
# =====================================================================
@AgentServer.custom_action("NodeOverride")
class NodeOverride(CustomAction):
    """
    在 node 中执行 pipeline_override。

    参数格式:
    {
        "node_name": {"被覆盖参数": "覆盖值", ...},
        "node_name1": {"被覆盖参数": "覆盖值", ...}
    }

    Pipeline JSON 引用示例:
    {
        "action": "Custom",
        "custom_action": "NodeOverride",
        "custom_action_param": {
            "节点A": {"enabled": false},
            "节点B": {"next": ["OtherTask"]}
        }
    }
    """

    def run(
        self,
        context: Context,
        argv: CustomAction.RunArg,
    ) -> CustomAction.RunResult:
        # 解析参数（无必填字段，允许空参数跳过）
        ppover = parse_params(argv.custom_action_param)

        if not ppover:
            print("[NodeOverride] 参数为空，跳过覆盖")
            return CustomAction.RunResult(success=True)

        print(f"[NodeOverride] 覆盖管线: {ppover}")
        context.override_pipeline(ppover)

        return CustomAction.RunResult(success=True)


# =====================================================================
# Action 3: ResetCount —— 重置计数器节点
# =====================================================================
@AgentServer.custom_action("ResetCount")
class ResetCount(CustomAction):
    """
    重置指定节点的命中计数器。

    参数格式:
    {
        "nodes": ["节点名1", "节点名2"],   # 目标计数器节点名称列表
        "strict": false                     # 可选，任一失败时是否视为整体失败，默认 false
    }

    Pipeline JSON 引用示例:
    {
        "action": "Custom",
        "custom_action": "ResetCount",
        "custom_action_param": {
            "nodes": ["计数节点A", "计数节点B"],
            "strict": false
        }
    }
    """

    def run(
        self,
        context: Context,
        argv: CustomAction.RunArg,
    ) -> CustomAction.RunResult:
        # 解析参数（nodes 无默认值，由下方手动校验）
        try:
            param = parse_params(argv.custom_action_param)
        except ValueError as e:
            print(f"[ResetCount] 参数解析失败: {e}")
            return CustomAction.RunResult(success=False)

        nodes = param.get("nodes", None)
        if not isinstance(nodes, list) or not nodes:
            print("[ResetCount] 缺少有效的 nodes 列表")
            return CustomAction.RunResult(success=False)

        strict = param.get("strict", False)
        if not isinstance(strict, bool):
            print("[ResetCount] strict 必须为布尔值")
            return CustomAction.RunResult(success=False)

        has_failure = False
        for index, node_name in enumerate(nodes):
            if not isinstance(node_name, str) or not node_name:
                msg = f"[ResetCount] 无效节点名 nodes[{index}]: {node_name!r}"
                print(msg)
                has_failure = True
                continue

            # 调用 MAA API 清除命中计数
            if not context.clear_hit_count(node_name):
                msg = f"[ResetCount] 清除失败: node={node_name}"
                print(msg)
                has_failure = True
                continue

            print(f"[ResetCount] 已清除计数: node={node_name}")

        # strict 模式下任一失败则整体失败
        if has_failure and strict:
            print("[ResetCount] strict 模式，存在失败节点 → 整体失败")
            return CustomAction.RunResult(success=False)

        return CustomAction.RunResult(success=True)


# =====================================================================
# Action 4: SubTask —— 按顺序执行子任务
# =====================================================================
@AgentServer.custom_action("SubTask")
class SubTask(CustomAction):
    """
    按顺序执行子任务（同步阻塞：每个子任务整条管线跑完才轮到下一个）。
    移植自 M9A（agent/custom/action/general.py 的 SubTask）；失败判定与原版一致，
    默认参数不同：原版默认一败即停+整体失败，本项目默认尽力而为。

    参数格式:
    {
        "sub": ["任务名1", "任务名2"],   # 必填，非空子任务名称列表
        "continue": true,                # 可选，任一失败后是否继续后续，默认 true
        "strict": false                  # 可选，任一失败时本节点是否视为失败，默认 false
    }

    失败判定（记一次子任务失败）:
      - 任务名无效（非字符串 / 空串）
      - 子任务执行后 status.failed（其内部节点失败且未被它自己的 on_error 兜住）
      注意：run_task 返回 None（任务不存在 / 启动失败）时静默放过，不计失败
      ——与 M9A 原版行为一致。

    continue / strict 组合效果（默认 continue=true, strict=false，
    即全部跑完、永远成功走 next 的尽力而为模式）:
      continue=true,  strict=false: 全部跑完，永远成功走 next —— 尽力而为（默认）
      continue=true,  strict=true : 全部跑完，最后统一算失败 —— 先全试再算账
      continue=false, strict=true : 一败即停，节点整体失败 —— 快速失败
      continue=false, strict=false: 一败即停，但节点算成功 —— 跑到哪算哪

    本组件不触碰本节点 next：子任务全部跑完后，框架照常走 next。
    子任务内部节点的 [Node] ▶/❌ 日志照常输出（context sink 对 run_task
    内部节点同样生效）；本组件只在出错时打 [SubTask] 日志。

    Pipeline JSON 引用示例:
    {
        "action": "Custom",
        "custom_action": "SubTask",
        "custom_action_param": {
            "sub": ["TaskA", "TaskB"],
            "continue": true,
            "strict": false
        },
        "next": ["全部执行完后去的节点"]
    }
    """

    def run(
        self,
        context: Context,
        argv: CustomAction.RunArg,
    ) -> CustomAction.RunResult:
        try:
            param = parse_params(argv.custom_action_param)
        except ValueError as e:
            print(f"[SubTask] 参数解析失败: {e}")
            return CustomAction.RunResult(success=False)

        sub = param.get("sub", None)
        if not isinstance(sub, list) or not sub:
            print("[SubTask] sub 必填，且必须是非空任务名列表")
            return CustomAction.RunResult(success=False)

        # 关键决策参数：控制失败行为（默认尽力而为：全跑完、永远成功走 next）
        continue_on_failure = bool(param.get("continue", True))
        strict = bool(param.get("strict", False))
        has_sub_failure = False

        for index, task_name in enumerate(sub):
            if not isinstance(task_name, str) or not task_name:
                print(f"[SubTask] ❌ 无效任务名 sub[{index}]: {task_name!r}")
                has_sub_failure = True
                if not continue_on_failure:
                    break  # 不继续则终止循环
                continue

            task_detail = context.run_task(task_name)
            # run_task 返回 None（任务不存在 / 启动失败）时静默放过，与 M9A 原版一致
            if task_detail and task_detail.status.failed:
                print(f"[SubTask] ❌ 子任务运行失败: index={index}, task={task_name}")
                has_sub_failure = True
                if not continue_on_failure:
                    break  # 不继续则终止循环

        return CustomAction.RunResult(success=not (has_sub_failure and strict))


# =====================================================================
# Action 5: CheckWeekday —— 指定星期中止任务
# =====================================================================
@AgentServer.custom_action("CheckWeekday")
class CheckWeekday(CustomAction):
    """
    检测到指定星期几时中止当前节点后续任务，其他日子正常继续。

    参数格式:
    {
        "days": [0, 1, 2]   # 要中止的星期，0=周一 1=周二 2=周三 3=周四 4=周五 5=周六 6=周日
    }

    不传参数默认周一中止。

    星期数字对照:  0=周一  1=周二  2=周三  3=周四  4=周五  5=周六  6=周日

    Pipeline JSON 引用示例:
    {
        "action": "Custom",
        "custom_action": "CheckWeekday",
        "custom_action_param": {
            "days": [1, 2]
        },
        "next": ["非中止日继续执行的节点"]
    }
    """

    def run(
        self,
        context: Context,
        argv: CustomAction.RunArg,
    ) -> CustomAction.RunResult:
        # 解析参数：取 days 列表，未传参则默认周一
        param = parse_params(argv.custom_action_param)
        days = param.get("days", [0])

        if datetime.datetime.today().weekday() in days:
            # 命中指定星期 → 清空后续节点，任务中止
            context.override_next(argv.node_name, [])

        # 未命中 → 不干预，管线自动走向 next
        return CustomAction.RunResult(success=True)


# =====================================================================
# Action 6: CheckDate —— 指定日期检测
# =====================================================================
@AgentServer.custom_action("CheckDate")
class CheckDate(CustomAction):
    """
    检测今日日期是否在指定日期列表中。

    默认行为:
      在列表中 → 继续走 next 节点；
      不在列表中 → 清空 next，中止当前任务线。

    inverse: true 时行为反转:
      在列表中 → 清空 next，中止；
      不在列表中 → 继续走 next 节点。

    参数格式:
    {
        "dates": ["2026-05-28", "2026-06-01"],   # 日期列表，格式 YYYY-MM-DD
        "inverse": false                          # 可选，是否反转行为，默认 false
    }

    Pipeline JSON 引用示例:
    {
        "action": "Custom",
        "custom_action": "CheckDate",
        "custom_action_param": {
            "dates": ["2026-05-28", "2026-06-15"],
            "inverse": false
        },
        "next": ["匹配日期后执行的节点"]
    }
    """

    def run(
        self,
        context: Context,
        argv: CustomAction.RunArg,
    ) -> CustomAction.RunResult:
        # 解析参数
        try:
            param = parse_params(argv.custom_action_param)
        except ValueError as e:
            print(f"[CheckDate] 参数解析失败: {e}")
            return CustomAction.RunResult(success=False)

        dates = param.get("dates", None)
        if not isinstance(dates, list) or not dates:
            print("[CheckDate] 缺少有效的 dates 列表")
            return CustomAction.RunResult(success=False)

        inverse = bool(param.get("inverse", False))

        # 获取今日日期字符串
        today_str = datetime.date.today().isoformat()  # 格式: "YYYY-MM-DD"

        # should_stop 判定: inverse=false → 不在列表中时中止; inverse=true → 在列表中时中止
        should_stop = (today_str in dates) == inverse

        if should_stop:
            reason = "在列表中(inverse)" if inverse else "不在列表中"
            print(f"[CheckDate] 今日 {today_str} {reason}，中止后续")
            context.override_next(argv.node_name, [])
        else:
            reason = "不在列表中(inverse)" if inverse else "在列表中"
            print(f"[CheckDate] 今日 {today_str} {reason}，继续执行")

        return CustomAction.RunResult(success=True)


# =====================================================================
# Action 7: RetryTask —— 带重试的任务执行器
# =====================================================================
@AgentServer.custom_action("RetryTask")
class RetryTask(CustomAction):
    """
    执行子任务，失败后自动从头重试，超过最大次数后跳过。

    ── 核心机制 ──
    每次重试通过 context.clone() 创建独立执行上下文，
    所有节点的 max_hit / enabled 状态 / override_pipeline 修改全部重置。

    ── 参数格式 ──
    {
        "task": "子任务入口节点名",     // 必填
        "max_retry": 1,              // 可选，最大重试次数（不含首次），默认 1
        "fallback": "兜底任务入口"     // 可选，全部失败后执行，如 "backtohomepage"
    }

    ── Pipeline JSON 引用示例 ──
    {
        "action": "Custom",
        "custom_action": "RetryTask",
        "custom_action_param": {
            "task": "arena",
            "max_retry": 1,
            "fallback": "backtohomepage"
        },
        "next": ["下一个任务入口"]
    }

    ── 如何搭建 RetryTask 包装 ──
    假设要给 "竞技场" (arena) 任务加重试，只需改动 2 处，不动原文件：

    【步骤 1】新建包装管线文件
      路径: resource/base/pipeline/task/arena_retry.json
      内容:
      {
          "arena_retry": {
              "action": "Custom",
              "custom_action": "RetryTask",
              "custom_action_param": {
                  "task": "arena",
                  "max_retry": 1
              },
              "next": []
          }
      }
      说明: 这个文件只包含 1 个节点，作为包装入口。

    【步骤 2】修改 interface.json
      找到 "竞技场" 对应的条目，把 entry 从 "arena" 改为 "arena_retry":
      {
          "name": "竞技场",
          "entry": "arena_retry",     // ← 只改这里
          ...
      }

    【步骤 3】原 arena.json —— 完全不动

    ── 执行流程 ──
    GUI 选择 "竞技场"
      → interface.json: entry="arena_retry"
        → arena_retry.json: arena_retry 节点
          → RetryTask.run()
            ├─ 第1次 context.run_task("arena")    ← 全新上下文
            │   → arena.json 从头执行
            │   → 成功? 返回 ✅  → 任务结束
            │   → 失败? 进入重试
            │
            ├─ 第2次 context.run_task("arena")    ← 再次全新上下文
            │   → arena.json 从头执行
            │   → 成功? 返回 ✅  → 任务结束
            │   → 失败? max_retry 耗尽
            │
            └─ 执行 fallback (如果有) → 返回 ✅ → next 空 → 任务结束

    ── 设计要点 ──
    1. task 参数填的是【原任务入口节点名】，不是文件名。
       例如 arena.json 里有个节点叫 "arena"，task 就填 "arena"。
    2. 被包装的任务内部节点完全不需要 on_error，RetryTask 接管所有错误处理。
    3. wrapper 节点 next 通常设为 []，让重试耗尽后自然结束当前任务链。
    4. max_retry=1 表示失败后重试 1 次，总共最多执行 2 次。
    5. 如果被包装任务内部有 context.override_next() 清空 next 导致"主动终止"
       （如 CheckWeekday、CheckDate），run_task 返回的可能不是 failed 状态，
       此时 RetryTask 不会触发重试——这是预期行为。
    """

    def run(
        self,
        context: Context,
        argv: CustomAction.RunArg,
    ) -> CustomAction.RunResult:
        # --- 参数解析 ---
        try:
            param = parse_params(argv.custom_action_param)
        except ValueError as e:
            print(f"[RetryTask] 参数解析失败: {e}")
            return CustomAction.RunResult(success=False)

        task_name = param.get("task", None)
        if not isinstance(task_name, str) or not task_name:
            print("[RetryTask] 缺少必填参数 task")
            return CustomAction.RunResult(success=False)

        max_retry = param.get("max_retry", 1)
        if not isinstance(max_retry, int) or max_retry < 0:
            print("[RetryTask] max_retry 必须为非负整数")
            return CustomAction.RunResult(success=False)

        fallback = param.get("fallback", None)

        # --- 执行 + 重试循环 ---
        # 总共最多执行 (1 + max_retry) 次
        for attempt in range(1 + max_retry):
            print(f"[RetryTask] 第 {attempt + 1} 次执行: {task_name}")

            # ★ 每次重试使用全新克隆上下文
            # clone() 创建独立上下文，所有 override_pipeline / max_hit / enabled 状态重置
            fresh_ctx = context.clone()
            task_detail = fresh_ctx.run_task(task_name)

            if task_detail is None:
                print(f"[RetryTask] run_task 返回 None（任务可能不存在）: {task_name}")
                break

            if not task_detail.status.failed:
                print(f"[RetryTask] 第 {attempt + 1} 次成功: {task_name}")
                return CustomAction.RunResult(success=True)

            print(f"[RetryTask] 第 {attempt + 1} 次失败: {task_name}")

        # --- 全部失败 ---
        print(f"[RetryTask] 已执行 {1 + max_retry} 次均失败: {task_name}")

        if fallback:
            print(f"[RetryTask] 执行兜底任务: {fallback}")
            context.run_task(fallback)

        # 返回 success=True 让管线继续走 next（跳到下一个任务）
        return CustomAction.RunResult(success=True)


# =====================================================================
# Action 8: DisableAnchorNode —— 禁用锚点指向的节点
# =====================================================================
@AgentServer.custom_action("DisableAnchorNode")
class DisableAnchorNode(CustomAction):
    """
    通过 context.get_anchor() 解析锚点 → 节点名，
    然后对目标节点设置 enabled: false。

    锚点机制（MaaFramework v5.1+）:
      - 节点通过 "anchor": "锚点名" 设置锚点，后执行的节点会覆盖先执行的
      - context.get_anchor("锚点名") 返回当前锚点指向的节点名
      - 这是 C++ 层 MaaTypes.h 中 get_anchor 的 Python 绑定

    参数格式:
    {
        "anchor": "锚点名称"
    }

    Pipeline JSON 引用示例:
    {
        "action": "Custom",
        "custom_action": "DisableAnchorNode",
        "custom_action_param": {
            "anchor": "oldtalesanchor"
        }
    }
    """

    def run(
        self,
        context: Context,
        argv: CustomAction.RunArg,
    ) -> CustomAction.RunResult:
        # 解析必填参数 anchor
        anchor_name = parse_params(argv.custom_action_param, "anchor")["anchor"]

        # ★ 通过 MaaFramework C++ API 解析锚点 → 节点名
        node_name = context.get_anchor(anchor_name)

        if node_name is None:
            print(f"[DisableAnchorNode] 锚点 [{anchor_name}] 未设置，跳过")
            return CustomAction.RunResult(success=True)

        print(f"[DisableAnchorNode] 锚点 [{anchor_name}] → 节点 [{node_name}]，禁用它")
        context.override_pipeline({node_name: {"enabled": False}})
        return CustomAction.RunResult(success=True)


# =====================================================================
# Action 9: LoopBack —— 循环回跳指定节点
# =====================================================================
@AgentServer.custom_action("LoopBack")
class LoopBack(CustomAction):
    """
    固定次数循环闸门：流程每经过本节点一次计一次数，前 max_loops 次把流程
    回跳到锚点 `_loopback` 标记的入口节点，第 max_loops+1 次恢复自身 next 放行。

    【用途】"无脑固定刷 N 遍"的场景（如活动困难关刷满次数再走后续流程）。
    与原生 max_hit 的区别：max_hit 数"识别命中次数"、耗满后该节点被跳过属
    被动退出，适合"条件还在就继续"的条件循环；LoopBack 数"经过次数"、主动
    override_next 改路，与画面识别无关，适合固定次数循环。

    【次数语义】max_loops 是"回跳次数"而非总次数：循环体共执行 max_loops+1
    遍（初始 1 遍 + 回跳 N 遍）。想刷 2 次关卡就写 max_loops: 1。

    【跳转目标不在参数里】
    - 回跳目标 = 声明了 "anchor": "_loopback" 的节点（get_anchor 反查）；
    - 放行去向 = 本节点自己的 next（首次经过时自动保存，放行时恢复；不配
      next 则放行即掐断任务线）。
    换任务复用时只需把 anchor 挪到新入口节点，本节点一个字不用改。

    【配置三步】
    1. 循环入口节点加一行 "anchor": "_loopback"（其余不变）；
    2. 循环体末尾放本节点，配 max_loops 和放行后的 next；
    3. 循环体最后一环的 next 指向本节点，接进链。

    ── Pipeline JSON（新版嵌套格式）──
    "my_entry": {
        "anchor": "_loopback",
        "recognition": { "type": "OCR", "param": { "expected": "确认" } },
        "action": { "type": "Click" },
        "next": ["loop_body"]
    },
    "loop_check": {
        "action": {
            "type": "Custom",
            "param": {
                "custom_action": "LoopBack",
                "custom_action_param": { "max_loops": 1 }
            }
        },
        "next": ["循环结束后的节点"]
    }

    【锚点语义（官方 3.1 协议）】
    - 锚点在节点"识别命中并执行动作后"才注册（无论动作成败），没执行过就不存在；
    - 多节点可声明同名锚点，后执行的覆盖先执行的。
    因此 `_loopback` 必须只给唯一的入口节点——循环路径上的其他节点若也声明，
    会把锚点抢过去，回跳目标被悄悄换掉。

    【注意】
    - 计数器/保存的 next 是类变量，任务中途停止会残留半截状态；每次跑任务是
      新 agent 进程，实际无碍。
    - max_loops 传非数字会抛 ValueError 导致节点失败。
    - 现状（本项目）：smallevent1_hard_return / killthelord_hard_return 挂着本
      action，但没有任何 next 链引用这两个节点，且全资源无节点声明 _loopback
      ——当前不会执行；即使执行也只会打印警告空转。要启用按上面三步接线即可。
    """

    _counters: dict[str, int] = {}
    _saved_next: dict[str, list[str]] = {}

    def run(self, context: Context, argv: CustomAction.RunArg) -> CustomAction.RunResult:
        param = parse_params(argv.custom_action_param)
        max_loops = int(param.get("max_loops", 1))

        target = context.get_anchor("_loopback")
        if target is None:
            print("[LoopBack] ⚠ 入口节点缺少 'anchor: _loopback'，跳过")
            return CustomAction.RunResult(success=True)

        key = argv.node_name
        cnt = self._counters.get(key, 0) + 1
        self._counters[key] = cnt

        if cnt == 1:
            node_data = context.get_node_data(key)
            if node_data and "next" in node_data:
                # get_node_data 返回的 next 是 [{"name": "xx", ...}, ...] 格式，取 name
                raw_next = node_data["next"]
                if isinstance(raw_next, list):
                    self._saved_next[key] = [
                        n["name"] if isinstance(n, dict) else str(n)
                        for n in raw_next
                    ]
                else:
                    self._saved_next[key] = []
            else:
                self._saved_next[key] = []

        if cnt <= max_loops:
            print(f"[LoopBack] {cnt}/{max_loops} → 跳回 [{target}]")
            context.override_next(key, [target])
        else:
            original = self._saved_next.get(key, [])
            print(f"[LoopBack] {max_loops} 次完成 → 继续 next {original}")
            context.override_next(key, original)
            self._counters[key] = 0

        return CustomAction.RunResult(success=True)


# =====================================================================
# Action 10: addrecodatebase —— 日期临时字段 +1
# =====================================================================
@AgentServer.custom_action("addrecodatebase")
class AddRecoDateBase(CustomAction):
    """
    将 recodatebase 写入的日期临时字段日部分 +1（如 1-7 → 1-8）；
    唯独当前值为 1-12 时改为 -1（得 1-11）。
    字段不存在时视为默认值 "1-1"（+1 得 "1-2"）；
    格式异常（非 "月-日" 数字）时不改动。始终返回成功。无参数。

    Pipeline JSON 引用示例:
    {
        "action": "Custom",
        "custom_action": "addrecodatebase"
    }
    """

    def run(
        self,
        context: Context,
        argv: CustomAction.RunArg,
    ) -> CustomAction.RunResult:
        old = datebase_get()
        new = datebase_add()
        if new == old:
            print(f"[addrecodatebase] 字段保持 {old}（格式异常未改动）")
        else:
            print(f"[addrecodatebase] {old} → {new}")
        return CustomAction.RunResult(success=True)


# =====================================================================
# Action 11: clearrecodatebase —— 清除日期临时字段
# =====================================================================
@AgentServer.custom_action("clearrecodatebase")
class ClearRecoDateBase(CustomAction):
    """
    将 recodatebase 的日期临时字段重置为默认值 "1-1"
    （重置而非删除，字段全程存在、不留空缺）。始终返回成功。无参数。

    Pipeline JSON 引用示例:
    {
        "action": "Custom",
        "custom_action": "clearrecodatebase"
    }
    """

    def run(
        self,
        context: Context,
        argv: CustomAction.RunArg,
    ) -> CustomAction.RunResult:
        old = datebase_get()
        if datebase_clear():
            print(f"[clearrecodatebase] 临时字段 {old} 已重置为默认值 1-1")
        else:
            print("[clearrecodatebase] 临时字段已是默认值 1-1")
        return CustomAction.RunResult(success=True)


# =====================================================================
# ★ 在此线以下添加你的自定义 Action ★
# =====================================================================
# 模板参考：
#
# @AgentServer.custom_action("YourActionName")
# class YourActionName(CustomAction):
#     def run(self, context, argv) -> CustomAction.RunResult:
#         params = parse_params(argv.custom_action_param)
#         # 你的业务逻辑...
#         return CustomAction.RunResult(success=True)
#
# Pipeline JSON 中引用:
# {
#     "action": "Custom",
#     "custom_action": "YourActionName",
#     "custom_action_param": { ... }
# }


# =====================================================================
# Action 12: NextBurst —— next 候选突发扫描（挂在父节点，候选零改动）
# =====================================================================
@AgentServer.custom_action("NextBurst")
class NextBurst(CustomAction):
    """
    next 候选突发扫描：挂在"被识别节点的前一个节点"（父节点）的 action 槽位，
    候选节点完全不用改。

    框架节点生命周期是 action → 截图 → 识别 next 列表。本 action 在框架进入
    next 识别阶段之前，先对（本节点的）next 列表做一轮突发扫描：
    next1 最多连续识别 tries 次（每次重新截图），全未命中再扫 next2，以此类推；
    所有候选都试完 tries 次仍全空 = 一个循环结束。

    ── 自定义参数（custom_action_param） ──
    {
        "tries": 5,          // 可选，每个候选最多识别次数，默认 5
        "delay": 200,        // 可选，第 2 试起每次尝试前的等待毫秒，默认 200
        "nodes": ["A", "B"]  // 可选，指定扫描列表；不写则自动读取本节点自己的 next
    }

    ── 命中后的交接 ──
    某候选命中：override_next(本节点, [命中候选, ...其余候选原序])——只把命中者
    提到队首、其余候选保留不丢，然后返回成功。框架随后照常"截图 → 识别 next"，
    命中者第一个被识别、当即进入，后续链完全原生；万一确认时画面已变导致没再命中，
    框架也能继续轮巡其余候选直到 timeout → on_error。
    （副作用：override 对整个任务生效，本任务内该节点 next 顺序自此变为命中者优先。）

    ── 全空（循环结束）──
    不做任何 override 直接返回成功：交还框架对原 next 列表做原生轮巡
    （一轮一截图、每候选一次），直到本节点 timeout → on_error。
    父节点每次被执行时本组件只跑一轮突发扫描。

    ── 候选列表解析（与框架 next 语义对齐） ──
    支持字符串、"[JumpBack]名"（识别时剥前缀，交接时保留原形）、
    "[Anchor]锚点名"（经 get_anchor 解析，未设置则跳过，与框架语义一致）、
    对象形式 {"name": ..., "jump_back"/"anchor": ...}。

    ── 注意 ──
    - 候选若 disabled / max_hit 用尽，run_recognition 返回 None，按未命中处理（白扫 tries 次）。
    - 挂在已有真实 action 的节点上会顶替原 action；这种情况建议在父节点前插一个
      recognition=DirectHit + action=本组件 的中转节点。
    - 耗时 ≈ Σ tries × (delay+截图+识别)；每试前检查 tasker.stopping，停止立即返回。
    - 某试截图抛 RuntimeError（加载期不产帧等瞬态故障）按当次未命中处理、
      continue 进下一试（循环自带重拍），日志打 ⚠，不再掀桌。
    - 日志前缀 [NextBurst]。

    ── Pipeline JSON ──
    "父节点": {
        "recognition": ...,
        "action": { "type": "Custom", "param": {
            "custom_action": "NextBurst",
            "custom_action_param": { "tries": 5, "delay": 200 }
        }},
        "next": ["候选A", "候选B", "候选C"],   // 候选节点一律不动
        "timeout": 30000
    }
    """

    def run(
        self,
        context: Context,
        argv: CustomAction.RunArg,
    ) -> CustomAction.RunResult:
        params = parse_params(argv.custom_action_param)
        tries = max(1, int(params.get("tries", 5)))
        delay = max(0, int(params.get("delay", 200)))

        # ── 候选列表：nodes 参数优先，否则读本节点自己的 next ──
        nodes_param = params.get("nodes")
        if nodes_param:
            entries = list(nodes_param)
        else:
            data = context.get_node_data(argv.node_name) or {}
            entries = list(data.get("next") or [])
        if not entries:
            print("[NextBurst] 无候选节点，直接交还框架")
            return CustomAction.RunResult(success=True)

        # ── 突发扫描：next1 连试 tries 次 → next2 → ... ──
        for idx, entry in enumerate(entries):
            name = _resolve_next_entry(context, entry)
            if not name:
                print(f"[NextBurst] 跳过无法解析的候选: {entry!r}")
                continue
            for i in range(1, tries + 1):
                if context.tasker.stopping:
                    print("[NextBurst] 任务停止中，提前返回")
                    return CustomAction.RunResult(success=True)
                if i > 1 and delay > 0:
                    time.sleep(delay / 1000)
                controller = context.tasker.controller
                try:
                    controller.post_screencap().wait()
                    img = controller.cached_image
                except RuntimeError as e:
                    print(f"[NextBurst] ⚠ 第 {i}/{tries} 试截图失败: {e}，按未命中处理")
                    continue
                detail = context.run_recognition(name, img)
                if detail is not None and detail.hit and detail.box is not None:
                    # 命中：把该候选提到 next 队首（其余保留），交还框架原生进入
                    new_next = [entry] + entries[:idx] + entries[idx + 1:]
                    context.override_next(argv.node_name, new_next)
                    print(f"[NextBurst] 命中(第 {i}/{tries} 试): {name}，已提到 next 队首")
                    return CustomAction.RunResult(success=True)
            print(f"[NextBurst] {name} {tries} 试全空")

        # ── 一个循环结束（全空）：不 override，交还框架原生轮巡 ──
        print("[NextBurst] 一轮循环结束（全空），交还框架原生轮巡")
        return CustomAction.RunResult(success=True)


def _resolve_next_entry(context: Context, entry) -> str | None:
    """把 next 条目解析成可识别的节点名；解析不出（如未设置的 [Anchor]）返回 None。"""
    if isinstance(entry, str):
        if entry.startswith("[JumpBack]"):
            return entry[len("[JumpBack]"):] or None
        if entry.startswith("[Anchor]"):
            return context.get_anchor(entry[len("[Anchor]"):])
        return entry
    if isinstance(entry, dict):
        name = entry.get("name")
        if not name:
            return None
        if entry.get("anchor"):  # {"name": "锚点名", "anchor": true} 形式
            return context.get_anchor(str(name))
        return str(name)
    return None
