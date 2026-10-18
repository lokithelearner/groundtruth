"""Photo integrity signals: EXIF capture metadata and perceptual-hash duplicate detection.

These are evidence for the assessor, not verdict overrides: a missing EXIF block is common
for forwarded or messaging-app images, and the same photo can legitimately be resubmitted.
In production, a duplicate hash across different farmers is routed to survey.
"""
from __future__ import annotations

import io
from datetime import datetime


def _ahash(img) -> str:
    """64-bit average hash: robust to resizing and recompression, cheap to compare."""
    g = img.convert("L").resize((8, 8))
    px = list(g.getdata())
    avg = sum(px) / 64
    bits = "".join("1" if p > avg else "0" for p in px)
    return f"{int(bits, 2):016x}"


def hamming(a: str, b: str) -> int:
    return bin(int(a, 16) ^ int(b, 16)).count("1")


def _gps_to_deg(v):
    d, m, s = (float(x) for x in v)
    return d + m / 60 + s / 3600


def analyse(image_bytes: bytes | None) -> dict:
    if not image_bytes:
        return {"has_photo": False, "signals": ["No photo provided"]}
    try:
        from PIL import Image
        img = Image.open(io.BytesIO(image_bytes))
        out = {"has_photo": True, "width": img.width, "height": img.height, "phash": _ahash(img),
               "has_exif": False, "captured_at": None, "gps": None, "signals": []}
        exif = img.getexif() if hasattr(img, "getexif") else None
        if exif:
            out["has_exif"] = True
            dt = exif.get(36867) or exif.get(306)  # DateTimeOriginal / DateTime
            if dt:
                try:
                    out["captured_at"] = datetime.strptime(str(dt), "%Y:%m:%d %H:%M:%S").isoformat()
                except ValueError:
                    pass
            gps = exif.get_ifd(0x8825) if hasattr(exif, "get_ifd") else {}
            if gps and 2 in gps and 4 in gps:
                lat = _gps_to_deg(gps[2]) * (-1 if gps.get(1) == "S" else 1)
                lon = _gps_to_deg(gps[4]) * (-1 if gps.get(3) == "W" else 1)
                out["gps"] = [round(lat, 5), round(lon, 5)]
        out["signals"].append("Capture metadata present" if out["has_exif"] else
                              "No capture metadata (forwarded or edited image): assessor note")
        if out["gps"]:
            out["signals"].append(f"Geotag {out['gps'][0]}, {out['gps'][1]}")
        return out
    except Exception as e:
        return {"has_photo": True, "signals": [f"Unreadable image ({type(e).__name__})"]}


def duplicate_check(store, phash: str | None, claim_id: str, farmer: str, max_dist: int = 4) -> dict:
    """Look up near-identical photos in earlier claims (Firestore), then register this one."""
    if not store or not phash:
        return {"checked": False}
    try:
        col = store.collection("photo_hashes")
        matches = []
        for d in col.where("prefix", "==", phash[:4]).limit(50).stream():
            r = d.to_dict()
            if hamming(r["phash"], phash) <= max_dist:
                matches.append({"claim": r["claim"], "same_farmer": r.get("farmer") == farmer})
        col.document(claim_id).set({"phash": phash, "prefix": phash[:4], "claim": claim_id, "farmer": farmer})
        other = [m for m in matches if not m["same_farmer"]]
        return {"checked": True, "matches": len(matches), "other_farmers": len(other),
                "signal": (f"Same photo seen in {len(other)} claim(s) by other farmers: flagged for the assessor"
                           if other else f"Photo seen in {len(matches)} earlier claim(s) by this farmer"
                           if matches else "No earlier claim uses this photo")}
    except Exception as e:
        return {"checked": False, "error": type(e).__name__}
