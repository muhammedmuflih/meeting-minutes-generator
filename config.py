# config.py
import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key'
    UPLOAD_FOLDER = 'data/uploaded_audio'
    OUTPUT_FOLDER = 'outputs'
    ALLOWED_EXTENSIONS = {'mp3', 'wav', 'ogg', 'flac', 'm4a', 'mp4'}
    MAX_CONTENT_LENGTH = 1024 * 1024 * 1024  # 1GB
    
    # Whisper settings
    WHISPER_MODEL_SIZE = os.environ.get('WHISPER_MODEL_SIZE', 'base')
    
    # Deployment settings
    DEPLOYMENT_TESTING = os.environ.get('DEPLOYMENT_TESTING', 'false').lower() == 'true'

class DevelopmentConfig(Config):
    DEBUG = True

class ProductionConfig(Config):
    DEBUG = False

config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}