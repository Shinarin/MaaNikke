"""
============================================================
  ★ 在此文件中编写你的自定义 Recognition ★
============================================================

使用 @AgentServer.custom_recognition("名称") 装饰器注册，
继承 CustomRecognition 并实现 analyze() 方法即可。

示例见下方模板。
============================================================
"""

from maa.agent.agent_server import AgentServer
from maa.context import Context
from maa.custom_recognition import CustomRecognition
from utils.params import parse_params

import numpy as np
import math
import time

try:
    from PIL import Image as _PILImage
except ImportError:
    _PILImage = None  # type: ignore[assignment]


# ====== 在此处继续添加你的自定义 Reco ======


# =====================================================================
# 自动旋转文字识别器（RotatedOCR）
# =====================================================================
# 流程: 裁剪 ROI → 0°/±3°/±6°/... 交替旋转 → 上采样放大 → 锐化 → OCR
# 依赖: numpy + Pillow（启动时自动安装）


@AgentServer.custom_recognition("RotatedOCR")
class RotatedOCR(CustomRecognition):
    """
    自动旋转 + 图像增强 OCR。

    流程: 0°→±step→±2step→... 交替旋转 → 上采样放大 → 锐化 → OCR

    ── 自定义参数（custom_recognition_param） ──
    {
        "expected": "确认",        // 必填，要识别的文字
        "threshold": 0.8,          // 可选，OCR 置信度，默认 0.8
        "angle_step": 3,           // 可选，每次扩展步长（度），默认 3
        "angle_range": 45,         // 可选，最大范围 ±N°，默认 ±45
        "scale_factor": 2,         // 可选，上采样倍数，1=不放大，默认 2
        "sharpen_strength": 1.0    // 可选，锐化强度，0=关闭，默认 1.0
    }

    ── Pipeline JSON ──
    {
        "recognition": "Custom",
        "custom_recognition": "RotatedOCR",
        "custom_recognition_param": { "expected": "确认" },
        "roi": [500, 300, 200, 80],
        "action": "Click"
    }
    """

    def analyze(
        self,
        context: Context,
        argv: CustomRecognition.AnalyzeArg,
    ) -> CustomRecognition.AnalyzeResult:
        # ── 1. 解析参数 ──
        params = parse_params(argv.custom_recognition_param)
        expected = params.get("expected", "")
        if not expected:
            print("[RotatedOCR] 缺少必填参数 expected")
            return CustomRecognition.AnalyzeResult(box=None, detail={})

        threshold = params.get("threshold", 0.8)
        angle_step = int(params.get("angle_step", 3))
        angle_range = int(params.get("angle_range", 45))
        scale_factor = int(params.get("scale_factor", 2))
        sharpen = float(params.get("sharpen_strength", 1.0))

        # ── 2. 裁剪 ROI ──
        roi = argv.roi
        img = argv.image
        x, y, w, h = roi.x, roi.y, roi.w, roi.h
        img_h, img_w = img.shape[:2]
        x, y = max(0, x), max(0, y)
        w, h = min(w, img_w - x), min(h, img_h - y)
        if w <= 0 or h <= 0:
            print(f"[RotatedOCR] ROI 无效: {roi}")
            return CustomRecognition.AnalyzeResult(box=None, detail={})
        roi_crop = img[y:y+h, x:x+w]

        # ── 3. 生成交替角度序列 ──
        angles: list[float] = [0.0]
        for i in range(1, angle_range // angle_step + 1):
            d = float(i * angle_step)
            angles.append(+d)
            angles.append(-d)
        if angle_range % angle_step != 0:
            angles.append(float(angle_range))
            angles.append(float(-angle_range))

        enhance_info = f"scale×{scale_factor}" if scale_factor > 1 else "不放大"
        if sharpen > 0:
            enhance_info += f" + sharpen×{sharpen}"
        print(f"[RotatedOCR] 搜索 '{expected}'，{len(angles)} 角度，{enhance_info}")

        # ── 4. 逐个角度: 旋转 → 增强 → OCR ──
        for deg in angles:
            rotated = roi_crop if deg == 0.0 else _rotate_image(roi_crop, deg)
            test_img = _enhance_image(rotated, scale_factor, sharpen)

            ocr_pipeline = {
                "_rot": {
                    "recognition": "OCR",
                    "roi": [0, 0, test_img.shape[1], test_img.shape[0]],
                    "expected": expected,
                    "threshold": threshold,
                }
            }
            result = context.run_recognition("_rot", test_img, ocr_pipeline)
            if result and result.hit and result.box is not None:
                # ★ OCR 返回的是增强图坐标 → 映射回原始截图坐标
                orig_box = _map_to_original(
                    ocr_box=result.box,
                    angle=deg,
                    crop_size=(w, h),
                    roi_offset=(x, y),
                    scale=scale_factor,
                )
                print(f"[RotatedOCR] ✅ 角度 {deg:+.0f}° 命中: {expected}"
                      f" → 原图坐标 {orig_box}")
                return CustomRecognition.AnalyzeResult(
                    box=orig_box,
                    detail={"matched_text": expected, "angle": deg},
                )

        # ── 5. 全部失败 ──
        print(f"[RotatedOCR] ❌ 未命中: {expected} ({len(angles)} 个角度全试)")
        return CustomRecognition.AnalyzeResult(box=None, detail={})


# =====================================================================
# RotatedOCR 辅助函数
# =====================================================================


def _rotate_image(img: np.ndarray, angle: float) -> np.ndarray:
    """以图像中心旋转，画布自动扩大保留完整内容，黑边填充。"""
    if _PILImage is None:
        raise ImportError("RotatedOCR 需要 Pillow，请执行: pip install Pillow")
    mode = "L" if img.ndim == 2 else "RGB"
    pil = _PILImage.fromarray(img, mode=mode)
    rotated = pil.rotate(angle, expand=True, fillcolor=0 if mode == "L" else (0, 0, 0))
    return np.array(rotated)


def _enhance_image(img: np.ndarray, scale: int = 2, sharpen_strength: float = 1.0) -> np.ndarray:
    """
    图像增强：上采样放大 + Unsharp Mask 锐化。

    参数:
        img:              numpy 数组 (H, W) 或 (H, W, 3)
        scale:            放大倍数，1=不放大
        sharpen_strength: 锐化强度，0=关闭
    """
    if _PILImage is None:
        raise ImportError("RotatedOCR 需要 Pillow，请执行: pip install Pillow")

    pil = _PILImage.fromarray(img)

    # ── 上采样放大（LANCZOS 算法，公认质量最好的插值） ──
    if scale > 1:
        new_w = pil.width * scale
        new_h = pil.height * scale
        pil = pil.resize((new_w, new_h), _PILImage.Resampling.LANCZOS)

    # ── Unsharp Mask 锐化 ──
    # 原理: 原图 + strength×(原图 - 高斯模糊) → 边缘更锐利
    if sharpen_strength > 0:
        from PIL import ImageFilter
        blurred = pil.filter(ImageFilter.GaussianBlur(radius=2))
        orig_arr = np.array(pil, dtype=np.float32)
        blur_arr = np.array(blurred, dtype=np.float32)
        sharpened = orig_arr + sharpen_strength * (orig_arr - blur_arr)
        sharpened = np.clip(sharpened, 0, 255).astype(np.uint8)
        return sharpened

    return np.array(pil)


def _map_to_original(
    ocr_box,             # MaaFramework Rect 对象 (x, y, w, h)
    angle: float,        # 旋转角度
    crop_size: tuple[int, int],  # 裁剪 ROI 的 (w, h)
    roi_offset: tuple[int, int], # ROI 在原截图中的 (x, y)
    scale: int,          # 上采样倍数
) -> tuple[int, int, int, int]:
    """
    将 OCR 在增强图上的坐标映射回原始截图坐标。

    变换链: 增强图 →(÷scale)→ 旋转图 →(逆旋转)→ 裁剪图 →(+ROI偏移)→ 原图
    """
    crop_w, crop_h = crop_size
    roi_x, roi_y = roi_offset

    # ── 1. 逆缩放：增强图 → 旋转图 ──
    rx = ocr_box.x / scale
    ry = ocr_box.y / scale
    rw = ocr_box.w / scale
    rh = ocr_box.h / scale
    rcx = rx + rw / 2.0   # 文字中心在旋转图中的坐标
    rcy = ry + rh / 2.0

    if angle == 0.0:
        ox = rcx + roi_x - rw / 2.0
        oy = rcy + roi_y - rh / 2.0
        return (int(ox), int(oy), int(rw), int(rh))

    # ── 2. 逆旋转：旋转图 → 裁剪图 ──
    # 先算旋转后图像的尺寸（与 _rotate_image 中 Pillow expand 一致）
    rad = math.radians(abs(angle))
    cos_a = abs(math.cos(rad))
    sin_a = abs(math.sin(rad))
    rotated_w = int(crop_h * sin_a + crop_w * cos_a)
    rotated_h = int(crop_h * cos_a + crop_w * sin_a)

    # 旋转中心：裁剪图中心和旋转图中心
    rot_cx = rotated_w / 2.0
    rot_cy = rotated_h / 2.0
    crop_cx = crop_w / 2.0
    crop_cy = crop_h / 2.0

    # 将文字中心平移到旋转中心原点 → 反方向旋转 → 再平移到裁剪图中心
    dx = rcx - rot_cx
    dy = rcy - rot_cy
    rad_neg = math.radians(-angle)
    cx_crop = dx * math.cos(rad_neg) - dy * math.sin(rad_neg) + crop_cx
    cy_crop = dx * math.sin(rad_neg) + dy * math.cos(rad_neg) + crop_cy

    # ── 3. +ROI 偏移：裁剪图 → 原始截图 ──
    ox = cx_crop + roi_x - rw / 2.0
    oy = cy_crop + roi_y - rh / 2.0
    return (int(ox), int(oy), int(rw), int(rh))


# =====================================================================
# 日期字段识别组合：recodatebase / userecodatebase
# =====================================================================
# 两者通过"临时字段"协作：
#   recodatebase    在 roi 内分两轮 OCR 扫描日期字段（第 1 轮 1-12→1-6，
#                   第 2 轮 1-7→1-1），命中值写入临时字段（不存在时先以
#                   默认值 "1-1" 创建）
#   userecodatebase 以临时字段当前值为 expected 做 OCR（只读，不清除）
# 临时字段为 agent 进程内全局唯一，模块加载即初始化为默认值 "1-1"，
# 进程结束即销毁；+1 / 重置由 custom action addrecodatebase /
# clearrecodatebase 显式执行（my_actions.py），三者共用下方 datebase_*
# 辅助函数；清除即重置为默认值，全程不留空缺。

_DATEBASE_KEY = "datebase"
_DATEBASE_DEFAULT = "1-1"
# 进程启动（模块加载）即初始化为默认值；清除（datebase_clear）也是重置为
# 默认值而非删除——临时字段全程存在，不留空缺
_RECO_TEMP_STORE: dict[str, str] = {_DATEBASE_KEY: _DATEBASE_DEFAULT}

# 两轮扫描的字段区间：1-7 / 1-6 为边界重叠（两轮都扫，刻意双保险）
_DATEBASE_FIELDS_R1 = [f"1-{d}" for d in range(12, 5, -1)]  # 1-12 → 1-6
_DATEBASE_FIELDS_R2 = [f"1-{d}" for d in range(7, 0, -1)]   # 1-7 → 1-1


def datebase_get() -> str:
    """读临时字段当前值；正常必有值（模块加载即初始化），兜底返回默认值。"""
    return _RECO_TEMP_STORE.get(_DATEBASE_KEY, _DATEBASE_DEFAULT)


def datebase_set(value: str) -> None:
    """写入临时字段（recodatebase 命中时调用）。"""
    _RECO_TEMP_STORE[_DATEBASE_KEY] = value


def datebase_add() -> str:
    """临时字段日部分 +1 并写回，返回新值；唯独 1-12 改为 -1（得 1-11）。
    字段不存在时视为默认值 "1-1"（+1 得 "1-2"）；
    格式异常（非 "月-日" 数字）时不改动并返回原值。"""
    value = datebase_get()
    try:
        month_s, day_s = value.split("-")
        month, day = int(month_s), int(day_s)
    except ValueError:
        print(f"[datebase] ⚠ 临时字段格式异常: {value!r}，未执行 +1")
        return value
    if day == 12:
        day -= 1  # 唯独 1-12 减 1，其余一律 +1
    else:
        day += 1
    new_value = f"{month}-{day}"
    _RECO_TEMP_STORE[_DATEBASE_KEY] = new_value
    return new_value


def datebase_clear() -> bool:
    """临时字段重置为默认值 "1-1"（重置而非删除，不产生空缺）。
    返回重置前是否为非默认值（即是否确有内容被清掉）。"""
    old = _RECO_TEMP_STORE.get(_DATEBASE_KEY)
    _RECO_TEMP_STORE[_DATEBASE_KEY] = _DATEBASE_DEFAULT
    return old is not None and old != _DATEBASE_DEFAULT


def _clamp_roi(img: np.ndarray, roi) -> tuple[int, int, int, int, np.ndarray] | None:
    """按 roi 裁剪图像并做边界钳制，返回 (x, y, w, h, crop)；roi 无效返回 None。"""
    x, y, w, h = roi.x, roi.y, roi.w, roi.h
    img_h, img_w = img.shape[:2]
    x, y = max(0, x), max(0, y)
    w, h = min(w, img_w - x), min(h, img_h - y)
    if w <= 0 or h <= 0:
        return None
    return x, y, w, h, img[y:y + h, x:x + w]


def _run_ocr(context: Context, img: np.ndarray, expected: str, threshold: float):
    """对整张小图跑一次内置 OCR，命中返回 box（图内坐标），未命中返回 None。"""
    ocr_pipeline = {
        "_dateocr": {
            "recognition": "OCR",
            "roi": [0, 0, img.shape[1], img.shape[0]],
            "expected": expected,
            "threshold": threshold,
        }
    }
    result = context.run_recognition("_dateocr", img, ocr_pipeline)
    if result and result.hit and result.box is not None:
        return result.box
    return None


def _otsu_threshold(gray: np.ndarray) -> int:
    """经典 Otsu 自动阈值（numpy 实现，无需 OpenCV）。"""
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


def _preprocess_for_ocr(
    img: np.ndarray,
    scale: int = 2,
    binarize: bool = True,
) -> tuple[np.ndarray, int]:
    """
    OCR 前处理：灰度 → 上采样 → autocontrast 对比度拉伸 →（可选）Otsu 二值化+自动反色。
    目的：让数字/字母更醒目，抹掉花背景对字形的干扰。

    返回 (处理后的图, 实际缩放倍数)；图固定为 3 通道 uint8——绑定层
    ImageBuffer.set 硬编码 CV_8UC3，单通道图会导致原生层越界读内存。
    调用方需将 OCR 命中的 box ÷ 倍数映射回原图。
    Pillow 不可用时原样返回 (img, 1)。
    """
    if _PILImage is None:
        print("[reco] ⚠ Pillow 不可用，跳过图像前处理")
        return img, 1

    from PIL import ImageOps, ImageFilter

    # ── 灰度 + 上采样 ──
    # argv.image 为 BGR，fromarray 按 RGB 解释会让 R/B 权重互换，
    # 仅影响灰度值的轻微偏差，对 OCR 目的可忽略
    pil = _PILImage.fromarray(img).convert("L")
    if scale > 1:
        pil = pil.resize((pil.width * scale, pil.height * scale),
                         _PILImage.Resampling.LANCZOS)

    # ── 对比度拉伸（cutoff=1 去掉头尾 1% 极端像素，淡化灰暗背景） ──
    pil = ImageOps.autocontrast(pil, cutoff=1)

    if not binarize:
        # 不二值化：补一道锐化让字形更清晰
        pil = pil.filter(ImageFilter.UnsharpMask(radius=2, percent=100, threshold=3))
        # ★ 必须转 3 通道：绑定层 ImageBuffer.set 硬编码 CV_8UC3，
        #   单通道图会让原生层按 3 倍长度越界读内存（access violation）
        return np.array(pil.convert("RGB")), scale

    # ── Otsu 二值化 + 自动反色 ──
    # 深底浅字（均值<127）反转为黑字白底，贴近 OCR 模型的常见训练分布
    gray = np.array(pil)
    t = _otsu_threshold(gray)
    if gray.mean() < 127:
        binary = np.where(gray > t, 0, 255)
    else:
        binary = np.where(gray > t, 255, 0)
    # ★ 单通道二值图复制为 3 通道（理由同上：原生层按 CV_8UC3 读取）
    return np.stack([binary.astype(np.uint8)] * 3, axis=-1), scale


def _scan_date_fields(
    context: Context,
    raw_crop: np.ndarray,
    proc_crop: np.ndarray | None,
    proc_scale: int,
    offset: tuple[int, int],
    threshold: float,
    fields: list[str],
    tries_per_image: int = 5,
) -> tuple[str, tuple[int, int, int, int]] | None:
    """
    按 fields 顺序扫描。每个字段两段式识别：
      1. 先用原图 raw_crop OCR tries_per_image 次；
      2. 未命中再用处理后图 proc_crop OCR tries_per_image 次；
      3. 两段都未命中才进入下一个字段。
    proc_crop 为 None 时跳过第二段（preprocess=false）。
    命中返回 (字段, 原图坐标 box)，全部未命中返回 None。
    """
    ox, oy = offset
    for field in fields:
        # 第一段：原图识别
        for _ in range(tries_per_image):
            box = _run_ocr(context, raw_crop, field, threshold)
            if box is not None:
                return field, (box.x + ox, box.y + oy, box.w, box.h)
        # 第二段：处理后图识别（box 需 ÷scale 映射回原图）
        if proc_crop is not None:
            for _ in range(tries_per_image):
                box = _run_ocr(context, proc_crop, field, threshold)
                if box is not None:
                    return field, (
                        int(box.x / proc_scale + ox), int(box.y / proc_scale + oy),
                        int(box.w / proc_scale), int(box.h / proc_scale),
                    )
    return None


@AgentServer.custom_recognition("recodatebase")
class RecoDateBase(CustomRecognition):
    """
    日期字段扫描：分两轮在 roi 内 OCR 日期字段，命中即写入临时字段。

    ── 执行流程 ──
    第 1 轮（1-12→1-6）: 每个字段两段式识别: 先用原图 OCR triesperimage 次
              （默认 5），未命中再用处理后图 OCR 同样次数，然后才进入下一个
              字段（preprocess=false 时只有原图段）；命中即停止扫描
    第 1 轮全未命中: 手动调用 action_node 指定的独立动作节点
              （context.run_action，通常为滑动刷新列表），等待后重新截图
    第 2 轮（1-7→1-1）: 同两段式再扫一遍；无论是否命中都返回成功

    ※ 跳过 action 的方案（扫描节点与动作节点分离）：本节点在 pipeline 中的
      action 必须写死 DoNothing，刷新动作放在 action_node 指向的独立节点里。
      识别命中后框架执行 DoNothing 自然进入 next，全程不做任何
      override_pipeline——节点可无限次循环重入，每次行为完全一致。
      （旧方案把 action 覆盖为 DoNothing 会污染整个任务，循环重入时手动
      action 变成 DoNothing 导致刷新失效，已废弃。）
    ※ 未配置 action_node 时：第 1 轮未命中不执行动作，第 2 轮沿用当前截图。

    ── 自定义参数（custom_recognition_param） ──
    {
        "threshold": 0.8,          // 可选，OCR 置信度，默认 0.8
        "triesperimage": 5,        // 可选，每个字段每张图的 OCR 次数，默认 5
        "action_node": "xxx_swipe",// 可选，首轮未命中时手动执行的独立动作节点名
        "post_action_wait": 1000,  // 可选，手动 action 后等待毫秒数，默认 1000
        "preprocess": true,        // 可选，OCR 前图像前处理总开关，默认 true
        "preprocess_scale": 2,     // 可选，前处理上采样倍数，默认 2
        "binarize": true           // 可选，前处理是否 Otsu 二值化+自动反色，默认 true
    }
    前处理管线: 灰度 → 上采样 → autocontrast →（可选）Otsu 二值化+自动反色，
    让数字/字母更醒目、背景干扰最小化；每轮扫描只处理一次。

    ── 实测建议 ──
    默认参数为通用取向。游戏里实测时：
    1. 若 OCR 反而变差（如字体带渐变/描边被二值化吃掉），先试 "binarize": false
    2. 漏识别则降 threshold（如 0.7）
    3. 字特别小可把 preprocess_scale 提到 3

    ── Pipeline JSON ──
    {
        "recognition": {
            "type": "Custom",
            "param": {
                "custom_recognition": "recodatebase",
                "custom_recognition_param": { "action_node": "task_datebase_swipe" },
                "roi": [x, y, w, h]
            }
        },
        "action": { "type": "DoNothing" },
        "next": ["使用临时字段的节点（userecodatebase）"]
    }
    // 独立动作节点（不进任何 next 链，仅供 action_node 手动调用）：
    "task_datebase_swipe": {
        "action": { "type": "Swipe", "param": { ... } }
    }

    ── 注意 ──
    1. 两轮字段区间在 1-7 / 1-6 处重叠（刻意双保险）；1-1 只在第 2 轮扫描。
    2. 临时字段的 +1 / 清除由 custom action addrecodatebase /
       clearrecodatebase 执行；userecodatebase 只读不清除。
    """

    def analyze(
        self,
        context: Context,
        argv: CustomRecognition.AnalyzeArg,
    ) -> CustomRecognition.AnalyzeResult:
        # ── 1. 解析参数 ──
        params = parse_params(argv.custom_recognition_param)
        threshold = float(params.get("threshold", 0.8))
        tries_per_image = max(1, int(params.get("triesperimage", 5)))
        action_node = str(params.get("action_node", "")).strip()
        post_action_wait = int(params.get("post_action_wait", 1000))
        preprocess = bool(params.get("preprocess", True))
        preprocess_scale = int(params.get("preprocess_scale", 2))
        binarize = bool(params.get("binarize", True))

        # ── 2. 裁剪 ROI + 图像前处理（灰度/放大/二值化，让数字更醒目） ──
        clamped = _clamp_roi(argv.image, argv.roi)
        if clamped is None:
            print(f"[recodatebase] ROI 无效: {argv.roi}")
            return CustomRecognition.AnalyzeResult(box=None, detail={})
        x, y, w, h, roi_crop = clamped
        if preprocess:
            proc_crop, proc_scale = _preprocess_for_ocr(roi_crop, preprocess_scale, binarize)
        else:
            proc_crop, proc_scale = None, 1

        # ── 3. 临时字段：不存在则以默认值创建 ──
        _RECO_TEMP_STORE.setdefault(_DATEBASE_KEY, _DATEBASE_DEFAULT)

        # ── 4. 第 1 轮扫描（1-12→1-6，每字段两段式，各 triesperimage 次） ──
        hit = _scan_date_fields(context, roi_crop, proc_crop, proc_scale, (x, y), threshold,
                                _DATEBASE_FIELDS_R1, tries_per_image)
        if hit is not None:
            field, box = hit
            datebase_set(field)
            print(f"[recodatebase] 第 1 轮命中 {field}，临时字段已更新")
            # 节点 action 在 pipeline 中固定为 DoNothing → 命中后自然进 next，
            # 无需任何 override，节点可循环重入
            return CustomRecognition.AnalyzeResult(
                box=box, detail={"matched": field, "round": 1}
            )

        # ── 5. 第 1 轮未命中：手动执行 action_node 动作（如滑动刷新） ──
        if action_node:
            print(f"[recodatebase] 第 1 轮未命中，手动执行动作节点 {action_node} 后重试")
            act = context.run_action(action_node, (x, y, w, h))
            if act is None or not act.success:
                print("[recodatebase] ⚠ 手动 action 未成功，仍继续第 2 轮")
            time.sleep(post_action_wait / 1000)
            # 重新截图（action 后画面已变化，argv.image 是旧图）
            try:
                controller = context.tasker.controller
                controller.post_screencap().wait()
                fresh_img = controller.cached_image
            except RuntimeError as e:
                print(f"[recodatebase] ⚠ 重新截图失败: {e}，第 2 轮沿用旧图")
                fresh_img = argv.image
        else:
            print("[recodatebase] 第 1 轮未命中，未配置 action_node，第 2 轮沿用当前截图")
            fresh_img = argv.image

        fresh_clamped = _clamp_roi(fresh_img, argv.roi)
        if fresh_clamped is None:
            print(f"[recodatebase] 新截图 ROI 无效: {argv.roi}")
            fresh_crop = roi_crop
        else:
            fresh_crop = fresh_clamped[4]

        # ── 6. 第 2 轮扫描（1-7→1-1，同参数前处理）：无论结果如何都算成功 ──
        if preprocess:
            fresh_proc, fresh_scale = _preprocess_for_ocr(fresh_crop, preprocess_scale, binarize)
        else:
            fresh_proc, fresh_scale = None, 1
        hit = _scan_date_fields(context, fresh_crop, fresh_proc, fresh_scale, (x, y), threshold,
                                _DATEBASE_FIELDS_R2, tries_per_image)
        if hit is not None:
            field, _ = hit
            datebase_set(field)
            print(f"[recodatebase] 第 2 轮命中 {field}，临时字段已更新")
        else:
            print(f"[recodatebase] 第 2 轮未命中，临时字段保持 {datebase_get()}")
        return CustomRecognition.AnalyzeResult(
            box=(x, y, w, h),
            detail={"round": 2, "temp": datebase_get()},
        )


@AgentServer.custom_recognition("userecodatebase")
class UseRecoDateBase(CustomRecognition):
    """
    以临时字段（recodatebase 写入，默认 "1-1"）为 expected 在 roi 内做 OCR。
    只读识别，命中后不清除临时字段；+1 / 清除由 custom action
    addrecodatebase / clearrecodatebase 在 pipeline 中显式执行。

    ── 识别方式 ──
    每次 analyze 调用只用一张图识别一次，原图与处理后图逐次交替轮换，
    以提高识别率；识别次数不设上限——未命中时框架会在节点 timeout 内
    反复调用本方法，节奏由 pipeline 节点的 timeout 字段控制。
    preprocess=false 时固定只用原图。

    ── 自定义参数（custom_recognition_param） ──
    {
        "threshold": 0.8,          // 可选，OCR 置信度，默认 0.8
        "preprocess": true,        // 可选，OCR 前图像前处理总开关，默认 true
        "preprocess_scale": 2,     // 可选，前处理上采样倍数，默认 2
        "binarize": true           // 可选，前处理是否 Otsu 二值化+自动反色，默认 true
    }
    前处理管线与 recodatebase 相同: 灰度 → 上采样 → autocontrast →（可选）二值化。
    调参实测建议见 recodatebase docstring 的"实测建议"一节。

    ── Pipeline JSON ──
    {
        "recognition": {
            "type": "Custom",
            "param": {
                "custom_recognition": "userecodatebase",
                "custom_recognition_param": {},
                "roi": [x, y, w, h]
            }
        },
        "action": { "type": "Click" },
        "next": ["下一节点"]
    }
    """

    # 交替标记：本次 analyze 调用是否用处理后图（实例在注册时创建并复用，
    # 属性随调用持久翻转；preprocess=false 时恒用原图）
    _use_preprocessed_next = False

    def analyze(
        self,
        context: Context,
        argv: CustomRecognition.AnalyzeArg,
    ) -> CustomRecognition.AnalyzeResult:
        params = parse_params(argv.custom_recognition_param)
        threshold = float(params.get("threshold", 0.8))
        preprocess = bool(params.get("preprocess", True))
        preprocess_scale = int(params.get("preprocess_scale", 2))
        binarize = bool(params.get("binarize", True))
        expected = datebase_get()

        # ── 裁剪 ROI ──
        clamped = _clamp_roi(argv.image, argv.roi)
        if clamped is None:
            print(f"[userecodatebase] ROI 无效: {argv.roi}")
            return CustomRecognition.AnalyzeResult(box=None, detail={})
        x, y, _, _, roi_crop = clamped

        # ── 交替识别：每次 analyze 调用只用一张图识别一次，原图 ↔ 处理后图
        #    逐次轮换；未命中时由框架按节点 timeout 反复调用本方法 ──
        if preprocess:
            use_preprocessed = self._use_preprocessed_next
            self._use_preprocessed_next = not self._use_preprocessed_next
        else:
            use_preprocessed = False
        src = "处理后图" if use_preprocessed else "原图"

        if use_preprocessed:
            img_for_ocr, scale = _preprocess_for_ocr(roi_crop, preprocess_scale, binarize)
        else:
            img_for_ocr, scale = roi_crop, 1

        # ── OCR 识别临时字段 ──
        box = _run_ocr(context, img_for_ocr, expected, threshold)
        if box is None:
            print(f"[userecodatebase] 未命中({src}): {expected}")
            return CustomRecognition.AnalyzeResult(box=None, detail={})

        # ── 命中：只读，不清除临时字段（清除由 clearrecodatebase action 负责） ──
        print(f"[userecodatebase] 命中({src}) {expected}")
        # 处理后图的 box 需 ÷scale 还原，原图 scale=1 不受影响 → +ROI 偏移映射回原图
        return CustomRecognition.AnalyzeResult(
            box=(int(box.x / scale + x), int(box.y / scale + y),
                 int(box.w / scale), int(box.h / scale)),
            detail={"matched": expected, "source": src},
        )
