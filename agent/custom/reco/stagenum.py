"""
============================================================
  stagenum —— 活动 STAGE LIST 关卡号识别（custom recognition）
============================================================

给定较宽 roi（整行或整个列表区域），自动定位关卡号并识别，
归一化匹配 expected（"1-01" 与 "1-1" 互通；小活动页 STAGE LIST 的
纯数字 "01"~"12" 无前缀形态按尾段适配，expected 仍写 "1-x"）。

det-first 两级流程：对 roi 整图跑一次框架 OCR（不带 expected），
det 框 + rec 文本直接做归一化匹配（严格 / 宽松 / 尾段兜底）；
没匹配上的含数字框再做框内紧裁剪重读（原图 + 黑字白底提取图）。
定位完全交给 det 模型，与关卡号的位置、字体、背景无关。

同文件另有：stagematch（顺序轮巡 + 进程内存态临时数据库）、
custom action stagematchdel（删除被标记字段）/ stagematchclear（清空数据库）、
stagepre（锚点字段识别器 + 锚点配置载体：识别节点 param 写
"stagepre": "<节点名>" 即在原识别流程上叠加"数字框须邻近锚点框"的
空间过滤兜底——锚点检出时用它消歧，锚点未检出时降级为无过滤原流程，
不取代、不阻断原识别）。

错配防护（2026-08-27 收紧）：纯 2 位数字只按 int==expected 尾段匹配，
"11"/"12"/"10" 不会中 1-1、"12" 不会中 1-2；数字串全等仅保留 ≥3 位
（"HII"→"111"≡"1-11" 的旧页艺术字兜底）。
"""

import json
import re
import time

from maa.agent.agent_server import AgentServer
from maa.context import Context
from maa.custom_action import CustomAction
from maa.custom_recognition import CustomRecognition
from utils.params import parse_params

import numpy as np

# 关卡号正则：数字 + 分隔符 + 数字（分隔符容忍常见误读：-—–_./,·:：空格）
_STAGE_RE = re.compile(r"(\d{1,2})\s*[-—–_./,·:：' ]+\s*(\d{1,2})")


def parse_stage(text: str) -> tuple[int, int] | None:
    """从文本提取关卡号整数对。"1-01"→(1,1)；无分隔符的纯数字串→None。"""
    if not text:
        return None
    m = _STAGE_RE.search(text)
    if not m:
        return None
    return int(m.group(1)), int(m.group(2))


def stages_equal(candidate: str, expected: str) -> bool:
    """归一化比较 OCR 文本与 expected（任一不可解析→False）。"""
    a, b = parse_stage(candidate), parse_stage(expected)
    return a is not None and b is not None and a == b


def _digits(text: str) -> str:
    """文本中的全部数字拼接（"1-01"→"101"）。"""
    return "".join(ch for ch in text if ch.isdigit())


# 本页艺术斜体 "1" 常被 rec 整串误读（实机实测 "1-11" 原图→"HII"、
# "1-1"→"HI"/"H"）：这些形近字在宽松匹配前一律归一为 '1'
_CONFUSE_AS_ONE = str.maketrans({"I": "1", "l": "1", "|": "1",
                                 "!": "1", "i": "1", "H": "1"})

# 宽松匹配允许出现的分隔符（与 _STAGE_RE 的分隔符类一致）
_LOOSE_SEP = "-—–_./,·:：'"


def stages_equal_loose(candidate: str, expected: str) -> bool:
    """宽松比较：候选先归一斜体 "1" 的误读字（I/l/|/!/i/H→'1'），再比
    数字串——**仅 ≥3 位保留数字串全等**（"HII"→"111"≡"1-11" 的整串字形
    误读兜底）。2 位纯数字不再走全等："11"/"12"/"10" 绝不中 1-1、"12"
    绝不中 1-2（丢分隔符形态与纯数字尾段形态文本层不可分，宁漏勿错；
    空间消歧交给 stagepre 锚点过滤）。映射后残留其它字母直接出局；
    映射后可严格解析的（"H-1"→"1-1"→(1,1)）按解析结果与 expected
    比对，不进下方各兜底档。

    尾段兜底（映射后仍解析不出关卡号时才走，"1-1"/"H-1" 能解析走不到
    这里，不会误中 "1-11"），两种形态：
    1. 映射后带分隔符：数字串 int == expected 末段——兜底前导 "1" 被 det
       丢掉（选中行实测读作 "-11"/"-09"）；
    2. 整框纯数字（strip 后全是数字）且 ≥2 位：int == expected 末段——
       小活动页 STAGE LIST 显示 "01"~"12" 无前缀（"01"≡"1-1"、"12"≡"1-12"）。
       一位纯数字（"5"/"6"）不认：防 "5/5"、"6天8小时" 这类计数/时间文本
       拆框后误中尾段。"""
    if not candidate:
        return False
    mapped = candidate.translate(_CONFUSE_AS_ONE)
    if any(not (ch.isdigit() or ch.isspace() or ch in _LOOSE_SEP)
           for ch in mapped):
        return False
    # 映射后可严格解析的按解析结果比对（"H-1"→"1-1"→(1,1)：只中 1-1，
    # 不被尾段档的数字串 "11" 抢去 1-11）；真丢前导的 "-11" 映射后仍
    # 不可解析，继续走下方尾段兜底
    m_stage = parse_stage(mapped)
    if m_stage is not None:
        e_stage = parse_stage(expected)
        return e_stage is not None and m_stage == e_stage
    a, b = _digits(mapped), _digits(expected)
    if a and b and len(a) >= 3 and a == b:      # 数字串全等仅 ≥3 位（"111"≡"1-11"）
        return True
    tail = parse_stage(expected)
    if not a or tail is None:
        return False
    if any(ch in _LOOSE_SEP for ch in mapped):  # 带分隔符尾段："-11"≡"1-11"
        return int(a) == tail[1]
    s = mapped.strip()
    if s.isdigit() and len(s) >= 2:             # 纯数字尾段："01"≡"1-1"
        return int(s) == tail[1]
    return False


# =====================================================================
# stagepre 锚点过滤（数字框必须邻近锚点字段框，空间消歧防错配）
# =====================================================================
def _reading_order(results: list) -> list:
    """OCR 结果按阅读顺序（y 主 x 次）排序，保证遍历/取首个的确定性。"""
    return sorted(results, key=lambda r: (r[2][1], r[2][0]))


def _anchors_in(results: list, fields: list[str]) -> list[tuple[int, int, int, int]]:
    """OCR 结果中匹配锚点字段的框。锚点是普通文字：contains 匹配、
    大小写不敏感（"Q加成奖励妮姬" 可中 "加成奖励妮姬"），不走关卡号解析。"""
    lows = [f.lower() for f in fields]
    return [box for text, _, box in results
            if any(f in (text or "").lower() for f in lows)]


def _near_anchor(box, anchor_boxes: list, max_dist: int) -> bool:
    """数字框是否邻近某个锚点框：横向行带（y 区间相交且水平间距 ≤ max_dist）
    或纵向列带（x 区间相交且垂直间距 ≤ max_dist），取最近锚点判定。"""
    bx, by, bw, bh = box
    for ax, ay, aw, ah in anchor_boxes:
        if by < ay + ah and ay < by + bh:            # y 相交 → 横向邻居
            if max(0, max(ax - (bx + bw), bx - (ax + aw))) <= max_dist:
                return True
        elif bx < ax + aw and ax < bx + bw:          # x 相交 → 纵向邻居
            if max(0, max(ay - (by + bh), by - (ay + ah))) <= max_dist:
                return True
    return False


def _extract_stagepre_cfg(data: dict) -> dict | None:
    """从 stagepre 节点定义提取锚点配置 {fields, max_dist}。
    兼容 v2 嵌套（recognition.param.custom_recognition_param）与平铺两种形状；
    custom_recognition_param 误写成 JSON 字符串时尝试解析，非法 JSON 返回 None。"""
    cpp = None
    reco = data.get("recognition")
    if isinstance(reco, dict):
        param = reco.get("param")
        if isinstance(param, dict):
            cpp = param.get("custom_recognition_param")
    if cpp is None:
        cpp = data.get("custom_recognition_param")
    if isinstance(cpp, str):
        try:
            cpp = json.loads(cpp)
        except ValueError:
            return None
    if not isinstance(cpp, dict) or not cpp:
        return None
    raw = cpp.get("expected")
    fields = [str(v).strip() for v in (raw if isinstance(raw, list) else [raw])
              if str(v).strip()]
    if not fields:
        return None
    return {"fields": fields, "max_dist": int(cpp.get("max_dist", 300))}


def _load_stagepre_cfg(context: Context, params: dict):
    """读取 params["stagepre"] 指向的 stagepre 节点的锚点配置。

    返回 None  = 未配置（调用方保持无过滤旧行为）；
    返回 False = 配置了但节点缺失/无有效字段（调用方应未命中兜底，
                 防配置笔误静默退回无过滤）；
    返回 dict  = {fields: [...], max_dist: int}。"""
    node = str(params.get("stagepre", "")).strip()
    if not node:
        return None
    try:
        data = context.get_node_data(node)
    except Exception as e:
        print(f"[stagenum] ⚠ stagepre 节点 {node!r} 定义读取失败: {e}，本帧不识别")
        return False
    if not isinstance(data, dict):
        print(f"[stagenum] ⚠ stagepre 节点 {node!r} 不存在，本帧不识别")
        return False
    cfg = _extract_stagepre_cfg(data)
    if cfg is None:
        print(f"[stagenum] ⚠ stagepre 节点 {node!r} 的 custom_recognition_param 无有效 expected"
              "（应为对象或合法 JSON 字符串），本帧不识别")
        return False
    return cfg


def _otsu_threshold(gray: np.ndarray) -> int:
    """经典 Otsu 自动阈值（numpy 实现，无需 OpenCV；与 my_reco 同款）。"""
    hist = np.bincount(gray.ravel(), minlength=256).astype(np.float64)
    total = gray.size
    sum_total = float(np.dot(hist, np.arange(256)))
    sum_b = 0.0
    w_b = 0.0
    best_t, best_var = 0, 0.0
    for t in range(256):
        w_b += hist[t]
        if w_b == 0:
            continue
        w_f = total - w_b
        if w_f == 0:
            break
        sum_b += t * hist[t]
        m_b = sum_b / w_b
        m_f = (sum_total - sum_b) / w_f
        var_between = w_b * w_f * (m_b - m_f) ** 2
        if var_between > best_var:
            best_var, best_t = var_between, t
    return best_t


def build_foreground_mask(
    crop: np.ndarray,
    variant: str,
    bright_min: int = 220,
    dark_max: int = 60,
) -> np.ndarray:
    """生成文字前景掩码（H×W bool）。

    bright: 三通道均 >= bright_min（白/浅色字；对齐实测文字色 RGB(222,225,227)）
    dark:   三通道均 <= dark_max（黑/深色字）
    otsu:   灰度 Otsu 二值化，前景取像素少数派（彩色字/复杂底兜底）
    """
    if variant == "bright":
        return np.all(crop >= bright_min, axis=-1)
    if variant == "dark":
        return np.all(crop <= dark_max, axis=-1)
    if variant == "otsu":
        gray = crop.astype(np.float32).mean(axis=-1).astype(np.uint8)
        t = _otsu_threshold(gray)
        fg = gray > t
        if fg.mean() > 0.5:  # 文字应为少数派，否则取反
            fg = ~fg
        return fg
    raise ValueError(f"未知变体: {variant!r}（可选 bright/dark/otsu）")


def _clamp_roi(img: np.ndarray, roi) -> tuple[int, int, int, int, np.ndarray] | None:
    """按 roi 裁剪图像并做边界钳制，返回 (x, y, w, h, crop)；roi 无效返回 None。"""
    x, y, w, h = roi.x, roi.y, roi.w, roi.h
    img_h, img_w = img.shape[:2]
    x, y = max(0, x), max(0, y)
    w, h = min(w, img_w - x), min(h, img_h - y)
    if w <= 0 or h <= 0:
        return None
    return x, y, w, h, img[y:y + h, x:x + w]


def _box_xywh(box) -> tuple[int, int, int, int]:
    """框架返回的识别结果 box 实测是 list [x,y,w,h]（绑定层 dataclass 不做
    类型转换，JSON 原样透传），这里同时兼容 Rect 对象。"""
    if hasattr(box, "x"):
        return int(box.x), int(box.y), int(box.w), int(box.h)
    x, y, w, h = box
    return int(x), int(y), int(w), int(h)


def _ocr_texts(
    context: Context,
    img: np.ndarray,
    threshold: float,
) -> list[tuple[str, float, tuple[int, int, int, int]]]:
    """对给定图片跑一次框架 OCR，不带 expected（匹配自己做，否则框架的
    精确匹配会丢掉 "1-01" 这类归一化才能救活的变体）。
    返回 filtered_results 的 (text, score, box)；未识别到文本返回空表。"""
    ocr_pipeline = {
        "_stagenum": {
            "recognition": "OCR",
            "roi": [0, 0, img.shape[1], img.shape[0]],
            "threshold": threshold,
        }
    }
    result = context.run_recognition("_stagenum", img, ocr_pipeline)
    if result is None:
        return []
    out = []
    for r in (result.filtered_results or result.all_results or []):
        # box 走 getattr：RecognitionResult 是 9 类 Union（And/Or 无 box），
        # 静态检查会误报；运行时此处恒为 OCR 子结果
        box = getattr(r, "box", None)
        if box is None:
            continue
        out.append((getattr(r, "text", ""), float(getattr(r, "score", 0.0)),
                    _box_xywh(box)))
    return out


def _parse_engine_params(params: dict) -> dict:
    """从 custom_recognition_param 解析引擎参数（StageNum/StageMatch 共用）。"""
    variants = [v.strip() for v in
                str(params.get("variants", "otsu,dark,bright")).split(",") if v.strip()]
    return {
        "threshold": float(params.get("threshold", 0.3)),
        "variants": variants,          # stage-1 提取图变体顺序
        "bright_min": int(params.get("bright_min", 220)),
        "dark_max": int(params.get("dark_max", 60)),
    }


def _recognize_one(context: Context, image: np.ndarray, roi, expected: str, *,
                   threshold=0.3, variants=("otsu", "dark", "bright"),
                   bright_min=220, dark_max=60,
                   anchor: dict | None = None) -> "tuple[tuple[int,int,int,int], dict] | None":
    """单字段完整识别（stagenum 引擎核心，StageNum/StageMatch 共用）。

    det-first 两级流程：
    stage-0 整图直配——对 roi 跑一次不带 expected 的框架 OCR，det 框 +
    rec 文本直接做归一化匹配（严格优先，宽松/尾段兜底）；
    stage-1 框内兜底——对没匹配上且含数字/形近字的框，紧裁剪（pad 3px）
    先原图重读、再按 variants 顺序做提取图（黑字白底）重读；原始文本
    可严格解析的框跳过（能严格解析却没在 stage-0 命中 ⇒ 解析值 ≠
    expected，框属于别的关卡；重读丢信息会引入歧义——实机案例：粘连框
    "CLEAR1-2" 重读丢横杠成 "12"，纯数字尾段档误中 1-12）。
    日志前缀 [stagenum]（引擎层日志）。命中返回 ((x,y,w,h), detail)；
    未命中返回 None。

    anchor（可选，{"fields": [...], "max_dist": int}，来自 stagepre 节点）：
    在原识别流程之上叠加空间过滤兜底——先按阅读顺序排序全部框；本帧
    锚点字段有检出时，只保留邻近某个锚点框（横向行带/纵向列带，间距
    ≤ max_dist）的框参与匹配与框内重读（防 "825/5" 这类杂散数字错配），
    且含锚点字段的框同时作为关卡号候选做"锚点尾段"匹配（剥字母数字串
    int==expected 尾段，1 位也认——EVENT x 关卡标题形态，尾段比对自带
    消歧），另放开"锚点单H"档：映射后为单 "1" 的邻近框可中 1-1（斜体
    1-1 整串读作 H 的实测形态，无锚点时维持单位数不认防计数误中）；
    锚点全部未检出时**降级为无过滤原流程**（锚点是增强兜底而非
    前置闸门，锚点字段 OCR 不稳的页面不会被卡死）。
    """
    clamped = _clamp_roi(image, roi)
    if clamped is None:
        print(f"[stagenum] ROI 无效: {roi}")
        return None
    x0, y0, _, _, roi_crop = clamped

    def match(text: str) -> str | None:
        if stages_equal(text, expected):
            return "严格"
        if stages_equal_loose(text, expected):
            return "宽松"
        return None

    results = _reading_order(_ocr_texts(context, roi_crop, threshold))

    anchor_fields_lower: list[str] = []   # 非空 = 本帧锚点已检出
    if anchor is not None:
        anchor_boxes = _anchors_in(results, anchor["fields"])
        if not anchor_boxes:
            print(f"[stagenum] 锚点字段 {anchor['fields']} 本帧全部未检出，"
                  f"降级为无过滤识别（锚点仅作兜底增强）")
        else:
            anchor_fields_lower = [f.lower() for f in anchor["fields"]]
            before = len(results)
            results = [r for r in results
                       if _near_anchor(r[2], anchor_boxes, anchor["max_dist"])]
            print(f"[stagenum] 锚点过滤：{before} 框 → {len(results)} 框"
                  f"（锚点 {len(anchor_boxes)} 个）")

    expected_stage = parse_stage(expected)

    def anchor_tail(text: str) -> bool:
        """锚点框数字尾段匹配：本帧锚点已检出、且文本含锚点字段时，该框
        同时作为关卡号候选——取**最后一个数字组**按 int==expected 尾段匹配
        （1 位数字也认）。EVENT x 关卡标题形态：锚点字段本身即关卡号担保，
        不受"单位数纯数字防计数误中"限制；尾段比对自带消歧
        （"EVENT 1"→1≠11 不中 1-11，"EVENT 12"→12 中 1-12）。
        取最后组而非全串拼接：防 "CLEAR1-2" 粘连框拼出 "12" 误中 1-12。"""
        if not anchor_fields_lower or expected_stage is None:
            return False
        low = (text or "").lower()
        if not any(f in low for f in anchor_fields_lower):
            return False
        groups = re.findall(r"\d+", text or "")
        return bool(groups) and int(groups[-1]) == expected_stage[1]

    def anchor_single_one(text: str) -> bool:
        """锚点担保的单字符 "1"：本帧锚点已检出时，映射后 strip 为单 "1"
        的框（斜体 1-1 整串被读成 H 的实测形态——"1-1" 三笔画形似 H）
        允许中 1-1。能走到这里的框已通过锚点过滤（邻近锚点），单字母
        噪声由空间关系担保压住；无锚点/锚点未检出时维持"单位数纯数字
        不认"（防 "5/5"、"6天8小时" 类计数误中）。"""
        if not anchor_fields_lower or expected_stage != (1, 1):
            return False
        return (text or "").strip().translate(_CONFUSE_AS_ONE) == "1"

    def full_match(text: str) -> str | None:
        """全部档位统一入口（stage-0 整图 / stage-1 框内重读共用）。"""
        how = match(text)
        if not how and anchor_tail(text):
            how = "锚点尾段"
        if not how and anchor_single_one(text):
            how = "锚点单H"
        return how

    # stage-0：整图 OCR 结果直接匹配
    for text, score, (bx, by, bw, bh) in results:
        how = full_match(text)
        if how:
            orig = (x0 + bx, y0 + by, bw, bh)
            print(f"[stagenum] ✅ 命中 {expected}（整图/{how}，"
                  f"OCR {text!r} score={score:.2f}）→ {orig}")
            return orig, {"matched": text, "expected": expected,
                          "source": "整图", "score": score}

    # stage-1：框内兜底。只处理含数字或斜体 "1" 形近字的框
    #（Repeat/Clear 等纯字母框没有重读价值）
    def eligible(text: str) -> bool:
        return any(ch.isdigit() for ch in text.translate(_CONFUSE_AS_ONE))

    pad = 3  # 与实机一致：紧裁剪加一点边距，避免抗锯齿笔画被切掉
    img_h, img_w = roi_crop.shape[:2]
    for text, score, (bx, by, bw, bh) in results:
        if not eligible(text):
            continue
        # 否决：原始文本可严格解析 ⇒ 框属于解析出的那个关卡（能在 stage-0
        # 严格命中当前 expected 的话根本走不到这里，所以解析值必然 ≠
        # expected）；重读只会丢信息引入歧义——实机案例：粘连框
        # "CLEAR1-2"（解析得 (1,2)）紧裁剪送提取图重读丢横杠读成 "12"，
        # 纯数字尾段档误中 1-12
        if parse_stage(text) is not None:
            continue
        px0, py0 = max(0, bx - pad), max(0, by - pad)
        px1, py1 = min(img_w, bx + bw + pad), min(img_h, by + bh + pad)
        sub = roi_crop[py0:py1, px0:px1]
        if sub.size == 0:
            continue
        # 框内原图重读：紧裁剪上 det 重跑，偶发能拆开整图粘连的框
        for t2, s2, (cx, cy, cw, ch) in _ocr_texts(context, sub, threshold):
            how = full_match(t2)
            if how:
                orig = (x0 + px0 + cx, y0 + py0 + cy, cw, ch)
                print(f"[stagenum] ✅ 命中 {expected}（框内原图/{how}，整图读 "
                      f"{text!r}，重读 {t2!r} score={s2:.2f}）→ {orig}")
                return orig, {"matched": t2, "expected": expected,
                              "source": "框内原图", "score": s2}
        # 框内提取图（黑字白底）：斜体/低对比字形的最后手段
        for variant in variants:
            try:
                mask = build_foreground_mask(sub, variant, bright_min, dark_max)
            except ValueError as e:
                print(f"[stagenum] {e}，跳过该提取变体")
                continue
            bw3 = np.stack([np.where(mask, 0, 255).astype(np.uint8)] * 3, axis=-1)
            for t2, s2, (cx, cy, cw, ch) in _ocr_texts(context, bw3, threshold):
                how = full_match(t2)
                if how:
                    orig = (x0 + px0 + cx, y0 + py0 + cy, cw, ch)
                    print(f"[stagenum] ✅ 命中 {expected}（提取图({variant})/{how}，"
                          f"整图读 {text!r}，重读 {t2!r} score={s2:.2f}）→ {orig}")
                    return orig, {"matched": t2, "expected": expected,
                                  "source": f"提取图({variant})", "score": s2}

    print(f"[stagenum] ❌ 未命中 {expected}（整图读数 "
          f"{[t for t, _, _ in results] or '∅'}）")
    return None


def _wrap(hit) -> "CustomRecognition.AnalyzeResult":
    """_recognize_one 返回值 → AnalyzeResult。"""
    if hit is None:
        return CustomRecognition.AnalyzeResult(box=None, detail={})
    box, detail = hit
    return CustomRecognition.AnalyzeResult(box=box, detail=detail)


@AgentServer.custom_recognition("stagenum")
class StageNum(CustomRecognition):
    """
    关卡号识别：在 roi 内自动定位关卡号，归一化匹配 expected。

    ── 执行流程 ──
    stage-0 整图直配：对 roi 跑一次框架 OCR（不带 expected，det 框 + rec
    文本全部由框架产出），逐条文本做归一化匹配——严格（parse_stage，
    "1-04 √ Clear" 这类合并文本也能抠出 "1-04"）→ 宽松（斜体 "1" 误读
    字归一，"HII"≈"1-11"）→ 尾段兜底（前导 "1" 丢失 "-11"≈"1-11"；
    整框纯数字无前缀 "01"≡"1-1"、"12"≡"1-12"）。
    stage-1 框内兜底：对没匹配上且含数字/形近字的框，紧裁剪（pad 3px）
    先原图重读，再按 variants 顺序做黑字白底提取图重读。
    命中即把 box 映射回原图坐标返回；全部不匹配 → 未命中，框架按 timeout 重试。

    ── 自定义参数（custom_recognition_param，直接写对象） ──
    {
        "expected": "1-11",        // 必填，目标关卡号（与 1-01 等写法互通）
        "stagepre": "xxx_pre",     // 可选，stagepre 节点名；填写后启用锚点
                                   // 空间过滤（配置取自该节点的 expected/max_dist）
        "threshold": 0.3,          // 可选，OCR 置信度，默认 0.3
        "variants": "otsu,dark,bright",  // 可选，stage-1 提取图变体顺序
        "bright_min": 220,         // 可选，亮字提取阈值
        "dark_max": 60             // 可选，暗字提取阈值
    }

    ── Pipeline JSON ──
    {
        "recognition": {
            "type": "Custom",
            "param": {
                "custom_recognition": "stagenum",
                "custom_recognition_param": { "expected": "1-11" },
                "roi": [400, 150, 460, 450]
            }
        },
        "action": { "type": "Click" },
        "timeout": 20000
    }

    ── 注意 ──
    1. 定位完全交给 det 模型：与关卡号的位置、字体、背景（立绘/斜纹）无关，
       roi 给整个列表区域即可，列表滚动也能命中。
    2. 错配防护（2026-08-27 收紧）：纯 2 位数字只按 int==expected 尾段匹配，
       "11"/"12"/"10" 不会中 1-1、"12" 不会中 1-2；丢分隔符歧义不再靠
       stagematch 长号码优先兜底，改由 stagepre 锚点空间过滤消歧
       （锚点为叠加兜底：检出时消歧，未检出时降级无过滤原流程）。
    """

    def analyze(
        self,
        context: Context,
        argv: CustomRecognition.AnalyzeArg,
    ) -> CustomRecognition.AnalyzeResult:
        params = parse_params(argv.custom_recognition_param)
        expected = str(params.get("expected", "")).strip()
        if parse_stage(expected) is None:
            print(f"[stagenum] expected 缺失或格式非法: {expected!r}（需要形如 '1-11'）")
            return CustomRecognition.AnalyzeResult(box=None, detail={})
        anchor = _load_stagepre_cfg(context, params)
        if anchor is False:
            return CustomRecognition.AnalyzeResult(box=None, detail={})
        return _wrap(_recognize_one(context, argv.image, argv.roi, expected,
                                    anchor=anchor, **_parse_engine_params(params)))


# =====================================================================
# stagepre —— 锚点字段识别器 + stage 系列的锚点配置载体
# =====================================================================
@AgentServer.custom_recognition("stagepre")
class StagePre(CustomRecognition):
    """
    锚点字段识别：对 roi 跑一次框架 OCR，contains 匹配 expected 锚点字段
    （普通文字匹配，大小写不敏感，不做关卡号解析），命中返回阅读顺序
    （y 主 x 次）第一个锚点框。

    另一个身份是 stagenum/stagematch 的锚点配置载体：识别节点的 param 写
    "stagepre": "<本节点名>"，运行时经 context.get_node_data 取本节点
    custom_recognition_param 的 expected/max_dist，在原识别流程上叠加
    "数字框须邻近锚点框（横向行带/纵向列带，间距 ≤ max_dist）"的
    空间过滤兜底——文本层分不清的 "11"/"12" 歧义由卡片锚点的位置关系
    消歧；本帧锚点全部未检出时降级为无过滤原流程（增强兜底而非前置
    闸门，锚点字段 OCR 不稳的页面不会被卡死）。

    ── 自定义参数（custom_recognition_param，直接写对象） ──
    {
        "expected": ["NONE", "CLEAR"],  // 必填（字符串或数组），卡片级锚点文字
        "max_dist": 300,                // 可选，数字框与锚点框最大间距 px，默认 300
        "threshold": 0.3                // 可选，OCR 置信度，默认 0.3
    }

    ── Pipeline JSON ──
    {
        "recognition": {
            "type": "Custom",
            "param": {
                "custom_recognition": "stagepre",
                "custom_recognition_param": { "expected": ["NONE", "CLEAR"] },
                "roi": [400, 150, 460, 450]
            }
        }
    }

    ── 注意 ──
    1. 锚点字段应选"每张关卡卡片上都会重复出现"的文字（锁定时 NONE、
       已通关 CLEAR、Repeat 按钮等），随活动皮肤维护。
    2. 节点被框架正常执行时就是普通锚点识别器（命中首个锚点框）；
       仅被 stagenum/stagematch 的 "stagepre" 参数引用时不需挂进 next 链。
    """

    def analyze(
        self,
        context: Context,
        argv: CustomRecognition.AnalyzeArg,
    ) -> CustomRecognition.AnalyzeResult:
        params = parse_params(argv.custom_recognition_param)
        raw = params.get("expected", "")
        fields = [str(v).strip() for v in (raw if isinstance(raw, list) else [raw])
                  if str(v).strip()]
        if not fields:
            print("[stagepre] expected 缺失或为空（需要锚点字段，如 [\"NONE\", \"CLEAR\"]）")
            return CustomRecognition.AnalyzeResult(box=None, detail={})
        clamped = _clamp_roi(argv.image, argv.roi)
        if clamped is None:
            print(f"[stagepre] ROI 无效: {argv.roi}")
            return CustomRecognition.AnalyzeResult(box=None, detail={})
        x0, y0, _, _, crop = clamped
        threshold = float(params.get("threshold", 0.3))
        results = _reading_order(_ocr_texts(context, crop, threshold))
        for text, score, (bx, by, bw, bh) in results:
            low = (text or "").lower()
            hit_field = next((f for f in fields if f.lower() in low), None)
            if hit_field is not None:
                orig = (x0 + bx, y0 + by, bw, bh)
                print(f"[stagepre] ✅ 锚点命中 {hit_field!r}（OCR {text!r} "
                      f"score={score:.2f}）→ {orig}")
                return CustomRecognition.AnalyzeResult(
                    box=orig, detail={"matched": text, "anchor": hit_field,
                                      "score": score})
        print(f"[stagepre] ❌ 锚点字段 {fields} 全部未命中"
              f"（整图读数 {[t for t, _, _ in results] or '∅'}）")
        return CustomRecognition.AnalyzeResult(box=None, detail={})


def _fresh_screenshot(context: Context, fallback: np.ndarray) -> np.ndarray:
    """重新截图；失败警告并沿用上一张（与 recodatebase 同款模式）。"""
    try:
        controller = context.tasker.controller
        controller.post_screencap().wait()
        return controller.cached_image
    except RuntimeError as e:
        print(f"[stagematch] ⚠ 重新截图失败: {e}，沿用上一张")
        return fallback


# =====================================================================
# stagematch 临时数据库（进程内存态，agent 子进程结束即销毁，无残留）
# =====================================================================
# 结构：{"fields": [...], "marked": {...}}
#   fields —— 建库时 expected 的入库顺序（去重），识别顺序与之保持一致
#   marked —— "最近命中待确认"字段（替换式单标记：新命中顶掉旧标记；
#             标记不妨碍识别，仅 stagematchdel 确认后才会真正删除）
# None 表示库不存在（未建库 / 已被 stagematchclear 清空）
_STAGE_DB: dict | None = None


def _db_init(fields: list[str]) -> None:
    """以给定字段建库（去重，保持传入顺序）。"""
    global _STAGE_DB
    _STAGE_DB = {"fields": list(dict.fromkeys(fields)), "marked": set()}


def _db_pending() -> list[str]:
    """库中可识别字段（未删除的全部字段，保持入库顺序）；无库返回 []。
    已标记字段仍参与识别——标记只是"待确认"记录，确认删除权在 stagematchdel。"""
    if _STAGE_DB is None:
        return []
    return list(_STAGE_DB["fields"])


def _db_mark(field: str) -> None:
    """把字段标记为"最近命中待确认"（替换式：新标记顶掉旧标记，
    旧字段恢复为普通字段）。单标记保证 stagematchdel 只删"刚确认的那关"。"""
    if _STAGE_DB is not None:
        _STAGE_DB["marked"] = {field}


def stagedb_fields() -> list[str]:
    """读库中字段（含已标记待删，保持入库顺序）；无库返回 []。"""
    return list(_STAGE_DB["fields"]) if _STAGE_DB is not None else []


def stagedb_del() -> list[str]:
    """删除当前被标记字段（替换式单标记，至多一个）并清空标记，
    返回删除列表（保持入库顺序）。

    无库或无标记字段为空操作（幂等）。
    """
    if _STAGE_DB is None:
        return []
    marked = _STAGE_DB["marked"]
    if not marked:
        return []
    removed = [f for f in _STAGE_DB["fields"] if f in marked]
    _STAGE_DB["fields"] = [f for f in _STAGE_DB["fields"] if f not in marked]
    marked.clear()
    return removed


def stagedb_clear() -> bool:
    """清空整个临时数据库（置为不存在），返回此前是否有库。幂等。"""
    global _STAGE_DB
    had = _STAGE_DB is not None
    _STAGE_DB = None
    return had


@AgentServer.custom_recognition("stagematch")
class StageMatch(CustomRecognition):
    """
    按顺序轮巡识别关卡字段（recodatebase 骨架 × stagenum 识别方式）。

    ── 执行流程 ──
    1. 临时数据库不存在 → 以本节点 expected 按序建库（去重）；
       已存在 → 忽略本节点 expected，沿用库中剩余字段（库优先）
    2. for 轮次 in 1..rounds:
         for 字段 in 库中全部未删除字段（识别顺序 = 建库时 expected 顺序）:
             for 尝试 in 1..tries_per_field:
                 重新截图 → 调 stagenum 引擎识别该字段
                 命中 → 标记为"最近待确认"（替换旧标记）→ 返回词组 box
             全空 → 下一字段
         一轮全空 → 执行 action_node（不填跳过）→ 等 post_action_wait → 下一轮
    3. 库中字段全部被删除 → 未命中（pipeline 退出信号）
    全轮皆空 → 未命中，框架按节点 timeout 重试

    ※ 每次识别前都重新截图（post_screencap）：同图重试结果确定性相同无意义，
      动画/加载期画面会变，重截才有收益。action_node 的价值是改变画面内容
      （如滑动列表露出其他关卡），不配时各轮差异仅来自画面自身动态。

    ── 临时数据库（进程内存态，agent 子进程结束即销毁，无残留）──
    命中即把字段标记为"最近待确认"——**替换式单标记**（新命中顶掉旧标记，
    旧字段恢复普通），且**标记不妨碍识别**（未删除的字段每轮都会重新扫）。
    只有 pipeline 后续节点明确确认该关"未开放/已通关"（如识别到"无法重复
    通关"弹窗）时，才放 stagematchdel 把当前标记字段真正删除；点击未生效、
    战斗未完成等未确认场景，字段留在库里下轮还会再被识别重试。一轮刷完
    （或流程收尾）放 stagematchclear 整库清空，下次进入重新建库。

    ── 自定义参数（custom_recognition_param，直接写对象） ──
    {
        "expected": ["1-11", "1-10"],  // 必填，字符串或数组；仅建库时生效（顺序即识别顺序）
        "tries_per_field": 3,          // 可选，每字段每轮识别次数（每次重截），默认 3
        "rounds": 2,                   // 可选，总轮数，默认 2
        "action_node": "xxx_swipe",    // 可选，一轮全空后手动执行的动作节点名
        "post_action_wait": 1000,      // 可选，动作后等待毫秒，默认 1000
        "stagepre": "xxx_pre",         // 可选，stagepre 节点名；叠加锚点空间过滤
                                       // 兜底（锚点未检出时降级无过滤原流程）
        // 其余 stagenum 引擎参数原样透传：threshold/variants/bright_min/dark_max
    }

    ── Pipeline JSON ──
    {
        "recognition": {
            "type": "Custom",
            "param": {
                "custom_recognition": "stagematch",
                "custom_recognition_param": {
                    "expected": ["1-11", "1-10"],
                    "action_node": "xxx_swipe"
                },
                "roi": [400, 150, 460, 450]
            }
        },
        "action": { "type": "Click" },
        "timeout": 60000
    }

    ── 注意 ──
    1. detail 中 matched 为命中的字段名，OCR 原文在 ocr_text，
       db_remaining 为库内未删除字段总数（标记不减少该值，删除才减）。
    2. 独立动作节点写法与 recodatebase 相同：不进任何 next 链，仅供
       action_node 手动调用。
    3. 临时数据库与 my_reco 的 datebase 体系代码完全独立，互不影响。
    """

    def analyze(
        self,
        context: Context,
        argv: CustomRecognition.AnalyzeArg,
    ) -> CustomRecognition.AnalyzeResult:
        params = parse_params(argv.custom_recognition_param)

        # ── expected：字符串或数组，过滤非法字段（仅建库时使用）──
        raw = params.get("expected", "")
        if isinstance(raw, str):
            raw_fields = [raw]
        elif isinstance(raw, list):
            raw_fields = raw
        else:
            raw_fields = []
        fields, dropped = [], []
        for v in raw_fields:
            f = str(v).strip()
            (fields if parse_stage(f) is not None else dropped).append(f)
        if dropped:
            print(f"[stagematch] ⚠ 忽略非法字段: {dropped}")

        tries = max(1, int(params.get("tries_per_field", 3)))
        rounds = max(1, int(params.get("rounds", 2)))
        action_node = str(params.get("action_node", "")).strip()
        post_action_wait = int(params.get("post_action_wait", 1000))
        engine = _parse_engine_params(params)

        anchor = _load_stagepre_cfg(context, params)
        if anchor is False:
            return CustomRecognition.AnalyzeResult(box=None, detail={})

        if _clamp_roi(argv.image, argv.roi) is None:
            print(f"[stagematch] ROI 无效: {argv.roi}")
            return CustomRecognition.AnalyzeResult(box=None, detail={})

        # ── 临时数据库：不存在则以 expected 建库；存在则库优先（忽略 expected）──
        if _STAGE_DB is None:
            if not fields:
                print(f"[stagematch] expected 缺失或全部非法: {raw!r}（需要形如 '1-11' 或数组）")
                return CustomRecognition.AnalyzeResult(box=None, detail={})
            _db_init(fields)
            print(f"[stagematch] 建库 {stagedb_fields()}")
        else:
            outside = [f for f in fields if f not in _STAGE_DB["fields"]]
            if outside:
                print(f"[stagematch] ⚠ 本节点 expected 含库外字段 {outside}，已忽略"
                      "（库优先；需重建请先 stagematchclear）")

        pending = _db_pending()
        if not pending:
            print("[stagematch] 库中字段已全部完成，无剩余可识别（未命中）")
            return CustomRecognition.AnalyzeResult(box=None, detail={})

        print(f"[stagematch] 开始轮巡 {pending}（{rounds} 轮 × 每字段 {tries} 试）")
        img = argv.image
        for round_i in range(1, rounds + 1):
            for field in pending:
                for try_i in range(1, tries + 1):
                    img = _fresh_screenshot(context, img)
                    hit = _recognize_one(context, img, argv.roi, field,
                                         anchor=anchor, **engine)
                    if hit is not None:
                        box, info = hit
                        _db_mark(field)
                        detail = {**info, "ocr_text": info.get("matched", ""),
                                  "matched": field, "round": round_i, "try": try_i,
                                  "db_remaining": len(_db_pending())}
                        print(f"[stagematch] ✅ 命中 {field}（第 {round_i} 轮第 {try_i} 试，"
                              f"OCR {info.get('matched')!r} score={info.get('score', 0):.2f}，"
                              f"已标记为最近待确认，库未删除剩 {detail['db_remaining']}）→ {box}")
                        return CustomRecognition.AnalyzeResult(box=box, detail=detail)
                print(f"[stagematch] 字段 {field} 第 {round_i} 轮 {tries} 试全空")
            print(f"[stagematch] 第 {round_i} 轮全部字段未命中")
            if round_i < rounds and action_node:
                print(f"[stagematch] 手动执行动作节点 {action_node}")
                act = context.run_action(
                    action_node, (argv.roi.x, argv.roi.y, argv.roi.w, argv.roi.h))
                if act is None or not act.success:
                    print("[stagematch] ⚠ 手动 action 未成功，仍继续下一轮")
                time.sleep(post_action_wait / 1000)
        print(f"[stagematch] ❌ 全轮皆空: {pending}")
        return CustomRecognition.AnalyzeResult(box=None, detail={})


# =====================================================================
# Action: stagematchdel —— 删除临时数据库中当前被标记的字段
# =====================================================================
@AgentServer.custom_action("stagematchdel")
class StageMatchDel(CustomAction):
    """
    删除 stagematch 临时数据库中当前被标记的字段（替换式单标记，至多一个，
    保持剩余字段入库顺序）。

    典型用法：stagematch 命中某关卡只是把它标记为"最近待确认"（不妨碍
    识别）；pipeline 在后续节点明确确认该关"未开放/已通关"（如识别到
    "无法重复通关"弹窗）之后放本 action，把该字段真正删除，stagematch
    再次进入时就少一个字段。无库或无标记字段时为空操作（幂等），
    始终返回成功。无参数。

    Pipeline JSON 引用示例:
    {
        "action": "Custom",
        "custom_action": "stagematchdel"
    }
    """

    def run(
        self,
        context: Context,
        argv: CustomAction.RunArg,
    ) -> CustomAction.RunResult:
        removed = stagedb_del()
        if removed:
            print(f"[stagematchdel] 已删除被标记字段 {removed}，剩余 {stagedb_fields()}")
        else:
            print("[stagematchdel] 无被标记字段（或库不存在），无需删除")
        return CustomAction.RunResult(success=True)


# =====================================================================
# Action: stagematchclear —— 清空整个临时数据库
# =====================================================================
@AgentServer.custom_action("stagematchclear")
class StageMatchClear(CustomAction):
    """
    清空 stagematch 临时数据库（置为不存在），防止数据残留。

    用于一轮刷完 / 流程收尾：清空后 stagematch 下次进入会重新以
    本节点 expected 建库。（库本身是进程内存态，agent 子进程结束即
    销毁，本 action 提供任务内的显式重置。）幂等，始终返回成功。无参数。

    Pipeline JSON 引用示例:
    {
        "action": "Custom",
        "custom_action": "stagematchclear"
    }
    """

    def run(
        self,
        context: Context,
        argv: CustomAction.RunArg,
    ) -> CustomAction.RunResult:
        if stagedb_clear():
            print("[stagematchclear] 临时数据库已清空")
        else:
            print("[stagematchclear] 临时数据库不存在，无需清空")
        return CustomAction.RunResult(success=True)
