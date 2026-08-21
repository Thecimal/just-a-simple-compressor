# Simple Compressor

A tiny, self-hosted batch image compressor. Drop in a folder of photos, get
back a zip of resized `.webp` files. No accounts, no database, nothing kept
on disk after the download — each upload gets its own temp directory that's
deleted the moment the request finishes.

Built with Flask on the backend and [ImageMagick](https://imagemagick.org/)
doing the actual resize/compress work.

## Features

- Drag-and-drop or click-to-browse upload, any number of files at once
- Resizes to a configurable max dimension (default `1600×1600`, never upscales)
- Re-encodes to WebP at a configurable quality (default `82`)
- Auto-corrects EXIF orientation (so phone photos come out right-side up)
- Bad files in a batch are skipped, not fatal — the rest of the batch still
  downloads, with a `skipped_files.txt` in the zip listing what didn't make it
- Per-file conversion timeout, upload size cap, and file-count cap, so a
  hostile or corrupt file can't hang or overload the server
- Nothing persisted: everything lives in an in-memory zip and a temp
  directory that's wiped as soon as the request completes

## Quickstart

### Docker (recommended)

```bash
git clone https://github.com/<you>/simple-compressor.git
cd simple-compressor
cp .env.example .env
docker compose up --build
```

Open `http://localhost:5000`.

### Local Python

Requires Python 3.10+ and ImageMagick installed on your system.

```bash
# Debian/Ubuntu
sudo apt install imagemagick

# macOS
brew install imagemagick
```

```bash
git clone https://github.com/<you>/simple-compressor.git
cd simple-compressor
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python app.py
```

Open `http://localhost:5000`.

For production, run it behind gunicorn instead of the Flask dev server:

```bash
gunicorn --bind 0.0.0.0:5000 --workers 2 --timeout 60 app:app
```

## Configuration

Everything is set via environment variables (see `.env.example`):

| Variable                | Default   | What it does                                              |
|--------------------------|-----------|-------------------------------------------------------------|
| `MAX_DIMENSION`          | `1600`    | Longest edge, in px, output images are capped to             |
| `QUALITY`                | `82`      | Output quality, 1–100                                        |
| `OUTPUT_FORMAT`          | `webp`    | Output container format (anything ImageMagick can write)     |
| `MAX_FILES_PER_REQUEST`  | `50`      | Max files accepted in a single upload                        |
| `MAX_CONTENT_LENGTH_MB`  | `200`     | Max total upload size, in MB                                 |
| `CONVERT_TIMEOUT_SECONDS`| `30`      | Per-file conversion timeout                                  |
| `HOST` / `PORT`          | `0.0.0.0` / `5000` | Bind address for `python app.py`                     |
| `LOG_LEVEL`              | `INFO`    | Python logging level                                          |
| `FLASK_DEBUG`            | `false`   | Enable Flask's debugger (dev only — never in production)     |

## Using it without the browser

The upload form posts to `/` and streams back a zip, so it's scriptable:

```bash
curl -F "files=@photo1.jpg" -F "files=@photo2.heic" \
     -o compressed.zip http://localhost:5000/
```

A `GET /healthz` endpoint is included for container/orchestrator health checks.

## Security notes

- **File type allow-list.** Only common image extensions are accepted
  (`jpg`, `png`, `webp`, `heic`, `heif`, `tif`, `bmp`, `gif`, `avif`, …);
  everything else is skipped before it ever reaches ImageMagick.
- **ImageMagick's `policy.xml`.** This app shells out to ImageMagick, so its
  own hardening matters too. Most current distro packages ship with unsafe
  coders (`MSL`, `MVG`, `URL`, `EPHEMERAL`, etc.) already disabled — worth
  double-checking `/etc/ImageMagick-6/policy.xml` (or `-7/`) on whatever
  host you deploy to, especially if you build ImageMagick from source.
- **Resource limits.** Uploads are capped by size (`MAX_CONTENT_LENGTH_MB`)
  and count (`MAX_FILES_PER_REQUEST`), and each individual conversion is
  killed if it runs past `CONVERT_TIMEOUT_SECONDS` — this bounds the damage
  a decompression-bomb-style file can do.
- **No persistence.** Uploaded files and their converted output live only
  in a per-request temp directory, deleted as soon as the response is sent.
  There's no database and nothing is logged beyond filenames and errors.
- This app has no authentication of its own. If you're exposing it beyond
  your local network, put it behind a reverse proxy with auth (or a
  network-level restriction) — it will happily compress images for anyone
  who can reach it.

## HEIC/HEIF support

HEIC read support depends on ImageMagick's `libheif` delegate being present
on the host — it isn't always installed by default. The included
`Dockerfile` installs `libheif-examples` to enable it; if you're running
locally instead, check `identify -list format | grep -i heic` to confirm
your system's ImageMagick build supports it.

## Development

```bash
pip install -r requirements-dev.txt
pytest tests/
```

## License

MIT — see [LICENSE](LICENSE).
