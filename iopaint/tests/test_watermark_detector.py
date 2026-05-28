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
