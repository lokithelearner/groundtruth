"use strict";
const $ = (s) => document.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const money = (n) => "₹" + Number(n || 0).toLocaleString("en-IN");

const PRESETS = {
  flood: { farmer: "Ramesh", district: "nagaon-in", acres: 2.5, days: 3, img: "flood.jpg",
    note: "बाढ़ में मेरी धान की पूरी फसल डूब गई है, नौ दिन से खेत में पानी खड़ा है।" },
  drought: { farmer: "Sunita", district: "yavatmal-in", acres: 4, days: 5, img: "drought.jpg",
    note: "पाऊस न पडल्यामुळे माझ्या कापसाची झाडे सुकून गेली आहेत." },
  typhoon: { farmer: "Maria", district: "isabela-ph", acres: 3, days: 2, img: "flood.jpg",
    note: "Nalubog at nadapa ang palay ko dahil sa bagyo at baha." },
  fraud: { farmer: "Harpreet", district: "ludhiana-in", acres: 6, days: 4, img: "healthy.jpg",
    note: "Heavy flood destroyed my entire wheat crop, total loss." },
};
let presetBlob = null;

async function loadDistricts() {
  const ds = await fetch("/api/districts").then((r) => r.json());
  $("#district").innerHTML = ds.map((d) => `<option value="${esc(d.id)}">${esc(d.name)} — ${esc(d.event)}</option>`).join("");
}

async function applyPreset(key) {
  const p = PRESETS[key], f = $("#claimForm");
  f.farmer.value = p.farmer; f.district.value = p.district; f.acres.value = p.acres;
  f.days_since_event.value = p.days; f.note.value = p.note; $("#photo").value = "";
  presetBlob = null;
  try {
    const r = await fetch("/static/samples/" + p.img);
    if (r.ok) { presetBlob = await r.blob(); showPreview(presetBlob); } else { $("#preview").hidden = true; }
  } catch { $("#preview").hidden = true; }
}

function showPreview(blob) { const img = $("#preview"); img.src = URL.createObjectURL(blob); img.alt = "Field photo"; img.hidden = false; }

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
function setAgent(i, state, html) {
  const li = document.querySelector(`[data-a="${i}"]`);
  li.classList.remove("run", "done"); if (state) li.classList.add(state);
  if (html !== undefined) li.querySelector(".out").innerHTML = html;
}

async function submitClaim(e) {
  e.preventDefault();
  const btn = $("#submitBtn"); btn.disabled = true; btn.textContent = "Verifying…";
  [0, 1, 2, 3].forEach((i) => setAgent(i, null, ""));
  $("#result").className = "empty"; $("#result").textContent = "Agents are working…";
  const fd = new FormData($("#claimForm"));
  if (!$("#photo").files.length && presetBlob) fd.set("photo", presetBlob, "field.jpg");
  const t0 = performance.now();
  setAgent(0, "run");
  let c;
  try {
    const r = await fetch("/api/claims", { method: "POST", body: fd });
    if (!r.ok) throw new Error((await r.json()).detail || r.statusText);
    c = await r.json();
  } catch (err) {
    $("#result").textContent = "Could not verify: " + err.message; setAgent(0, null);
    btn.disabled = false; btn.textContent = "Verify claim"; return;
  }
  const secs = ((performance.now() - t0) / 1000).toFixed(1);
  const it = c.intake, ev = c.evidence, d = c.decision, x = c.explanation;
  setAgent(0, "done", `Crop <code>${esc(it.crop)}</code> · peril <code>${esc(it.peril)}</code> · photo loss <code>${esc(it.field_loss_pct)}%</code> · language <code>${esc(it.language)}</code><br>${esc(it.visual_evidence)}<br><i>“${esc(it.note_english)}”</i>`);
  setAgent(1, "run"); await sleep(600);
  setAgent(1, "done", `${esc(ev.event)}<br>${ev.signals.map(esc).join("<br>")}<br>Corroborates claim: <b>${ev.corroborates ? "yes" : "no"}</b>`);
  setAgent(2, "run"); await sleep(600);
  setAgent(2, "done", `${d.checks.filter((k) => k.pass).length}/${d.checks.length} checks passed · clauses ${d.clauses.map((k) => k.id).join(", ")}`);
  setAgent(3, "run"); await sleep(500);
  setAgent(3, "done", `Message written in ${esc(it.language)}`);
  $("#kpiTime").textContent = secs + " s";

  $("#result").className = "";
  $("#result").innerHTML = `
    <div class="verdict">
      <div class="badge ${esc(d.verdict)}"><span>Verdict · ${esc(c.id)}</span><b>${esc(d.verdict)}</b></div>
      <div class="stat"><b>${esc(d.assessed_loss_pct)}%</b><span>assessed loss</span></div>
      <div class="stat"><b>${money(d.sum_insured)}</b><span>sum insured</span></div>
      <div class="stat"><b>${money(d.payout)}</b><span>payout (after 5% deductible)</span></div>
      <div class="stat"><b>${secs} s</b><span>end-to-end time</span></div>
    </div>
    ${d.topup_survey ? `<div class="flag topup">✓ Paid now for the ${esc(d.assessed_loss_pct)}% loss the satellite confirms. The farmer reported more; a field survey is booked automatically for the remaining ${esc(d.topup_gap_pct)} points, so no genuine loss is silently cut.</div>` : ""}
    ${d.fraud_flag ? `<div class="flag">⚠ Mismatch: the claimed loss is not supported by satellite and rainfall data for this district. Routed to a physical survey before any payout.</div>` : ""}
    <table class="checks"><thead><tr><th>Check</th><th>Result</th><th>Evidence</th><th>Clause</th></tr></thead><tbody>
      ${d.checks.map((k) => `<tr><td>${esc(k.check)}</td><td class="${k.pass ? "pass" : "fail"}">${k.pass ? "PASS" : "FAIL"}</td><td>${esc(k.detail)}</td><td>${esc(k.clause)}</td></tr>`).join("")}
    </tbody></table>
    <div class="msg">
      <div><h3>Message to farmer (${esc(it.language)})</h3>${esc(x.farmer_message)}</div>
      <div><h3>Assessor summary</h3>${esc(x.assessor_summary)}<br><small>${d.clauses.map((k) => `[${esc(k.id)}] ${esc(k.title)}: ${esc(k.text)}`).join("<br>")}</small></div>
    </div>`;
  btn.disabled = false; btn.textContent = "Verify claim";
  loadLedger();
}

async function loadLedger() {
  try {
    const rows = await fetch("/api/claims").then((r) => r.json());
    $("#ledger tbody").innerHTML = rows.map((c) => `<tr><td>${esc(c.id)}</td><td>${esc(c.farmer)}</td><td>${esc(c.district)}</td><td class="${c.verdict === "APPROVE" ? "pass" : "fail"}">${esc(c.verdict)}</td><td>${money(c.payout)}</td></tr>`).join("") || `<tr><td colspan="5">No claims yet.</td></tr>`;
  } catch { /* ledger optional */ }
}

document.querySelectorAll("[data-preset]").forEach((b) => b.addEventListener("click", () => applyPreset(b.dataset.preset)));
$("#photo").addEventListener("change", (e) => { presetBlob = null; if (e.target.files[0]) showPreview(e.target.files[0]); });
$("#claimForm").addEventListener("submit", submitClaim);
loadDistricts().then(() => applyPreset("flood"));
loadLedger();
