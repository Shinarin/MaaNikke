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
