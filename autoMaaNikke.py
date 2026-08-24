# -*- coding: utf-8 -*-
"""等价于 autoMaaNikke.bat：先拉起游戏，再运行 MaaNikke，直到结束。"""

import os
import sys
import time
import subprocess

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
AHK_SCRIPT = os.path.join(SCRIPT_DIR, "startnikke.ahk")
MAANIKKE_EXE = os.path.join(SCRIPT_DIR, "MaaNikke.exe")

GAME_PROCESS = "nikke.exe"
MAANIKKE_PROCESS = "MaaNikke.exe"

LOAD_WAIT = 60        # 启动后等待秒数
POLL_INTERVAL = 10    # 轮询间隔秒数


def _log(msg: str):
    print("[autoMaaNikke] " + msg, flush=True)


def _is_admin() -> bool:
    try:
        import ctypes
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def _process_running(name: str) -> bool:
    name = name.lower()
    try:
        out = subprocess.run(
            ["tasklist", "/NH"],
            capture_output=True, text=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        ).stdout
    except Exception:
        return False
    for line in out.splitlines():
        parts = line.split()
        if parts and parts[0].lower() == name:
            return True
    return False


def _start(path: str):
    _log("正在启动 " + os.path.basename(path) + " ...")
    os.startfile(path)


def _wait_game():
    while True:
        _start(AHK_SCRIPT)
        _log("等待 %d 秒加载…" % LOAD_WAIT)
        time.sleep(LOAD_WAIT)
        while True:
            time.sleep(POLL_INTERVAL)
            if _process_running(GAME_PROCESS):
                _log(GAME_PROCESS + " 正在运行")
                return
            _log(GAME_PROCESS + " 未运行，重新启动…")
            break


def _wait_maanikke():
    _start(MAANIKKE_EXE)
    _log("等待 %d 秒加载…" % LOAD_WAIT)
    time.sleep(LOAD_WAIT)
    while True:
        time.sleep(POLL_INTERVAL)
        if not _process_running(MAANIKKE_PROCESS):
            _log("MaaNikke.exe 已结束")
            return
        _log(MAANIKKE_PROCESS + " 仍在运行…")


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    _log("启动")

    if not _is_admin():
        _log("错误：需要管理员权限")
        return 1

    _wait_game()
    _wait_maanikke()
    _log("结束")
    return 0


if __name__ == "__main__":
    sys.exit(main())
