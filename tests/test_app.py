import io
import zipfile

import pytest
from PIL import Image

import app as app_module


@pytest.fixture
def client():
    app_module.app.config["TESTING"] = True
    with app_module.app.test_client() as client:
        yield client


def _tiny_png_bytes():
    buf = io.BytesIO()
    Image.new("RGB", (32, 32), color=(200, 40, 40)).save(buf, format="PNG")
    buf.seek(0)
    return buf


def test_index_loads(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"Load the tray" in resp.data


def test_healthz(client):
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.get_json() == {"status": "ok"}


def test_compress_with_no_files_returns_400(client):
    resp = client.post("/", data={}, content_type="multipart/form-data")
    assert resp.status_code == 400


def test_compress_valid_image_returns_zip(client):
    data = {"files": (_tiny_png_bytes(), "sample.png")}
    resp = client.post("/", data=data, content_type="multipart/form-data")

    assert resp.status_code == 200
    assert resp.mimetype == "application/zip"

    with zipfile.ZipFile(io.BytesIO(resp.data)) as zf:
        names = zf.namelist()
        assert "sample.webp" in names


def test_compress_rejects_unsupported_extension(client):
    bogus = io.BytesIO(b"not an image")
    data = {"files": (bogus, "notes.txt")}
    resp = client.post("/", data=data, content_type="multipart/form-data")

    # The .txt is skipped client-side by the allow-list; since it's the
    # only file in the batch, nothing ends up in the zip at all.
    assert resp.status_code == 400


def test_compress_name_collision_gets_suffixed(client):
    data = {
        "files": [
            (_tiny_png_bytes(), "photo.png"),
            (_tiny_png_bytes(), "photo.jpg"),
        ]
    }
    resp = client.post("/", data=data, content_type="multipart/form-data")
    assert resp.status_code == 200

    with zipfile.ZipFile(io.BytesIO(resp.data)) as zf:
        names = set(zf.namelist())
        assert "photo.webp" in names
        assert "photo_1.webp" in names
