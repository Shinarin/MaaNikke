<div align="center">

<img src="Assets/logo.png" alt="MaaNikke" width="160">

# MaaNikke

**《胜利女神：NIKKE》自动化每日任务工具**

免去每日重复操作，真正的解放自己，享受人生 🎉

[![License: GPL-3.0](https://img.shields.io/badge/license-GPL--3.0-blue.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Windows-lightgrey.svg)]()
[![Python](https://img.shields.io/badge/python-3.10%2B-3776AB.svg?logo=python&logoColor=white)]()
[![MaaFramework](https://img.shields.io/badge/MaaFramework-5.10.2-brightgreen.svg)](https://github.com/MaaXYZ/MaaFramework)
[![下载最新版](https://img.shields.io/badge/download-最新版本-orange.svg)](https://github.com/Shinarin/MaaNikke/releases/latest)

</div>

---

## ⚠️ 声明

- 本项目仅供**学习与技术交流**使用，禁止用于任何商业用途。
- 本项目与《胜利女神：NIKKE》及其开发商、发行商无任何关联，未获得官方授权或许可。
- 游戏内素材（图像、文字、商标等）的版权归原权利方所有，如涉及侵权请联系删除。
- 使用本工具产生的一切后果（包括但不限于账号异常、封禁）由使用者自行承担。
- 下载或使用本项目即视为同意以上条款。

## 📋 使用前必读

> ⚠️ **重要提示**
> 本自动化程序未考虑到过于复杂的场景，仅能满足**绝大部分养老号**的需求。
> 如果你仍处于**开荒阶段**、功能未解锁或关卡打不过，建议暂时**不要使用**。
> 本程序旨在**免去每日任务的重复操作**，若希望培养顶级战力号，还请多上线微操 😉

### 环境要求

- **Windows 10/11（64 位）**，NIKKE **国服桌面端**，账号由 **WeGame** 登录启动。
- **必须安装 Python（3.10 及以上），安装时务必勾选 "Add Python to PATH"**，否则 agent 无法启动。
  Python 3.13.13 下载地址：<https://www.python.org/ftp/python/3.13.13/python-3.13.13-amd64.exe>
- 首次启动 agent 时会自动安装 `maafw==5.10.2` 和 `Pillow`（需要联网；网络不佳会自动切换清华镜像源；若已安装其他 5.x 版本 maafw 会直接复用，不重复安装）。
- `MaaNikke.exe` 及各启动脚本均需右键以**管理员身份**运行。
- 方案 B（全程自动化）还需安装 **[AutoHotkey 2.0](https://www.autohotkey.com/)**。

### 游戏内设置（务必完成）

1. 过场动画需改为简化版或者关闭。

<img src="resource/announcement/pic/skill_cutscene_setting.png" title="" alt="" width="300">

2. 画质修改如下，**务必！！！**

<img src="resource/announcement/pic/graphics_quality_setting.png" title="" alt="" width="300">

3. 动态壁纸播放建议关闭，防止莫名其妙的 bug 出现。

<img src="resource/announcement/pic/wallpaper_playback_setting.png" title="" alt="" width="300">

4. 在使用 MaaNikke 前，先手动完成过一次每日。

5. **务必战斗模式默认开启自动。**

## 📦 安装与更新

### 下载安装

> 📥 完整程序（含 GUI，解压即用）请前往 [**Releases**](https://github.com/Shinarin/MaaNikke/releases/latest) 下载最新版本；本仓库仅包含自定义层源码（agent / resource / interface），适合二次开发或手动更新。

1. 下载 zip 并解压到任意目录（建议不要有过多层级的嵌套路径）。
2. 按上文完成 Python 安装与游戏内设置。
3. 若双击 `MaaNikke.exe` 无法启动（提示缺少 dll / 运行时），右键以**管理员身份**运行 `DependencySetup_依赖库安装_win.bat`，安装完成后**重启电脑**再试（详见 [常见问题](#-常见问题)）。

### 更新方式

版本更新时替换 `agent`、`interface.json`、`resource` 这三个文件（建议先删除原文件再复制）。

## 🗂 程序组成

解压后目录中，与日常使用直接相关的文件如下：

| 文件 | 类型 | 作用 |
| ---- | ---- | ---- |
| `MaaNikke.exe` | GUI 主程序 | 任务勾选/配置界面，每日任务的实际执行者 |
| `autoMaaNikke.bat` | 批处理脚本 | **一键全流程**：拉起游戏 → 运行每日任务 → 守候到结束 |
| `autoMaaNikke.py` | Python 脚本 | `autoMaaNikke.bat` 的等价 Python 版，供只接受 `.py` 的任务调度器（如 OneDragon ScriptChainer）接入 |
| `startnikke.ahk` | AutoHotkey 脚本 | 自动打开 WeGame 并点击"启动"，把游戏拉起到 `nikke.exe` 运行 |
| `DependencySetup_依赖库安装_win.bat` | 批处理脚本 | 安装 VC++ 运行库与 .NET Desktop Runtime 10（`MaaNikke.exe` 打不开时使用） |
| `launcher_cache.txt` | 缓存文件 | `startnikke.ahk` 首次定位成功后自动生成的启动器路径缓存，**勿手动编辑** |
| `interface.json` | 配置文件 | 任务清单与选项定义（GUI 启动时读取，普通用户无需改动） |
| `config/`、`logs/` | 目录 | GUI 配置与运行日志（出问题时排查用） |

整体启动链（方案 B）：

```
autoMaaNikke.bat / autoMaaNikke.py（管理员运行，二选一）
  │
  ├─ ① 调用 startnikke.ahk
  │       └─ 定位 WeGame 启动器 → 打开 WeGame → 点击"启动" → 等待 nikke.exe 出现
  │
  ├─ ② 每 10 秒检查 nikke.exe 是否在运行，不在则重跑 startnikke.ahk
  │
  ├─ ③ 确认游戏在运行后，启动 MaaNikke.exe
  │       └─ GUI 自动开始执行你勾选的任务列表
  │
  └─ ④ 每 10 秒守候 MaaNikke.exe，直到其退出（任务跑完自动关闭）→ 脚本结束
```

## 🚀 使用方法

本程序提供两种方案，请根据需求选择。

### 方案 A：手动版

适合人在电脑旁、只想省去每日操作的情况：

1. 自行打开 **WeGame**，启动 **Nikke** 并进入游戏大厅。
2. 右键以**管理员身份**运行 `MaaNikke.exe`。
3. 在任务列表勾选要执行的任务（默认已勾选全部日常项），点击开始。
4. 去吃早/晚餐，回来后任务即自动完成。

### 方案 B：全程自动化

适合希望"电脑开着就全自动跑完每日"的情况。由 `autoMaaNikke.bat`（或 `.py`）串联 `startnikke.ahk` 与 `MaaNikke.exe`，配合 Windows 任务计划程序实现定时无人值守。

#### 1. 安装依赖

- 下载并安装 **[AutoHotkey 2.0](https://www.autohotkey.com/)**（注意必须是 v2 版本，`startnikke.ahk` 使用 v2 语法）。

#### 2. 启动脚本详解

##### ① `autoMaaNikke.bat`（一键全流程入口）

**使用方式**：右键以**管理员身份**运行（非管理员会直接提示并退出）。

执行流程：

1. 校验管理员权限；
2. 启动 `startnikke.ahk`，等待 60 秒让游戏加载；
3. 之后每 10 秒检查一次 `nikke.exe` 进程：若游戏没在运行，重新调用 `startnikke.ahk` 再拉一次；
4. 确认游戏运行后，启动 `MaaNikke.exe`，等待 60 秒让其加载；
5. 之后每 10 秒守候 `MaaNikke.exe`：进程仍在则继续等待，进程退出（任务执行完毕自动关闭）则脚本结束。

> 脚本不会主动杀游戏进程；游戏与 GUI 的关闭依赖 GUI 的"结束后操作"设置（见下文"配置 MaaNikke"）。

##### ② `autoMaaNikke.py`（bat 的 Python 等价版）

行为与 `autoMaaNikke.bat` **完全一致**（管理员校验 → ahk 拉起游戏并轮询 → 守候 MaaNikke.exe 退出），区别仅在于：

- 进程名为精确匹配（bat 是子串匹配），判定更严谨；
- 供只接受 `.py` 脚本的第三方任务调度器（如 OneDragon ScriptChainer）接入任务链。

**使用方式**：在**管理员权限**的终端中运行：

```bat
python autoMaaNikke.py
```

或直接由你的调度器调用。普通双击/任务计划场景请优先使用 `autoMaaNikke.bat`。

##### ③ `startnikke.ahk`（游戏启动脚本）

**一般无需单独运行**，由 `autoMaaNikke.bat/.py` 自动调用。也可双击单独运行来手动拉起游戏。

工作流程：

1. **游戏已在运行**：不做任何启动动作，仅补齐 `launcher_cache.txt` 路径缓存后静默退出；
2. **定位 WeGame 启动器**，按以下优先级依次尝试：
   - 读取 `launcher_cache.txt` 缓存（秒开）；
   - 若 `nikke.exe` 正在运行，从进程路径反查启动器；
   - 遍历所有本地硬盘，按目录关键字（nikke / 胜利女神等）搜索游戏安装目录；
   - 以上都失败则**弹窗提示**：此时请在 WeGame 中手动启动一次游戏，再点"确定"，脚本检测到后会自动记下路径（5 分钟超时）；
3. **拉起游戏**：打开启动器 → 把 WeGame 窗口固定到左上角 1600×900 → 按比例位置点击"启动"按钮 → 等待 `nikke.exe` 出现；
   - 点击最多重试 3 次，每次等待 15 秒；
   - 整轮失败会重启启动器再来一轮（最多 2 轮）；
   - 检测到"错误/更新失败/网络异常"弹窗时，脚本退出并弹**红色托盘提示**，需人工处理；
4. 启动成功或彻底失败后，脚本自动退出，结果由托盘气泡提示（蓝色=一般提示，红色=需要人工介入）。

**关于 `launcher_cache.txt`**：首次定位成功后自动保存启动器路径，之后秒级命中。若你**移动/重装了游戏**，或缓存指向的路径已失效，直接**删除该文件**即可，下次运行会自动重建。

<details>
<summary>🔧 高级：脚本可调参数（一般无需修改，WeGame 界面大改版时才需要）</summary>

打开 `startnikke.ahk` 顶部的"配置区"可调整：

| 参数 | 默认值 | 含义 |
| ---- | ---- | ---- |
| `LAUNCHER_W` / `LAUNCHER_H` | 1600 / 900 | 固定 WeGame 窗口的尺寸（WeGame 最小窗口即 1600×900，勿改小） |
| `BTN_RATIO_X` / `BTN_RATIO_Y` | 0.85 / 0.93 | "启动"按钮中心相对窗口宽/高的比例，**WeGame 布局改版点不到按钮时调这两个值** |
| `MAX_RETRIES` | 3 | 每轮内点击"启动"的重试次数 |
| `WAIT_TIME` | 15000 | 每次点击后等待游戏进程出现的毫秒数 |
| `MAX_LAUNCHER_RETRIES` | 2 | 启动器整体重启的轮数 |

</details>

##### ④ `DependencySetup_依赖库安装_win.bat`（运行库安装/修复）

仅当 `MaaNikke.exe` **无法启动**（闪退、报缺少 `VCRUNTIME*.dll`、`.NET Runtime` 相关错误）时使用：

1. 右键以**管理员身份**运行；
2. 脚本自动识别系统架构（x64 / x86 / ARM64），优先用 winget 安装，不可用时转为直接下载安装：
   - Microsoft Visual C++ Redistributable
   - .NET Desktop Runtime 10.0
3. 安装完成后**重启电脑**，再运行 `MaaNikke.exe`。

#### 3. 启动方式（二选一）

- **方式一：手动直接运行批处理**
  右键以**管理员身份**运行 `autoMaaNikke.bat`。

- **方式二：定时自动化（通过 Windows 任务计划程序定时启动）**

  1. 打开 **任务计划程序**（开始 → Windows 管理工具 → 任务计划程序）。

     ![](resource/announcement/pic/task_scheduler_open.png)

  2. 点击 **创建基本任务**。

  3. 填写名称 → 下一步。

  4. 勾选 **每天** → 下一步。

  5. 设定希望运行的时间 → 下一步。

  6. 选择 **启动程序** → 下一步。

  7. 点击 **浏览**，选择下载解压后文件夹内的 `autoMaaNikke.bat` → 下一步 → 完成。

  8. 右键刚刚创建的任务，选择 **属性**。

     ![](resource/announcement/pic/task_properties_menu.png)

  9. 勾选 **最高权限运行**（必须，否则脚本会因权限不足直接退出）。

     ![](resource/announcement/pic/run_highest_privileges.png)

#### 4. 配置 MaaNikke

打开 `MaaNikke.exe`，进入 **设置 → 启动设置 → 启动后操作**，勾选 **仅启动脚本**

> （因为 Nikke 必须由 WeGame 启动，此处选择"启动游戏"无效；游戏的拉起由 `startnikke.ahk` 负责）
>
> ![](resource/announcement/pic/startup_script_only.png)

#### 5. 可选设置（更省心）

在 **设置 → 启动设置** 中，将 **结束后操作** 设为 **关闭目标程序和本程序**：

- 任务跑完后 GUI 会自动关闭游戏和自己；
- `autoMaaNikke.bat/.py` 检测到 `MaaNikke.exe` 退出后也随之结束，定时任务完整闭环。

### 最终效果

只需保持电脑开机，到设定时间后，程序将自动完成每日任务。
**真正的解放自己，享受人生吧！🎉**

## ✨ 功能列表

| 分类 | 功能 |
| ---- | ---- |
| 🎮 启动 | 启动游戏 |
| 🎁 奖励领取 | 登录奖励 · 邮件领取 · 每日/每周奖励 · PASS 奖励 |
| 🛒 商店 | 付费商店领取 · 道具商店每日购买 |
| 🏠 日常玩法 | 前哨防御 · 派遣公告栏 · 咨询和送礼 · 装备升级 · 好友点数收取赠送 · 社交点招募 |
| ⚔️ 副本挑战 | 模拟室 · 竞技场 · 拦截战 · 爬塔 · 协同作战 · 单人突击 · 联盟突袭(beta) · 更生馆 |
| 🔧 基地养成 | 同步器和循环室 |
| 🎪 大型活动 | 不定时随版本更新（如果有空的话） |

### 各任务说明与可配置选项

在 GUI 任务列表中勾选任务后，部分任务会展开可配置选项：

| 任务 | 说明 | 可配置选项 |
| ---- | ---- | ---- |
| 启动游戏 | 游戏启动后到进入主页大厅的过程 | — |
| 领取登录奖励 | 领取月卡及登录奖励 | — |
| 付费商店领取 | 付费商店每日/每周/每月的免费钻石 | — |
| 道具商店每日购买 | 道具商店每日折扣商品购买 | 普通商店 / 躯体标签商店 / 废铁商店开关；竞技场通用道具开关（可细选风/火/电/物理/水代码、代码手册宝箱、企业装备熔炉） |
| 前哨防御 | 睡醒了 | 是否用钻石一举歼灭（默认关，只用每日免费 1 次）；开启后可设连续歼灭次数（1-11，含免费那次） |
| 派遣公告栏 | 自动领取、自动派遣 | —（需游戏内已解锁自动派遣） |
| 咨询和送礼 | 批量咨询送礼 | —（需手动咨询的 3 个妮姬请收藏至顶端） |
| 装备升级 | 自动升级装备 | —（无法指定装备，仓库需至少有一件未满级装备） |
| 好友点数收取赠送 | 如任务名 | — |
| 社交点招募 | 为完成更生馆任务和每日任务 | — |
| 模拟室 | 一键快速模拟 | —（需已通关最后一个模拟室、解锁快速模拟） |
| 竞技场 | 纯自动战斗 | 特殊竞技场只领取奖励（开启后不战斗） |
| 拦截战 | 自动拦截战 | 周一手操 boss 战开关；特殊拦截战 boss 选择（默认克拉肯，其他 boss 识别失败率较高，谨慎选择） |
| 爬塔 | 无限之塔 + 企业塔 | 无限之塔开关及每日次数（建议别太高，会拉长耗时）；企业塔开关、是否每天打满 3 次、四个企业（朝圣者/超标准、泰特拉、米西利斯、极乐净土）单独开关 |
| 每日每周奖励领取 | 含反叛之路的每日/每周奖励 | — |
| 邮件领取 | 如任务名 | — |
| 同步器和循环室 | 如任务名 | 是否使用时间盒子道具（关闭则保持游戏内原状态） |
| 协同作战 | 打满三次 | —（可能不稳定，出错不影响其他每日） |
| 单人突击 | 如任务名 | — |
| 联盟突袭(beta) | 不稳定，默认不勾选 | —（出错不影响其他每日） |
| 更生馆 | 识别困难，**如无必要建议不勾选** | —（特定节点会弹对话，识别耗时较长属正常） |
| 限时活动 | 随版本开放的活动（如 p5、juveniledays） | 商店兑换暂定：专票、普票、红眼盒子 2h、红眼 |
| PASS 奖励领取 | 如任务名 | — |

> 爬塔说明：企业塔未选择"打满"时，每天只按优先级爬一个开启中的企业塔（优先级：朝圣者/超标准 > 泰特拉 > 米西利斯 > 极乐净土），未开启时段自动跳到下一个企业塔。

## ❓ 常见问题

- **`MaaNikke.exe` 双击没反应 / 报错缺运行时**
  管理员运行 `DependencySetup_依赖库安装_win.bat`，装完**重启电脑**。
- **agent 启动失败 / 提示找不到 Python**
  确认安装 Python 时勾选了 "Add Python to PATH"；在终端执行 `python --version` 能输出版本号才行。
- **`startnikke.ahk` 找不到启动器路径**
  按弹窗提示在 WeGame 里手动启动一次游戏，脚本检测到后会自动缓存路径；之后秒级定位。
- **游戏换了安装目录后脚本找不到游戏**
  删除 `launcher_cache.txt`，下次运行自动重建缓存。
- **WeGame 更新后点不到"启动"按钮**
  调整 `startnikke.ahk` 配置区的 `BTN_RATIO_X` / `BTN_RATIO_Y`（见上文高级参数表）。
- **游戏重启/加载期间日志刷"截图用时过长"且截图全黑**
  游戏加载期不产帧，属正常现象，进大厅后自愈，不用处理。
- **任务跑到一半卡住或行为异常**
  先看游戏窗口是否被最小化/遮挡、画质设置是否被改动；日志在 `logs/` 目录（`log-*.log` 为 GUI 日志，`maafw.log` 为底层识别日志，`vision/` 存识别截图），排查时提供这些文件。
- **不要同时运行多个 MaaNikke 实例**（例如开发版与正式版双开），会互踩文件锁导致异常。

## 🙏 致谢

衷心感谢以下开源项目的大力支持：

- [MFAAvalonia](https://github.com/MaaXYZ/MFAAvalonia)
- [MaaFramework](https://github.com/MaaXYZ/MaaFramework)
- [MaaPipelineEditor](https://github.com/kqcoxn/MaaPipelineEditor)

感谢各位开发者的无私贡献，让我的工作得以顺利进行。

## 📄 开源许可证

本项目基于 [GPL-3.0](LICENSE) 开源。
