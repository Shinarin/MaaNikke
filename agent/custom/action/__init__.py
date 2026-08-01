"""action 模块注册

在这里添加你自己的 action 模块名即可自动注册。
"""

from importlib import import_module

# ============================================================
# ★ 在此元组中添加你自己的 action 模块名（不含 .py 后缀）
# 例如你新建了 custom/action/foo.py 和 bar.py，就改成：
#   ACTION_MODULES = ("my_actions", "foo", "bar")
# ============================================================
ACTION_MODULES = (
    "my_actions",  # ← 用户自定义 action 文件
)


def register_all() -> None:
    for module_name in ACTION_MODULES:
        import_module(f"custom.action.{module_name}")


__all__ = ["register_all"]
