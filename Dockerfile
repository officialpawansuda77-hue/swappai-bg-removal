FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    BG_MODEL=isnet-general-use

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download the model at build time so the first request is fast.
RUN python -c "from rembg import new_session; new_session('$BG_MODEL')"

COPY app.py .
EXPOSE 7860
# Render assigns the port via $PORT; fall back to 7860 locally.
CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port ${PORT:-7860}"]
