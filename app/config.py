import os
from dotenv import load_dotenv

from modules.secure_api_key_manager import get_secure_key_manager

load_dotenv()


_KEY_MANAGER = get_secure_key_manager()


def _default_provider() -> str:
    env_provider = os.getenv('LLM_PROVIDER')
    if env_provider:
        return env_provider
    if _KEY_MANAGER.has_key('qwen'):
        return 'dashscope'
    if _KEY_MANAGER.has_key('openai'):
        return 'openai'
    if _KEY_MANAGER.has_key('minimax'):
        return 'minimax'
    return 'openai'


def _default_model(provider: str) -> str:
    defaults = {
        'dashscope': 'qwen-turbo',
        'openai': 'gpt-4',
        'minimax': 'abab6-chat',
        'deepseek': 'deepseek-chat',
        'zhipu': 'glm-4',
        'volcano': 'doubao-seed-1-8-251228',
        'ollama': 'llama2',
    }
    return os.getenv('LLM_MODEL', defaults.get(provider, 'gpt-4'))


def _default_api_key(provider: str):
    provider_map = {
        'dashscope': 'qwen',
        'openai': 'openai',
        'minimax': 'minimax',
        'deepseek': 'deepseek',
        'zhipu': 'zhipu',
        'volcano': 'volcano',
    }
    service = provider_map.get(provider, provider)
    return _KEY_MANAGER.get_key(service)


class Config:
    """系统配置类"""

    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    OUTPUT_DIR = os.path.join(BASE_DIR, 'output')
    UPLOAD_DIR = os.path.join(BASE_DIR, 'uploads')
    TEMP_DIR = os.path.join(BASE_DIR, 'temp')

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    os.makedirs(TEMP_DIR, exist_ok=True)

    _provider = _default_provider()
    LLM_CONFIG = {
        'provider': _provider,
        'model': _default_model(_provider),
        'api_key': _default_api_key(_provider),
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
