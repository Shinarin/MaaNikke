"""sink 模块注册

在这里添加你自己的 sink 模块名即可自动注册。
"""

from importlib import import_module

# ============================================================
# ★ 在此元组中添加你自己的 sink 模块名（不含 .py 后缀）
# ============================================================
SINK_MODULES = (
    "my_sink",  # ← 用户自定义 sink 文件
)


def register_all() -> None:
    for module_name in SINK_MODULES:
        import_module(f"custom.sink.{module_name}")


__all__ = ["register_all"]
