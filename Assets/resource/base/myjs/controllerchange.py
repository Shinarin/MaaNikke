from maa.tasker import Tasker  
from maa.toolkit import Toolkit  
from maa.resource import Resource  
from maa.controller import Win32Controller, MaaWin32ScreencapMethodEnum, MaaWin32InputMethodEnum  
  
def make_controller(hwnd) -> Win32Controller:  
    ctrl = Win32Controller(  
        hwnd=hwnd,  
        screencap_method=MaaWin32ScreencapMethodEnum.FramePool,  
        mouse_method=MaaWin32InputMethodEnum.PostMessageWithCursorPos,  
        keyboard_method=MaaWin32InputMethodEnum.PostMessageWithCursorPos,  
    )  
    ctrl.post_connection().wait()  # 必须先连接  
    return ctrl  
  
def main():  
    Toolkit.init_option("./")  
  
    # 找到所有窗口，按标题筛选  
    all_windows = Toolkit.find_desktop_windows()  
    win_a = next(w for w in all_windows if "WeGame" in w.window_name)  
    win_b = next(w for w in all_windows if "胜利女神:新的希望" in w.window_name)  
  
    # 提前为每个窗口创建并连接好 Controller  
    ctrl_a = make_controller(win_a.hwnd)  
    ctrl_b = make_controller(win_b.hwnd)  
  
    # 加载资源（两个窗口共用同一份资源）  
    resource = Resource()  
    resource.post_bundle("./resource/base").wait()  
  
    # 创建 Tasker，先绑定窗口 A  
    tasker = Tasker()  
    tasker.bind(resource, ctrl_a)  
  
    # ---- Task 1：在窗口 A 执行 ----  
    detail = tasker.post_task("wegamelogin").wait().get()  
    print(f"Task A done, status: {detail.status}")  
  
    # ---- 切换到窗口 B ----  
    tasker.bind(resource, ctrl_b)   # 只替换 controller，resource 不变  
  
    # ---- Task 2：在窗口 B 执行 ----  
    detail = tasker.post_task("startgame").wait().get()  
    print(f"Task B done, status: {detail.status}")  
  
  