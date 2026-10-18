"""Generate the demo field photos with Gemini image generation (Vertex AI) as compact JPEGs.

Usage (Cloud Shell): python3 video/gen_samples.py [name ...]   # default: any missing
"""
import base64, io, json, os, subprocess, sys, time, urllib.request

P = os.environ.get("PROJECT", "august-apogee-382815")
OUT = "static/samples"
PROMPTS = {
    "flood": "Realistic smartphone photo of a rice paddy field in Assam India completely submerged by brown floodwater, flattened green rice plants under water, overcast sky, no people, no text",
    "drought": "Realistic smartphone photo of a cotton field in Maharashtra India during drought, wilted dry brown cotton plants, cracked dry soil, harsh sunlight, no people, no text",
    "typhoon": "Realistic smartphone photo of a rice field in the Philippines after a typhoon, rice plants flattened and lodged by wind, puddles of water, damaged, no people, no text",
    "healthy": "Realistic smartphone photo of a healthy green wheat field in Punjab India, lush uniform crop, clear blue sky, no damage, no flooding, no people, no text",
}


def to_jpeg(raw):
    try:
        from PIL import Image
        im = Image.open(io.BytesIO(raw)).convert("RGB")
        im.thumbnail((1280, 1280))
        buf = io.BytesIO(); im.save(buf, "JPEG", quality=82, optimize=True)
        return buf.getvalue()
    except Exception:
        return raw


def gen(name):
    tok = subprocess.check_output(["gcloud", "auth", "print-access-token"]).decode().strip()
    body = {"contents": [{"role": "user", "parts": [{"text": PROMPTS[name]}]}],
            "generationConfig": {"responseModalities": ["IMAGE"], "imageConfig": {"aspectRatio": "4:3"}}}
    for host, loc in [("aiplatform.googleapis.com", "global"), ("us-central1-aiplatform.googleapis.com", "us-central1")]:
        for attempt in range(3):
            try:
                req = urllib.request.Request(
                    f"https://{host}/v1/projects/{P}/locations/{loc}/publishers/google/models/gemini-2.5-flash-image:generateContent",
                    data=json.dumps(body).encode(), headers={"Authorization": "Bearer " + tok, "Content-Type": "application/json"})
                r = json.load(urllib.request.urlopen(req, timeout=90))
                part = [x for x in r["candidates"][0]["content"]["parts"] if "inlineData" in x][0]["inlineData"]
                open(f"{OUT}/{name}.jpg", "wb").write(to_jpeg(base64.b64decode(part["data"])))
                print(name, "ok", loc); return True
            except Exception as e:
                print(name, loc, "retry", attempt, str(e)[:100]); time.sleep(8)
    return False


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    names = sys.argv[1:] or [n for n in PROMPTS if not os.path.exists(f"{OUT}/{n}.jpg")]
    for n in names:
        gen(n)
    # recompress any oversized existing samples
    for n in PROMPTS:
        p = f"{OUT}/{n}.jpg"
        if os.path.exists(p) and os.path.getsize(p) > 600_000:
            data = to_jpeg(open(p, "rb").read()); open(p, "wb").write(data); print("recompressed", n, os.path.getsize(p))
