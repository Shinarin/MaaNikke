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

import datetime


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
    按顺序批量执行子任务。

    参数格式:
    {
        "sub": ["任务名1", "任务名2"],   # 子任务名称列表
        "continue": false,               # 可选，任一失败后是否继续后续，默认 false
        "strict": true                   # 可选，任一失败时是否视为整体失败，默认 true
    }

    Pipeline JSON 引用示例:
    {
        "action": "Custom",
        "custom_action": "SubTask",
        "custom_action_param": {
            "sub": ["TaskA", "TaskB"],
            "continue": false,
            "strict": true
        }
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
            print(f"[SubTask] 参数解析失败: {e}")
            return CustomAction.RunResult(success=False)

        sub = param.get("sub", None)
        if not isinstance(sub, list) or not sub:
            print("[SubTask] 缺少有效的 sub 任务列表")
            return CustomAction.RunResult(success=False)

        # 关键决策参数：控制失败行为
        continue_on_failure = bool(param.get("continue", False))
        strict = bool(param.get("strict", True))
        has_sub_failure = False

        for index, task_name in enumerate(sub):
            if not isinstance(task_name, str) or not task_name:
                print(f"[SubTask] 无效任务名 sub[{index}]: {task_name!r}")
                has_sub_failure = True
                if not continue_on_failure:
                    break  # 不继续则终止循环
                continue

            # 执行子任务
            task_detail = context.run_task(task_name)
            if task_detail and task_detail.status.failed:
                print(f"[SubTask] 子任务失败: index={index}, task={task_name}")
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
    循环回跳：max_loops 次内跳回入口，耗尽后继续 next。

    【唯一配置】入口节点加一行 `"anchor": "_loopback"`
    其他什么都不用写。

    ── Pipeline JSON ──
    "my_entry": {
        "anchor": "_loopback",
        "recognition": "OCR",
        "expected": "确认",
        "action": "Click",
        "next": ["loop_check"]
    },
    "loop_check": {
        "action": "Custom",
        "custom_action": "LoopBack",
        "custom_action_param": { "max_loops": 3 },
        "next": ["下一个任务"]
    }
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
