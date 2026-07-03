"""
EAST Text Detection Service
────────────────────────────
Uses OpenCV's EAST (Efficient and Accurate Scene Text Detector) to locate
text regions in an image before passing those regions to the OCR engine.

EAST model download:
    wget https://raw.githubusercontent.com/oyyd/frozen_east_text_detection.pb/master/frozen_east_text_detection.pb
    # Place in: models/frozen_east_text_detection.pb

Reference:
    Zhou et al., "EAST: An Efficient and Accurate Scene Text Detector", CVPR 2017
"""

import logging
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

from backend.config import settings

logger = logging.getLogger(__name__)

# EAST output layer names
_EAST_LAYERS = [
    "feature_fusion/Conv_7/Sigmoid",   # Geometry scores
    "feature_fusion/concat_3",         # Bounding box geometry
]


class EASTDetector:
    """
    Wraps OpenCV DNN EAST model for text region detection.

    The model outputs:
    - scores: confidence that a cell contains text
    - geometry: encoded bounding box offsets per cell

    After decoding geometry and applying NMS, returns a list of
    (x, y, w, h) bounding boxes in original image pixel space.
    """

    def __init__(self):
        self._net: Optional[cv2.dnn.Net] = None
        self._model_path = Path(settings.east_model_path)
        self._conf_threshold = settings.east_confidence_threshold
        self._nms_threshold = settings.east_nms_threshold

    def _load_model(self):
        if self._net is not None:
            return
        if not self._model_path.exists():
            raise FileNotFoundError(
                f"EAST model not found at '{self._model_path}'. "
                "Download from: https://github.com/oyyd/frozen_east_text_detection.pb "
                "and place it at the path specified in EAST_MODEL_PATH."
            )
        self._net = cv2.dnn.readNet(str(self._model_path))
        logger.info(f"EAST model loaded from {self._model_path}")

    def detect(self, image: np.ndarray) -> list[dict]:
        """
        Detect text regions in `image` (BGR numpy array).

        Returns:
            List of dicts: {"x": int, "y": int, "w": int, "h": int, "score": float}
        """
        try:
            self._load_model()
        except FileNotFoundError as e:
            logger.warning(f"EAST detection skipped: {e}")
            return []

        orig_h, orig_w = image.shape[:2]

        # EAST requires dimensions divisible by 32
        new_w = max(32, (orig_w // 32) * 32)
        new_h = max(32, (orig_h // 32) * 32)
        ratio_w = orig_w / float(new_w)
        ratio_h = orig_h / float(new_h)

        resized = cv2.resize(image, (new_w, new_h))
        blob = cv2.dnn.blobFromImage(
            resized,
            scalefactor=1.0,
            size=(new_w, new_h),
            mean=(123.68, 116.78, 103.94),
            swapRB=True,
            crop=False,
        )

        self._net.setInput(blob)
        scores_map, geometry_map = self._net.forward(_EAST_LAYERS)

        boxes, confidences = self._decode_predictions(scores_map, geometry_map)

        if not boxes:
            return []

        # Non-maximum suppression
        indices = cv2.dnn.NMSBoxesRotated(
            boxes,
            confidences,
            self._conf_threshold,
            self._nms_threshold,
        )

        results = []
        for i in (indices.flatten() if len(indices) > 0 else []):
            cx, cy = boxes[i][0]
            w, h = boxes[i][1]
            # Convert centre+size to top-left origin, scale back to original
            x = int((cx - w / 2) * ratio_w)
            y = int((cy - h / 2) * ratio_h)
            w_orig = int(w * ratio_w)
            h_orig = int(h * ratio_h)

            # Clamp to image bounds
            x = max(0, x)
            y = max(0, y)
            w_orig = min(w_orig, orig_w - x)
            h_orig = min(h_orig, orig_h - y)

            if w_orig > 4 and h_orig > 4:
                results.append({
                    "x": x, "y": y, "w": w_orig, "h": h_orig,
                    "score": float(confidences[i]),
                })

        logger.debug(f"EAST detected {len(results)} text regions")
        return results

    @staticmethod
    def _decode_predictions(scores, geometry) -> tuple[list, list]:
        """
        Decode EAST network output into (rotated bounding boxes, confidences).
        Returns lists compatible with cv2.dnn.NMSBoxesRotated.
        """
        num_rows, num_cols = scores.shape[2], scores.shape[3]
        boxes, confidences = [], []

        for y in range(num_rows):
            score_data = scores[0, 0, y]
            x_data0 = geometry[0, 0, y]
            x_data1 = geometry[0, 1, y]
            x_data2 = geometry[0, 2, y]
            x_data3 = geometry[0, 3, y]
            angles_data = geometry[0, 4, y]

            for x in range(num_cols):
                score = float(score_data[x])
                if score < 0.5:
                    continue

                # Compute offset in original feature map space (stride = 4)
                offset_x = x * 4.0
                offset_y = y * 4.0

                angle = float(angles_data[x])
                cos_a = np.cos(angle)
                sin_a = np.sin(angle)

                h = float(x_data0[x]) + float(x_data2[x])
                w = float(x_data1[x]) + float(x_data3[x])

                end_x = int(offset_x + cos_a * x_data1[x] + sin_a * x_data2[x])
                end_y = int(offset_y - sin_a * x_data1[x] + cos_a * x_data2[x])

                cx = end_x - w / 2
                cy = end_y - h / 2

                boxes.append(((cx + w / 2, cy + h / 2), (w, h), -angle * 180.0 / np.pi))
                confidences.append(score)

        return boxes, confidences


# Singleton instance
east_detector = EASTDetector()
