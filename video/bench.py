"""Benchmark the live service: latency and verdicts for the four demo scenarios."""
import json, sys, time, urllib.request, uuid

URL = sys.argv[1].rstrip("/")
import os; os.makedirs("video/out", exist_ok=True)
CASES = [
    ("Flood, Assam (Hindi)", "nagaon-in", 2.5, 3, "flood.jpg", "बाढ़ में मेरी धान की पूरी फसल डूब गई है, नौ दिन से खेत में पानी खड़ा है।", "APPROVE"),
    ("Drought, Maharashtra (Marathi)", "yavatmal-in", 4, 5, "drought.jpg", "पाऊस न पडल्यामुळे माझ्या कापसाची झाडे सुकून गेली आहेत.", "APPROVE"),
    ("Typhoon, Philippines (Filipino)", "isabela-ph", 3, 2, "typhoon.jpg", "Nalubog at nadapa ang palay ko dahil sa bagyo at baha.", "APPROVE"),
    ("Unsupported claim, Punjab", "ludhiana-in", 6, 4, "healthy.jpg", "Heavy flood destroyed my entire wheat crop, total loss.", "SURVEY"),
    ("Late report, Assam (20 days)", "nagaon-in", 2.5, 20, "flood.jpg", "Flood destroyed my paddy.", "REJECT"),
]


def post(fields, img):
    b = uuid.uuid4().hex
    body = b""
    for k, v in fields.items():
        body += f"--{b}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode()
    body += f"--{b}\r\nContent-Disposition: form-data; name=\"photo\"; filename=\"f.jpg\"\r\nContent-Type: image/jpeg\r\n\r\n".encode() + img + b"\r\n"
    body += f"--{b}--\r\n".encode()
    req = urllib.request.Request(URL + "/api/claims", data=body, headers={"Content-Type": "multipart/form-data; boundary=" + b})
    return json.load(urllib.request.urlopen(req, timeout=120))


rows = []
for name, d, acres, days, img, note, expect in CASES:
    data = open("static/samples/" + img, "rb").read()
    t = time.time()
    c = post({"district": d, "acres": acres, "days_since_event": days, "note": note, "farmer": "Bench"}, data)
    ms = int((time.time() - t) * 1000)
    rows.append({"case": name, "expected": expect, "verdict": c["decision"]["verdict"], "ok": c["decision"]["verdict"] == expect,
                 "loss": c["decision"]["assessed_loss_pct"], "payout": c["decision"]["payout"], "ms": ms,
                 "intake": c["intake"].get("source"), "lang": c["intake"].get("language"), "stored": c.get("stored")})
    print(rows[-1])
json.dump(rows, open("video/out/bench.json", "w"), ensure_ascii=False, indent=1)
print("accuracy", sum(r["ok"] for r in rows), "/", len(rows), "median ms", sorted(r["ms"] for r in rows)[len(rows) // 2])
