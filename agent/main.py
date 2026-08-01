"""
maanikke_agent 启动入口

用法:
    python main.py <socket_id> [socket_id=<socket_id>] [instance_id=...] [instance_name=...]

    GUI 实际会同时传位置参数和 key=value 参数（key=value 在后），
    解析规则：优先取 socket_id= 前缀的值，其次取第一个位置参数。

运行流程:
    1. 设定 CWD → 项目根目录
    2. 添加 sys.path → 确保内部模块可导入
    3. 初始化运行时路径 (config / resource / debug 目录映射)
    4. 自动检测安装 maafw==5.10.2（锁定版本，与 GUI 匹配）
    5. 调用 agent_runtime.run_agent() 启动 AgentServer
"""

import os
import sys

# =====================================================================
# 阶段0: 基础环境设定
# =====================================================================
# 确保 stdout 为 UTF-8，防止中文日志在 Windows 下乱码
sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]

# Python 版本检查：utils.params / utils.runtime_paths 等模块使用了 3.10+ 语法
# （如 str | None 联合类型注解），低版本会在 import 阶段直接崩溃，必须最先检查
if sys.version_info < (3, 10):
    print(
        f"[maanikke] ❌ 需要 Python 3.10 或更高版本，当前: {sys.version.split()[0]}",
        file=sys.stderr,
    )
    sys.exit(1)

# 获取当前文件所在目录 → 向上两级即为项目根目录
# 例如: .../agent/main.py → project_root = .../
current_file_path = os.path.abspath(__file__)
current_script_dir = os.path.dirname(current_file_path)  # .../agent/
project_root_dir = os.path.dirname(current_script_dir)   # .../           (项目根)

# 切换 CWD 到项目根目录（MAA 管线文件使用相对路径，需要 CWD 正确）
if os.getcwd() != project_root_dir:
    os.chdir(project_root_dir)
print(f"[maanikke] CWD 设定: {os.getcwd()}")

# 将 agent 包所在目录加入 sys.path（使 from bootstrap import ... 生效）
if current_script_dir not in sys.path:
    sys.path.insert(0, current_script_dir)

# =====================================================================
# 阶段1: 路径初始化
# =====================================================================
from bootstrap import configure_initial_runtime_paths

configure_initial_runtime_paths(project_root_dir)


# =====================================================================
# 阶段2: maafw 环境保障
# =====================================================================

# 与 MaaNikke GUI 实际加载的 MaaFramework 原生库版本一致
# 版本号来源于 GUI 日志: logs/log-*.log 中的 "MaaFramework 版本：v5.10.2"
_MAAFW_REQUIRED_VERSION = "5.10.2"

# pip 安装子进程硬超时（秒）：防止网络黑洞导致 pip 下载永久挂死
_PIP_INSTALL_TIMEOUT = 300


def _check_installed_version(ver: str) -> tuple[bool, str]:
    """
    判断已安装的 maafw 版本是否可直接使用（验收放宽策略）。

    依据：agent 与 GUI 间的 IPC 协议由 MaaAgentBinary 实现，其二进制自 2024-04
    起冻结未再更新，maafw 5.10.2 ~ 5.12.x 全部依赖同一版本，跨 minor 握手无碍；
    现存 custom 代码只用稳定核心 API，Python 层 API 漂移风险很低。

    返回 (是否接受, 附加提示):
      - 5.10.x              → 接受（同 minor，patch 级兼容）
      - 其他 5.x            → 接受，但附"未实测"警告
      - 4.x 及以下 / 6.x+ / 无法解析 → 不接受，需安装锁定版本
    """
    try:
        parts = tuple(int(p) for p in ver.split(".")[:3])
    except ValueError:
        return False, ""
    if len(parts) < 2 or parts[0] != 5:
        return False, ""
    if parts[1] == 10:
        note = "（同 minor，patch 级兼容）" if ver != _MAAFW_REQUIRED_VERSION else ""
        return True, note
    return True, "（⚠ 非实测版本，如 Agent 行为异常请安装 5.10.2）"


def _ensure_maafw() -> bool:
    """
    确保当前 Python 环境中已安装可用版本的 maafw。
    验收放宽: 已装 5.x 即接受（不重装/不降级，避免破坏共享环境中的其他 MAA 项目）；
    安装锁定: 未安装或版本不兼容时安装 _MAAFW_REQUIRED_VERSION。
    支持: pip 可用性检查 / 直连与清华镜像回退 / --user 权限兜底 / 安装后版本校验。
    返回 True 表示就绪，False 表示所有尝试均失败。
    """
    import subprocess

    python_exe = sys.executable
    print(f"[maanikke] Python 路径: {python_exe}")

    # ── 1. 快速检查：是否已安装可用版本（验收放宽，见 _check_installed_version） ──
    try:
        import maa  # noqa: F401  # 先确认模块本身可导入
    except ImportError:
        print("[maanikke] maafw 未安装")
    else:
        # 从包元数据读取版本（不依赖模块是否暴露 __version__ 属性）
        from importlib.metadata import version, PackageNotFoundError
        try:
            installed_ver = version("maafw")
        except PackageNotFoundError:
            installed_ver = ""
        acceptable, note = _check_installed_version(installed_ver)
        if acceptable:
            print(f"[maanikke] maafw {installed_ver} 已就绪{note}")
            return True
        print(f"[maanikke] maafw 版本 {installed_ver or '未知'} 不在兼容范围 (5.x)，需要安装 {_MAAFW_REQUIRED_VERSION}")

    # ── 2. 确认 pip 可用 ──
    try:
        subprocess.run(
            [python_exe, "-m", "pip", "--version"],
            capture_output=True, check=True, timeout=30,
        )
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        print(
            "[maanikke] ❌ pip 未安装！",
            "请先运行: python -m ensurepip",
            "或重新安装 Python 并勾选 'Add Python to PATH'",
            sep="\n", file=sys.stderr,
        )
        return False

    # ── 3. 安装（直连 → 清华源回退 → --user 兜底） ──
    base_cmd = [
        python_exe, "-m", "pip", "install",
        f"maafw=={_MAAFW_REQUIRED_VERSION}",
    ]

    strategies = [
        ("直连 PyPI", base_cmd),
        ("清华镜像", base_cmd + ["-i", "https://pypi.tuna.tsinghua.edu.cn/simple"]),
        ("直连 + --user", base_cmd + ["--user"]),
        ("清华镜像 + --user", base_cmd + ["--user", "-i", "https://pypi.tuna.tsinghua.edu.cn/simple"]),
    ]

    for label, cmd in strategies:
        print(f"[maanikke] 尝试安装 ({label})...")
        try:
            # 硬超时兜底：网络黑洞会让 pip 下载永久挂死，必须能超时退出
            subprocess.check_call(cmd, timeout=_PIP_INSTALL_TIMEOUT)
        except subprocess.TimeoutExpired:
            print(f"[maanikke] ({label}) 超过 {_PIP_INSTALL_TIMEOUT}s 未完成，判定网络不通，尝试下一个策略...")
            continue
        except subprocess.CalledProcessError:
            print(f"[maanikke] ({label}) 失败，尝试下一个策略...")
            continue

        # 安装命令成功 → 子进程验证
        try:
            result = subprocess.run(
                [python_exe, "-c",
                 "from importlib.metadata import version; print(version('maafw'))"],
                capture_output=True, text=True, check=True, timeout=30,
            )
            if result.stdout.strip() == _MAAFW_REQUIRED_VERSION:
                # 若本进程此前已导入过旧版 maa，清除模块缓存，
                # 确保后续 from maa.agent... 加载的是新装版本
                import importlib
                importlib.invalidate_caches()
                for mod in [k for k in list(sys.modules) if k == "maa" or k.startswith("maa.")]:
                    del sys.modules[mod]
                print(f"[maanikke] ✅ maafw {_MAAFW_REQUIRED_VERSION} 安装成功")
                return True
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            pass
        print(f"[maanikke] ({label}) 安装命令成功但版本校验失败，可能是 VC 运行时或杀软问题")

    # ── 4. 所有策略失败 ──
    print(
        f"[maanikke] ❌ 所有安装策略均失败",
        f"[maanikke] 请手动执行: {python_exe} -m pip install maafw=={_MAAFW_REQUIRED_VERSION}",
        f"[maanikke] 如仍有问题请检查: 网络/VPN/杀毒软件/VC++ 运行时",
        sep="\n", file=sys.stderr,
    )
    return False


# =====================================================================
# 阶段3: custom 模块外部依赖预检
# =====================================================================
# custom action / reco 可能依赖第三方包（如 Pillow），
# 必须在 AgentServer.start_up() 之前全部就绪，否则任务中途才会报错。

_CUSTOM_DEPS = {
    "Pillow": {
        "import_name": "PIL",
        "pip_name": "Pillow",
        "used_by": "RotatedOCR（旋转文字识别）",
    },
    # 后续如有新依赖在此追加，格式相同
    # "opencv-python": {
    #     "import_name": "cv2",
    #     "pip_name": "opencv-python",
    #     "used_by": "XXX",
    # },
}


def _ensure_custom_deps() -> bool:
    """
    预检 custom 模块所需的所有第三方包，缺失则自动安装。
    返回 True 表示全部就绪。
    """
    import subprocess

    python_exe = sys.executable
    all_ok = True

    for display_name, info in _CUSTOM_DEPS.items():
        import_name = info["import_name"]
        pip_name = info["pip_name"]
        used_by = info["used_by"]

        # ── 快速检查：模块是否可导入 ──
        try:
            __import__(import_name)
            print(f"[maanikke] ✓ {display_name} 已就绪 ({used_by})")
            continue
        except ImportError:
            print(f"[maanikke] ⚠ {display_name} 未安装 ({used_by})，尝试自动安装...")

        # ── 安装（直连 → 清华镜像回退） ──
        strategies = [
            ("直连 PyPI", [python_exe, "-m", "pip", "install", pip_name]),
            ("清华镜像", [python_exe, "-m", "pip", "install", pip_name,
                          "-i", "https://pypi.tuna.tsinghua.edu.cn/simple"]),
        ]
        installed = False
        for label, cmd in strategies:
            print(f"[maanikke]   尝试 ({label})...")
            try:
                subprocess.check_call(cmd, timeout=_PIP_INSTALL_TIMEOUT)
            except subprocess.TimeoutExpired:
                print(f"[maanikke]   ({label}) 超过 {_PIP_INSTALL_TIMEOUT}s 未完成")
                continue
            except subprocess.CalledProcessError:
                print(f"[maanikke]   ({label}) 失败")
                continue
            # 验证（先刷新导入缓存，否则同进程内可能看不到刚装的包）
            import importlib
            importlib.invalidate_caches()
            try:
                __import__(import_name)
                print(f"[maanikke] ✓ {display_name} 安装成功 ({label})")
                installed = True
                break
            except ImportError:
                print(f"[maanikke]   ({label}) 安装命令完成但导入失败")

        if not installed:
            print(
                f"[maanikke] ❌ {display_name} 安装失败",
                f"[maanikke]   用途: {used_by}",
                f"[maanikke]   手动安装: {python_exe} -m pip install {pip_name}",
                sep="\n", file=sys.stderr,
            )
            all_ok = False

    return all_ok


# =====================================================================
# 阶段4: 主函数
# =====================================================================


def main():
    # --- 自动安装 maafw（多策略回退 + 版本校验） ---
    if not _ensure_maafw():
        print("[maanikke] maafw 环境未就绪，Agent 无法启动", file=sys.stderr)
        sys.exit(1)

    # --- 预检 custom 模块外部依赖（Pillow 等） ---
    if not _ensure_custom_deps():
        print("[maanikke] custom 模块依赖未就绪，Agent 无法启动", file=sys.stderr)
        sys.exit(1)

    # --- 参数校验与诊断 ---
    print(f"[maanikke] sys.argv = {sys.argv}", flush=True)

    # --- 从命令行获取 socket_id（MAA 主进程传入的 IPC 标识） ---
    # GUI 实际传参格式:
    #   python -u main.py <id> socket_id=<id> instance_id=default instance_name=配置 1
    # 不能用 sys.argv[-1]（会取到 instance_name=...）：
    # 优先取 socket_id= 前缀的值，其次取第一个位置参数（兼容旧调用方式）。
    socket_id = ""
    for arg in sys.argv[1:]:
        if arg.startswith("socket_id="):
            socket_id = arg.split("=", 1)[1]
            break
    if not socket_id and len(sys.argv) >= 2:
        socket_id = sys.argv[1]
    if not socket_id:
        print("[maanikke] 用法: python main.py <socket_id>", file=sys.stderr)
        sys.exit(1)
    if "=" in socket_id:
        print(f"[maanikke] ⚠ socket_id 格式可疑（含 '='），可能解析错误: {socket_id!r}",
              file=sys.stderr)
    print(f"[maanikke] 解析 socket_id = {socket_id!r}", flush=True)

    # --- 启动 agent 运行时 ---
    from agent_runtime import run_agent
    run_agent(project_root_dir=project_root_dir, socket_id=socket_id)


if __name__ == "__main__":
    main()
