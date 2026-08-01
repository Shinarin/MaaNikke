"""
核心编排 —— 精简版

职责：
  1. 动态导入并注册所有 custom action / reco / sink 模块
  2. 启动 AgentServer 并阻塞等待主进程调度

运行流程：
  main.py → bootstrap.py(路径初始化) → agent_runtime.run_agent() → AgentServer 生命周期
"""

import sys
import traceback


def run_agent(project_root_dir: str, socket_id: str):
    """
    主运行函数。

    参数:
        project_root_dir: 项目根目录（resource/ 和 config/ 的父级）
        socket_id:       MAA 主进程传入的 IPC socket 标识
    """
    # ================================================================
    # 阶段1/2: 导入 MAA 核心模块 + custom 模块
    # 本模块由 main.py 以顶层模块方式导入（agent 目录已在 sys.path），
    # 直接使用绝对导入；失败时保留原始异常信息，便于定位真实原因
    # ================================================================
    try:
        from maa.agent.agent_server import AgentServer
        import custom
    except ImportError as e:
        # 模块导入失败 —— 通常是因为 maafw 未安装或 custom 目录结构错误
        print(f"[maanikke] 导入模块失败: {e}", file=sys.stderr)
        print("[maanikke] 请检查 maafw 是否安装: pip install maafw", file=sys.stderr)
        traceback.print_exc()
        sys.exit(1)

    custom.register_all()
    print("[maanikke] custom 模块注册完成")

    # ================================================================
    # 阶段3: 启动 AgentServer 生命周期
    # start_up:  连接到主进程的 IPC socket，返回 bool 表示成败
    # join:      阻塞当前线程，等待主进程下发任务并调度
    # shut_down: 主进程通知关闭后，清理资源
    # ================================================================
    try:
        print(f"[maanikke] socket_id: {socket_id}")
        if not AgentServer.start_up(socket_id):
            print("[maanikke] AgentServer.start_up() 失败！与主进程 IPC 握手未成功", file=sys.stderr)
            print("[maanikke] 可能原因: socket_id 与主进程不匹配、socket 被占用，"
                  "或已装 maafw 版本与 GUI 不兼容（建议 5.10.2）", file=sys.stderr)
            sys.exit(1)
        print("[maanikke] ===== Agent 就绪，已连接主进程 =====", flush=True)
        print("[maanikke] Agent 加载完成，已连接主进程，等待任务调度...", file=sys.stderr, flush=True)
        AgentServer.join()  # ★ 阻塞点 —— 此处等待主进程所有任务完成
        AgentServer.shut_down()
        print("[maanikke] AgentServer 已关闭")
    except Exception:
        # 运行时异常 —— 打印完整堆栈便于定位问题
        print("[maanikke] 运行过程中发生异常:", file=sys.stderr)
        traceback.print_exc()
        raise
