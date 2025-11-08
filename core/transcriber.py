import os
import logging
import subprocess
import shutil  
import whisper
import warnings
import time
import threading

warnings.filterwarnings('ignore')
logger = logging.getLogger(__name__)

_model_cache = {}
_model_lock = threading.Lock()

def get_whisper_model(model_size="base"):
    global _model_cache, _model_lock
    
    with _model_lock:
        if model_size not in _model_cache:
            logger.info(f"Loading Whisper model '{model_size}'...")
            try:
                start_time = time.time()
                _model_cache[model_size] = whisper.load_model(model_size)
                load_time = time.time() - start_time
                logger.info(f"Model loaded in {load_time:.2f} seconds")
            except Exception as e:
                logger.error(f"Failed to load Whisper model: {e}")
                raise
        
        return _model_cache[model_size]

def convert_audio_to_wav(input_path, output_dir="temp_audio"):
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    base_name = os.path.basename(input_path)
    file_name_without_ext = os.path.splitext(base_name)[0]
    output_wav_path = os.path.join(output_dir, f"{file_name_without_ext}.wav")

    try:
        logger.info(f"Converting {input_path} to WAV...")
        
        if input_path.lower().endswith('.wav'):
            try:
                result = subprocess.run(
                    ['ffprobe', '-v', 'error', '-select_streams', 'a:0',
                     '-show_entries', 'stream=sample_rate,channels',
                     '-of', 'default=noprint_wrappers=1:nokey=1', input_path],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                output_lines = result.stdout.strip().split('\n')
                if len(output_lines) >= 2:
                    sample_rate = int(output_lines[0])
                    channels = int(output_lines[1])
                    
                    if sample_rate == 16000 and channels == 1:
                        shutil.copy2(input_path, output_wav_path)  # Now this will work
                        return output_wav_path
            except Exception:
                pass
        
        cmd = [
            'ffmpeg', '-i', input_path,
            '-ar', '16000',
            '-ac', '1',
            '-c:a', 'pcm_s16le',
            '-y',
            output_wav_path
        ]
        
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        
        if result.returncode != 0:
            raise Exception(f"ffmpeg conversion failed: {result.stderr}")
        
        if not os.path.exists(output_wav_path) or os.path.getsize(output_wav_path) < 1000:
            raise Exception("Conversion failed - output file invalid")
        
        return output_wav_path
        
    except FileNotFoundError:
        raise Exception("ffmpeg not found. Please install ffmpeg and add it to PATH.")
    except Exception as e:
        logger.error(f"Error converting audio: {e}")
        raise

def transcribe_audio(audio_path, model_size="base", language="en", max_duration=None):
    try:
        logger.info(f"Transcribing {os.path.basename(audio_path)}")
        
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"Audio file not found: {audio_path}")
        
        file_size = os.path.getsize(audio_path)
        if file_size < 1000:
            return [{"start": 0.0, "end": 1.0, "text": "Audio file too short"}]
        
        try:
            duration = _get_audio_duration(audio_path)
            if max_duration and duration > max_duration:
                logger.warning(f"Audio exceeds max duration ({duration}s > {max_duration}s)")
        except Exception:
            pass
        
        model = get_whisper_model(model_size)
        
        start_time = time.time()
        result = model.transcribe(
            audio_path,
            language=language if language != "auto" else None,
            verbose=False,
            word_timestamps=False,
            fp16=False,
            temperature=0.0,
        )
        transcription_time = time.time() - start_time
        logger.info(f"Transcription completed in {transcription_time:.2f}s")
        
        segments = []
        if "segments" in result and result["segments"]:
            for segment in result["segments"]:
                text = segment["text"].strip()
                if text:
                    segments.append({
                        "start": float(segment["start"]),
                        "end": float(segment["end"]),
                        "text": text
                    })
        elif "text" in result and result["text"].strip():
            segments.append({
                "start": 0.0,
                "end": duration if 'duration' in locals() else 10.0,
                "text": result["text"].strip()
            })
        else:
            segments.append({"start": 0.0, "end": 1.0, "text": "No speech detected"})
        
        return segments
        
    except Exception as e:
        logger.error(f"Transcription failed: {e}")
        return [{"start": 0.0, "end": 1.0, "text": f"Transcription failed: {str(e)}"}]

def _get_audio_duration(audio_path):
    try:
        cmd = ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
               '-of', 'default=noprint_wrappers=1:nokey=1', audio_path]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return float(result.stdout.strip())
    except Exception:
        return 10.0

def check_dependencies():
    deps = {}
    try:
        subprocess.run(['ffmpeg', '-version'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        deps['ffmpeg'] = True
    except FileNotFoundError:
        deps['ffmpeg'] = False
    
    try:
        subprocess.run(['ffprobe', '-version'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        deps['ffprobe'] = True
    except FileNotFoundError:
        deps['ffprobe'] = False
    
    try:
        import whisper
        deps['whisper'] = True
    except ImportError:
        deps['whisper'] = False
    
    return deps

def preload_models():
    logger.info("Preloading Whisper models...")
    for model_size in ["tiny", "base", "small"]:
        try:
            get_whisper_model(model_size)
            logger.info(f"Preloaded {model_size} model")
        except Exception as e:
            logger.error(f"Failed to preload {model_size}: {e}")