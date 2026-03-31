import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """系统配置类"""

    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    OUTPUT_DIR = os.path.join(BASE_DIR, 'output')
    UPLOAD_DIR = os.path.join(BASE_DIR, 'uploads')
    TEMP_DIR = os.path.join(BASE_DIR, 'temp')

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    os.makedirs(TEMP_DIR, exist_ok=True)

    LLM_CONFIG = {
        'provider': os.getenv('LLM_PROVIDER', 'openai'),
        'model': os.getenv('LLM_MODEL', 'gpt-4'),
        'api_key': os.getenv('OPENAI_API_KEY'),
        'base_url': os.getenv('LLM_BASE_URL'),
        'max_retries': int(os.getenv('LLM_MAX_RETRIES', '3')),
        'retry_delay': float(os.getenv('LLM_RETRY_DELAY', '1'))
    }

    TESSERACT_PATH = os.getenv('TESSERACT_PATH', 'tesseract')

    NDL_MODEL_PATH = os.getenv('NDL_MODEL_PATH', '')

    NDLOCR_LITE_PATH = os.getenv('NDLOCR_LITE_PATH', '')
    NDLOCR_LITE_GPU = os.getenv('NDLOCR_LITE_GPU', 'false').lower() == 'true'
    NDLOCR_LITE_VIZ = os.getenv('NDLOCR_LITE_VIZ', 'false').lower() == 'true'
    NDLOCR_LITE_TIMEOUT = int(os.getenv('NDLOCR_LITE_TIMEOUT', '300'))

    NDLKOTENOCR_LITE_PATH = os.getenv('NDLKOTENOCR_LITE_PATH', '')
    NDLKOTENOCR_LITE_GPU = os.getenv('NDLKOTENOCR_LITE_GPU', 'false').lower() == 'true'
    NDLKOTENOCR_LITE_VIZ = os.getenv('NDLKOTENOCR_LITE_VIZ', 'false').lower() == 'true'
    NDLKOTENOCR_LITE_TIMEOUT = int(os.getenv('NDLKOTENOCR_LITE_TIMEOUT', '300'))

    DEFAULT_OCR_MODEL = os.getenv('DEFAULT_OCR_MODEL', 'ndlocr_lite')

    PDF_DPI = int(os.getenv('PDF_DPI', '300'))
    PDF_FORMAT = os.getenv('PDF_FORMAT', 'PNG')

    OCR_LANGUAGE = os.getenv('OCR_LANGUAGE', 'zh')

    MAX_CONTENT_LENGTH = 50 * 1024 * 1024

    ALLOWED_EXTENSIONS = {'docx', 'pdf', 'png', 'jpg', 'jpeg', 'tiff'}


class DevelopmentConfig(Config):
    """开发环境配置"""
    DEBUG = True


class ProductionConfig(Config):
    """生产环境配置"""
    DEBUG = False


config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
