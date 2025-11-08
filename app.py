import os
import sys
import logging
from flask import Flask, render_template, request, redirect, url_for, send_from_directory, flash, jsonify
from werkzeug.utils import secure_filename
from datetime import datetime
import traceback
import time
import uuid
import threading

# Setup logging for tracking app activity and errors
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Try to import Transcriber module
try:
    from core.transcriber import convert_audio_to_wav, transcribe_audio, preload_models
    TRANSCRIBER_AVAILABLE = True
    logger.info("Transcriber module loaded")
except ImportError as e:
    logger.error(f"Failed to import transcriber: {e}")
    TRANSCRIBER_AVAILABLE = False

# Try to import Summarizer module
try:
    from core.summarizer import generate_meeting_minutes
    SUMMARIZER_AVAILABLE = True
    logger.info("Summarizer module loaded")
except ImportError as e:
    logger.error(f"Failed to import summarizer: {e}")
    SUMMARIZER_AVAILABLE = False

# Try to import Exporter module
try:
    from core.exporter import export_to_text, export_to_word, export_to_pdf
    EXPORTER_AVAILABLE = True
    logger.info("Exporter module loaded")
except ImportError as e:
    logger.error(f"Failed to import exporter: {e}")
    EXPORTER_AVAILABLE = False

# Initialize Flask app and set folder paths
app = Flask(__name__, template_folder='templates')
app.config['UPLOAD_FOLDER'] = 'data/uploaded_audio'   # where uploaded files are stored
app.config['OUTPUT_FOLDER'] = 'outputs'               # where output files are saved
app.config['ALLOWED_EXTENSIONS'] = {'mp3', 'wav', 'ogg', 'flac', 'm4a', 'mp4'}
app.config['MAX_CONTENT_LENGTH'] = 1024 * 1024 * 1024 # 1GB upload limit
app.secret_key = 'supersecretkey'                     # secret key for sessions

# Create necessary folders if not present
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['OUTPUT_FOLDER'], exist_ok=True)
os.makedirs('temp_audio', exist_ok=True)
os.makedirs('templates', exist_ok=True)

# Dictionary to store job status and results
job_data = {}

# Check if uploaded file is allowed
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

# Handle large file upload error
@app.errorhandler(413)
def request_entity_too_large(error):
    flash('File too large. Max size: 1GB')
    return redirect(url_for('index'))

# Homepage route
@app.route('/')
def index():
    # Check if all core modules are available
    if not all([TRANSCRIBER_AVAILABLE, SUMMARIZER_AVAILABLE, EXPORTER_AVAILABLE]):
        missing = [name for name, avail in [
            ("Transcriber", TRANSCRIBER_AVAILABLE),
            ("Summarizer", SUMMARIZER_AVAILABLE),
            ("Exporter", EXPORTER_AVAILABLE)
        ] if not avail]
        return render_template('error.html', error=f"Missing modules: {', '.join(missing)}")
    return render_template('index.html')

# Processing page route
@app.route('/processing')
def processing():
    job_id = request.args.get('job_id')
    if not job_id or job_id not in job_data:
        flash('Invalid job ID')
        return redirect(url_for('index'))
    return render_template('processing.html', job_id=job_id)

# API route to get job progress
@app.route('/job_status/<job_id>')
def job_status(job_id):
    return jsonify(job_data.get(job_id, {"status": "not_found"}))

# Function to update job status
def update_job_status(job_id, status, progress=None, step=None):
    job_data[job_id]["status"] = status
    if progress is not None:
        job_data[job_id]["progress"] = progress
    if step is not None:
        job_data[job_id]["step"] = step

# Background task to process audio file
def process_audio_file(job_id, filepath, filename):
    wav_filepath = None
    try:
        update_job_status(job_id, "processing", 0, "Starting")
        start_time = time.time()
        logger.info(f"[Job {job_id}] Processing {filename}")

        # Step 1: Convert audio to wav
        update_job_status(job_id, "processing", 20, "Converting audio")
        wav_filepath = convert_audio_to_wav(filepath, output_dir='temp_audio')

        # Step 2: Transcribe audio to text
        update_job_status(job_id, "processing", 30, "Transcribing audio")
        raw_transcript = transcribe_audio(wav_filepath, model_size="base", language="en")
       
        # Step 3: Join all transcribed text
        update_job_status(job_id, "processing", 60, "Processing transcript")
        full_text = " ".join([seg["text"].strip() for seg in raw_transcript if seg.get("text")])
       
        # Step 4: Check if valid speech found
        if not full_text or len(full_text) < 10:
            raise Exception("No speech detected in audio")

        # Step 5: Generate meeting summary and minutes
        update_job_status(job_id, "processing", 75, "Generating minutes")
        minutes = generate_meeting_minutes(full_text)
       
        # Store all results
        results = {
            "summary": minutes["summary"],
            "decisions": minutes["decisions"],
            "action_items": minutes["action_items"],
            "deadlines": minutes["deadlines"],
            "full_transcript": full_text
        }

        # Step 6: Export results to files
        update_job_status(job_id, "processing", 90, "Exporting files")
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        safe_filename = secure_filename(os.path.splitext(filename)[0])
        output_basename = f"{timestamp}_{safe_filename}"
       
        export_to_text(results, os.path.join(app.config['OUTPUT_FOLDER'], f"{output_basename}.txt"))
        export_to_word(results, os.path.join(app.config['OUTPUT_FOLDER'], f"{output_basename}.docx"))
        export_to_pdf(results, os.path.join(app.config['OUTPUT_FOLDER'], f"{output_basename}.pdf"))

        # Step 7: Delete temp files
        for file_path in [wav_filepath, filepath]:
            if file_path and os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except:
                    pass

        # Step 8: Save results and time taken
        total_time = time.time() - start_time
        job_data[job_id]['results'] = {
            'results': results,
            'text_file': f"{output_basename}.txt",
            'word_file': f"{output_basename}.docx",
            'pdf_file': f"{output_basename}.pdf",
            'processing_time': f"{total_time:.2f}s"
        }
       
        update_job_status(job_id, "completed", 100, "Complete")
        job_data[job_id]["results_url"] = f"/results/{job_id}"

    except Exception as e:
        # If any error occurs, log and mark job as failed
        logger.error(f"[Job {job_id}] Error: {str(e)}")
        update_job_status(job_id, "error", 0, "Error")
        job_data[job_id]["message"] = str(e)
       
        for file_path in [wav_filepath, filepath]:
            if file_path and os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except:
                    pass

# Route to handle file uploads
@app.route('/upload', methods=['POST'])
def upload_file():
    if 'audio_file' not in request.files:
        flash('No file selected')
        return redirect(request.url)

    file = request.files['audio_file']
    if file.filename == '':
        flash('No file selected')
        return redirect(request.url)

    # If file type is allowed, save it
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
       
        # Create new job entry
        job_id = str(uuid.uuid4())
        job_data[job_id] = {
            "status": "uploaded",
            "progress": 10,
            "step": "File uploaded",
            "filename": filename
        }
       
        # Start background thread for processing
        thread = threading.Thread(target=process_audio_file, args=(job_id, filepath, filename))
        thread.daemon = True
        thread.start()
       
        return redirect(url_for('processing', job_id=job_id))
    else:
        flash('Invalid file type')
        return redirect(request.url)

# Route to show results page
@app.route('/results/<job_id>')
def results(job_id):
    if job_id not in job_data:
        flash('Results not found')
        return redirect(url_for('index'))
   
    job_info = job_data[job_id]
   
    if job_info.get('status') == 'error':
        flash(f'Processing failed: {job_info.get("message")}')
        return redirect(url_for('index'))
   
    if job_info.get('status') != 'completed' or 'results' not in job_info:
        flash('Results not ready')
        return redirect(url_for('processing', job_id=job_id))
   
    results_data = job_info['results']
    return render_template(
        'results.html',
        results=results_data['results'],
        text_file=results_data['text_file'],
        word_file=results_data['word_file'],
        pdf_file=results_data['pdf_file'],
        processing_time=results_data.get('processing_time')
    )

# Route to download exported files
@app.route('/download/<filename>')
def download_file(filename):
    try:
        return send_from_directory(app.config['OUTPUT_FOLDER'], filename, as_attachment=True)
    except Exception as e:
        logger.error(f"Download error: {e}")
        flash(f"Download failed: {str(e)}")
        return redirect(url_for('index'))

# Function to preload models when app starts
def initialize_app():
    def preload_thread():
        try:
            if TRANSCRIBER_AVAILABLE:
                preload_models()
        except Exception as e:
            logger.error(f"Preload error: {e}")
   
    thread = threading.Thread(target=preload_thread)
    thread.daemon = True
    thread.start()

# Run the Flask app
if __name__ == '__main__':
    initialize_app()
    app.run(debug=True, host='0.0.0.0', port=5000)