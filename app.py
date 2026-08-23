"""
Simple Compressor
--------------------
A tiny, self-hosted image compressor: drop in a batch of photos, get back a
zip of resized WebP (or whatever format you configure) files. Nothing is
written to persistent storage — each request gets its own temp directory
that's wiped the moment it's done.

Run it directly (`python app.py`) for local use, or see the Dockerfile /
README for a production setup behind gunicorn.
"""
import os
import io
import logging
import os
import shutil
import subprocess
import tempfile
import uuid
import zipfile

from flask import Flask, render_template, request
from werkzeug.utils import secure_filename

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    # python-dotenv is a convenience, not a hard requirement — env vars
    # can always be set some other way (Docker, systemd, the shell, etc).
    pass

# --------------------------------------------------------------------------
# Configuration — override any of these with environment variables.
# --------------------------------------------------------------------------
MAX_DIMENSION = int(os.environ.get("MAX_DIMENSION") or 1600)
QUALITY = int(os.environ.get("QUALITY", 82))
OUTPUT_FORMAT = os.environ.get("OUTPUT_FORMAT", "webp").lower().lstrip(".")
MAX_FILES_PER_REQUEST = int(os.environ.get("MAX_FILES_PER_REQUEST", 50))
MAX_CONTENT_LENGTH_MB = int(os.environ.get("MAX_CONTENT_LENGTH_MB", 200))
CONVERT_TIMEOUT_SECONDS = int(os.environ.get("CONVERT_TIMEOUT_SECONDS", 30))

ALLOWED_EXTENSIONS = {
    "jpg", "jpeg", "png", "webp", "heic", "heif",
    "tif", "tiff", "bmp", "gif", "avif",
}

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH_MB * 1024 * 1024

logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
logger = logging.getLogger("compressor")


def _find_imagemagick_command():
    """ImageMagick 7 renamed the CLI to `magick`; the `convert` shim is
    deprecated and missing entirely on some distro packages. Detect
    whichever is actually installed rather than hard-coding one."""
    if shutil.which("magick"):
        return ["magick"]
    if shutil.which("convert"):
        return ["convert"]
    raise RuntimeError(
        "ImageMagick isn't installed or isn't on PATH. Install it first "
        "(e.g. `apt install imagemagick` on Debian/Ubuntu, "
        "`brew install imagemagick` on macOS)."
    )


IM_COMMAND = _find_imagemagick_command()


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def unique_output_name(base_name: str, used_names: set) -> str:
    """Avoid collisions when two different inputs would produce the same
    output filename (e.g. photo.jpg and photo.png both become photo.webp)."""
    candidate = f"{base_name}.{OUTPUT_FORMAT}"
    counter = 1
    while candidate in used_names:
        candidate = f"{base_name}_{counter}.{OUTPUT_FORMAT}"
        counter += 1
    used_names.add(candidate)
    return candidate


@app.route("/", methods=["GET"])
def index():
    return render_template(
        "index.html",
        max_dimension=MAX_DIMENSION,
        quality=QUALITY,
        output_format=OUTPUT_FORMAT.upper(),
    )


@app.route("/", methods=["POST"])
def compress():
    files = [f for f in request.files.getlist("files") if f and f.filename]

    if not files:
        return "No files came through — pick at least one image and try again.", 400

    if len(files) > MAX_FILES_PER_REQUEST:
        return (
            f"That's {len(files)} files — this tray only holds "
            f"{MAX_FILES_PER_REQUEST} at a time. Split the batch and try again.",
            400,
        )

    zip_buffer = io.BytesIO()
    used_names = set()
    skipped = []
    processed_count = 0

    with tempfile.TemporaryDirectory() as work_dir:
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for file in files:
                original_name = file.filename

                if not allowed_file(original_name):
                    skipped.append(f"{original_name} — unsupported file type")
                    continue

                # Prefix with a random id so two uploads named the same
                # thing can never collide inside the scratch directory,
                # regardless of what secure_filename() does with either.
                safe_name = secure_filename(original_name) or "file"
                input_path = os.path.join(work_dir, f"{uuid.uuid4().hex}_{safe_name}")
                file.save(input_path)

                base_name = os.path.splitext(safe_name)[0] or "file"
                output_filename = unique_output_name(base_name, used_names)
                output_path = os.path.join("/tmp", "compressed_image.jpg")
                image.save(output_path)

                try:
                    subprocess.run(
                        [
                            *IM_COMMAND, input_path,
                            "-auto-orient",
                            "-resize", f"{MAX_DIMENSION}x{MAX_DIMENSION}>",
                            "-quality", str(QUALITY),
                            output_path,
                        ],
                        check=True,
                        timeout=CONVERT_TIMEOUT_SECONDS,
                        capture_output=True,
                    )
                except subprocess.TimeoutExpired:
                    logger.warning("Conversion timed out: %s", original_name)
                    skipped.append(f"{original_name} — took too long to process")
                    continue
                except subprocess.CalledProcessError as exc:
                    stderr = exc.stderr.decode(errors="replace") if exc.stderr else ""
                    logger.warning("ImageMagick failed on %s: %s", original_name, stderr.strip())
                    skipped.append(f"{original_name} — couldn't be read as an image")
                    continue
                finally:
                    if os.path.exists(input_path):
                        os.remove(input_path)

                if os.path.exists(output_path):
                    with open(output_path, "rb") as f:
                        zf.writestr(output_filename, f.read())
                    os.remove(output_path)
                    processed_count += 1

            if skipped:
                zf.writestr(
                    "skipped_files.txt",
                    "These files didn't make it into the zip:\n\n"
                    + "\n".join(skipped) + "\n",
                )

    if processed_count == 0:
        return (
            "Nothing came out of the tray — none of the uploaded files "
            "could be developed. Check the file types and try again.",
            400,
        )

    zip_buffer.seek(0)
    response = app.response_class(
        zip_buffer.getvalue(),
        mimetype="application/zip",
        headers={"Content-Disposition": "attachment; filename=compressed_images.zip"},
    )
    return response


@app.errorhandler(413)
def too_large(_e):
    return (
        f"That batch is too large — total upload size is capped at "
        f"{MAX_CONTENT_LENGTH_MB} MB. Send fewer or smaller files.",
        413,
    )


@app.errorhandler(500)
def server_error(e):
    logger.exception("Unhandled error: %s", e)
    return "Something went wrong while developing your images.", 500


@app.route("/healthz")
def healthz():
    return {"status": "ok"}, 200


if __name__ == "__main__":
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    app.run(host=host, port=port, debug=debug)
