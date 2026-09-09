---
name: pipeline-task-rename
description: 当需要把 resource/base/pipeline/task/ 下已有任务 JSON 派生为新任务（复制文件后全量替换任务名前缀，如 absolute→colorless、juveniledays→absolute），或批量重命名某 pipeline 文件内的节点前缀时使用；新限时活动复刻旧活动任务文件即为此场景。
whenToUse: 用户要求把某 pipeline 任务文件内的旧任务名字段全部替换为新任务名（含 anchor、重定向引用、MPE 数据、便签、模板路径）时触发
---

# Pipeline 任务文件改名（活动派生）

## 为什么要全量改干净

MaaFramework 全局合并所有 pipeline JSON 到同一节点表，**节点名全局唯一**。副本里漏改一个旧名，就会和源文件的同名节点互相覆盖、抢识别，且排查困难。漏改 anchor/MPE 键则会让 MPE 编辑器画布关联丢失。

## 已验证的关键事实（直接采用，勿重复验证）

- 任务文件：`resource/base/pipeline/task/<分类>/<任务名>.json`；**顶层入口节点名 == 文件名 stem**（如 `colorless.json` 内有 `"colorless": {...}`）。
- 模板图按事件分目录：`resource/base/image/<分类>/<任务名>/<任务名>_*.png`，pipeline 里 `template` 写 `<分类>/<任务名>/xxx.png`。
- 校验脚本（必跑）：`PYTHONIOENCODING=utf-8 python temp/verify_pipeline.py task/<分类>/<文件>.json`，覆盖：全局重名、未知字段、断引用、anchor 闭环、MPE 键与文件名一致性、ROI 边界、模板图存在性、expected 正则合法性。
- `$__mpe_*` 键是 MPE 画布数据，框架运行时忽略，但**必须一并改名**（AGENTS.md §13 第 11/12 条）。
- `$__mpe_anchor_<锚点名>_<文件名stem>`、`$__mpe_config_<文件名stem>` 等键名尾部带文件名 stem，也要换成新名。

## 替换规则

逐行正则替换（Python）：`re.sub(r"(?<![A-Za-z])旧名(?!-v1)", "新名", line)`，逐文件、逐行处理并计数。

- **`(?<![A-Za-z])` 负向后发断言**：旧名前是字母则不动，防误改连贯词（如 p5→x 时 `keep5` 保留）。字母粘连前缀（如 `claimp5`）需单独评估，不要一刀切。
- **`(?!-v1)` 负向先行断言**：`"coordinateMode": "absolute-v1"` 是 MPE 协议枚举值，旧名为 absolute 时绝不能改成 `<新名>-v1`。
- 只改目标文件本身；其他文件里指向源任务的引用**不要动**（它们引用的是源文件节点，新旧文件并存）。
- `interface.json` 的入口注册是独立动作，改名流程不含；改完提醒用户即可。

## 覆盖清单（8 项，逐项核对，漏一项即事故）

1. 顶层节点 key（含入口节点）。
2. `next` / `on_error` 列表引用——**含 `[JumpBack]xxx`、`[Anchor]xxx` 前缀的重定向引用**（易漏）。
3. `anchor` 字段值；锚点**设置方与 `[Anchor]` 引用方必须同改**，否则闭环断裂（易漏）。
4. `$__mpe_anchor_*` / `$__mpe_config_*` / `$__mpe_external_*` / `$__mpe_group_*` / `$__mpe_sticker_*` 键名。
5. group 的 `childrenLabels`、sticker 便签的**名称/text 中内嵌的节点名**（易漏）。
6. MPE config 内的 `filePath`（→ 新文件路径）和 `filename`（→ 新 stem）。
7. `template` 图片路径（目录名 + 文件名都含旧名）。
8. 模板图目录：`image/<分类>/<旧名>/` **复制**（不是移动，源任务还在用）为 `<新名>/`，内部文件同步改名。

## 执行方式

用本目录的 `rename_task.py`（已按上述规则实现并带断言）：

```bash
cd 项目根 && PYTHONIOENCODING=utf-8 python .kimi-code/skills/pipeline-task-rename/rename_task.py \
    resource/base/pipeline/task/<分类>/<新名>.json <旧名> <新名> --copy-images
```

前置：`<新名>.json` 已由源文件复制产生（`cp` 源文件 目标文件）。脚本要点：逐行 `re.sub`；`newline=""` 读写保持 LF 行尾；写回前断言无残留、JSON 合法、无重复 key、顶层 key 数不变、MPE config 自洽；`--copy-images` 复制模板图目录。

## 验收（全部通过才算完成）

1. **残留检查**：`Grep "旧名" 目标文件` —— 除白名单（如 `absolute-v1`）外 0 命中。
2. **校验脚本全绿**：输出无 `[DUP]` `[FIELD]` `[BADREF]` `[MPE]` `[RECT]` `[BOUNDS]` `[IMG]` `[REGEX]` 任何一类。
3. **与源文件对比**：对源文件跑同一 verify 脚本，两边节点数相同、anchor 列表一一对应（各锚点 refs 数一致；源文件已有的 `set but unused` 属继承状态，不算新问题）。
4. **MPE 自洽**：verify 输出 `mpe config: filename='<新名>'`、`filePath exists on disk: True`，无 stale anchor key。
5. **模板图存在**：无 `[IMG] missing template`；图片目录已复制且文件名已改。
6. **行尾**：LF 保持，整文件不应炸红。文件未被 git 跟踪时 `git diff` 不可见，改用 `git diff --no-index 源文件 目标文件`（应只剩改名行差异；差异行数 ≤ 替换计数属正常，一行可含多处替换）或字节级检查（无 CRLF）。
7. **DEVLOG 留痕**：`## [未发布]` 区顶部追加 `- YYYY-MM-DD [新增] ...（涉及：pipeline 文件、图目录）`。

## 常见错误

| 错误 | 后果 |
|---|---|
| 只改节点 key，漏 next/[JumpBack]/[Anchor] 引用 | 断引用，任务链断裂 |
| anchor 设置方改了、[Anchor] 引用方没改（或反之） | 锚点闭环断裂，跳回失败 |
| 漏 `$__mpe_*` 键名 / 便签内嵌节点名 | MPE 画布残留旧名，下次编辑丢关联 |
| 无 lookbehind 直接字符串替换 | `keep5` 类连贯词被误改 |
| `coordinateMode` 的 `absolute-v1` 被改 | MPE 协议值损坏 |
| 图片目录没复制 | TemplateMatch 找不到模板，运行时必炸 |
| 改完不跑 verify_pipeline.py | 上述任何漏项都发现不了 |
