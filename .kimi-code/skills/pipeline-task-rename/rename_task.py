#!/usr/bin/env python
"""pipeline 任务文件全量改名（活动派生）。规则见同目录 SKILL.md。

用法:
    cd 项目根 && PYTHONIOENCODING=utf-8 python rename_task.py <目标json> <旧名> <新名> [--copy-images] [--update-interface]

前置：目标 json 已由源文件复制产生。脚本做逐行正则替换 + 断言 + 可选的模板图目录复制
与 interface.json 注册联动更新。
"""
import argparse
import json
import re
import shutil
import sys
from pathlib import Path

IMG_ROOT = Path("resource/base/image")
INTERFACE = Path("interface.json")


def update_interface(old, new, pat):
    """把 interface.json 中 entry==旧名 的任务注册切换到新名（entry + name 的 (旧名) 后缀）。

    逐行定点编辑，不重排整个文件；改完做合规断言。
    """
    with open(INTERFACE, encoding="utf-8", newline="") as fp:
        src = fp.read()
    data = json.loads(src)
    hits = [t for t in data.get("task", []) if t.get("entry") == old]
    assert len(hits) == 1, f"interface.json 中 entry=={old!r} 的任务有 {len(hits)} 个，期望恰好 1 个"

    # 定点改 entry 行（必须全文唯一，防止误伤其他任务）
    entry_pat = re.compile(rf'("entry"\s*:\s*"){re.escape(old)}(")')
    assert len(entry_pat.findall(src)) == 1, f'"entry": "{old}" 行不唯一，拒绝自动修改'
    dst = entry_pat.sub(rf"\g<1>{new}\g<2>", src)

    # name 显示名的 (旧名) 后缀 → (新名)；没有该后缀则保持原样并告警
    m = re.search(rf'"name"\s*:\s*"[^"]*\({re.escape(old)}\)', dst)
    if m:
        dst = dst[: m.start()] + m.group(0).replace(f"({old})", f"({new})") + dst[m.end() :]
        print(f"interface name: ({old}) -> ({new})")
    else:
        print(f"[WARN] name 字段无 ({old}) 后缀，显示名保持原样")

    # 合规断言：JSON 合法；新 entry 恰好 1 条；旧 entry 0 残留；option 引用存在
    d2 = json.loads(dst)
    task = [t for t in d2.get("task", []) if t.get("entry") == new]
    assert len(task) == 1, f"改完后 entry=={new!r} 的任务应为 1 条，实际 {len(task)}"
    assert not [t for t in d2.get("task", []) if t.get("entry") == old], "entry 仍残留旧名"
    opts = d2.get("option", {})
    for o in task[0].get("option", []):
        assert o in opts, f"option {o!r} 未在 interface option 区定义"
    leftover = pat.findall(dst)
    if leftover:
        print(f"[WARN] interface.json 其余位置仍有 {len(leftover)} 处 {old!r}（非本任务注册块，请人工确认归属）")

    with open(INTERFACE, "w", encoding="utf-8", newline="") as fp:
        fp.write(dst)
    print(f"interface.json updated: entry {old} -> {new}")



def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("file", help="目标 pipeline json 路径（已复制好的新文件）")
    ap.add_argument("old")
    ap.add_argument("new")
    ap.add_argument("--copy-images", action="store_true", help="复制 image/**/<旧名>/ 目录为 <新名>/ 并改文件名")
    ap.add_argument("--update-interface", action="store_true", help="同步更新 interface.json 的任务注册（entry + name 后缀）")
    args = ap.parse_args()

    f = Path(args.file)
    old, new = args.old, args.new
    # (?<![A-Za-z]) 防误改连贯词（keep5）；  (?!-v1) 保护 MPE 协议枚举 absolute-v1
    pat = re.compile(rf"(?<![A-Za-z]){re.escape(old)}(?!-v1)")

    with open(f, encoding="utf-8", newline="") as fp:
        src = fp.read()

    if new in src:
        print(f"[WARN] 新名 {new!r} 在文件中已存在，注意 key 冲突风险")

    out, nsub = [], 0
    for line in src.splitlines(keepends=True):
        new_line, k = pat.subn(new, line)
        nsub += k
        out.append(new_line)
    dst = "".join(out)
    print(f"replacements: {nsub}")
    assert nsub > 0, "一处都没替换到，检查旧名/文件是否选对"

    # 断言 1：白名单（<旧名>-v1）外无残留
    residual = [
        m.start() for m in re.finditer(rf"(?<![A-Za-z]){re.escape(old)}", dst)
        if not dst[m.start():].startswith(f"{old}-v1")
    ]
    assert not residual, f"残留 {len(residual)} 处 {old}"

    # 断言 2：JSON 合法、无重复 key、顶层 key 数不变
    def no_dup(pairs):
        d = {}
        for k, v in pairs:
            assert k not in d, f"重复 key: {k}"
            d[k] = v
        return d

    data = json.loads(dst, object_pairs_hook=no_dup)
    old_data = json.loads(src)
    assert len(data) == len(old_data), "顶层 key 数变了"

    # 断言 3：入口节点 == 文件名 stem
    stem = f.stem
    assert stem == new, f"文件名 {f.name} 与新名 {new} 不一致"
    assert new in data, f"入口节点 {new!r} 不存在"

    # 断言 4：MPE config 自洽（coordinateMode 保留 -v1；filename/filePath 指向新名）
    cfg_key = f"$__mpe_config_{new}"
    if cfg_key in data:
        cfg = data[cfg_key].get("$__mpe_code", {})
        assert cfg.get("filename") == new, cfg.get("filename")
        fp = cfg.get("filePath", "")
        assert not fp or Path(fp).name == f.name, fp
        cm = cfg.get("coordinateMode", "")
        assert not cm.endswith(f"{new}-v1"), "coordinateMode 被误改"

    # 断言 5：$__mpe_anchor_* 等键名尾部与新 stem 闭环
    for k in data:
        if re.match(r"^\$__mpe_(anchor|config|external|group|sticker)_", k):
            assert k.endswith(f"_{new}"), f"MPE 键名未改净: {k}"

    with open(f, "w", encoding="utf-8", newline="") as fp:
        fp.write(dst)
    print(f"json rewritten: {f}")

    if args.copy_images:
        for d in sorted(p for p in IMG_ROOT.rglob(old) if p.is_dir()):
            tgt = d.parent / new
            tgt.mkdir(exist_ok=True)
            for p in sorted(d.iterdir()):
                q = tgt / pat.sub(new, p.name)
                shutil.copy2(p, q)
                print(f"copy {p} -> {q}")

    if args.update_interface:
        update_interface(old, new, pat)

    # 断言 6：所有 template 路径在磁盘上存在
    missing = []
    for body in data.values():
        if not isinstance(body, dict):
            continue
        p = body.get("recognition", {})
        p = p.get("param", {}) if isinstance(p, dict) else {}
        t = p.get("template") if isinstance(p, dict) else None
        for t1 in (t if isinstance(t, list) else [t] if t else []):
            if not (IMG_ROOT / t1).is_file():
                missing.append(t1)
    assert not missing, f"模板图缺失: {missing}"
    print("done")


if __name__ == "__main__":
    sys.exit(main())
