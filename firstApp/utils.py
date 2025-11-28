import cv2
import numpy as np

def is_valid_fundus(image_file, debug=False):
    """
    FINAL ROP-FRIENDLY VALIDATOR
    Accepts ALL neonatal ROP fundus images (even extremely hazy ones)
    Rejects only obvious non-fundus (skin, papers, iris).
    """
    try:
        # ---------------------- LOAD & DECODE ----------------------------------
        file_bytes = np.frombuffer(image_file.read(), np.uint8)
        image_file.seek(0)
        img = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)

        if img is None:
            return False, "Corrupted image."

        # Resize for consistency
        img = cv2.resize(img, (512, 512))
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        metrics = {}

        # ---------------------------------------------------------
        # 1. Reject SKIN / FACE / NORMAL EYE (very important)
        # ---------------------------------------------------------
        # Skin tones: high R + moderate G
        avg_r = np.mean(img[:,:,2])
        avg_g = np.mean(img[:,:,1])
        skin_ratio = avg_g / (avg_r + 1e-5)

        metrics['skin_ratio'] = skin_ratio

        if skin_ratio > 0.85:  
            return False, "Invalid: Skin-like image detected."

        # Reject very bright white (paper, flashlight)
        white_pixels = np.mean(gray > 230)
        metrics['white_pixels'] = white_pixels
        if white_pixels > 0.40:
            return False, "Invalid: Image is too bright / glare."

        # ---------------------------------------------------------
        # 2. Circular fundus field (VERY PERMISSIVE)
        # ---------------------------------------------------------
        h, w = gray.shape
        cx, cy = w//2, h//2
        r = int(min(cx, cy) * 0.80)

        mask = np.zeros_like(gray)
        cv2.circle(mask, (cx, cy), r, 255, -1)

        circle_overlap = np.mean(mask[gray > 5])
        metrics['circle_overlap'] = circle_overlap

        if circle_overlap < 0.05:   # almost anything circular passes
            return False, "Invalid: No circular fundus-like shape."

        # ---------------------------------------------------------
        # 3. COLOR CHECK (ROP is hazy pink/orange/gray — accept all)
        # ---------------------------------------------------------
        hue = hsv[:,:,0]
        red_orange_fraction = np.mean((hue < 30).astype(np.uint8))
        metrics['red_orange_fraction'] = red_orange_fraction

        # Only reject if image has NO red/orange AT ALL (completely wrong)
        if red_orange_fraction < 0.02:
            return False, "Invalid: No retinal-like coloration present."

        # ---------------------------------------------------------
        # 4. Reject perfect iris circle (normal smartphone eye photo)
        # ---------------------------------------------------------
        blur = cv2.GaussianBlur(gray, (7, 7), 0)
        circles = cv2.HoughCircles(
            blur,
            cv2.HOUGH_GRADIENT,
            dp=1.3,
            minDist=150,
            param1=80,
            param2=35,
            minRadius=int(r*0.8),
            maxRadius=int(r*1.1)
        )

        metrics['iris_circles'] = int(len(circles[0]) if circles is not None else 0)

        if circles is not None:
            # Iris generally forms perfect large centered circle
            (x, y, rr) = circles[0][0]
            if abs(x - cx) < 20 and abs(y - cy) < 20:
                return False, "Invalid: Iris-like eye photo detected."

        # ---------------------------------------------------------
        # 5. VESSELS (NOT REQUIRED ANYMORE)
        # ---------------------------------------------------------
        # ROP images may have almost NO visible vessels.
        # So we DO NOT reject based on vessel visibility.

        # ---------------------------------------------------------
        # 6. If all basic non-fundus filters are passed → ACCEPT
        # ---------------------------------------------------------
        if debug:
            return True, "Valid ROP fundus image.", metrics

        return True, "Valid ROP fundus image."

    except Exception as e:
        return False, f"Error: {e}"
