"""Swappai background-removal microservice (rembg, MIT-licensed, commercial-safe).

POST /remove-bg  (multipart: file=<image>) -> PNG with transparent background
GET  /health     -> {"status":"ok","model":...}

Env:
  BG_API_KEY   shared secret; if set, client must send header x-api-key
  BG_MODEL     rembg model name (default: isnet-general-use)
  BG_MAX_MB    max upload size in MB (default: 12)
  BG_MAX_PX    max image dimension in px; larger images are downscaled (default: 2000)
"""
import io
import os

from fastapi import FastAPI, File, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from PIL import Image
from rembg import new_session, remove

API_KEY = os.environ.get("BG_API_KEY", "")
MODEL = os.environ.get("BG_MODEL", "isnet-general-use")
MAX_MB = int(os.environ.get("BG_MAX_MB", "12"))
MAX_PX = int(os.environ.get("BG_MAX_PX", "2000"))

app = FastAPI(title="swappai bg-removal")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

session = new_session(MODEL)  # downloads model once, then cached


@app.get("/health")
def health():
    return {"status": "ok", "model": MODEL}


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
        out = remove(img, session=session)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"removal failed: {e}")

    buf = io.BytesIO()
    out.save(buf, format="PNG")
    return Response(content=buf.getvalue(), media_type="image/png")


@app.exception_handler(HTTPException)
async def http_exc_handler(_, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"error": exc.detail})
