from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

import cv2
import numpy as np
from loguru import logger

from iopaint.plugins.base_plugin import BasePlugin
from iopaint.schema import RunPluginRequest, WatermarkDetectionMode


@dataclass
class WatermarkCandidate:
    mask: np.ndarray
    score: float
    source: str


class WatermarkDetectorPlugin(BasePlugin):
    """Generate editable masks for visible watermarks.

    The plugin deliberately focuses on mask generation and leaves actual removal
    to IOPaint's existing inpainting models. 255 means area to repaint.
    """

    name = "WatermarkDetector"
    support_gen_image = False
    support_gen_mask = True

    def __init__(self, vl_backend: Optional[Callable[[np.ndarray, RunPluginRequest], np.ndarray]] = None):
        self._vl_backend = vl_backend
        super().__init__()

    def check_dep(self):
        return None

    def gen_mask(self, rgb_np_img, req: RunPluginRequest) -> np.ndarray:
        image = self._limit_image(rgb_np_img)
        mode = req.watermark_mode
        masks: list[np.ndarray] = []

        if mode in (WatermarkDetectionMode.CV_OCR, WatermarkDetectionMode.COMBINED):
            masks.append(self.detect_cv_ocr(image, req))

        if mode in (WatermarkDetectionMode.VL_SAM, WatermarkDetectionMode.COMBINED):
            masks.append(self.detect_vl_sam(image, req))

        merged = self.merge_masks(masks, image.shape[:2])
        return self.post_process_mask(merged, req)

    def detect_cv_ocr(self, rgb_np_img: np.ndarray, req: RunPluginRequest) -> np.ndarray:
        """Lightweight CV/OCR-like detector for text, logos and translucent overlays.

        No heavy OCR dependency is required for the baseline: text-like regions are
        approximated by high-contrast connected components and edge density.
        """

        gray = cv2.cvtColor(rgb_np_img, cv2.COLOR_RGB2GRAY)
        height, width = gray.shape[:2]

        # Dark/bright text and logo strokes against the local background.
        blackhat_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (17, 7))
        blackhat = cv2.morphologyEx(gray, cv2.MORPH_BLACKHAT, blackhat_kernel)
        tophat = cv2.morphologyEx(gray, cv2.MORPH_TOPHAT, blackhat_kernel)
        contrast = cv2.max(blackhat, tophat)
        _, contrast_mask = cv2.threshold(
            contrast, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU
        )

        # Edge-dense transparent marks and signatures.
        edges = cv2.Canny(gray, 80, 180)
        edge_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (9, 3))
        edge_mask = cv2.dilate(edges, edge_kernel, iterations=1)

        # Low-saturation light overlays are common for watermark text/logos.
        hsv = cv2.cvtColor(rgb_np_img, cv2.COLOR_RGB2HSV)
        low_sat = cv2.inRange(hsv[:, :, 1], 0, 70)
        bright = cv2.inRange(hsv[:, :, 2], 145, 255)
        low_sat_bright = cv2.bitwise_and(low_sat, bright)

        raw = cv2.bitwise_or(contrast_mask, edge_mask)
        raw = cv2.bitwise_or(raw, cv2.bitwise_and(low_sat_bright, edge_mask))
        raw = self._keep_plausible_components(raw, width, height, req.watermark_max_area_ratio)
        return raw

    def detect_vl_sam(self, rgb_np_img: np.ndarray, req: RunPluginRequest) -> np.ndarray:
        """Open-vocabulary detector/SAM adapter.

        A real Florence/GroundingDINO/SAM backend can be injected through
        ``vl_backend``. When it is not installed, use a deterministic CV fallback
        so the UI can still exercise the strategy without breaking app startup.
        """

        if self._vl_backend is not None:
            try:
                mask = self._vl_backend(rgb_np_img, req)
                return self._as_gray_mask(mask, rgb_np_img.shape[:2])
            except Exception as exc:  # pragma: no cover - defensive logging
                logger.warning(f"Watermark open-vocabulary backend failed: {exc}")

        logger.info(
            "Watermark open-vocabulary backend is not configured; "
            "falling back to saliency/text-like CV mask."
        )
        return self._detect_saliency_fallback(rgb_np_img, req)

    def merge_masks(self, masks: list[np.ndarray], shape: tuple[int, int]) -> np.ndarray:
        merged = np.zeros(shape, dtype=np.uint8)
        for mask in masks:
            if mask is None:
                continue
            merged = cv2.bitwise_or(merged, self._as_gray_mask(mask, shape))
        return merged

    def post_process_mask(self, mask: np.ndarray, req: RunPluginRequest) -> np.ndarray:
        mask = self._as_gray_mask(mask, mask.shape[:2])
        if req.watermark_dilate > 0:
            kernel_size = max(1, int(req.watermark_dilate))
            kernel = cv2.getStructuringElement(
                cv2.MORPH_ELLIPSE, (kernel_size * 2 + 1, kernel_size * 2 + 1)
            )
            mask = cv2.dilate(mask, kernel, iterations=1)
        close_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, close_kernel)
        mask = cv2.medianBlur(mask, 3)
        _, mask = cv2.threshold(mask, 127, 255, cv2.THRESH_BINARY)
        return mask

    def _detect_saliency_fallback(self, rgb_np_img: np.ndarray, req: RunPluginRequest) -> np.ndarray:
        gray = cv2.cvtColor(rgb_np_img, cv2.COLOR_RGB2GRAY)
        lap = cv2.Laplacian(gray, cv2.CV_8U, ksize=3)
        _, mask = cv2.threshold(lap, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
        height, width = gray.shape[:2]
        return self._keep_plausible_components(mask, width, height, req.watermark_max_area_ratio)

    def _keep_plausible_components(
        self, mask: np.ndarray, width: int, height: int, max_area_ratio: float
    ) -> np.ndarray:
        num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
        output = np.zeros((height, width), dtype=np.uint8)
        image_area = float(width * height)
        min_area = max(8, int(image_area * 0.00003))
        max_area = max(min_area, int(image_area * max_area_ratio))

        for label in range(1, num_labels):
            x, y, w, h, area = stats[label]
            if area < min_area or area > max_area:
                continue
            if w > width * 0.95 and h > height * 0.95:
                continue
            # Keep text/logo-like components: thin text, strips, corner badges or signatures.
            aspect = w / max(h, 1)
            touches_border = x < width * 0.08 or y < height * 0.08 or x + w > width * 0.92 or y + h > height * 0.92
            if aspect >= 1.2 or touches_border or area < image_area * 0.02:
                output[labels == label] = 255
        return output

    def _as_gray_mask(self, mask: np.ndarray, shape: tuple[int, int]) -> np.ndarray:
        if mask.ndim == 3:
            mask = cv2.cvtColor(mask, cv2.COLOR_RGB2GRAY)
        if mask.shape[:2] != shape:
            mask = cv2.resize(mask, (shape[1], shape[0]), interpolation=cv2.INTER_NEAREST)
        _, mask = cv2.threshold(mask.astype(np.uint8), 127, 255, cv2.THRESH_BINARY)
        return mask

    def _limit_image(self, rgb_np_img: np.ndarray) -> np.ndarray:
        max_pixels = 4096 * 4096
        if rgb_np_img.shape[0] * rgb_np_img.shape[1] > max_pixels:
            raise ValueError("Image is too large for automatic watermark detection")
        return rgb_np_img
