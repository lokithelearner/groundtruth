import io

from PIL import Image

from app import integrity


def _img(color, size=(64, 48)):
    b = io.BytesIO(); Image.new("RGB", size, color).save(b, "JPEG"); return b.getvalue()


def _gradient(size):
    im = Image.new("L", size)
    im.putdata([(x * 255 // size[0]) for y in range(size[1]) for x in range(size[0])])
    b = io.BytesIO(); im.convert("RGB").save(b, "JPEG"); return b.getvalue()


def test_hash_survives_resize_and_recompression():
    a = integrity.analyse(_gradient((320, 240)))["phash"]
    b = integrity.analyse(_gradient((160, 120)))["phash"]
    assert integrity.hamming(a, b) <= 4


def test_missing_exif_is_a_note_not_a_rejection():
    info = integrity.analyse(_img((10, 10, 10)))
    assert info["has_photo"] and not info["has_exif"]
    assert any("assessor note" in s for s in info["signals"])


def test_no_photo():
    assert integrity.analyse(None)["has_photo"] is False
