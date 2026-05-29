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
        # Translucent text printed over a person can have weak global contrast.
        # Subtract a blurred local background to recover text strokes while
        # keeping broad body contours as one large component that will be
        # filtered out below.
        local_background = cv2.GaussianBlur(gray, (31, 31), 0)
        light_strokes = cv2.subtract(gray, local_background)
        _, light_text_mask = cv2.threshold(
            light_strokes, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU
        )

        # Edge-dense transparent marks and signatures. Edges are only used
        # together with low-saturation bright overlays to avoid selecting
        # natural body/clothing contours as watermarks.
        edges = cv2.Canny(gray, 80, 180)
        edge_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (9, 3))
        edge_mask = cv2.dilate(edges, edge_kernel, iterations=1)

        # Low-saturation light overlays are common for watermark text/logos.
        hsv = cv2.cvtColor(rgb_np_img, cv2.COLOR_RGB2HSV)
        low_sat = cv2.inRange(hsv[:, :, 1], 0, 70)
        bright = cv2.inRange(hsv[:, :, 2], 145, 255)
        low_sat_bright = cv2.bitwise_and(low_sat, bright)

        low_sat_edge = cv2.bitwise_and(low_sat_bright, edge_mask)
        # Filter every cue before merging.  If all cues are OR'ed first, weak
        # translucent text can accidentally connect to broad person contours and
        # then be rejected as one oversized body-like component.
        contrast_text = self._keep_plausible_components(
            contrast_mask, width, height, req.watermark_max_area_ratio
        )
        light_text = self._keep_plausible_components(
            light_text_mask, width, height, min(req.watermark_max_area_ratio, 0.03)
        )
        low_sat_text = self._keep_plausible_components(
            low_sat_edge, width, height, min(req.watermark_max_area_ratio, 0.03)
        )
        low_sat_text = cv2.bitwise_and(low_sat_text, light_text)
        return cv2.bitwise_or(cv2.bitwise_or(contrast_text, light_text), low_sat_text)

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
            "returning an empty mask to avoid saliency false positives."
        )
        return np.zeros(rgb_np_img.shape[:2], dtype=np.uint8)

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
            # Cap dilation by image size so small false positives are not
            # expanded into visible body/object repaint regions.
            height, width = mask.shape[:2]
            adaptive_cap = max(1, int(round(min(width, height) * 0.015)))
            kernel_size = max(0, min(int(req.watermark_dilate), adaptive_cap))
            horizontal_radius = max(1, kernel_size)
            kernel = cv2.getStructuringElement(
                cv2.MORPH_ELLIPSE, (horizontal_radius * 2 + 1, 1)
            )
            mask = cv2.dilate(mask, kernel, iterations=1)
        close_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 3))
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, close_kernel)
        mask = cv2.medianBlur(mask, 3)
        _, mask = cv2.threshold(mask, 127, 255, cv2.THRESH_BINARY)
        return self._enforce_mask_safety(mask, req.watermark_max_area_ratio)

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
            # Keep text/logo-like components and reject thick central blobs that
            # usually correspond to people, clothing, or foreground objects.
            aspect = w / max(h, 1)
            bbox_area = float(max(w * h, 1))
            fill_ratio = area / bbox_area
            component_area_ratio = area / image_area
            touches_border = (
                x < width * 0.08
                or y < height * 0.08
                or x + w > width * 0.92
                or y + h > height * 0.92
            )
            central_large_blob = (
                not touches_border
                and w > width * 0.22
                and h > height * 0.18
                and aspect < 1.8
            )
            if central_large_blob:
                continue
            long_text_line = aspect >= 2.0 and h <= height * 0.22
            text_like_shape = (
                aspect >= 1.15
                or h <= height * 0.16
                or w <= width * 0.28
            )
            text_like_area = (
                component_area_ratio <= 0.035
                or (long_text_line and component_area_ratio <= max_area_ratio)
            )
            text_like = (
                text_like_shape
                and text_like_area
                and (
                    0.08 <= fill_ratio <= 0.98
                    # Morphological text cues may merge a whole word into a
                    # nearly solid, very wide strip.  Keep that case while the
                    # central_large_blob gate still rejects body-shaped blobs.
                    or (long_text_line and fill_ratio <= 1.0)
                )
            )
            small_mark = component_area_ratio <= min(max_area_ratio * 0.25, 0.015)
            border_mark = touches_border and component_area_ratio <= min(max_area_ratio * 0.5, 0.03)
            if text_like or small_mark or border_mark:
                output[labels == label] = 255
        return output

    def _enforce_mask_safety(self, mask: np.ndarray, max_area_ratio: float) -> np.ndarray:
        height, width = mask.shape[:2]
        image_area = float(width * height)
        max_component_area = int(image_area * max_area_ratio)
        safe_total_area = int(image_area * min(max_area_ratio, 0.12))
        num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
        kept: list[tuple[int, int]] = []
        for label in range(1, num_labels):
            x, y, w, h, area = stats[label]
            if area <= 0 or area > max_component_area:
                continue
            aspect = w / max(h, 1)
            bbox_area = float(max(w * h, 1))
            fill_ratio = area / bbox_area
            component_area_ratio = area / image_area
            touches_border = (
                x < width * 0.08
                or y < height * 0.08
                or x + w > width * 0.92
                or y + h > height * 0.92
            )
            small_isolated_noise = (
                component_area_ratio <= 0.002
                and not touches_border
                and (w <= width * 0.12 or h <= height * 0.06)
                and not (aspect >= 1.8 and fill_ratio >= 0.08)
            )
            if small_isolated_noise:
                continue
            if not touches_border and w > width * 0.3 and h > height * 0.2 and aspect < 1.8:
                continue
            kept.append((label, int(area)))

        output = np.zeros_like(mask)
        used_area = 0
        for label, area in sorted(kept, key=lambda item: item[1], reverse=True):
            if used_area + area > safe_total_area:
                continue
            output[labels == label] = 255
            used_area += area
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
