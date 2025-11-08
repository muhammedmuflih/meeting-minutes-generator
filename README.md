# Meeting Minutes Generator

A Flask-based web application that converts meeting audio into structured meeting minutes (summary, decisions, action items, deadlines), exports them to text/Word/PDF, and provides a simple web UI and lightweight API to upload audio and retrieve results.

This README is tailored to the repository layout and runtime behavior found in this project (app.py, config.py, `core/` modules, `templates/`, `static/`, `requirements.txt`).

- Language: Python (Flask)
- App entrypoint: `app.py`
- Important directories created at runtime:
  - `data/uploaded_audio` — uploaded audio files (created automatically)
  - `outputs` — exported result files (created automatically)
  - `temp_audio` — temporary converted files
  - `templates` — Flask templates (expected templates: `index.html`, `processing.html`, `results.html`)
- Core logic entrypoints (expected under `core/`):
  - `core/transcriber.py` — should provide `convert_audio_to_wav`, `transcribe_audio`, `preload_models`
  - `core/summarizer.py` — should provide `generate_meeting_minutes`
  - `core/exporter.py` — should provide `export_to_text`, `export_to_word`, `export_to_pdf`

Table of Contents
- Features
- Quick start
- Running locally
- Endpoints & usage
- Configuration
- Project structure
- Troubleshooting
- Contributing
- License

## Features
- Upload audio (mp3/wav/ogg/flac/m4a/mp4) via web UI or HTTP POST
- Background processing: convert → transcribe → summarize → export
- Exports: .txt, .docx, .pdf
- Job status polling endpoint for progress updates
- Simple web UI to upload and view results

## Quick start

1. Clone the repository
```bash
git clone https://github.com/muhammedmuflih/meeting-minutes-generator.git
cd meeting-minutes-generator
```

2. Create virtual environment and install dependencies
```bash
python -m venv venv
source venv/bin/activate     # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

3. Ensure system dependencies are installed (if your transcriber uses ffmpeg or external STT)
- ffmpeg (for audio conversion)
- Any external STT / ML model runtime as required by `core/transcriber.py`

4. Run the app
```bash
python app.py
```
By default the Flask dev server will run on http://0.0.0.0:5000 with debug enabled (see `app.py`).

## Running in production
For production use, run with a WSGI server such as gunicorn:
```bash
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```
Make sure to set a secure secret key and use production-ready configuration.

## Endpoints & usage

Web UI:
- GET `/` — homepage (index.html). If core modules are missing, an error template with missing modules is shown.
- POST `/upload` — upload audio file via a form (field name: `audio_file`). This starts a background job and redirects to `/processing?job_id=<id>`.
- GET `/processing?job_id=<id>` — processing page to show progress
- GET `/results/<job_id>` — results page showing extracted minutes and links to exported files
- GET `/download/<filename>` — download exported file from `outputs/`

API (HTTP):
- POST `/upload` (multipart/form-data)
  - field: `audio_file` — file to upload
  - Response: redirect to `/processing?job_id=<id>` (same as UI)
  - Example using curl:
    ```bash
    curl -F "audio_file=@meeting.mp3" http://localhost:5000/upload -v
    ```
- GET `/job_status/<job_id>`
  - Returns JSON with keys like `status`, `progress`, `step`, `filename`, and when complete `results` and exported filenames
  - Poll to check job progress

Result object structure (as stored in-memory per job):
- summary
- decisions
- action_items
- deadlines
- full_transcript
- exported filenames: text_file, word_file, pdf_file
- processing_time

Notes:
- Upload field name must be `audio_file`.
- Allowed extensions are set in `app.py`: mp3, wav, ogg, flac, m4a, mp4.
- Max upload size in `app.py` is 1 GB by default.

## Configuration

Configuration values are currently set in `app.py` and `config.py` (where present). Important settings in `app.py`:
- `UPLOAD_FOLDER` (default: `data/uploaded_audio`)
- `OUTPUT_FOLDER` (default: `outputs`)
- `ALLOWED_EXTENSIONS` (set in `app.py`)
- `MAX_CONTENT_LENGTH` (1GB default)
- `app.secret_key` (currently set in `app.py` — replace with a secure value or set via environment/config)

Recommended environment variables or config changes for production:
- Use a secure secret key (via environment or config file)
- Configure host/port, logging level, and worker settings in your process manager
- Place exported outputs on persistent storage if running multiple instances

## Project structure (relevant files)
- app.py — main Flask application (routes, background processing)
- config.py — project configuration (adjust as needed)
- requirements.txt — Python dependencies (install with pip)
- core/ — expected to contain:
  - transcriber.py — audio conversion & transcription helpers
  - summarizer.py — meeting minutes generation
  - exporter.py — functions to write text/docx/pdf
- templates/ — Flask templates (index.html, processing.html, results.html)
- static/ — static files (css/js/images)
- data/uploaded_audio/ — upload destination (created by app)
- temp_audio/ — temporary files (created by app)
- outputs/ — exported .txt/.docx/.pdf results (created by app)

## Implementation notes / expectations
- `app.py` attempts to import core modules and will render an error page if any are missing.
- Transcription flow in `app.py`:
  1. Convert uploaded audio to WAV via `convert_audio_to_wav`
  2. Transcribe WAV to segments via `transcribe_audio`
  3. Build the full transcript and call `generate_meeting_minutes`
  4. Export results using `export_to_text`, `export_to_word`, `export_to_pdf`
  5. Remove temporary files and leave exported files in `outputs/`
- The app keeps job state in an in-memory dict `job_data`. This means:
  - Job state will be lost on process restart.
  - For scaling or persistence, replace in-memory storage with a database or cache (Redis).

## Troubleshooting
- ImportError for core modules:
  - Ensure `core/transcriber.py`, `core/summarizer.py`, and `core/exporter.py` exist and export the expected functions. If missing, the homepage will show which modules are unavailable.
- No speech detected / short transcript:
  - The app raises an error if the transcript is too short (checks length < 10 chars). Verify audio quality and supported formats.
- ffmpeg required:
  - If your transcriber uses ffmpeg for conversion, ensure ffmpeg is installed and in PATH.
- Permission errors saving files:
  - Ensure the process user can create and write to `data/`, `temp_audio/`, and `outputs/`.
- Large uploads:
  - Max content length is set to 1GB in `app.py`. Adjust `MAX_CONTENT_LENGTH` if needed.

## Adding tests
- Add unit tests for `core/*` modules and for any utility functions.
- For end-to-end tests, include fixture audio samples and assert expected exported content or JSON structure.

## Contributing
Contributions are welcome. Suggested workflow:
1. Fork the repo
2. Create a branch for your feature/fix
3. Run tests and style checks
4. Submit a PR with a clear description and screenshots (if UI changes)

Things you might contribute:
- Implement or improve `core/transcriber.py`, `core/summarizer.py`, `core/exporter.py`
- Add persistent job storage (Redis, DB)
- Add authentication for upload/management
- Add server-side rate limiting and file cleanup worker
- Add unit and integration tests

## Security considerations
- Do not commit production secret keys.
- Validate uploaded files and scan for malicious content if accepting user uploads publicly.
- Limit upload size and concurrency to avoid DoS.

## License
Specify your license (e.g., MIT). Update the LICENSE file accordingly.

## Acknowledgements
Project skeleton built around a Flask app that orchestrates transcription, summarization, and export logic. Thanks to any ML/ASR libraries or third-party services you integrate for transcription or summarization.

---

If any of the `core/` modules are not yet implemented or you want this README to include exact install/test commands from `requirements.txt` or `config.py`, I can update the README to include those exact commands and dependency lists. (The repository already includes `requirements.txt` — use `pip install -r requirements.txt` to install.)
