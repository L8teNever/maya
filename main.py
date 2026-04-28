import os
import cv2
import numpy as np
import mediapipe as mp
import glob
import time
import subprocess
import asyncio
from concurrent.futures import ThreadPoolExecutor
from fastapi import FastAPI, UploadFile, File
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import shutil

app = FastAPI(title="MAYA")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

os.makedirs("static", exist_ok=True)
os.makedirs("images/raw", exist_ok=True)
os.makedirs("images/aligned", exist_ok=True)
os.makedirs("videos", exist_ok=True)

icon_path = "static/icon.png"
if not os.path.exists(icon_path):
    img = np.zeros((512, 512, 3), dtype=np.uint8)
    img[:] = (164, 80, 103)
    cv2.putText(img, "M", (150, 350), cv2.FONT_HERSHEY_SIMPLEX, 10, (255, 255, 255), 20)
    cv2.imwrite(icon_path, img)

mp_face_mesh = mp.solutions.face_mesh
face_mesh = mp_face_mesh.FaceMesh(static_image_mode=True, max_num_faces=1, refine_landmarks=True)

_executor = ThreadPoolExecutor(max_workers=2)


def align_image(image_path, output_path):
    img = cv2.imread(image_path)
    if img is None:
        return False
    results = face_mesh.process(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    if not results.multi_face_landmarks:
        return False

    landmarks = results.multi_face_landmarks[0].landmark
    h, w, _ = img.shape

    left_eye  = (int(landmarks[468].x * w), int(landmarks[468].y * h))
    right_eye = (int(landmarks[473].x * w), int(landmarks[473].y * h))

    dx = right_eye[0] - left_eye[0]
    dy = right_eye[1] - left_eye[1]
    angle = np.degrees(np.arctan2(dy, dx))
    eyes_center = ((left_eye[0] + right_eye[0]) // 2, (left_eye[1] + right_eye[1]) // 2)

    M = cv2.getRotationMatrix2D(eyes_center, angle, 1.0)
    rotated = cv2.warpAffine(img, M, (w, h), flags=cv2.INTER_CUBIC)

    new_dist = np.sqrt(dx**2 + dy**2)
    desired_dist = w * 0.25
    scale = desired_dist / (new_dist + 1e-6)

    M_scale = cv2.getRotationMatrix2D(eyes_center, 0, scale)
    scaled = cv2.warpAffine(rotated, M_scale, (w, h), flags=cv2.INTER_CUBIC)

    new_eyes_center = (
        int(eyes_center[0] * scale + (1 - scale) * eyes_center[0]),
        int(eyes_center[1] * scale + (1 - scale) * eyes_center[1]),
    )
    desired_center = (w // 2, h // 3)
    tx = desired_center[0] - new_eyes_center[0]
    ty = desired_center[1] - new_eyes_center[1]

    M_trans = np.float32([[1, 0, tx], [0, 1, ty]])
    aligned = cv2.warpAffine(scaled, M_trans, (w, h))
    cv2.imwrite(output_path, aligned)
    return True


def _fit_frame(img: np.ndarray, target_w: int, target_h: int) -> np.ndarray:
    """Resize image to fit target size, preserving aspect ratio (black padding)."""
    h, w = img.shape[:2]
    scale = min(target_w / w, target_h / h)
    nw, nh = int(w * scale), int(h * scale)
    resized = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_AREA)
    canvas = np.zeros((target_h, target_w, 3), dtype=np.uint8)
    y0 = (target_h - nh) // 2
    x0 = (target_w - nw) // 2
    canvas[y0:y0+nh, x0:x0+nw] = resized
    return canvas


def _build_timelapse() -> dict:
    aligned_files = sorted(glob.glob("images/aligned/*"))
    if len(aligned_files) < 2:
        return {"status": "error", "message": "Mindestens 2 ausgerichtete Fotos benötigt."}

    # Fixed portrait canvas — all images fit into this without stretching
    target_w, target_h = 720, 960   # 3:4 portrait, H.264-friendly (both even)

    fps = 30
    hold  = 5   # frames each photo is shown solid  (~0.17 s)
    fade  = 10  # frames for the cross-fade         (~0.33 s)

    timestamp = int(time.time())
    output_path = f"videos/timelapse_{timestamp}.mp4"

    # Pipe raw BGR frames into ffmpeg → H.264 MP4 with faststart
    cmd = [
        "ffmpeg", "-y",
        "-f", "rawvideo", "-vcodec", "rawvideo",
        "-pix_fmt", "bgr24",
        "-s", f"{target_w}x{target_h}",
        "-r", str(fps),
        "-i", "-",
        "-vcodec", "libx264",
        "-pix_fmt", "yuv420p",
        "-crf", "22",
        "-preset", "fast",
        "-movflags", "+faststart",
        output_path,
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)

    images = []
    for path in aligned_files:
        img = cv2.imread(path)
        if img is not None:
            images.append(_fit_frame(img, target_w, target_h))

    for i, img in enumerate(images):
        raw = img.tobytes()
        for _ in range(hold):
            proc.stdin.write(raw)
        if i < len(images) - 1:
            nxt = images[i + 1]
            for f in range(fade):
                alpha = (f + 1) / (fade + 1)
                blended = cv2.addWeighted(img, 1 - alpha, nxt, alpha, 0)
                proc.stdin.write(blended.tobytes())

    proc.stdin.close()
    proc.wait()

    if proc.returncode != 0:
        return {"status": "error", "message": "ffmpeg-Fehler beim Erstellen des Videos."}

    return {"status": "success", "filename": f"timelapse_{timestamp}.mp4"}


app.mount("/static",  StaticFiles(directory="static"),         name="static")
app.mount("/raw",     StaticFiles(directory="images/raw"),     name="raw")
app.mount("/aligned", StaticFiles(directory="images/aligned"), name="aligned")
app.mount("/videos",  StaticFiles(directory="videos"),         name="videos")


@app.get("/", response_class=HTMLResponse)
async def get_index():
    with open("static/index.html", "r", encoding="utf-8") as f:
        return f.read()


@app.post("/upload")
async def upload_image(file: UploadFile = File(...)):
    name = file.filename
    raw_path     = f"images/raw/{name}"
    aligned_path = f"images/aligned/{name}"
    with open(raw_path, "wb") as buf:
        shutil.copyfileobj(file.file, buf)
    success = align_image(raw_path, aligned_path)
    if not success:
        return {"status": "error", "message": "Kein Gesicht erkannt oder Fehler beim Ausrichten."}
    return {"status": "success", "filename": name}


@app.post("/create-timelapse")
async def create_timelapse():
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(_executor, _build_timelapse)
    return result


@app.get("/api/images")
async def get_images():
    # Only show raw files that have a successfully aligned counterpart
    aligned = {os.path.basename(f) for f in glob.glob("images/aligned/*")}
    raw = [os.path.basename(f) for f in glob.glob("images/raw/*") if os.path.basename(f) in aligned]
    return {"images": sorted(raw, reverse=True)}


@app.delete("/api/images/{filename}")
async def delete_image(filename: str):
    filename = os.path.basename(filename)  # prevent path traversal
    aligned_path = f"images/aligned/{filename}"
    raw_path     = f"images/raw/{filename}"
    if not os.path.exists(aligned_path):
        return {"status": "error", "message": "Bild nicht gefunden."}
    os.remove(aligned_path)
    if os.path.exists(raw_path):
        os.remove(raw_path)
    return {"status": "success"}


@app.get("/api/videos")
async def get_videos():
    files = glob.glob("videos/*.mp4")
    return {"videos": sorted([os.path.basename(f) for f in files], reverse=True)}
