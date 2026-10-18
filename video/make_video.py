"""Build the demo video: Cloud TTS narration + Playwright capture of the live app.

Usage (Cloud Shell):  python3 video/make_video.py https://<service-url>
Needs: pip install playwright imageio-ffmpeg ; playwright install --with-deps chromium
"""
import socket; socket.setdefaulttimeout(45)
import asyncio, base64, json, os, subprocess, sys, urllib.request, wave

URL = sys.argv[1].rstrip("/")
OUT = "video/out"; os.makedirs(OUT, exist_ok=True)
P = os.environ.get("PROJECT", "august-apogee-382815")

SCENES = [
 ("intro", "Every monsoon, millions of smallholder farmers across Asia-Pacific lose their crops to floods, droughts and typhoons. Crop insurance exists, but a claim can take months to settle, because every claim waits for a manual field survey. GroundTruth changes that."),
 ("overview", "This is GroundTruth, running live on Cloud Run. A farmer files a claim with what they already have: a phone photo and a short note, in their own language. Four agents then check it against satellite and weather evidence, and settle it under the scheme rules."),
 ("flood", "Ramesh, in Assam, lost his paddy to the Brahmaputra flood. He writes in Hindi and attaches a photo of his field. The Intake Agent, Gemini on Vertex AI, reads both. It identifies the crop and the peril, estimates the visible loss, and translates the note. The Evidence Agent pulls the district's satellite vegetation index and rainfall. Rainfall more than double normal. Vegetation down by more than half. Nine days of standing water. The claim is corroborated."),
 ("verdict", "The Policy and Adjudicator engine applies each clause of the scheme. Covered peril. Reported within seven days. Corroborated. Loss above the thirty three percent threshold. Approved, with the payout calculated to the rupee, and every clause cited. The Explainer Agent writes the decision back to Ramesh in Hindi, and a summary for the assessor. Under a minute, instead of months."),
 ("drought", "Sunita, in Maharashtra, writes in Marathi about her drought-hit cotton. Look at the assessed loss. Her photo may suggest more, but GroundTruth caps the loss at what the satellite supports. A dramatic photo cannot outrun the evidence."),
 ("fraud", "Now a suspicious claim from Punjab. The note says total flood loss. But Gemini sees a healthy wheat field, and district rainfall was normal. GroundTruth does not pay it, and it does not silently reject the farmer either. It flags the mismatch, and routes the claim to a physical survey."),
 ("ledger", "Every claim, with its full evidence pack and agent trace, is stored in Firestore. The design principle is simple. The AI explains. A deterministic engine proves. Gemini reads and writes, but it never sets a number. So every decision is reproducible and auditable, which is exactly what an insurer and a regulator need."),
 ("close", "Next, we plug in live Sentinel-2 imagery from Earth Engine for each insured plot, voice intake, and each country's scheme documents in Vertex AI Search. GroundTruth. Crop claims, verified from space, in minutes, not months."),
]


def tts():
    tok = subprocess.check_output(["gcloud", "auth", "print-access-token"]).decode().strip()
    durs = {}
    for name, text in SCENES:
        path = f"{OUT}/{name}.wav"
        for voice in ([] if os.path.exists(path) else ["en-IN-Chirp3-HD-Charon", "en-IN-Neural2-B", "en-US-Neural2-J"]):
            body = {"input": {"text": text}, "voice": {"languageCode": voice[:5], "name": voice},
                    "audioConfig": {"audioEncoding": "LINEAR16", "sampleRateHertz": 24000, "speakingRate": 1.0}}
            req = urllib.request.Request("https://texttospeech.googleapis.com/v1/text:synthesize",
                                         data=json.dumps(body).encode(),
                                         headers={"Authorization": "Bearer " + tok, "Content-Type": "application/json",
                                                  "x-goog-user-project": P})
            try:
                r = json.load(urllib.request.urlopen(req, timeout=60))
                open(path, "wb").write(base64.b64decode(r["audioContent"]))
                break
            except Exception as e:
                print("voice failed", voice, str(e)[:120])
        with wave.open(path) as w:
            durs[name] = w.getnframes() / w.getframerate() + 6.0
        print(name, round(durs[name], 1), "s")
    # concat with 0.6s gaps
    with wave.open(f"{OUT}/{SCENES[0][0]}.wav") as w0:
        params = w0.getparams()
    with wave.open(f"{OUT}/narration.wav", "wb") as out:
        out.setparams(params)
        for name, _ in SCENES:
            with wave.open(f"{OUT}/{name}.wav") as w:
                out.writeframes(w.readframes(w.getnframes()))
            out.writeframes(b"\x00\x00" * int(params.framerate * 6.0))
    return durs


async def record(durs):
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        b = await p.chromium.launch()
        ctx = await b.new_context(viewport={"width": 1600, "height": 900},
                                  record_video_dir=OUT, record_video_size={"width": 1600, "height": 900})
        pg = await ctx.new_page()
        import time
        t_start = time.time()
        clock = [0.0]

        async def until(name):
            clock[0] += durs[name]
            left = clock[0] - (time.time() - t_start)
            if left > 0:
                await pg.wait_for_timeout(int(left * 1000))

        async def run_claim(preset):
            await pg.click(f"[data-preset='{preset}']")
            await pg.wait_for_timeout(1500)
            await pg.click("#submitBtn")
            await pg.wait_for_selector(".badge", timeout=90000)
            await pg.wait_for_timeout(2500)

        await pg.goto(URL + "/static/intro.html")
        await until("intro")
        await pg.goto(URL + "/")
        await pg.wait_for_timeout(2500)
        await pg.evaluate("window.scrollTo({top:0})")
        await until("overview")
        await run_claim("flood")
        await pg.screenshot(path=f"{OUT}/shot_app.png")
        await pg.evaluate("document.querySelector('#h-agents').scrollIntoView({behavior:'smooth'})")
        await until("flood")
        await pg.evaluate("document.querySelector('#h-result').scrollIntoView({behavior:'smooth'})")
        await pg.wait_for_timeout(int(durs["verdict"] * 450))
        await pg.screenshot(path=f"{OUT}/shot_verdict.png")
        await pg.mouse.wheel(0, 380)
        await until("verdict")
        await pg.evaluate("window.scrollTo({top:0,behavior:'smooth'})")
        await run_claim("drought")
        await pg.evaluate("document.querySelector('#h-result').scrollIntoView({behavior:'smooth'})")
        await until("drought")
        await pg.evaluate("window.scrollTo({top:0,behavior:'smooth'})")
        await run_claim("fraud")
        await pg.evaluate("document.querySelector('#h-agents').scrollIntoView({behavior:'smooth'})")
        await pg.wait_for_timeout(int(durs["fraud"] * 400))
        await pg.evaluate("document.querySelector('#h-result').scrollIntoView({behavior:'smooth'})")
        await pg.wait_for_timeout(1200)
        await pg.screenshot(path=f"{OUT}/shot_fraud.png")
        await until("fraud")
        await pg.evaluate("document.querySelector('#h-hist').scrollIntoView({behavior:'smooth'})")
        await pg.wait_for_timeout(int(durs["ledger"] * 400))
        await pg.screenshot(path=f"{OUT}/shot_ledger.png")
        await pg.goto(URL + "/static/arch.html")
        await pg.wait_for_timeout(800)
        await pg.screenshot(path=f"{OUT}/shot_arch.png")
        await until("ledger")
        await pg.goto(URL + "/static/intro.html")
        await until("close")
        await pg.wait_for_timeout(1200)
        vpath = await pg.video.path()
        await ctx.close(); await b.close()
        return vpath


def mux(vpath):
    import imageio_ffmpeg
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    out = f"{OUT}/GroundTruth_Demo.mp4"
    subprocess.check_call([ff, "-y", "-i", vpath, "-i", f"{OUT}/narration.wav", "-c:v", "libx264", "-preset", "veryfast",
                           "-crf", "22", "-pix_fmt", "yuv420p", "-vf", "scale=1920:1080:flags=lanczos", "-c:a", "aac",
                           "-b:a", "160k", "-shortest", out])
    print("VIDEO", out)


if __name__ == "__main__":
    d = tts()
    print("total narration", round(sum(d.values()), 1), "s")
    v = asyncio.run(record(d))
    mux(v)
