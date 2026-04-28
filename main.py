import os
import cv2
import numpy as np
import mediapipe as mp
import glob
from fastapi import FastAPI, UploadFile, File
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import shutil

app = FastAPI(title="MAYA")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# Ensure directories exist
os.makedirs("static", exist_ok=True)
os.makedirs("images/raw", exist_ok=True)
os.makedirs("images/aligned", exist_ok=True)

# Generate a dummy icon for the PWA if it doesn't exist
icon_path = "static/icon.png"
if not os.path.exists(icon_path):
    img = np.zeros((512, 512, 3), dtype=np.uint8)
    img[:] = (164, 80, 103) # Material primary color BGR
    cv2.putText(img, "M", (150, 350), cv2.FONT_HERSHEY_SIMPLEX, 10, (255, 255, 255), 20)
    cv2.imwrite(icon_path, img)

# Initialize Mediapipe Face Mesh for eye tracking
mp_face_mesh = mp.solutions.face_mesh
face_mesh = mp_face_mesh.FaceMesh(static_image_mode=True, max_num_faces=1, refine_landmarks=True)

def align_image(image_path, output_path):
    """
    Tracks eyes using MediaPipe, then rotates and scales the image to align
    the eyes to a fixed position (creating a perfect timelapse effect).
    """
    img = cv2.imread(image_path)
    if img is None: return False
    results = face_mesh.process(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    
    if not results.multi_face_landmarks:
        return False
    
    landmarks = results.multi_face_landmarks[0].landmark
    h, w, _ = img.shape
    
    # 468 is left eye pupil, 473 is right eye pupil (in MediaPipe refined landmarks)
    left_eye = (int(landmarks[468].x * w), int(landmarks[468].y * h))
    right_eye = (int(landmarks[473].x * w), int(landmarks[473].y * h))
    
    # Calculate angle to rotate the image
    dx = right_eye[0] - left_eye[0]
    dy = right_eye[1] - left_eye[1]
    angle = np.degrees(np.arctan2(dy, dx))
    
    eyes_center = ((left_eye[0] + right_eye[0]) // 2, (left_eye[1] + right_eye[1]) // 2)
    
    # Rotate
    M = cv2.getRotationMatrix2D(eyes_center, angle, 1.0)
    rotated = cv2.warpAffine(img, M, (w, h), flags=cv2.INTER_CUBIC)
    
    # Scale: target eye distance to be exactly 25% of the image width
    new_dist = np.sqrt(dx**2 + dy**2)
    desired_dist = w * 0.25
    scale = desired_dist / (new_dist + 1e-6)
    
    M_scale = cv2.getRotationMatrix2D(eyes_center, 0, scale)
    scaled = cv2.warpAffine(rotated, M_scale, (w, h), flags=cv2.INTER_CUBIC)
    
    # Translate: put the eyes center strictly at X=(w/2), Y=(h/3)
    new_eyes_center = (int(eyes_center[0] * scale + (1 - scale) * eyes_center[0]), 
                       int(eyes_center[1] * scale + (1 - scale) * eyes_center[1]))
    
    desired_center = (w // 2, h // 3)
    tx = desired_center[0] - new_eyes_center[0]
    ty = desired_center[1] - new_eyes_center[1]
    
    M_trans = np.float32([[1, 0, tx], [0, 1, ty]])
    aligned = cv2.warpAffine(scaled, M_trans, (w, h))
    
    cv2.imwrite(output_path, aligned)
    return True

app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/aligned", StaticFiles(directory="images/aligned"), name="aligned")

@app.get("/", response_class=HTMLResponse)
async def get_index():
    with open("static/index.html", "r", encoding="utf-8") as f:
        return f.read()

@app.post("/upload")
async def upload_image(file: UploadFile = File(...)):
    name = file.filename
    raw_path = f"images/raw/{name}"
    aligned_path = f"images/aligned/{name}"
    
    # Save the original image
    with open(raw_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    # Align the face and save to aligned_path
    success = align_image(raw_path, aligned_path)
    if not success:
        return {"status": "error", "message": "Kein Gesicht erkannt oder Fehler beim Ausrichten."}
    
    return {"status": "success", "filename": name}

@app.get("/api/images")
async def get_images():
    files = glob.glob("images/aligned/*")
    response_files = [os.path.basename(f) for f in files]
    return {"images": sorted(response_files, reverse=True)}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
