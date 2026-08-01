; ========== Nikke国服启动脚本（含重试验证 + 启动器重启）==========
#Requires AutoHotkey v2.0

; ===== 配置区 =====
LAUNCHER_TITLE        := "WeGame"
LAUNCHER_PROCESS      := "browser.exe"
GAME_PROCESS          := "nikke.exe"
CLICK_X               := 1740
CLICK_Y               := 1060
MAX_RETRIES           := 3          ; 每次启动器内点击重试次数
WAIT_TIME             := 15000      ; 每次等待毫秒数
MAX_LAUNCHER_RETRIES  := 2          ; 启动器整体重启次数
CACHE_FILE           := A_ScriptDir "\launcher_cache.txt"

; ----- 缓存读写 -----
ReadCache() {
    if !FileExist(CACHE_FILE)
        return ""
    path := FileRead(CACHE_FILE, "UTF-8")
    path := Trim(path, " `r`n`t")
    if (path != "" && FileExist(path))
        return path
    ; 缓存文件指向的路径已失效，删除缓存
    try FileDelete(CACHE_FILE)
    return ""
}

WriteCache(path) {
    try FileDelete(CACHE_FILE)
    FileAppend(path, CACHE_FILE, "UTF-8")
}

; ----- 自动查找启动器路径 -----
FindLauncher() {
    ; ★ 优先读缓存（秒开）
    cached := ReadCache()
    if (cached != "")
        return cached

    ; 方法1：nikke.exe 正在运行 → 直接从进程拿路径，反查 launcher
    if ProcessExist("nikke.exe") {
        nikkePath := ProcessGetPath("nikke.exe")
        SplitPath(nikkePath, , &gameDir)
        launcher := gameDir "\WeGameLauncher\launcher.exe"
        if FileExist(launcher) {
            WriteCache(launcher)
            return launcher
        }
    }

    ; 方法2：遍历所有本地硬盘，搜含关键字的文件夹，再在内搜 nikke.exe
    driveStr := DriveGetList("Fixed")
    searchRoots := []
    Loop Parse, driveStr {
        if RegExMatch(A_LoopField, "^[A-Za-z]$")
            searchRoots.Push(A_LoopField ":\")
    }
    keywords := ["nikke", "NIKKE", "胜利女神", "Nikke"]
    for root in searchRoots {
        if !DirExist(root)
            continue
        ; 第一层：只遍历一级子目录，用关键字过滤
        Loop Files, root "*", "D" {
            match := false
            for kw in keywords {
                if InStr(A_LoopFileName, kw) {
                    match := true
                    break
                }
            }
            if !match
                continue
            ; 第二层：在匹配的目录内递归搜 nikke.exe
            Loop Files, A_LoopFilePath "\*.exe", "FR" {
                if (A_LoopFileName = "nikke.exe") {
                    launcher := A_LoopFileDir "\WeGameLauncher\launcher.exe"
                    if FileExist(launcher) {
                        WriteCache(launcher)
                        return launcher
                    }
                }
            }
        }
    }

    ; ★ 方法3（兜底）：弹窗提示，确定=开始等待，取消/关闭=退出
    result := MsgBox(
        "未找到 Nikke 启动器路径。`n`n"
        "请在 WeGame 中【手动启动一次 Nikke 游戏】后，`n"
        "点击「确定」开始自动检测。`n`n"
        "点击「取消」或关闭窗口则退出脚本。"
    , "Nikke 启动脚本", "OC T30")
    if (result != "OK") {
        ExitApp()
    }

    ShowTray("等待 nikke.exe 启动... (5分钟超时)", 5)
    startTime := A_TickCount
    Loop {
        if ProcessExist("nikke.exe") {
            nikkePath := ProcessGetPath("nikke.exe")
            SplitPath(nikkePath, , &gameDir)
            launcher := gameDir "\WeGameLauncher\launcher.exe"
            if FileExist(launcher) {
                WriteCache(launcher)
                ShowTray("已检测到游戏路径并保存！", 3)
                return launcher
            }
        }
        if (A_TickCount - startTime > 300000) {   ; 5 分钟超时
            ShowTray("超时未检测到 nikke.exe，退出脚本", 5, true)
            ExitApp()
        }
        Sleep(2000)
    }
}

LAUNCHER_PATH := FindLauncher()
if LAUNCHER_PATH = "" {
    MsgBox("未找到 Nikke 启动器！`n请确认游戏已安装，或手动修改脚本中的 fallback 路径。")
    ExitApp()
}
; ======================================

if !IsSet(LAUNCHER_PROCESS) || LAUNCHER_PROCESS = ""
    SplitPath(LAUNCHER_PATH, &LAUNCHER_PROCESS)

; ----- 托盘通知 -----
; isError=true → 红色错误图标；isError=false → 蓝色信息图标（注：TrayTip 仅接受超时秒数，图标由系统决定）
ShowTray(msg, timeout := 3, isError := false) {
    TrayTip(msg, "Nikke 启动脚本", timeout)
}

; ----- 激活或重启启动器 -----
ActivateOrRestart() {
    global LAUNCHER_PATH, LAUNCHER_TITLE, LAUNCHER_PROCESS
    prevHidden := A_DetectHiddenWindows
    A_DetectHiddenWindows := true
    if WinExist(LAUNCHER_TITLE) {
        WinShow(LAUNCHER_TITLE)
        WinActivate(LAUNCHER_TITLE)
        if WinWaitActive(LAUNCHER_TITLE, , 5) {
            A_DetectHiddenWindows := prevHidden
            return true
        }
    }
    A_DetectHiddenWindows := prevHidden

    if ProcessExist(LAUNCHER_PROCESS) {
        ShowTray("启动器进程存在但窗口无法激活，尝试重启...", 3, true)
        ProcessClose(LAUNCHER_PROCESS)
        Sleep(1500)
    }

    Run(LAUNCHER_PATH)
    if WinWait(LAUNCHER_TITLE, , 15) {
        WinActivate(LAUNCHER_TITLE)
        return true
    }
    return false
}

; ===== ★ 主流程（外层：启动器重启循环） =====
launcherAttempt := 0
gameLaunched    := false

Loop MAX_LAUNCHER_RETRIES {
    launcherAttempt++

    ; --- 非首次尝试：先杀掉旧启动器进程 ---
    if (launcherAttempt > 1) {
        ShowTray("关闭启动器，准备第 " launcherAttempt " 轮尝试...", 3)
        if ProcessExist(LAUNCHER_PROCESS)
            ProcessClose(LAUNCHER_PROCESS)
        Sleep(3000)
    }

    ; --- 启动启动器 ---
    Run(LAUNCHER_PATH)

    if !WinWait(LAUNCHER_TITLE, , 30) {
        if ProcessExist(LAUNCHER_PROCESS) {
            ShowTray("启动器已在后台，尝试激活窗口...", 3)
            prevHidden := A_DetectHiddenWindows
            A_DetectHiddenWindows := true
            WinShow(LAUNCHER_TITLE)
            WinActivate(LAUNCHER_TITLE)
            if !WinWait(LAUNCHER_TITLE, , 10) {
                A_DetectHiddenWindows := prevHidden
                if (launcherAttempt < MAX_LAUNCHER_RETRIES) {
                    ShowTray("启动器窗口异常，准备重试... (" launcherAttempt "/" MAX_LAUNCHER_RETRIES ")", 5, true)
                    continue
                }
                ShowTray("无法激活启动器窗口，退出脚本", 5, true)
                ToolTip()
                ExitApp()
            }
            A_DetectHiddenWindows := prevHidden
        } else {
            if (launcherAttempt < MAX_LAUNCHER_RETRIES) {
                ShowTray("启动器未能启动，准备重试... (" launcherAttempt "/" MAX_LAUNCHER_RETRIES ")", 5, true)
                continue
            }
            ShowTray("启动器未能启动，请检查路径", 5, true)
            ToolTip()
            ExitApp()
        }
    }

    WinMove(0, 0, , , LAUNCHER_TITLE)
    Sleep(3000)

    ; --- 内层：点击开始游戏重试循环 ---
    retryCount := 0

    Loop MAX_RETRIES {
        retryCount++

        if !WinExist(LAUNCHER_TITLE) {
            if !ActivateOrRestart() {
                ShowTray("无法恢复启动器窗口，退出内层重试", 5, true)
                ToolTip()
                break
            }
            WinMove(0, 0, , , LAUNCHER_TITLE)
            Sleep(3000)
        }

        WinActivate(LAUNCHER_TITLE)
        Sleep(500)

        ToolTip("第 " retryCount " 次点击... (启动器第 " launcherAttempt " 轮)")
        SetTimer(() => ToolTip(), -2000)
        Click(CLICK_X, CLICK_Y)
        Sleep(1000)

        startTime := A_TickCount
        Loop {
            if ProcessExist(GAME_PROCESS) {
                gameLaunched := true
                ToolTip()
                ShowTray("Nikke 启动成功！(第 " launcherAttempt " 轮第 " retryCount " 次)", 3)
                break 3
            }
            if WinExist("错误") || WinExist("更新失败") || WinExist("网络异常") {
                ToolTip()
                ShowTray("启动器弹出错误窗口，请手动处理", 5, true)
                ExitApp()
            }
            if (A_TickCount - startTime > WAIT_TIME) {
                ToolTip()
                break
            }
            Sleep(1000)
            ToolTip("等待 Nikke 启动中... (第 " retryCount "/" MAX_RETRIES " 次)")
        }
        ToolTip()
    }

    ; ★ 本轮所有点击重试都失败 → 继续外层循环，重启启动器
    if (launcherAttempt < MAX_LAUNCHER_RETRIES) {
        ShowTray("本轮未成功启动，重启启动器... (" launcherAttempt "/" MAX_LAUNCHER_RETRIES ")", 5)
    }
}

; ★ 所有轮次都失败
if !gameLaunched {
    ShowTray("经过 " MAX_LAUNCHER_RETRIES " 轮尝试，Nikke 未能启动", 5, true)
}
ExitApp()