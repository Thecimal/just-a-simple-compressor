const dropZone = document.getElementById('drop-zone');
const fileInput = document.getElementById('file-input');
const sleeveText = document.getElementById('sleeve-text');
const grid = document.getElementById('grid');
const sheetLabel = document.getElementById('sheet-label');
const submitBtn = document.getElementById('submit-btn');
const hint = document.getElementById('hint');
const form = document.getElementById('compress-form');

const DEFAULT_HINT = 'Nothing is kept on the server after your download.';

function renderContactSheet(files) {
    grid.innerHTML = '';
    if (files.length === 0) {
        sheetLabel.classList.remove('visible');
        sleeveText.textContent = 'Drop images here, or click to browse';
        return;
    }

    sheetLabel.textContent = `Contact sheet — ${files.length} frame${files.length > 1 ? 's' : ''}`;
    sheetLabel.classList.add('visible');
    sleeveText.textContent = 'Tray loaded — drop more, or develop below';

    files.forEach((file, i) => {
        const frame = document.createElement('div');
        frame.className = 'frame';

        const num = document.createElement('span');
        num.className = 'fnum';
        num.textContent = String(i + 1).padStart(2, '0');
        frame.appendChild(num);

        const img = document.createElement('img');
        img.src = URL.createObjectURL(file);
        img.alt = file.name;
        frame.appendChild(img);

        grid.appendChild(frame);
    });
}

function resetTray() {
    grid.innerHTML = '';
    sheetLabel.classList.remove('visible');
    sleeveText.textContent = 'Drop images here, or click to browse';
    form.reset();
}

function setHint(text, isError) {
    hint.textContent = text;
    hint.classList.toggle('error', Boolean(isError));
}

if (fileInput) {
    ['dragenter', 'dragover'].forEach(evt =>
        dropZone.addEventListener(evt, (e) => { e.preventDefault(); dropZone.classList.add('dragover'); })
    );
    ['dragleave', 'drop'].forEach(evt =>
        dropZone.addEventListener(evt, () => dropZone.classList.remove('dragover'))
    );
    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        if (e.dataTransfer.files.length) {
            fileInput.files = e.dataTransfer.files;
            renderContactSheet(Array.from(fileInput.files));
        }
    });

    fileInput.addEventListener('change', () => {
        renderContactSheet(Array.from(fileInput.files));
    });

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        if (fileInput.files.length === 0) return;

        submitBtn.disabled = true;
        submitBtn.textContent = 'Developing…';
        setHint('Your download will start automatically.', false);

        // Simulate development: frames sweep from red duotone to full color, in sequence.
        const frames = Array.from(grid.querySelectorAll('.frame'));
        frames.forEach((frame, i) => {
            setTimeout(() => frame.classList.add('developed'), i * 90);
        });
        const sweepDuration = Math.max(600, frames.length * 90 + 400);

        const formData = new FormData();
        Array.from(fileInput.files).forEach((file) => formData.append('files', file));

        try {
            const response = await fetch('/', { method: 'POST', body: formData });

            if (!response.ok) {
                const message = await response.text();
                throw new Error(message || `The simple-compressor returned an error (${response.status}).`);
            }

            const blob = await response.blob();
            const disposition = response.headers.get('Content-Disposition') || '';
            const match = disposition.match(/filename="?([^"]+)"?/);
            const filename = match ? match[1] : 'compressed_images.zip';

            const url = URL.createObjectURL(blob);
            const link = document.createElement('a');
            link.href = url;
            link.download = filename;
            document.body.appendChild(link);
            link.click();
            link.remove();
            URL.revokeObjectURL(url);

            setTimeout(() => {
                submitBtn.disabled = false;
                submitBtn.textContent = 'Develop & download';
                setHint('Done — check your downloads.', false);
                resetTray();
            }, sweepDuration);
        } catch (err) {
            frames.forEach((f) => f.classList.remove('developed'));
            submitBtn.disabled = false;
            submitBtn.textContent = 'Develop & download';
            setHint(err.message || 'Something went wrong in the simple.', true);
        }
    });
}
