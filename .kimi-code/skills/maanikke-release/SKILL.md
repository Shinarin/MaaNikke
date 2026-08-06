---
name: maanikke-release
description: MaaNikke 发版流程。仅当用户同时给出 changelog 内容并明确要求 push/发版时执行完整流程（改 changelog 与版本号 → 复制模板打包 zip → 同步三件套到 C:\other\MaaNikke → git push → 创建 GitHub Release 并上传 zip）；用户只说 push 而未提供 changelog 内容时，只做普通 git push，不触发本流程。
whenToUse: 用户给出本次更新内容（changelog）并明确要求 push、发版、release、打包上传时触发
---

# MaaNikke 发版流程

## 触发判定（最先做）

- 用户**同时**给出 changelog 内容 + 明确 push/发版指令 → 执行完整流程（第一至第五步）。
- 用户只说 push、没给 changelog 内容 → 只做 `git add -A && git commit && git push`，**不要**改版本号、不要打包、不要发 Release。

## 已验证的关键事实（直接采用，勿重复验证）

- 项目根：`C:/other/MaaNikke_dev`，Windows + Git Bash 环境。
- changelog 文件：`resource/announcement/Changelog.md`，**最新版本条目置顶**。
- 版本字段：`interface.json` 的 `"version"`。注意 `"interface_version": 2` 是协议号，**绝不要动**。
- 模板文件夹：`F:\MaaNikke历史版本备份\MaaNikke-win-x86_64-v2.x.x`（完整程序：exe、libs、runtimes、plugins、MaaAgentBinary、Assets、bat 等，唯独缺 agent/resource/interface.json）。
- 同步目录：`C:\other\MaaNikke`（打包时把 agent/resource/interface.json 也复制一份到这里，**只复制，不做任何其他操作**）。
- zip 命名：`MaaNikke-win-x86_64-v<新版本>.zip`（连字符、win-x86_64，与历史一致）。
- zip 结构：根目录直接平铺 interface.json、agent、resource、MaaNikke.exe、libs 等共 16 个顶层条目，**含目录条目**（保留空目录），不多套一层文件夹。参照物：`F:\MaaNikke历史版本备份\MaaNikke-win-x86_64-v2.1.5.zip`。
- 打包工具：Git Bash 的 tar 是 GNU tar，**造不了 zip**；用 Python zipfile（已实测）。
- 产物（构建文件夹 + zip）留在项目根目录；`.gitignore` 是白名单模式，天然不会被提交。
- GitHub：仓库 `Shinarin/MaaNikke`，本机**无 gh CLI**；用 `git credential fill` 取 token 调 REST API（token 已验证有 `repo` scope，可建 Release）。token 严禁打印/写文件。
- QQ 群发送步骤：用户已明确**取消**，不执行。

## 第一步：changelog + 版本号

1. 读 `interface.json` 的 `version`，末位 +1；每段只能 0-9，逢 9 向左进位：`2.1.9→2.2.0`、`2.9.9→3.0.0`。
2. 把用户输入转成 md，仿照文件内旧条目风格，插到 `Changelog.md` 顶部第一个 `---` 之后（即最新条目位置）：
   - 版本标题：`## [vX.Y.Z] - YYYY-MM-DD`（日期用 `date +%F` 取真实当前日期，别信会话时间）
   - 分类小节按内容选用：`### 🚀 新增 & 优化` / `### 🔧 优化` / `### 🐛 修复`
   - 条目格式：`- <emoji> **加粗标题**  `（两空格换行）+ 缩进的一句描述
   - 条目之间空行；新旧版本块之间以 `---` 分隔
3. `interface.json` 的 `version` 同步改为新版本号。

## 第二步：复制模板到项目根目录并改名

```bash
cp -r "F:/MaaNikke历史版本备份/MaaNikke-win-x86_64-v2.x.x" "MaaNikke-win-x86_64-v<新版本>"
```

## 第三步：补足三件套、同步到 C:\other\MaaNikke、打包

```bash
cp -r agent resource "MaaNikke-win-x86_64-v<新版本>/"
cp interface.json "MaaNikke-win-x86_64-v<新版本>/"
find "MaaNikke-win-x86_64-v<新版本>" -type d -name __pycache__ -prune -exec rm -rf {} +

# 同样的三件套同步一份到 C:\other\MaaNikke（只复制，不做删除、打包等任何其他操作）
cp -r agent resource "C:/other/MaaNikke/"
cp interface.json "C:/other/MaaNikke/"
```

用 Python 打包（walk 时对 subdirs 也 z.write，以写入目录条目、保留空目录）：

```python
import zipfile, os
src = 'MaaNikke-win-x86_64-v<新版本>'
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

打包后校验：`testzip()` 返回 None；顶层条目 16 个、无嵌套同名文件夹；体积约 110MB。参考值：v2.1.6 演练为 733 条目 / 111.2MB。

## 第四步：push

1. `git add -A --dry-run` 先核对白名单（应只有 agent/、resource/、interface.json、.kimi-code/、README.md 等项目文件，绝无 exe/dll/logs/config）。
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

3. 上传 zip（约 110MB，网络差时耐心等，`--retry 3`）：

```bash
curl -s -X POST -H "Authorization: token $TOKEN" -H "User-Agent: curl" \
  -H "Content-Type: application/zip" --retry 3 \
  --data-binary @"MaaNikke-win-x86_64-vX.Y.Z.zip" \
  "https://uploads.github.com/repos/Shinarin/MaaNikke/releases/<id>/assets?name=MaaNikke-win-x86_64-vX.Y.Z.zip"
```

4. 校验返回的 asset `size` 与本地 zip 字节数一致。

## 汇报内容

新版本号、changelog 条目预览、zip 大小、commit hash、Release 链接（`html_url`）。

## 通用注意

- 任一步失败：**停下报告**，不要蛮干重试；push 和 Release 都是对外操作。
- 中文路径全程双引号；Python 打印中文前设 `PYTHONIOENCODING=utf-8`（Windows 控制台 GBK 会乱码）。
- 构建文件夹与 zip 用完后留在项目根目录（用户要求，按历史版本习惯摆放），不要删、不要移到 F 盘。
- 同步 `C:\other\MaaNikke` 只做复制动作，**不要**在那里删 __pycache__、不要打包、不要做版本控制操作。
