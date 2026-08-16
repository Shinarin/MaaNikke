; ========== Nikke国服启动脚本（含重试验证 + 启动器重启）==========
#Requires AutoHotkey v2.0

; ===================== 脚本工作流概览 =====================
; 0. nikke.exe 已在运行 → 仅补齐 launcher_cache.txt 路径缓存后退出（不碰启动器）
; 1. FindLauncher() 定位启动器路径：缓存 → 进程反查 → 全盘搜索 → 弹窗人工兜底
; 2. 外层循环(最多 MAX_LAUNCHER_RETRIES 轮)：启动 launcher.exe → 等窗口出现
; 3. 内层循环(最多 MAX_RETRIES 次)：ForceLauncherWindow() 固定窗口 → 按比例点击"启动"
;    → 等待 nikke.exe 出现；失败则下一轮外层重启启动器
;
; ===================== 历次踩坑记录（改动前必读）=====================
; [坑1] v2 的 Click/鼠标坐标默认是 Client（相对"当前活动窗口"客户区），v1 才是 Screen。
;       旧版写死的 Click(1740,1060) 在 v2 下实际点在活动窗口客户区偏移处，
;       1080p 下必然落到窗口外。本脚本已显式 CoordMode("Mouse","Screen") + 比例定位根治。
; [坑2] v2 TrayTip 第三参数是图标选项位掩码（1信息蓝/2警告黄/3错误红/16静音），
;       不是超时秒数！误传 timeout=3 会让所有提示都挂红色错误图标（ShowTray 已修正）。
; [坑3] WeGame 界面加载完成后会自行恢复记忆的窗口位置/尺寸，覆盖 WinMove。
;       故 ForceLauncherWindow 用"固定+连续两次采样一致"的稳定校验，否则第一次点击必落空。
; [坑4] WeGame 最小窗口 1600x900（实测：请求更小会被强制拉回），故 LAUNCHER_W/H 固定此值。
; [坑5] "启动"按钮中心 ≈ 窗口宽85%×高93%（1600x900 截图实测，右下角固定边距布局），
;       与旧坐标 1740/2048≈0.85 反推值吻合，证明是相对布局，比例定位跨分辨率成立。
; [坑6] WinExist("WeGame") 标题子串匹配会误匹配文件管理器（打开 WeGameLauncher 文件夹时），
;       已改用 LAUNCHER_WIN（标题+ahk_exe browser.exe 双重锁定）。
; [坑7] v2 WinMove 不能移动最小化窗口，且对受限窗口会"报告成功但没动"——必须先还原再校验。

; ===== 配置区 =====
LAUNCHER_TITLE        := "WeGame"
LAUNCHER_PROCESS      := "browser.exe"   ; WeGame 窗口的宿主进程：CEF 框架进程
                                         ; （实测位于 F:\Program Files\WeGame\QBBlinkTrial\browser.exe），
                                         ; 不是游戏专用启动器 launcher.exe，二者勿混淆
GAME_PROCESS          := "nikke.exe"     ; 游戏客户端进程名（ProcessExist 等值匹配，与窗口标题无关）
LAUNCHER_W            := 1600        ; 固定窗口尺寸（见坑4：WeGame 最小 1600x900，更小会被强制拉回）
LAUNCHER_H            := 900
BTN_RATIO_X           := 0.85        ; "启动"按钮中心相对窗口宽/高的比例（见坑5；布局改版时只需调这两个值）
BTN_RATIO_Y           := 0.93
MAX_RETRIES           := 3          ; 每次启动器内点击重试次数
WAIT_TIME             := 15000      ; 每次等待毫秒数
MAX_LAUNCHER_RETRIES  := 2          ; 启动器整体重启次数
CACHE_FILE           := A_ScriptDir "\launcher_cache.txt"

; 点击使用屏幕绝对坐标（由 ForceLauncherWindow 按窗口矩形+比例算出）
; ★ 必须显式设置：v2 默认是 Client（相对活动窗口客户区），不设这行点击基准就是错的（见坑1）
CoordMode("Mouse", "Screen")

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
    ; 注意：关键词 InStr 包含匹配只用于筛选候选目录（允许误中，只影响搜索范围），
    ;       最终确认是 A_LoopFileName = "nikke.exe" 等值匹配，不会误认其他程序
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

    ShowTray("等待 nikke.exe 启动... (5分钟超时)")
    startTime := A_TickCount
    Loop {
        if ProcessExist("nikke.exe") {
            nikkePath := ProcessGetPath("nikke.exe")
            SplitPath(nikkePath, , &gameDir)
            launcher := gameDir "\WeGameLauncher\launcher.exe"
            if FileExist(launcher) {
                WriteCache(launcher)
                ShowTray("已检测到游戏路径并保存！")
                return launcher
            }
        }
        if (A_TickCount - startTime > 300000) {   ; 5 分钟超时
            ShowTray("超时未检测到 nikke.exe，退出脚本", true)
            ExitApp()
        }
        Sleep(2000)
    }
}

; ===== 游戏已在运行：仅确保路径缓存存在，不执行启动流程 =====
; 场景：游戏已被其他方式启动（手动/MaaNikke 在跑），无需再点"启动"，
; 只顺手补齐 launcher_cache.txt 便于下次快速定位启动器。
; ★ 本分支必须放在 FindLauncher() 之前：否则缓存无效时会触发全盘搜索甚至弹窗，
;   违背"游戏在跑时静默退出"的约束
if ProcessExist(GAME_PROCESS) {
    if (ReadCache() = "") {
        try {
            nikkePath := ProcessGetPath(GAME_PROCESS)
            SplitPath(nikkePath, , &gameDir)
            launcher := gameDir "\WeGameLauncher\launcher.exe"
            if FileExist(launcher) {
                WriteCache(launcher)
                ShowTray("Nikke 已在运行，已保存启动器路径缓存")
            } else {
                ShowTray("Nikke 已在运行，但未找到启动器路径，未保存缓存")
            }
        } catch {
            ShowTray("Nikke 已在运行，但读取进程路径失败，未保存缓存")
        }
    }
    ExitApp()
}

LAUNCHER_PATH := FindLauncher()
if LAUNCHER_PATH = "" {
    MsgBox("未找到 Nikke 启动器！`n请确认游戏已安装，或手动修改脚本中的 fallback 路径。")
    ExitApp()
}
; ======================================

if !IsSet(LAUNCHER_PROCESS) || LAUNCHER_PROCESS = ""
    SplitPath(LAUNCHER_PATH, &LAUNCHER_PROCESS)

; 窗口匹配条件：标题子串 + 进程名双重锁定
; 防止文件管理器等标题包含 "WeGame" 的窗口（如打开 WeGameLauncher 文件夹）被误当作启动器
LAUNCHER_WIN := LAUNCHER_TITLE " ahk_exe " LAUNCHER_PROCESS

; ----- 托盘通知 -----
; v2 TrayTip 第三参数是图标选项（1=信息蓝 2=警告黄 3=错误红 16=静音），不是超时秒数！
; 约定：自动恢复/重试中的一般提示用 isError=false（蓝色）；
;       仅最终失败、需要人工介入时用 isError=true（红色）
ShowTray(msg, isError := false) {
    TrayTip(msg, "Nikke 启动脚本", (isError ? 3 : 1) + 16)
}

; ----- 固定启动器窗口并计算"启动"按钮点击点 -----
; 流程：还原(若最小化) → 置顶 → 激活 → 反复"固定+校验"直到位置尺寸稳定 → 按比例算点击点
; 返回 {x, y}（屏幕坐标）；窗口不存在返回 ""
; 注意：WeGame 界面加载完成后会自行恢复记忆的窗口位置/尺寸，会覆盖 WinMove，
;       因此固定后必须连续两次采样一致才视为稳定，否则第一次点击必然落空
; 比例定位对任意分辨率/DPI 缩放免疫（按 WinGetPos 实际尺寸动态计算）
ForceLauncherWindow() {
    global LAUNCHER_WIN, LAUNCHER_W, LAUNCHER_H, BTN_RATIO_X, BTN_RATIO_Y
    hwnd := WinExist(LAUNCHER_WIN)
    if !hwnd
        return ""
    if (WinGetMinMax(hwnd) = -1) {   ; 最小化窗口 WinMove 无效，必须先还原
        WinRestore(hwnd)
        Sleep(500)
    }
    WinSetAlwaysOnTop(1, hwnd)       ; 置顶保证点击时按钮在最上层，不依赖激活成功
    WinActivate(hwnd)
    WinWaitActive(hwnd, , 3)         ; 置顶已兜底，激活失败不阻塞

    ; 固定 + 稳定校验：每轮先 WinMove 抓回窗口，连续两次采样一致才算稳定
    prevX := -1, prevY := -1, prevW := -1, prevH := -1
    stable := false
    Loop 7 {
        WinMove(0, 0, LAUNCHER_W, LAUNCHER_H, hwnd)
        Sleep(700)
        WinGetPos(&X, &Y, &W, &H, hwnd)
        if (X = 0 && Y = 0 && W = LAUNCHER_W && H = LAUNCHER_H
            && X = prevX && Y = prevY && W = prevW && H = prevH) {
            stable := true
            break
        }
        prevX := X, prevY := Y, prevW := W, prevH := H
    }
    if !stable
        ShowTray("窗口未稳定在左上角（当前 " X "," Y " " W "x" H "），按实际位置定位")

    return {x: Round(X + W * BTN_RATIO_X), y: Round(Y + H * BTN_RATIO_Y)}
}

; ----- 激活或重启启动器 -----
; 仅在"窗口不存在"时被内层循环调用。注意既有行为：激活失败会直接 ProcessClose 杀进程重启，
; 属激进兜底（一次临时激活失败也会重启启动器）；与外层 MAX_LAUNCHER_RETRIES 轮联动
ActivateOrRestart() {
    global LAUNCHER_PATH, LAUNCHER_WIN, LAUNCHER_PROCESS
    prevHidden := A_DetectHiddenWindows
    A_DetectHiddenWindows := true
    if WinExist(LAUNCHER_WIN) {
        WinShow(LAUNCHER_WIN)
        WinActivate(LAUNCHER_WIN)
        if WinWaitActive(LAUNCHER_WIN, , 5) {
            A_DetectHiddenWindows := prevHidden
            return true
        }
    }
    A_DetectHiddenWindows := prevHidden

    if ProcessExist(LAUNCHER_PROCESS) {
        ShowTray("启动器进程存在但窗口无法激活，尝试重启...")
        ProcessClose(LAUNCHER_PROCESS)
        Sleep(1500)
    }

    Run(LAUNCHER_PATH)
    if WinWait(LAUNCHER_WIN, , 15) {
        WinActivate(LAUNCHER_WIN)
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
        ShowTray("关闭启动器，准备第 " launcherAttempt " 轮尝试...")
        if ProcessExist(LAUNCHER_PROCESS)
            ProcessClose(LAUNCHER_PROCESS)
        Sleep(3000)
    }

    ; --- 启动启动器 ---
    Run(LAUNCHER_PATH)

    if !WinWait(LAUNCHER_WIN, , 30) {
        if ProcessExist(LAUNCHER_PROCESS) {
            ShowTray("启动器已在后台，尝试激活窗口...")
            prevHidden := A_DetectHiddenWindows
            A_DetectHiddenWindows := true
            WinShow(LAUNCHER_WIN)
            WinActivate(LAUNCHER_WIN)
            if !WinWait(LAUNCHER_WIN, , 10) {
                A_DetectHiddenWindows := prevHidden
                if (launcherAttempt < MAX_LAUNCHER_RETRIES) {
                    ShowTray("启动器窗口异常，准备重试... (" launcherAttempt "/" MAX_LAUNCHER_RETRIES ")")
                    continue
                }
                ShowTray("无法激活启动器窗口，退出脚本", true)
                ToolTip()
                ExitApp()
            }
            A_DetectHiddenWindows := prevHidden
        } else {
            if (launcherAttempt < MAX_LAUNCHER_RETRIES) {
                ShowTray("启动器未能启动，准备重试... (" launcherAttempt "/" MAX_LAUNCHER_RETRIES ")")
                continue
            }
            ShowTray("启动器未能启动，请检查路径", true)
            ToolTip()
            ExitApp()
        }
    }

    Sleep(3000)     ; 等待界面加载（公告/更新检查等）

    ; --- 内层：点击开始游戏重试循环 ---
    retryCount := 0

    Loop MAX_RETRIES {
        retryCount++

        if !WinExist(LAUNCHER_WIN) {
            if !ActivateOrRestart() {
                ShowTray("无法恢复启动器窗口，退出内层重试")
                ToolTip()
                break
            }
        }

        ; 固定窗口到 1600x900@左上角置顶，按比例算"启动"按钮位置
        clickPt := ForceLauncherWindow()
        if (clickPt = "") {
            ShowTray("启动器窗口无法定位，准备重试... (" retryCount "/" MAX_RETRIES ")")
            Sleep(2000)
            continue
        }

        ToolTip("第 " retryCount " 次点击... (启动器第 " launcherAttempt " 轮)")
        SetTimer(() => ToolTip(), -2000)
        Click(clickPt.x, clickPt.y)
        Sleep(1000)

        startTime := A_TickCount
        Loop {
            if ProcessExist(GAME_PROCESS) {
                gameLaunched := true
                try WinSetAlwaysOnTop(0, LAUNCHER_WIN)   ; 游戏已启动，取消置顶
                ToolTip()
                ShowTray("Nikke 启动成功！(第 " launcherAttempt " 轮第 " retryCount " 次)")
                break 3
            }
            ; 错误弹窗检测：标题子串匹配，可能误中其他程序同名窗口；未加 ahk_exe 约束
            ; 是因为弹窗宿主进程不确定（browser.exe/launcher.exe/系统组件均可能），加了反而漏检
            if WinExist("错误") || WinExist("更新失败") || WinExist("网络异常") {
                ToolTip()
                ShowTray("启动器弹出错误窗口，请手动处理", true)
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
        ShowTray("本轮未成功启动，重启启动器... (" launcherAttempt "/" MAX_LAUNCHER_RETRIES ")")
    }
}

; ★ 所有轮次都失败
if !gameLaunched {
    ShowTray("经过 " MAX_LAUNCHER_RETRIES " 轮尝试，Nikke 未能启动", true)
}
ExitApp()