"""Build the demo video: Cloud TTS narration + Playwright capture of the live app.

Each scene is a list of beats (one narrated sentence + the on-screen action it describes).
Every beat is synthesised separately, so its exact duration is known; the recorder performs
the beat's action (scroll, highlight, reveal) as the sentence starts. Set-up work between
scenes (page loads, waiting for the live claim to finish) is recorded but cut in the edit,
so the final video has no dead air and the picture always matches the words.

Usage (Cloud Shell):  python3 video/make_video.py https://<service-url>
Needs: pip install playwright imageio-ffmpeg ; playwright install --with-deps chromium
"""
import socket; socket.setdefaulttimeout(45)
import asyncio, base64, hashlib, json, os, subprocess, sys, time, urllib.request, wave

URL = sys.argv[1].rstrip("/")
OUT = "video/out"; os.makedirs(OUT, exist_ok=True)
P = os.environ.get("PROJECT", "august-apogee-382815")
GAP = 0.35          # breath between sentences
SCENE_TAIL = 0.5    # settle time at the end of each scene
MIN_TOTAL = 182.0   # submission rule: 3 to 4 minutes

# (scene, action, sentence). Actions are interpreted by `act()` below.
BEATS = [
 ("intro", "stat:0", "Last month, floods in Nuwakot, Nepal, washed away more than eighteen hundred hectares of farmland."),
 ("intro", "stat:1", "In the Philippines, three typhoons in two weeks hit more than eighty five thousand farmers."),
 ("intro", "stat:2", "Many of them are insured. But every claim waits for a manual field survey, and the payout can take months."),
 ("intro", "stat:3", "GroundTruth settles it in under a minute."),

 ("overview", "spot:#claimForm", "This is GroundTruth, live on Cloud Run. A farmer files a claim with what they already have: a phone photo, and a short note in their own language."),
 ("overview", "spot:#agents", "Four agents take it from there. Two are Gemini on Vertex AI. Two are plain, deterministic code."),

 ("flood", "spot:#claimForm", "Ramesh, in Assam, lost his paddy to the Brahmaputra flood. He writes in Hindi, and attaches a photo of his field."),
 ("flood", "agent:0", "The Intake Agent reads both. It identifies the crop and the peril, estimates the visible loss, and translates his note."),
 ("flood", "agent:1", "The Evidence Agent pulls satellite vegetation index and rainfall for his district. Rainfall more than double normal. Vegetation down by more than half. The claim is corroborated."),
 ("flood", "agent:2", "The Adjudicator is tested code, not a model. It applies each clause of the scheme."),
 ("flood", "result:.checks", "Covered peril. Reported within seven days. Corroborated by evidence. Loss above the thirty three percent threshold."),
 ("flood", "spot:.verdict", "Approved. The payout is calculated to the rupee, after the deductible, and every line cites its clause."),
 ("flood", "agent3:.msg", "The Explainer Agent writes the decision back to Ramesh in Hindi, and a summary for the assessor, using only the engine's facts."),
 ("flood", "spot:.verdict .stat:last-child", "End to end, in seconds. Not months."),

 ("drought", "spot:#claimForm", "Sunita, in Maharashtra, writes in Marathi about her cotton, dried out by a failed monsoon."),
 ("drought", "result:.verdict .stat", "Look at the assessed loss. It is capped at what the satellite supports, so a dramatic photo can never outrun the evidence."),
 ("drought", "spot:.flag.topup|.checks", "But satellites miss local damage too. So when a farmer reports clearly more than the data confirms, GroundTruth pays the proven loss now, and books a field survey for the rest. No genuine loss is silently cut."),
 ("drought", "agent3:.msg", "And Sunita gets her answer in Marathi."),

 ("fraud", "spot:#claimForm", "Now a suspicious claim from Punjab. The note says: heavy flood, total loss."),
 ("fraud", "agents:0,1", "But Gemini sees a healthy wheat field, and district rainfall was normal."),
 ("fraud", "result:.flag", "GroundTruth does not pay it. It does not silently reject the farmer either. It flags the mismatch, and routes the claim to a physical survey."),
 ("fraud", "agent3:#agents li[data-a='0'] small", "Every photo is also checked for capture metadata and fingerprinted, so the same picture reused in another farmer's claim is caught."),

 ("ledger", "spot:#ledger", "Every claim is written to Firestore with its full evidence pack: the inputs, every rule check, the model output, timings, and the engine version."),

 ("arch", "spot:.principle", "The design principle is simple. The AI explains. A deterministic engine proves."),
 ("arch", "spot:.flow", "Gemini returns schema-validated output, with timeouts, retries, and a rule-based fallback. If the model is down, the explanation degrades. The verdict never does."),
 ("arch", "spot:.base", "Same inputs, same decision, every time. That is what an insurer, and a regulator, can sign off on."),
 ("arch", "spot:.next", "Next, live Sentinel-2 and radar imagery from Earth Engine for each insured plot, voice intake, and each country's scheme rules in Vertex AI Search."),

 ("close", "none", "GroundTruth. Crop claims, verified from space. In minutes, not months."),
]

SCENES = list(dict.fromkeys(s for s, _, _ in BEATS))
VOICES = ["en-IN-Chirp3-HD-Charon", "en-IN-Neural2-B", "en-US-Neural2-J"]


def wav_path(text):
    return f"{OUT}/b_{hashlib.sha1(text.encode()).hexdigest()[:10]}.wav"


def tts():
    tok = subprocess.check_output(["gcloud", "auth", "print-access-token"]).decode().strip()
    durs = []
    for i, (_, _, text) in enumerate(BEATS):
        path = wav_path(text)
        for voice in ([] if os.path.exists(path) else VOICES):
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
            durs.append(w.getnframes() / w.getframerate())
        print(f"beat {i:02d} {durs[-1]:5.1f}s  {text[:60]}")
    return durs


def timeline(durs):
    """Per-scene length, with the close scene padded so the cut meets the 3-minute floor."""
    scene_len = {s: SCENE_TAIL for s in SCENES}
    for (s, _, _), d in zip(BEATS, durs):
        scene_len[s] += d + GAP
    total = sum(scene_len.values())
    if total < MIN_TOTAL:
        scene_len["close"] += MIN_TOTAL - total
    return scene_len


def narration(durs, scene_len):
    with wave.open(wav_path(BEATS[0][2])) as w0:
        params = w0.getparams()
    silence = lambda sec: b"\x00\x00" * int(params.framerate * sec)
    with wave.open(f"{OUT}/narration.wav", "wb") as out:
        out.setparams(params)
        for s in SCENES:
            used = 0.0
            for (bs, _, text), d in zip(BEATS, durs):
                if bs != s:
                    continue
                with wave.open(wav_path(text)) as w:
                    out.writeframes(w.readframes(w.getnframes()))
                out.writeframes(silence(GAP)); used += d + GAP
            out.writeframes(silence(scene_len[s] - used))


STAGE_CSS = """
.spot{outline:4px solid #f5a623 !important;outline-offset:5px;border-radius:10px;
      box-shadow:0 0 0 9999px rgba(10,20,14,.18);transition:outline-color .3s;position:relative;z-index:5}
body.stage #agents li .out{visibility:hidden}
body.stage #result{visibility:hidden}
"""

JS = """
window.__spot = (sel) => {
  document.querySelectorAll('.spot').forEach(e => e.classList.remove('spot'));
  if (!sel) return false;
  const el = sel.split('|').map(s => document.querySelector(s)).find(Boolean);
  if (!el) return false;
  el.classList.add('spot');
  el.scrollIntoView({behavior: 'smooth', block: el.offsetHeight > innerHeight * .8 ? 'start' : 'center'});
  return true;
};
window.__stage = () => {           // hold finished outputs back so each is shown as it is narrated
  document.body.classList.add('stage');
  document.querySelectorAll('#agents li').forEach(li => { li.dataset.c = li.className; li.className = ''; });
};
window.__agent = (i) => {
  const li = document.querySelector(`#agents li[data-a='${i}']`);
  li.className = li.dataset.c || 'done'; li.querySelector('.out').style.visibility = 'visible';
};
window.__result = () => { document.querySelector('#result').style.visibility = 'visible'; };
"""


async def record(durs, scene_len):
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        b = await p.chromium.launch()
        ctx = await b.new_context(viewport={"width": 1600, "height": 900},
                                  record_video_dir=OUT, record_video_size={"width": 1600, "height": 900})
        await ctx.add_init_script(JS)
        pg = await ctx.new_page()
        tv0 = time.time()
        cuts = []

        async def load(path):
            await pg.goto(URL + path); await pg.add_style_tag(content=STAGE_CSS)
            await pg.wait_for_timeout(900)

        async def claim(preset):
            await pg.evaluate("window.scrollTo({top:0})")
            await pg.click(f"[data-preset='{preset}']")
            await pg.wait_for_timeout(1200)
            await pg.click("#submitBtn")
            await pg.wait_for_selector(".badge", timeout=90000)
            await pg.wait_for_timeout(2600)          # let the UI's own reveal finish
            await pg.evaluate("window.__stage(); window.__spot(null); window.scrollTo({top:0})")
            await pg.wait_for_timeout(500)

        async def act(a):
            kind, _, arg = a.partition(":")
            if kind == "stat":
                await pg.evaluate(f"window.__spot(null); document.querySelectorAll('.stats div')[{arg}].classList.add('spot')")
            elif kind == "spot":
                await pg.evaluate("s => window.__spot(s)", arg)
            elif kind == "agent":
                await pg.evaluate(f"window.__agent({arg}); window.__spot(\"#agents li[data-a='{arg}']\")")
            elif kind == "agents":
                for i in arg.split(","):
                    await pg.evaluate(f"window.__agent({i})")
                await pg.evaluate("window.__spot('#agents')")
            elif kind == "agent3":
                await pg.evaluate("window.__agent(3); window.__result()")
                await pg.evaluate("s => window.__spot(s)", arg)
            elif kind == "result":
                await pg.evaluate("window.__agent(0); window.__agent(1); window.__agent(2); window.__result()")
                await pg.evaluate("s => window.__spot(s)", arg)

        setup = {
            "intro": lambda: load("/static/intro.html"),
            "overview": lambda: load("/"),
            "flood": lambda: claim("flood"),
            "drought": lambda: claim("drought"),
            "fraud": lambda: claim("fraud"),
            "ledger": lambda: pg.evaluate("window.__agent(0);window.__agent(1);window.__agent(2);window.__agent(3);window.__result();window.__spot(null)"),
            "arch": lambda: load("/static/arch.html"),
            "close": lambda: load("/static/intro.html"),
        }
        for s in SCENES:
            await setup[s]()
            if s == "ledger":
                await pg.wait_for_timeout(300)
            t0 = time.time()
            clock = 0.0
            for (bs, a, _), d in zip(BEATS, durs):
                if bs != s:
                    continue
                await act(a)
                clock += d + GAP
                left = clock - (time.time() - t0)
                if left > 0:
                    await pg.wait_for_timeout(int(left * 1000))
            left = scene_len[s] - (time.time() - t0)
            if left > 0:
                await pg.wait_for_timeout(int(left * 1000))
            cuts.append((t0 - tv0, scene_len[s]))
            if s in ("flood", "fraud"):
                await pg.screenshot(path=f"{OUT}/shot_{s}.png")
            print(f"scene {s:9s} at {t0 - tv0:6.1f}s len {scene_len[s]:5.1f}s")
        vpath = await pg.video.path()
        await ctx.close(); await b.close()
        return vpath, cuts


def edit(vpath, cuts):
    import imageio_ffmpeg
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    parts = "".join(f"[0:v]trim=start={a:.3f}:duration={d:.3f},setpts=PTS-STARTPTS[v{i}];"
                    for i, (a, d) in enumerate(cuts))
    graph = parts + "".join(f"[v{i}]" for i in range(len(cuts))) + \
        f"concat=n={len(cuts)}:v=1:a=0,fps=30,scale=1920:1080:flags=lanczos[v]"
    out = f"{OUT}/GroundTruth_Demo.mp4"
    subprocess.check_call([ff, "-y", "-i", vpath, "-i", f"{OUT}/narration.wav", "-filter_complex", graph,
                           "-map", "[v]", "-map", "1:a", "-c:v", "libx264", "-preset", "veryfast", "-crf", "21",
                           "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart",
                           "-shortest", out])
    print("VIDEO", out)


if __name__ == "__main__":
    d = tts()
    L = timeline(d)
    print("speech", round(sum(d), 1), "s · cut length", round(sum(L.values()), 1), "s")
    narration(d, L)
    v, cuts = asyncio.run(record(d, L))
    edit(v, cuts)
