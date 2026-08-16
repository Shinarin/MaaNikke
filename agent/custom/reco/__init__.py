"""reco 模块注册

在这里添加你自己的 reco 模块名即可自动注册。
"""

from importlib import import_module

# ============================================================
# ★ 在此元组中添加你自己的 reco 模块名（不含 .py 后缀）
# ============================================================
RECO_MODULES = (
    "my_reco",  # ← 用户自定义 reco 文件
    "stagenum",  # ← 关卡号识别（STAGE LIST 1-N）
)


def register_all() -> None:
    for module_name in RECO_MODULES:
        import_module(f"custom.reco.{module_name}")


__all__ = ["register_all"]
