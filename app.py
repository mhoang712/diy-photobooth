from flask import Flask, request, jsonify, render_template
import subprocess
import time
import os
import cv2
import numpy as np
from PIL import Image
import cloudinary
import cloudinary.uploader
import qrcode
import base64
from io import BytesIO

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    _env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if os.path.exists(_env_path):
        with open(_env_path, "r", encoding="utf-8") as _f:
            for _line in _f:
                _line = _line.strip()
                if _line and not _line.startswith("#") and "=" in _line:
                    _k, _v = _line.split("=", 1)
                    os.environ.setdefault(_k.strip(), _v.strip().strip('"').strip("'"))

app = Flask(__name__)

# Base directory for absolute paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Cloudinary Configuration (loaded from .env / environment variables)
CLOUDINARY_CLOUD_NAME = os.environ.get("CLOUDINARY_CLOUD_NAME")
CLOUDINARY_API_KEY = os.environ.get("CLOUDINARY_API_KEY")
CLOUDINARY_API_SECRET = os.environ.get("CLOUDINARY_API_SECRET")

cloudinary.config(
    cloud_name=CLOUDINARY_CLOUD_NAME,
    api_key=CLOUDINARY_API_KEY,
    api_secret=CLOUDINARY_API_SECRET
)

# digiCamControl Configuration (built & tested for Canon DSLR + Windows)
DIGICAM_REMOTE_CMD = os.environ.get(
    "DIGICAM_REMOTE_CMD",
    r"C:\Program Files (x86)\digiCamControl\CameraControlRemoteCmd.exe"
)
DIGICAM_CAPTURE_CMD = os.environ.get("DIGICAM_CAPTURE_CMD", "capturenoaf")
TEMP_CAPTURE_PATH = os.environ.get(
    "TEMP_CAPTURE_PATH",
    os.path.join(os.path.expanduser("~"), "temp_capture.jpg")
)

def get_frame_bboxes(frame_filename="frame.png"):
    """
    Analyzes the frame to find transparent cutouts (alpha == 0).
    Returns a list of bounding boxes (x, y, w, h) sorted top-to-bottom, left-to-right.
    """
    frame_path = os.path.join(BASE_DIR, "static", "assets", frame_filename)
    if not os.path.exists(frame_path):
        return []
        
    # 1. OpenCV Alpha Detection
    img = cv2.imread(frame_path, cv2.IMREAD_UNCHANGED)
    if img is None or img.shape[2] != 4:
        return []

    alpha_channel = img[:, :, 3]
    
    # Threshold it (alpha == 0 is the cutout)
    _, mask = cv2.threshold(alpha_channel, 10, 255, cv2.THRESH_BINARY_INV)
    
    # 2. Contour Finding
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    bboxes = []
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area > 2000: # Filter out noise
            x, y, w, h = cv2.boundingRect(cnt)
            bboxes.append((x, y, w, h))
            
    # 3. Bounding Boxes & Sorting (Top-to-Bottom, Left-to-Right)
    if not bboxes:
        return []
        
    # Group by rows using a tolerance (e.g., half the average height)
    avg_h = sum(b[3] for b in bboxes) / len(bboxes)
    tolerance = avg_h / 2
    
    # Sort initially by Y coordinate
    bboxes.sort(key=lambda b: b[1])
    
    rows = []
    current_row = [bboxes[0]]
    for b in bboxes[1:]:
        if abs(b[1] - current_row[0][1]) < tolerance:
            current_row.append(b)
        else:
            rows.append(current_row)
            current_row = [b]
    rows.append(current_row)
    
    # Sort each row by X coordinate
    sorted_bboxes = []
    for row in rows:
        row.sort(key=lambda b: b[0])
        sorted_bboxes.extend(row)
        
    return sorted_bboxes

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/config", methods=["GET"])
def get_config():
    frame_filename = request.args.get("frame", "frame.png")
    bboxes = get_frame_bboxes(frame_filename)
    return jsonify({"shots_required": len(bboxes)})

@app.route("/api/capture", methods=["POST"])
def capture():
    timestamp = int(time.time() * 1000)
    filename = f"shot_{timestamp}.jpg"
    filepath = os.path.join(BASE_DIR, "static", "captures", filename)
    
    # Ensure directory exists
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    
    # Use a writable temp path without spaces because digiCamControl's
    # CameraControlRemoteCmd.exe splits arguments on spaces and rejects quotes.
    temp_capture_path = TEMP_CAPTURE_PATH
    os.makedirs(os.path.dirname(os.path.abspath(temp_capture_path)), exist_ok=True)
    if " " in temp_capture_path:
        print(f"WARNING: TEMP_CAPTURE_PATH ({temp_capture_path}) contains spaces; digiCamControl may fail to save.")

    # Remove any old temp capture
    if os.path.exists(temp_capture_path):
        try:
            os.remove(temp_capture_path)
        except Exception:
            pass

    cmd = [
        DIGICAM_REMOTE_CMD,
        "/c",
        f"{DIGICAM_CAPTURE_CMD} {temp_capture_path}"
    ]
    
    try:
        # Give it up to 30s to take the photo and transfer it
        subprocess.run(cmd, timeout=30)
    except subprocess.TimeoutExpired:
        print("CameraControlCmd timeout, continuing to poll...")
    except Exception as e:
        print(f"Error calling CameraControlCmd: {e}")
        
    # Polling loop (checking every 0.5s, with a 35-second timeout)
    timeout_duration = 35
    start_time = time.time()
    
    while time.time() - start_time < timeout_duration:
        if os.path.exists(temp_capture_path):
            import shutil
            try:
                # Wait a tiny bit to ensure the file is completely written by digiCamControl
                time.sleep(0.2)
                shutil.move(temp_capture_path, filepath)
                return jsonify({"status": "success", "filename": filename})
            except Exception as e:
                return jsonify({"status": "error", "message": f"Failed to move temp file: {e}"}), 500
                    
        time.sleep(0.5)
        
    return jsonify({"status": "error", "message": "Camera capture timeout or file not found"}), 500

@app.route("/api/process", methods=["POST"])
def process_photos():
    data = request.json
    filenames = data.get("filenames", [])
    frame_filename = data.get("frame", "frame.png")
    
    bboxes = get_frame_bboxes(frame_filename)
    
    if len(filenames) != len(bboxes):
        return jsonify({"status": "error", "message": "Mismatch between shots and frame cutouts"}), 400
        
    frame_path = os.path.join(BASE_DIR, "static", "assets", frame_filename)
    frame_img = Image.open(frame_path).convert("RGBA")
    
    # Create a blank canvas identical in size to frame.png
    canvas = Image.new("RGBA", frame_img.size, (255, 255, 255, 255))
    
    for i, (filename, bbox) in enumerate(zip(filenames, bboxes)):
        filepath = os.path.join(BASE_DIR, "static", "captures", filename)
        if not os.path.exists(filepath):
            return jsonify({"status": "error", "message": f"Missing file: {filename}"}), 400
            
        shot = Image.open(filepath).convert("RGBA")
        x, y, w, h = bbox
        
        # Center Crop to match (w, h) aspect ratio without distortion
        shot_ratio = shot.width / shot.height
        target_ratio = w / h
        
        if shot_ratio > target_ratio:
            # Shot is too wide: crop horizontally
            new_width = int(target_ratio * shot.height)
            offset = (shot.width - new_width) // 2
            shot = shot.crop((offset, 0, offset + new_width, shot.height))
        elif shot_ratio < target_ratio:
            # Shot is too tall: crop vertically
            new_height = int(shot.width / target_ratio)
            offset = (shot.height - new_height) // 2
            shot = shot.crop((0, offset, shot.width, offset + new_height))
            
        # Resize cropped image to exactly (w, h)
        shot = shot.resize((w, h), Image.Resampling.LANCZOS)
        
        # Paste processed photo onto canvas at (x, y)
        canvas.paste(shot, (x, y))
        
    # Alpha composite the original frame over the canvas to cover edges cleanly
    final_img = Image.alpha_composite(canvas, frame_img)
    
    # Save the processed image
    timestamp = int(time.time())
    final_filename = f"final_{timestamp}.png"
    final_filepath = os.path.join(BASE_DIR, "processed", final_filename)
    os.makedirs(os.path.dirname(final_filepath), exist_ok=True)
    final_img.save(final_filepath)

    # Cloudinary Upload & QR Generation
    if not all([CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET]):
        return jsonify({
            "status": "error",
            "message": "Cloudinary credentials are missing. Copy .env.example to .env and fill in CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, and CLOUDINARY_API_SECRET."
        }), 500

    try:
        # Note: Will fail if API keys are not valid
        upload_result = cloudinary.uploader.upload(final_filepath)
        secure_url = upload_result.get("secure_url")
        
        # Generate QR Code
        qr = qrcode.QRCode(box_size=10, border=4)
        qr.add_data(secure_url)
        qr.make(fit=True)
        qr_img = qr.make_image(fill_color="black", back_color="white")
        
        # Convert QR code image to Base64
        buffered = BytesIO()
        qr_img.save(buffered, format="PNG")
        qr_base64 = base64.b64encode(buffered.getvalue()).decode("utf-8")
        
        return jsonify({
            "status": "success",
            "image_url": secure_url,
            "qr_base64": qr_base64
        })
    except Exception as e:
        print(f"Cloudinary upload error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
