# swappai background-removal service

Free, self-hosted background removal for swappai (rembg + isnet-general-use).
No per-image fees, no API shutdown risk, full-resolution PNG output.

## Deploy on Hugging Face Spaces (free, ~3 minutes)

1. Go to https://huggingface.co/new-space → pick a name (e.g. `swappai-bg-removal`),
   select **Docker** as the SDK, keep it **Private**.
2. Upload these 3 files: `app.py`, `requirements.txt`, `Dockerfile`.
3. In the Space → **Settings → Variables and secrets**, add a secret:
   `BG_API_KEY` = any long random string (e.g. generated at random.org).
4. Wait for the build to finish (~3-5 min, the AI model downloads once).
5. Your API URL is `https://<your-username>-<space-name>.hf.space`.

## Wire up swappai

In Vercel → your `swappoai` project → **Settings → Environment Variables**, add:

| Variable | Value |
|---|---|
| `VITE_BG_REMOVAL_API_URL` | `https://<your-username>-<space-name>.hf.space` |
| `VITE_BG_REMOVAL_API_KEY` | the same `BG_API_KEY` secret from step 3 |

Then redeploy. The "Remove Background" buttons appear in the editor:
- **Uploads panel** — hover any image → scissors icon → cutout saved as a new item
- **Selected image** — Properties panel → Image Settings → Remove Background

## Local run

```bash
pip install -r requirements.txt
BG_API_KEY=dev-key uvicorn app:app --port 7860
curl -X POST http://127.0.0.1:7860/remove-bg \
  -H "x-api-key: dev-key" -F "file=@photo.jpg" -o cutout.png
```

## Notes

- First request after a cold start takes ~20-40s (model loads); after that ~5-10s per image on free CPU.
- Images are downscaled only if a side exceeds `BG_MAX_PX` (default 2000px).
- The Space is private + key-protected, so only swappai can use it.
