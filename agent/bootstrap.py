"""
环境初始化 —— 精简版

职责:
  - 配置运行时路径映射（project_root / work_root → config / resource / debug 目录）
  - 导出 get_runtime_paths() 供其他模块获取路径

不包含（与原始 agent 的区别）:
  - 无 venv 虚拟环境管理
  - 无 logger 日志系统
  - 无热更新 / 版本检查
  - 无 dependency 自动安装（maa 安装已移至 main.py）
"""

from utils.runtime_paths import configure_runtime_paths, get_runtime_paths


def configure_initial_runtime_paths(project_root_dir: str):
    """
    首次运行时配置路径映射。

    project_root: 项目根目录（interface.json 所在目录）
    work_root:    工作根目录（默认与 project_root 相同，即 resource/ config/ 的父级）
    """
    return configure_runtime_paths(
        project_root=project_root_dir,
        work_root=project_root_dir,
    )


__all__ = ["configure_initial_runtime_paths", "get_runtime_paths"]
