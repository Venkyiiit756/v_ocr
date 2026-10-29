"""
Dynamic Voter Card Boundary Detector using OpenCV Computer Vision.
Detects rectangular voter card borders on scanned electoral roll pages,
automatically adapting to section banners, variable margins, and partial pages.
"""

import cv2
import numpy as np

class VoterCardDetector:
    def __init__(self, min_width_ratio=0.22, max_width_ratio=0.38,
                 min_height_ratio=0.05, max_height_ratio=0.15):
        self.min_w = min_width_ratio
        self.max_w = max_width_ratio
        self.min_h = min_height_ratio
        self.max_h = max_height_ratio

    def detect_boxes(self, img_bgr):
        """
        Detects all voter card bounding boxes (x, y, w, h) in reading order.
        """
        h_img, w_img = img_bgr.shape[:2]
        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)

        # Invert and threshold to extract black borders
        thresh = cv2.adaptiveThreshold(
            ~gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY, 15, -2
        )

        # Detect horizontal and vertical lines with morphological kernels
        h_len = max(30, int(w_img * 0.02))
        v_len = max(30, int(h_img * 0.015))
        
        h_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (h_len, 1))
        v_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, v_len))
        
        h_lines = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, h_kernel)
        v_lines = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, v_kernel)
        
        table_mask = cv2.add(h_lines, v_lines)
        contours, _ = cv2.findContours(table_mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

        candidate_boxes = []
        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)
            if (self.min_w * w_img <= w <= self.max_w * w_img and
                self.min_h * h_img <= h <= self.max_h * h_img):
                candidate_boxes.append((x, y, w, h))

        # Deduplicate overlapping / nearly identical boxes (within 15px)
        unique_boxes = []
        for box in sorted(candidate_boxes, key=lambda b: (b[1], b[0])):
            if not any(abs(box[0] - ub[0]) < 20 and abs(box[1] - ub[1]) < 20 for ub in unique_boxes):
                unique_boxes.append(box)

        # If CV found boxes, order them row-by-row, left-to-right
        if len(unique_boxes) >= 1:
            return self._order_boxes(unique_boxes, row_tolerance=int(h_img * 0.015))

        # If no boxes detected, page is blank/nil additions/cover page
        return []

    def _order_boxes(self, boxes, row_tolerance=40):
        rows = []
        for b in sorted(boxes, key=lambda b: b[1]):
            placed = False
            for r in rows:
                if abs(r[0][1] - b[1]) <= row_tolerance:
                    r.append(b)
                    placed = True
                    break
            if not placed:
                rows.append([b])

        ordered = []
        for r in rows:
            r.sort(key=lambda b: b[0])
            ordered.extend(r)
        return ordered

    def _grid_fallback(self, width, height):
        top_margin = int(height * 0.068)
        bottom_margin = int(height * 0.96)
        left_margin = int(width * 0.035)
        right_margin = int(width * 0.965)

        row_h = (bottom_margin - top_margin) / 10
        col_w = (right_margin - left_margin) / 3

        boxes = []
        for r in range(10):
            for c in range(3):
                x = int(left_margin + c * col_w)
                y = int(top_margin + r * row_h)
                w = int(col_w)
                h = int(row_h)
                boxes.append((x, y, w, h))
        return boxes
