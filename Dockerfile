FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    OMP_NUM_THREADS=1 \
    OPENBLAS_NUM_THREADS=1

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Bake the u2netp weights into the image (4.7MB) so there is no runtime download.
RUN mkdir -p models && python - <<'EOF'
import hashlib, urllib.request
url = "https://github.com/danielgatis/rembg/releases/download/v0.0.0/u2netp.onnx"
dst = "models/u2netp.onnx"
urllib.request.urlretrieve(url, dst)
md5 = hashlib.md5(open(dst, "rb").read()).hexdigest()
assert md5 == "8e83ca70e441ab06c318d82300c84806", f"checksum mismatch: {md5}"
print("u2netp.onnx ok", md5)
EOF

COPY app.py .
EXPOSE 7860
CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port ${PORT:-7860} --workers 1"]
