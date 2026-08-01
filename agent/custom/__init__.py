"""custom 包 —— 统一注册 action / reco / sink"""

from . import action, reco, sink


def register_all() -> None:
    action.register_all()
    reco.register_all()
    sink.register_all()


__all__ = ["register_all"]
