"""
============================================================
  ★ 自定义 Sink —— Agent 事件监听与状态通知 ★
============================================================

MaaFramework Event Sink 机制:
  - 引擎在每个节点开始/成功/失败时触发回调
  - GUI 可以通过"focus"元数据显示通知（需在管线 JSON 中预设）
  - Python 端无 post_focus() API，但可通过 EventSink 接收事件 + 日志输出

四种 Sink 类型:
  - TaskerEventSink     任务管理器事件（任务开始/结束等）
  - ControllerEventSink 控制器事件（截图/点击等）
  - ResourceEventSink   资源事件（加载管线等）
  - ContextEventSink    上下文事件

用法:
  1. 继承对应的 EventSink 类
  2. 实现 on_raw_notification() 方法
  3. 用 @AgentServer.xxx_sink() 装饰器注册
============================================================
"""

from maa.agent.agent_server import AgentServer
from maa.tasker import TaskerEventSink
from maa.controller import ControllerEventSink
from maa.resource import ResourceEventSink
from maa.context import ContextEventSink

import json
import time


# =====================================================================
# 通用工具：格式化事件详情
# =====================================================================

def _fmt_detail(details: dict, max_len: int = 200) -> str:
    """将详情字典压缩为单行关键信息。"""
    if not details:
        return ""
    parts = []
    for key in ("name", "task_id", "node_id", "reco_id", "action_id", "status"):
        if key in details:
            parts.append(f"{key}={details[key]}")
    # 如果有 focus 消息也显示
    focus = details.get("focus")
    if isinstance(focus, dict):
        content = focus.get("content", "")
        if content:
            parts.append(f"focus=\"{content}\"")
    result = ", ".join(parts)
    if len(result) > max_len:
        result = result[:max_len] + "..."
    return result


# =====================================================================
# Tasker Sink —— 任务级事件
# =====================================================================

@AgentServer.tasker_sink()
class AppTaskerSink(TaskerEventSink):
    """
    监听任务管理器的所有事件。
    典型消息:
      - Tasker.Starting  → Agent 开始处理任务
      - Tasker.Succeeded → 所有任务执行完毕
      - Tasker.Failed    → 任务执行失败
    """

    _start_time: float = 0.0

    def on_raw_notification(self, tasker, msg: str, details: dict):
        info = _fmt_detail(details)
        if "Starting" in msg:
            self._start_time = time.time()
            print(f"[Agent] 🚀 任务开始 | {info}")
        elif "Succeeded" in msg:
            # 未收到 Starting 时 _start_time 为 0，不打印耗时（避免天文数字）
            elapsed = f" ({time.time() - self._start_time:.1f}s)" if self._start_time else ""
            print(f"[Agent] ✅ 任务完成{elapsed} | {info}")
        elif "Failed" in msg:
            elapsed = f" ({time.time() - self._start_time:.1f}s)" if self._start_time else ""
            print(f"[Agent] ❌ 任务失败{elapsed} | {info}")
        else:
            print(f"[Tasker] {msg} | {info}")


# =====================================================================
# Controller Sink —— 控制器事件
# =====================================================================

@AgentServer.controller_sink()
class AppControllerSink(ControllerEventSink):
    """
    监听控制器事件（截图/点击/滑动等）。
    用于调试时可打开，正常运行时建议注释掉以减少刷屏。
    """

    def on_raw_notification(self, controller, msg: str, details: dict):
        # 控制器事件非常频繁（每帧截图），默认只打印异常
        if "Failed" in msg:
            info = _fmt_detail(details)
            print(f"[Ctrl] ⚠ {msg} | {info}")


# =====================================================================
# Resource Sink —— 资源加载事件
# =====================================================================

@AgentServer.resource_sink()
class AppResourceSink(ResourceEventSink):
    """
    监听资源加载事件。
    如 Agent 首次加载管线文件时触发。
    """

    def on_raw_notification(self, resource, msg: str, details: dict):
        info = _fmt_detail(details)
        if "Failed" in msg:
            print(f"[Res] ❌ {msg} | {info}")
        elif "Starting" in msg:
            print(f"[Res] 📂 {msg} | {info}")


# =====================================================================
# Context Sink —— 上下文事件（单个节点粒度）
# =====================================================================

@AgentServer.context_sink()
class AppContextSink(ContextEventSink):
    """
    监听单个管线节点的执行事件。
    典型消息:
      - PipelineNode.Starting   → 进入某节点
      - Recognition.Starting    → 开始识别
      - Action.Starting         → 开始执行动作
      - PipelineNode.Succeeded  → 节点执行成功
    """

    def on_raw_notification(self, context, msg: str, details: dict):
        # PipelineNode 级别才打印，避免每个子步骤都刷屏
        if "PipelineNode" in msg and ("Starting" in msg or "Failed" in msg):
            info = _fmt_detail(details)
            if "Failed" in msg:
                print(f"[Node] ❌ {msg} | {info}")
            else:
                node_name = details.get("name", "?")
                print(f"[Node] ▶ {node_name}")


print("[my_sink] 事件监听已注册 (Tasker/Controller/Resource/Context)")
