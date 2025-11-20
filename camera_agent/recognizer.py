# recognizer.py — MediaPipe primary + Haar fallback, robust embedding matching & backend sending

import time
import json
import requests
import cv2
import numpy as np
import mediapipe as mp
import insightface
from datetime import datetime, timezone
from typing import Dict, List, Optional

# ---------- CONFIG ----------
BACKEND = "http://127.0.0.1:8000"
CONTINUOUS_URL = f"{BACKEND}/api/v1/continuous/presence"
STUDENTS_API = f"{BACKEND}/api/v1/students/encodings"
VIDEO_SRC = 0
SEND_INTERVAL = 0.6
MATCH_THRESHOLD = 0.45
RELOAD_INTERVAL = 30.0
CAMERA_ID = "cam-01"
# ----------------------------

# MediaPipe Detector — short-range for webcams
mp_face = mp.solutions.face_detection.FaceDetection(model_selection=0, min_detection_confidence=0.3)

# Haar fallback (OpenCV)
haar_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")

# InsightFace
fa = insightface.app.FaceAnalysis(name="buffalo_l")
fa.prepare(ctx_id=-1)

session = requests.Session()

_known_students: List[Dict] = []
_known_embeddings: Optional[np.ndarray] = None
_last_sent: Dict[int, float] = {}
_last_reload = 0.0


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def send_presence(student_id: int, confidence: float):
    payload = {
        "student_id": int(student_id),
        "confidence": float(confidence),
        "timestamp": now_iso(),
        "camera_id": CAMERA_ID,
        "liveness": True,
        "metadata": {}
    }
    try:
        session.post(CONTINUOUS_URL, json=payload, timeout=3)
    except Exception as e:
        print("[ERR send_presence]", e)


def load_students_from_backend():
    global _known_students, _known_embeddings

    try:
        r = session.get(STUDENTS_API, timeout=5)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        print("[ERR fetching students]", e)
        return

    encs = []
    prepared = []

    for s in data:
        emb = s.get("face_encoding") or s.get("face_embedding")
        if isinstance(emb, str):
            try:
                emb = json.loads(emb)
            except:
                emb = None
        if emb is not None:
            try:
                arr = np.array(emb, dtype=np.float32)
                prepared.append({**s, "_enc": arr})
                encs.append(arr)
            except Exception:
                prepared.append({**s, "_enc": None})
        else:
            prepared.append({**s, "_enc": None})

    _known_students = prepared

    if len(encs) > 0:
        dims = [e.size for e in encs]
        max_dim = max(dims)
        fixed = []
        for e in encs:
            if e.size < max_dim:
                p = np.zeros(max_dim, dtype=np.float32)
                p[:e.size] = e.flatten()
                fixed.append(p)
            else:
                fixed.append(e.flatten()[:max_dim])
        _known_embeddings = np.vstack(fixed)
    else:
        _known_embeddings = np.empty((0, 512), dtype=np.float32)

    print(f"[INFO] Loaded {len([s for s in _known_students if s.get('_enc') is not None])} students.")


def match_embedding(emb: np.ndarray):
    if _known_embeddings is None or _known_embeddings.size == 0:
        return None
    emb = emb.astype(np.float32).flatten()
    D = _known_embeddings.shape[1]
    if emb.size < D:
        p = np.zeros(D, dtype=np.float32)
        p[:emb.size] = emb
        emb = p
    elif emb.size > D:
        emb = emb[:D]
    emb_norm = np.linalg.norm(emb) + 1e-8
    dots = _known_embeddings @ emb
    norms = np.linalg.norm(_known_embeddings, axis=1) * emb_norm + 1e-8
    cos_sim = dots / norms
    dists = 1.0 - cos_sim
    idx = int(np.argmin(dists))
    best = float(dists[idx])
    if best <= MATCH_THRESHOLD:
        return {"student": _known_students[idx], "distance": best}
    return None


def mediapipe_detections(frame_rgb):
    """Return list of bboxes in (x1,y1,x2,y2) using MediaPipe (frame_rgb expected)."""
    res = mp_face.process(frame_rgb)
    if not res or not res.detections:
        return []
    ih, iw, _ = frame_rgb.shape
    out = []
    for det in res.detections:
        box = det.location_data.relative_bounding_box
        x1 = max(0, int(box.xmin * iw))
        y1 = max(0, int(box.ymin * ih))
        w = int(box.width * iw)
        h = int(box.height * ih)
        x2 = x1 + w
        y2 = y1 + h
        pad = int(0.15 * max(w, h))
        xa = max(0, x1 - pad)
        ya = max(0, y1 - pad)
        xb = min(iw, x2 + pad)
        yb = min(ih, y2 + pad)
        out.append((xa, ya, xb, yb))
    return out


def haar_detections(frame_bgr):
    """Return list of bboxes using Haar cascade (frame_bgr expected)."""
    gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
    faces = haar_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=4, minSize=(60, 60))
    out = []
    for (x, y, w, h) in faces:
        pad = int(0.15 * max(w, h))
        xa = max(0, x - pad)
        ya = max(0, y - pad)
        xb = min(frame_bgr.shape[1], x + w + pad)
        yb = min(frame_bgr.shape[0], y + h + pad)
        out.append((xa, ya, xb, yb))
    return out


def extract_embedding_from_crop(face_rgb):
    """Get embedding using insightface; returns None on failure."""
    try:
        faces = fa.get(face_rgb)
        if not faces:
            return None
        return np.array(faces[0].embedding, dtype=np.float32)
    except Exception as e:
        # sometimes InsightFace can fail on small/corrupted crops
        print("[ERR] insightface.get:", e)
        return None


def main():
    global _last_reload, _last_sent

    print("[INFO] Loading students…")
    load_students_from_backend()
    _last_reload = time.time()

    cap = cv2.VideoCapture(VIDEO_SRC)
    # request higher resolution
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    print("DEBUG: VIDEO_SRC:", VIDEO_SRC, "cap.isOpened():", cap.isOpened(), "actual_res:", (actual_w, actual_h))

    if not cap.isOpened():
        print("[ERR] Camera failed to open")
        return

    _last_sent = {}
    frame_count = 0

    try:
        while True:
            ret, frame = cap.read()
            frame_count += 1
            if not ret:
                time.sleep(0.05)
                continue

            # periodic reload
            if time.time() - _last_reload > RELOAD_INTERVAL:
                load_students_from_backend()
                _last_reload = time.time()

            # prefer MediaPipe (works well with webcams); fallback to Haar if none detected
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            dets = mediapipe_detections(rgb)

            if not dets:
                # debug print once every 120 frames
                if frame_count % 120 == 0:
                    print("DEBUG: MediaPipe found 0 detections; trying Haar fallback")
                dets = haar_detections(frame)

            if frame_count % 120 == 0:
                print("DEBUG: frame", frame_count, "dets:", len(dets),
                      "known_embeddings.shape", None if _known_embeddings is None else _known_embeddings.shape)

            now_ts = time.time()

            # process each detected face bbox
            for (xa, ya, xb, yb) in dets:
                # ensure valid crop coords
                xa = max(0, int(xa)); ya = max(0, int(ya))
                xb = min(frame.shape[1], int(xb)); yb = min(frame.shape[0], int(yb))
                face_rgb = cv2.cvtColor(frame[ya:yb, xa:xb], cv2.COLOR_BGR2RGB)
                if face_rgb.size == 0:
                    continue

                emb = extract_embedding_from_crop(face_rgb)
                if emb is None:
                    # optionally try without padding (tighter crop) — skip for brevity
                    continue

                match = match_embedding(emb)
                label = "Unknown"
                conf_score = 0.0

                if match:
                    sid = match["student"]["id"]
                    dist = match["distance"]
                    conf_score = max(0.0, 1.0 - dist)
                    name = match["student"].get("name") or str(sid)
                    label = f"{name} ({sid})"
                    last = _last_sent.get(sid, 0)
                    if now_ts - last >= SEND_INTERVAL:
                        send_presence(sid, conf_score)
                        _last_sent[sid] = now_ts
                    if frame_count % 120 == 0:
                        print(f"DEBUG: matched id {sid} dist {dist:.4f} conf {conf_score:.3f}")

                color = (0, 255, 0) if label != "Unknown" else (0, 0, 255)
                cv2.rectangle(frame, (xa, ya), (xb, yb), color, 2)
                cv2.putText(frame, f"{label} {conf_score:.2f}", (xa, max(ya-8,10)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

            cv2.imshow("Recognizer", frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

    except KeyboardInterrupt:
        pass
    except Exception as e:
        print("[ERR main loop]", e)
    finally:
        cap.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
