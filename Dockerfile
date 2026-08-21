FROM python:3.12-slim

# ImageMagick does the actual resize/compress work. libheif-examples adds
# HEIC/HEIF read support (iPhone photos); drop it if you don't need that.
RUN apt-get update && \
    apt-get install -y --no-install-recommends imagemagick libheif-examples && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PORT=5000

EXPOSE 5000

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--timeout", "60", "app:app"]
