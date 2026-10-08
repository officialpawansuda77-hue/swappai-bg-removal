"""Swappai background-removal microservice — slim build for 512MB hosts.

Uses u2netp (4.7MB) via raw onnxruntime: no rembg/cv2/scipy, so the whole
process peaks around ~250MB — fits Render's free tier.

POST /remove-bg  (multipart: file=<image>, header x-api-key) -> PNG with alpha
GET  /health     -> {"status":"ok","model":"u2netp"}

Env:
  BG_API_KEY   shared secret; if set, client must send header x-api-key
  BG_MAX_MB    max upload size in MB (default: 12)
  BG_MAX_PX    max image dimension in px; larger images are downscaled (default: 1600)
  MODEL_PATH   path to u2netp.onnx (default: models/u2netp.onnx)
"""
import io
import os

import numpy as np
import onnxruntime as ort
from fastapi import FastAPI, File, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from PIL import Image, ImageFilter

API_KEY = os.environ.get("BG_API_KEY", "")
MAX_MB = int(os.environ.get("BG_MAX_MB", "12"))
MAX_PX = int(os.environ.get("BG_MAX_PX", "1600"))
MODEL_PATH = os.environ.get("MODEL_PATH", "models/u2netp.onnx")

MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)
SIZE = (320, 320)

app = FastAPI(title="swappai bg-removal")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

sess_opts = ort.SessionOptions()
sess_opts.intra_op_num_threads = 1
sess_opts.inter_op_num_threads = 1
_session = ort.InferenceSession(
    MODEL_PATH, sess_options=sess_opts, providers=["CPUExecutionProvider"]
)
_input_name = _session.get_inputs()[0].name


def predict_mask(img: Image.Image) -> Image.Image:
    """Return a grayscale alpha mask at the image's original size."""
    im = img.convert("RGB").resize(SIZE, Image.LANCZOS)
    arr = np.asarray(im).astype(np.float32)
    arr = arr / max(float(arr.max()), 1e-6)
    arr = (arr - MEAN) / STD
    arr = arr.transpose(2, 0, 1)[np.newaxis, ...]

    pred = _session.run(None, {_input_name: arr})[0][:, 0, :, :]
    mi, ma = float(pred.min()), float(pred.max())
    pred = (pred - mi) / max(ma - mi, 1e-8)
    mask = Image.fromarray((pred[0] * 255).astype(np.uint8), mode="L")
    mask = mask.resize(img.size, Image.LANCZOS)
    return mask.filter(ImageFilter.GaussianBlur(0.75))


@app.get("/health")
def health():
    return {"status": "ok", "model": "u2netp"}


@app.post("/remove-bg")
async def remove_bg(file: UploadFile = File(...), x_api_key: str = Header(default="")):
    if API_KEY and x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="invalid api key")
    if not (file.content_type or "").startswith("image/"):
        raise HTTPException(status_code=400, detail="file must be an image")

    data = await file.read()
    if len(data) > MAX_MB * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"image larger than {MAX_MB}MB")

    try:
        img = Image.open(io.BytesIO(data)).convert("RGB")
    except Exception:
        raise HTTPException(status_code=400, detail="could not read image")

    if max(img.size) > MAX_PX:
        img.thumbnail((MAX_PX, MAX_PX), Image.LANCZOS)

    try:
        mask = predict_mask(img)
        out = img.convert("RGBA")
        out.putalpha(mask)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"removal failed: {e}")

    buf = io.BytesIO()
    out.save(buf, format="PNG")
    return Response(content=buf.getvalue(), media_type="image/png")


@app.exception_handler(HTTPException)
async def http_exc_handler(_, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"error": exc.detail})
