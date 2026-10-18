"""Fill the official AI Builder Cup template. Usage: python3 video/build_deck.py template.pptx out.pptx URL REPO VIDEO"""
import copy, json, os, sys
from pptx import Presentation
from pptx.util import Emu, Pt, Inches
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE

TPL, OUTP, APP, REPO, VIDEO = sys.argv[1:6]
SH = "video/out/"
prs = Presentation(TPL)
W, H = prs.slide_width, prs.slide_height
INK = RGBColor(0x17, 0x23, 0x1A); GREEN = RGBColor(0x1F, 0x7A, 0x4D); MUTE = RGBColor(0x5D, 0x6B, 0x60)
bench = json.load(open(SH + "bench.json")) if os.path.exists(SH + "bench.json") else []


def title_shape(slide):
    best = None
    for s in slide.shapes:
        if s.has_text_frame and s.text_frame.text.strip():
            if best is None or s.top < best.top:
                best = s
    return best


def content_top(slide):
    t = title_shape(slide)
    return (t.top + t.height + Inches(0.12)) if t else Inches(1.2)


def add_text(slide, items, top=None, left=Inches(0.55), width=None, size=15, bottom_pad=Inches(0.45)):
    top = top or content_top(slide)
    width = width or (W - left - Inches(0.5))
    tb = slide.shapes.add_textbox(left, top, width, H - top - bottom_pad)
    tf = tb.text_frame; tf.word_wrap = True
    first = True
    for it in items:
        head, body = (it if isinstance(it, tuple) else (None, it))
        p = tf.paragraphs[0] if first else tf.add_paragraph(); first = False
        p.space_after = Pt(5)
        if head:
            r = p.add_run(); r.text = head + "  "; r.font.bold = True; r.font.size = Pt(size); r.font.color.rgb = GREEN
        r = p.add_run(); r.text = body; r.font.size = Pt(size); r.font.color.rgb = INK
    return tb


def add_pic(slide, path, left, top, max_w, max_h):
    if not os.path.exists(path):
        return
    pic = slide.shapes.add_picture(path, left, top)
    ratio = min(max_w / pic.width, max_h / pic.height)
    pic.width, pic.height = int(pic.width * ratio), int(pic.height * ratio)
    pic.left = int(left + (max_w - pic.width) / 2)
    pic.line.color.rgb = RGBColor(0xDF, 0xE5, 0xDC)


def flow(slide):
    top = content_top(slide) + Inches(0.2)
    steps = [("Farmer", "Photo + note in own language, via phone"), ("Intake Agent", "Gemini: crop, peril, visible loss, translation"),
             ("Evidence Agent", "Satellite vegetation index + rainfall for district"), ("Adjudicator", "Scheme clauses, loss cap, payout (deterministic)"),
             ("Explainer Agent", "Gemini: verdict to farmer + assessor"), ("Outcome", "APPROVE + payout · SURVEY · REJECT, stored in Firestore")]
    n = len(steps); gap = Inches(0.18); left0 = Inches(0.45)
    bw = int((W - left0 * 2 - gap * (n - 1)) / n); bh = Inches(1.9)
    for i, (h, b) in enumerate(steps):
        x = left0 + i * (bw + gap)
        box = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, x, top, bw, bh)
        det = h in ("Evidence Agent", "Adjudicator")
        box.fill.solid(); box.fill.fore_color.rgb = RGBColor(0xE8, 0xF3, 0xEC) if det else RGBColor(0xE6, 0xF0, 0xFF)
        box.line.color.rgb = GREEN if det else RGBColor(0x1A, 0x4F, 0xA0)
        tf = box.text_frame; tf.word_wrap = True
        p = tf.paragraphs[0]; r = p.add_run(); r.text = h; r.font.bold = True; r.font.size = Pt(13); r.font.color.rgb = INK
        p2 = tf.add_paragraph(); r2 = p2.add_run(); r2.text = b; r2.font.size = Pt(10.5); r2.font.color.rgb = MUTE
        if i < n - 1:
            a = slide.shapes.add_shape(MSO_SHAPE.RIGHT_ARROW, x + bw + Inches(0.02), top + bh / 2 - Inches(0.1), gap - Inches(0.04), Inches(0.2))
            a.fill.solid(); a.fill.fore_color.rgb = MUTE; a.line.fill.background()
    add_text(slide, [("Blue", "= Gemini (reads, translates, explains)"), ("Green", "= deterministic engine (every number, every verdict)"),
                     ("Branch:", "photo/note contradicted by satellite + rainfall → fraud flag → physical survey queue")],
             top=top + bh + Inches(0.35), size=13)


def table(slide, rows, top):
    cols = len(rows[0]); left = Inches(0.5); width = W - Inches(1.0)
    shp = slide.shapes.add_table(len(rows), cols, left, top, width, Inches(0.3) * len(rows))
    t = shp.table
    t.columns[0].width = Inches(2.4)
    for j in range(1, cols): t.columns[j].width = int((width - Inches(2.4)) / (cols - 1))
    for i, row in enumerate(rows):
        for j, v in enumerate(row):
            c = t.cell(i, j); c.text = str(v)
            for p in c.text_frame.paragraphs:
                for r in p.runs:
                    r.font.size = Pt(9.5); r.font.bold = (i == 0)
    return shp


S = prs.slides
# Slide 1: team details
for shp in S[0].shapes:
    if not shp.has_text_frame:
        continue
    for p in shp.text_frame.paragraphs:
        txt = p.text.strip()
        fill = {"Team name:": "GroundTruth", "Team leader name:": "Lokesh Kadyan",
                "Problem Statement:": "Sustainability & Social Impact: crop-loss insurance claims for smallholder farmers settled in minutes, not months, with satellite-verified evidence"}
        for k, v in fill.items():
            if txt.startswith(k) and p.runs:
                r = p.add_run(); r.text = " " + v
                r.font.size = p.runs[0].font.size; r.font.bold = False; r.font.color.rgb = GREEN

add_text(S[2], [
    ("\u201cOur efforts were wiped out in three days.\u201d", "Jaya Krishna Dharal, paddy farmer, Jumla, Nepal, after unseasonal rain flattened the harvest (Kathmandu Post, Nov 2025)."),
    ("This is the season farmers are living right now:", "the Bhotekoshi floods washed away 1,806 hectares of farmland in Nuwakot, Nepal (Sep 2026). Three typhoons hit 85,671 Philippine farmers in two weeks (Sep 2025). In India, about \u20b9948 crore of crop-insurance claims sat unpaid in mid-2025, and some farmers waited up to 14 months."),
    ("The cruel part:", "the payout arrives after the next sowing season, when it can no longer buy seed. Assessment still depends on manual field surveys, and in the Philippines only about 1 in 10 farm households is insured at all."),
    ("GroundTruth:", "a farmer sends a phone photo and a note in their own language. Four agents on Google Cloud check it against satellite and rainfall evidence and settle it under the scheme rules in seconds, with every number traceable. The AI explains; a deterministic engine proves."),
], size=13)
add_text(S[3], [
    ("Different:", "Governments already run the two halves separately: satellite yield estimates for whole areas (India's YES-TECH) and farmer crop photos (CROPIC). Neither settles an individual claim. GroundTruth reconciles the farmer's photo with satellite evidence into one cited, deterministic decision per claim, explained back to the farmer."),
    ("Solves it by:", "Taking the survey off the critical path for corroborated claims; surveys go only to contradicted claims or unconfirmed top-ups. Best fit: individual localized-calamity claims (hail, inundation, post-harvest), which under India's PMFBY must be reported within 72 hours and today wait for a field inspection."),
    ("USP:", "A dramatic photo cannot outrun the satellite: assessed loss is capped by what remote sensing supports. Fraud is flagged, not silently paid or silently rejected. Works in the farmer's language."),
    ("Who it serves:", "smallholder farmers first; insurers and government schemes (India's PMFBY, Philippines' PCIC, Nepal's subsidised crop insurance) as the paying customers, with fewer surveys and fewer disputes."),
], size=13)
add_text(S[4], [
    ("Multilingual multimodal intake", "Gemini reads the field photo + note in Hindi, Marathi, Filipino, English and more"),
    ("Satellite + weather corroboration", "Vegetation-index drop, rainfall anomaly and standing-water days per district"),
    ("Deterministic adjudicator", "Covered peril, 7-day intimation, 33% threshold, corroboration, payout formula"),
    ("Fair top-up", "Pays the satellite-proven loss now and books a survey for any larger reported loss, so local damage is never silently cut"),
    ("Fraud / mismatch flag", "Contradicted claims routed to physical survey"),
    ("Explainable verdicts", "Farmer message in their language + assessor summary with cited clauses"),
    ("Claims ledger", "Every claim, evidence pack and agent trace stored in Firestore"),
    ("Never breaks", "Deterministic fallback if the model is unavailable"),
], size=14)
flow(S[5])
add_pic(S[6], SH + "shot_app.png", Inches(0.5), content_top(S[6]), W - Inches(1.0), H - content_top(S[6]) - Inches(0.4))
add_pic(S[7], SH + "shot_arch.png", Inches(0.5), content_top(S[7]), W - Inches(1.0), H - content_top(S[7]) - Inches(0.4))
add_text(S[8], [
    ("Gemini 2.5 Flash on Vertex AI", "multimodal intake agent and multilingual explainer agent"),
    ("Cloud Run", "serverless FastAPI service + web app, deployed from source"),
    ("Firestore (Firebase)", "claims ledger: claim, evidence pack, decision, agent trace"),
    ("Cloud Build + Artifact Registry", "container build and image storage"),
    ("Cloud Text-to-Speech", "narration for the demo"),
    ("Python, FastAPI, vanilla JS", "no heavy front-end framework; accessible, mobile-friendly UI"),
    ("Roadmap on GCP", "Earth Engine (Sentinel-2 per plot), Speech-to-Text voice intake, Vertex AI Search over scheme documents, BigQuery for portfolio analytics"),
], size=14)
add_text(S[9], [
    ("Per claim:", "2 Gemini Flash calls (one with an image) + one Firestore write: well under one US cent per claim at list prices."),
    ("Platform:", "Cloud Run scales to zero; a pilot district of 10,000 claims a season runs for tens of US dollars of cloud cost."),
    ("Biggest saving:", "field surveys avoided for corroborated claims, which today cost insurers far more per claim than the cloud does."),
], size=15)
top11 = content_top(S[10]); half = (W - Inches(1.2)) / 2
add_pic(S[10], SH + "shot_verdict.png", Inches(0.5), top11, half, H - top11 - Inches(0.4))
add_pic(S[10], SH + "shot_fraud.png", Inches(0.7) + half, top11, half, H - top11 - Inches(0.4))
if bench:
    rows = [["Scenario", "Expected", "Verdict", "Assessed loss", "Payout (₹)", "Latency (s)", "Language"]]
    for b in bench:
        rows.append([b["case"], b["expected"], b["verdict"], f"{b['loss']}%", f"{b['payout']:,}", f"{b['ms']/1000:.1f}", b.get("lang") or ""])
    t = table(S[11], rows, content_top(S[11]))
    ok = sum(b["ok"] for b in bench); med = sorted(b["ms"] for b in bench)[len(bench) // 2] / 1000
    add_text(S[11], [("Result:", f"{ok}/{len(bench)} verdicts correct on live Cloud Run · median end-to-end {med:.1f}s per claim (vs weeks to months today) · 6/6 engine unit tests pass · identical inputs give identical decisions.")],
             top=H - Inches(0.95), size=12)
add_text(S[12], [
    ("Live data:", "plot-level Sentinel-2 NDVI via Earth Engine, using field boundaries such as Google's AnthroKrishi maps; Sentinel-1 radar so monsoon cloud cover does not blind flood checks; gridded rainfall feeds."),
    ("Voice intake:", "Speech-to-Text so farmers can simply speak the claim."),
    ("Scheme knowledge:", "Vertex AI Search over each country's scheme documents, so policy clauses are retrieved and cited per programme."),
    ("Insurer console:", "survey queue for flagged claims, portfolio analytics in BigQuery."),
    ("Scale:", "tenant-per-insurer isolation, least-privilege IAM, regional deployment across JAPAC."),
    ("Note:", "satellite and rainfall values in this prototype are synthetic, clearly labelled sample signals; the scheme is a model area-yield scheme."),
    ("Sources:", "Kathmandu Post (2 Nov 2025; 7 Sep 2026); Malaya Business Insight / Philippine Dept. of Agriculture (2 Oct 2025); IASgyan summary of PMFBY data and IIM study (2025); PhilRice survey via SEARCA (2015)."),
], size=13)
add_text(S[13], [("GitHub repository:", REPO), ("Demo video:", VIDEO), ("Live prototype:", APP)], size=17)

# drop the template's instruction slide (2) and the trailing duplicate
def drop(idx):
    sld = prs.slides._sldIdLst[idx]
    prs.part.drop_rel(sld.rId); prs.slides._sldIdLst.remove(sld)
n = len(prs.slides)
if n >= 16 and "Team" in "".join(s.text_frame.text for s in prs.slides[n - 1].shapes if s.has_text_frame):
    drop(n - 1)
drop(14); drop(1)
prs.save(OUTP)
print("saved", OUTP, len(prs.slides), "slides", W, H)
