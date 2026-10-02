---
name: maanikke-release
description: MaaNikke 发版流程。当用户明确要求 push/发版/打包上传时执行完整流程（changelog = 用户给的内容优先 + DEVLOG 未发布区条目过滤改写合并，用户没给就只用 DEVLOG 总结 → 写入 Changelog.md → DEVLOG 封存新版本线、版本号 +1 → 复制模板打包 zip → 同步三件套到 C:\other\MaaNikke → git push → 创建 GitHub Release 并上传 zip → 备好 QQ 群发送材料：changelog 纯文本复制到剪贴板、告知 zip 路径，由用户自行粘贴发送）；用户只说 push 而无发版意图时，只做普通 git push，不触发本流程（DEVLOG 也不动）。
whenToUse: 用户给出本次更新内容（changelog）并明确要求 push、发版、release、打包上传时触发
---

# MaaNikke 发版流程

## 触发判定（最先做）

- 用户明确要求 push/发版/打包上传 → 执行完整流程（第一至第六步）。changelog 来源：**用户给的内容优先**；用户没给 changelog 内容时，**只用 `DEVLOG.md` `[未发布]` 区条目的用户向改写总结**（过滤规则见第一步），不再因缺 changelog 而退化为普通 push。
- 用户只说 push、语境无发版意图 → 只做 `git add -A && git commit && git push`，**不要**改版本号、不要打包、不要发 Release，**也不要动 DEVLOG.md**（版本线封存只在发版时做）。

## 已验证的关键事实（直接采用，勿重复验证）

- 项目根：`C:/other/MaaNikke_dev`，Windows + Git Bash 环境。
- changelog 文件：`resource/announcement/Changelog.md`（用户向），**最新版本条目置顶**。
- 开发留痕文件：`DEVLOG.md`（开发向），结构为：头部规则说明 → `## [未发布]` 区 → `---` → 各版本线（新上旧下）。平时每次改动由会话随手记录在未发布区；本流程负责发版时的合并与封存。
- 版本字段：`interface.json` 的 `"version"`。注意 `"interface_version": 2` 是协议号，**绝不要动**。
- 模板文件夹：`F:\MaaNikke历史版本备份\MaaNikke-win-x86_64-v2.x.x`（完整程序：exe、libs、runtimes、plugins、MaaAgentBinary、Assets、autoMaaNikke.bat/.py 等，唯独缺 agent/resource/interface.json）。
- 构建与产物位置：构建文件夹和 zip 都直接生成在 `F:\MaaNikke历史版本备份\` 内（与 v2.1.0~v2.1.6 的存放习惯一致），**不要放在项目根目录**。
- 同步目录：`C:\other\MaaNikke`（打包时把 agent/resource/interface.json 也复制一份到这里，**只复制，不做任何其他操作**）。
- zip 命名：`MaaNikke-win-x86_64-v<新版本>.zip`（连字符、win-x86_64，与历史一致）。
- zip 结构：根目录直接平铺 interface.json、agent、resource、MaaNikke.exe、libs 等共 17 个顶层条目，**含目录条目**（保留空目录），不多套一层文件夹。参照物：`F:\MaaNikke历史版本备份\MaaNikke-win-x86_64-v2.1.5.zip`。
- 打包工具：Git Bash 的 tar 是 GNU tar，**造不了 zip**；用 Python zipfile（已实测）。
- `.gitignore` 已含 `MaaNikke-win-x86_64-v*/` 排除规则（兜底，防止构建产物误入项目被提交）。
- GitHub：仓库 `Shinarin/MaaNikke`，本机**无 gh CLI**；用 `git credential fill` 取 token 调 REST API（token 已验证有 `repo` scope，可建 Release）。token 严禁打印/写文件。
- QQ 群发送材料准备：默认随完整流程执行（第六步，2026-10-07 定案）。不再用 Computer Use 操作 QQ，改为把 changelog 纯文本复制到系统剪贴板、告知 zip 路径，由用户自行粘贴/拖拽发送到群。

## 第一步：changelog + DEVLOG 封存 + 版本号

1. 读 `interface.json` 的 `version`，末位 +1；每段只能 0-9，逢 9 向左进位：`2.1.9→2.2.0`、`2.9.9→3.0.0`。
2. Changelog.md 条目 = **用户给的 changelog 内容 + DEVLOG.md `[未发布]` 区条目的用户向改写**，两者合并去重后，插到 `Changelog.md` 顶部第一个 `---` 之后（即最新条目位置）：
   - DEVLOG 过滤规则：剔除 `[文档]`/`[调查]` 条目和纯内部改动（重构、注释、skill、脚本、配置等用户无感知的）；只保留**用户可感知**的新增/修复/优化，用用户语言重写——**不要出现代码细节、文件名、内部机制**。
   - 用户给的内容优先；DEVLOG 改写条目与其重复时以用户表述为准。
   - 版本标题：`## [vX.Y.Z] - YYYY-MM-DD`（日期用 `date +%F` 取真实当前日期，别信会话时间）
   - 分类小节按内容选用：`### 🚀 新增 & 优化` / `### 🔧 优化` / `### 🐛 修复`
   - 条目格式：`- <emoji> **加粗标题**  `（两空格换行）+ 缩进的一句描述
   - 条目之间空行；新旧版本块之间以 `---` 分隔
3. DEVLOG.md 封存：把 `## [未发布]` 标题改为 `## vX.Y.Z - YYYY-MM-DD`（条目原样保留在线下，不删不改），并在头部规则说明之后重建空的 `## [未发布]` 区（保留 `---` 分隔结构，新上旧下）。
4. `interface.json` 的 `version` 同步改为新版本号。

## 第二步：在 F 盘备份目录复制模板并改名

```bash
cp -r "F:/MaaNikke历史版本备份/MaaNikke-win-x86_64-v2.x.x" "F:/MaaNikke历史版本备份/MaaNikke-win-x86_64-v<新版本>"
```

## 第三步：补足三件套、同步到 C:\other\MaaNikke、打包

```bash
cp -r agent resource "F:/MaaNikke历史版本备份/MaaNikke-win-x86_64-v<新版本>/"
cp interface.json "F:/MaaNikke历史版本备份/MaaNikke-win-x86_64-v<新版本>/"
find "F:/MaaNikke历史版本备份/MaaNikke-win-x86_64-v<新版本>" -type d -name __pycache__ -prune -exec rm -rf {} +

# 同样的三件套同步一份到 C:\other\MaaNikke（只复制，不做删除、打包等任何其他操作）
cp -r agent resource "C:/other/MaaNikke/"
cp interface.json "C:/other/MaaNikke/"
```

用 Python 打包（walk 时对 subdirs 也 z.write，以写入目录条目、保留空目录；zip 也生成在 F 盘备份目录）：

```python
import zipfile, os
src = 'F:/MaaNikke历史版本备份/MaaNikke-win-x86_64-v<新版本>'
out = src + '.zip'
with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
    for root, subdirs, files in os.walk(src):
        for d in subdirs:
            p = os.path.join(root, d)
            z.write(p, os.path.relpath(p, src))
        for f in files:
            p = os.path.join(root, f)
            z.write(p, os.path.relpath(p, src))
```

打包后校验：`testzip()` 返回 None；顶层条目 17 个、无嵌套同名文件夹；体积约 110MB。参考值：v2.1.6 为 733 条目 / 116,558,718 字节。

## 第四步：push

1. `git add -A --dry-run` 先核对白名单（应只有 agent/、resource/、interface.json、.kimi-code/、README.md 等项目文件，绝无 exe/dll/logs/config 及构建产物）。
2. 提交信息用中文，如 `chore: release vX.Y.Z`，然后 `git push origin main`。

## 第五步：GitHub Release

```bash
TOKEN=$(printf 'protocol=https\nhost=github.com\n\n' | git credential fill | sed -n 's/^password=//p')
# token 只存变量，严禁 echo/写文件
```

1. 用 Python 生成 `release.json`（避免手工转义 changelog 里的引号换行）：

```json
{"tag_name": "vX.Y.Z", "target_commitish": "main", "name": "MaaNikke-win-x86_64-vX.Y.Z.zip", "body": "<本次 changelog 条目的 md>", "draft": false, "prerelease": false, "make_latest": "true"}
```

2. 创建 Release：

```bash
curl -s -X POST -H "Authorization: token $TOKEN" -H "User-Agent: curl" \
  https://api.github.com/repos/Shinarin/MaaNikke/releases -d @release.json
```

从返回取 `id` 和 `html_url`。**tag 已存在会返回 422 —— 停下报告用户，不要删除重建、不要强试。**

3. 上传 zip（约 113MB，后台任务执行；**去掉 `-s` 静默、保留 `-S`**，curl 进度条会写入任务输出日志，用户想看实时进度可运行 `/tasks` 打开后台任务面板查看）：

```bash
curl -S -X POST -H "Authorization: token $TOKEN" -H "User-Agent: curl" \
  -H "Content-Type: application/zip" \
  --connect-timeout 30 --speed-limit 10240 --speed-time 30 \
  --retry 8 --retry-all-errors --retry-delay 5 \
  --data-binary @"F:/MaaNikke历史版本备份/MaaNikke-win-x86_64-vX.Y.Z.zip" \
  "https://uploads.github.com/repos/Shinarin/MaaNikke/releases/<id>/assets?name=MaaNikke-win-x86_64-vX.Y.Z.zip"
```

断流检测参数含义：速度 <10KB/s 持续 30s 主动断开并重试（v2.1.8 实测有效）。上传中断后 GitHub 会残留 `state=starter` 的占位 asset（页面不可见，同名重传会 422），重传前必须先查 asset 列表并 DELETE 占位：`GET/DELETE /repos/Shinarin/MaaNikke/releases/assets/<asset_id>`。

4. 校验返回的 asset `size` 与本地 zip 字节数一致、`state` 为 `uploaded`。

## 第六步：备好 QQ 群发送材料，由用户自行粘贴发送（2026-10-07 定案）

发版主流程完成后默认执行。**不再用 Computer Use 操作 QQ**（NTQQ 无 UIA 树、坐标操作脆弱且踩过"假死窗"坑）；改为把材料准备好交给用户自己发：

1. **changelog 纯文本写入系统剪贴板**：把 changelog 的**纯文本版**（去掉 `##`/`**` 等 md 标记（QQ 不渲染），首行加 `MaaNikke vX.Y.Z 更新日志` 标题）先写临时文件，再执行：
   ```bash
   powershell -NoProfile -Command "Get-Content -Raw -Encoding UTF8 '<临时文件>' | Set-Clipboard"
   ```
   避免命令行转义和 GBK 乱码。
2. **告知用户**：剪贴板已复制 changelog 文本，到 MaaNikke 群直接 Ctrl+V 粘贴发送即可；zip 文件在 `F:\MaaNikke历史版本备份\MaaNikke-win-x86_64-vX.Y.Z.zip`，由用户自行拖入群发送。
3. 收尾：清理 temp 下的临时文件。

**历史教训（旧 Computer Use 方案 2026-10-01 存档，仅备查勿复用）**：
- ❌ 严禁用脚本 `ShowWindow` 强拉托盘隐藏的 QQ 主窗口：NTQQ 被强制 SW_SHOW 后成"假死窗"——渲染冻结、不处理任何输入，minimize→restore 也救不回。
- ❌ QQ 已运行时不要再 `launch_app` QQ.exe——会开出第二个实例的扫码登录窗。
- 如需恢复自动操作 QQ，必须走 kimi-cu-win「截图 + 坐标」模式并每步截图自检（NTQQ 的 UIA 树为空）。

## 汇报内容

新版本号、changelog 条目预览、zip 大小、commit hash、Release 链接（`html_url`）、QQ 群发送结果。

## 通用注意

- 任一步失败：**停下报告**，不要蛮干重试；push 和 Release 都是对外操作。
- 中文路径全程双引号；Python 打印中文前设 `PYTHONIOENCODING=utf-8`（Windows 控制台 GBK 会乱码）。
- 构建文件夹与 zip 只放 `F:\MaaNikke历史版本备份`，**不要**放项目根目录，也不要在打包后移动（直接在 F 盘构建）。
- 同步 `C:\other\MaaNikke` 只做复制动作，**不要**在那里删 __pycache__、不要打包、不要做版本控制操作。
