import numpy as np
import cv2

import importlib.util
from pathlib import Path
import sys
import types

plugins_pkg = types.ModuleType("iopaint.plugins")
plugins_pkg.__path__ = [str(Path(__file__).resolve().parents[1] / "plugins")]
sys.modules.setdefault("iopaint.plugins", plugins_pkg)

_module_path = Path(__file__).resolve().parents[1] / "plugins" / "watermark_detector.py"
_spec = importlib.util.spec_from_file_location("watermark_detector", _module_path)
_watermark_module = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _watermark_module
_spec.loader.exec_module(_watermark_module)
WatermarkDetectorPlugin = _watermark_module.WatermarkDetectorPlugin
from iopaint.schema import RunPluginRequest, WatermarkDetectionMode


def _synthetic_watermark_image():
    image = np.full((160, 260, 3), 210, dtype=np.uint8)
    cv2.putText(
        image,
        "WATERMARK",
        (24, 86),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (80, 80, 80),
        2,
        cv2.LINE_AA,
    )
    return image


def _person_like_image(with_watermark: bool = False):
    image = np.full((220, 180, 3), 226, dtype=np.uint8)
    # 模拟人物主体：头部、身体和衣物边缘，制造自然高频轮廓但不代表水印。
    cv2.circle(image, (90, 58), 28, (190, 160, 135), -1, cv2.LINE_AA)
    cv2.ellipse(image, (90, 146), (54, 70), 0, 0, 360, (88, 132, 184), -1, cv2.LINE_AA)
    cv2.line(image, (52, 110), (128, 110), (58, 102, 150), 3, cv2.LINE_AA)
    cv2.line(image, (70, 104), (58, 190), (58, 102, 150), 2, cv2.LINE_AA)
    cv2.line(image, (110, 104), (122, 190), (58, 102, 150), 2, cv2.LINE_AA)
    if with_watermark:
        cv2.putText(
            image,
            "WM",
            (122, 202),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (72, 72, 72),
            2,
            cv2.LINE_AA,
        )
    return image


def test_run_plugin_request_accepts_watermark_options():
    req = RunPluginRequest(
        name="WatermarkDetector",
        image="data:image/png;base64,AA==",
        watermark_mode="combined",
        watermark_confidence=0.42,
        watermark_dilate=5,
        watermark_max_area_ratio=0.4,
    )

    assert req.watermark_mode == WatermarkDetectionMode.COMBINED
    assert req.watermark_confidence == 0.42
    assert req.watermark_dilate == 5
    assert req.watermark_max_area_ratio == 0.4


def test_cv_ocr_detects_synthetic_text_watermark():
    plugin = WatermarkDetectorPlugin()
    image = _synthetic_watermark_image()
    req = RunPluginRequest(
        name="WatermarkDetector",
        image="data:image/png;base64,AA==",
        watermark_mode="cv_ocr",
        watermark_dilate=2,
    )

    mask = plugin.gen_mask(image, req)

    assert mask.shape == image.shape[:2]
    assert mask.dtype == np.uint8
    assert mask.max() == 255
    assert np.count_nonzero(mask) > 100


def test_combined_mode_merges_cv_and_vl_masks():
    image = _synthetic_watermark_image()

    def fake_vl_backend(_image, _req):
        mask = np.zeros(_image.shape[:2], dtype=np.uint8)
        mask[120:140, 200:240] = 255
        return mask

    plugin = WatermarkDetectorPlugin(vl_backend=fake_vl_backend)
    req = RunPluginRequest(
        name="WatermarkDetector",
        image="data:image/png;base64,AA==",
        watermark_mode="combined",
        watermark_dilate=0,
    )

    mask = plugin.gen_mask(image, req)

    assert mask[130, 220] == 255
    assert np.count_nonzero(mask) > 100


def test_cv_ocr_does_not_mask_person_like_body_without_watermark():
    plugin = WatermarkDetectorPlugin()
    image = _person_like_image(with_watermark=False)
    req = RunPluginRequest(
        name="WatermarkDetector",
        image="data:image/png;base64,AA==",
        watermark_mode="cv_ocr",
        watermark_dilate=0,
        watermark_max_area_ratio=0.1,
    )

    mask = plugin.gen_mask(image, req)
    body_region = mask[92:214, 34:146]

    assert np.count_nonzero(mask) / mask.size < 0.01
    assert np.count_nonzero(body_region) / body_region.size < 0.01


def test_cv_ocr_detects_corner_text_watermark_without_large_body_region():
    plugin = WatermarkDetectorPlugin()
    image = _person_like_image(with_watermark=True)
    req = RunPluginRequest(
        name="WatermarkDetector",
        image="data:image/png;base64,AA==",
        watermark_mode="cv_ocr",
        watermark_dilate=2,
        watermark_max_area_ratio=0.1,
    )

    mask = plugin.gen_mask(image, req)
    watermark_region = mask[178:215, 118:176]
    body_region = mask[92:174, 38:142]

    assert np.count_nonzero(watermark_region) > 20
    assert np.count_nonzero(body_region) / body_region.size < 0.03


def test_vl_sam_without_backend_does_not_use_saliency_body_edges():
    plugin = WatermarkDetectorPlugin()
    image = _person_like_image(with_watermark=False)
    req = RunPluginRequest(
        name="WatermarkDetector",
        image="data:image/png;base64,AA==",
        watermark_mode="vl_sam",
        watermark_dilate=0,
        watermark_max_area_ratio=0.1,
    )

    mask = plugin.gen_mask(image, req)

    assert np.count_nonzero(mask) / mask.size < 0.01


def test_combined_detects_translucent_text_on_person_body_without_outline_noise():
    plugin = WatermarkDetectorPlugin()
    image = _person_like_image(with_watermark=False)
    overlay = image.copy()
    cv2.putText(
        overlay,
        "SAMPLE",
        (38, 142),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.72,
        (235, 235, 235),
        2,
        cv2.LINE_AA,
    )
    image = cv2.addWeighted(overlay, 0.58, image, 0.42, 0)
    req = RunPluginRequest(
        name="WatermarkDetector",
        image="data:image/png;base64,AA==",
        watermark_mode="combined",
        watermark_dilate=2,
        watermark_max_area_ratio=0.1,
    )

    mask = plugin.gen_mask(image, req)
    watermark_region = mask[116:150, 34:156]
    head_region = mask[30:88, 58:122]
    outer_body_edges = np.concatenate(
        [
            mask[100:205, 34:48].reshape(-1),
            mask[100:205, 132:146].reshape(-1),
        ]
    )

    assert np.count_nonzero(watermark_region) > 80
    assert np.count_nonzero(head_region) / head_region.size < 0.02
    assert np.count_nonzero(outer_body_edges) / outer_body_edges.size < 0.05
