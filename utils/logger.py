"""
统一日志模块

为整个项目提供统一的日志配置和管理

功能特性：
- 统一日志格式：所有模块使用相同的日志格式
- 日志级别管理：支持DEBUG、INFO、WARNING、ERROR、CRITICAL
- 多输出目标：支持控制台和文件输出
- 模块化配置：每个模块可独立配置日志级别
- 性能优化：延迟初始化、日志缓冲

使用方法：
```python
from utils.logger import get_logger, setup_logging

# 设置全局日志配置
setup_logging(level='INFO', log_file='app.log')

# 获取模块专用日志器
logger = get_logger('my_module')
logger.info('这是一条信息日志')
logger.error('这是一条错误日志')
```
"""

import os
import sys
import logging
import logging.handlers
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime
from dataclasses import dataclass
from enum import Enum
import threading
import json


class LogLevel(Enum):
    """日志级别枚举"""
    DEBUG = logging.DEBUG
    INFO = logging.INFO
    WARNING = logging.WARNING
    ERROR = logging.ERROR
    CRITICAL = logging.CRITICAL


@dataclass
class LogConfig:
    """日志配置"""
    level: str = 'INFO'
    log_file: Optional[str] = None
    max_file_size: int = 10 * 1024 * 1024
    backup_count: int = 5
    format_string: str = '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s'
    date_format: str = '%Y-%m-%d %H:%M:%S'
    console_output: bool = True
    file_output: bool = True
    colored_console: bool = True


class ColoredFormatter(logging.Formatter):
    """彩色日志格式化器"""
    
    COLORS = {
        'DEBUG': '\033[36m',     # 青色
        'INFO': '\033[32m',      # 绿色
        'WARNING': '\033[33m',   # 黄色
        'ERROR': '\033[31m',     # 红色
        'CRITICAL': '\033[35m',  # 紫色
    }
    RESET = '\033[0m'
    
    def format(self, record):
        if record.levelname in self.COLORS:
            record.levelname = (
                f"{self.COLORS[record.levelname]}{record.levelname}{self.RESET}"
            )
        return super().format(record)


class JSONFormatter(logging.Formatter):
    """JSON格式日志格式化器"""
    
    def format(self, record):
        log_data = {
            'timestamp': datetime.now().isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno
        }
        
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)
        
        return json.dumps(log_data, ensure_ascii=False)


class LogManager:
    """日志管理器"""
    
    _instance = None
    _lock = threading.Lock()
    _initialized = False
    _loggers: Dict[str, logging.Logger] = {}
    _config: LogConfig = LogConfig()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def setup(self, config: Optional[LogConfig] = None, **kwargs):
        """
        设置日志配置
        
        Args:
            config: 日志配置对象
            **kwargs: 配置参数（优先级高于config对象）
        """
        if config:
            self._config = config
        
        for key, value in kwargs.items():
            if hasattr(self._config, key):
                setattr(self._config, key, value)
        
        self._initialized = True
        
        root_logger = logging.getLogger()
        root_logger.setLevel(LogLevel[self._config.level.upper()].value)
        
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
        
        if self._config.console_output:
            self._add_console_handler(root_logger)
        
        if self._config.file_output and self._config.log_file:
            self._add_file_handler(root_logger)
    
    def _add_console_handler(self, logger: logging.Logger):
        """添加控制台处理器"""
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(LogLevel[self._config.level.upper()].value)
        
        if self._config.colored_console and sys.stdout.isatty():
            formatter = ColoredFormatter(
                self._config.format_string,
                datefmt=self._config.date_format
            )
        else:
            formatter = logging.Formatter(
                self._config.format_string,
                datefmt=self._config.date_format
            )
        
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    
    def _add_file_handler(self, logger: logging.Logger):
        """添加文件处理器"""
        log_path = Path(self._config.log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        handler = logging.handlers.RotatingFileHandler(
            self._config.log_file,
            maxBytes=self._config.max_file_size,
            backupCount=self._config.backup_count,
            encoding='utf-8'
        )
        handler.setLevel(LogLevel[self._config.level.upper()].value)
        
        formatter = logging.Formatter(
            self._config.format_string,
            datefmt=self._config.date_format
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    
    def get_logger(self, name: str, level: Optional[str] = None) -> logging.Logger:
        """
        获取日志器
        
        Args:
            name: 日志器名称
            level: 日志级别（可选，覆盖全局配置）
            
        Returns:
            logging.Logger: 日志器实例
        """
        if not self._initialized:
            self.setup()
        
        if name not in self._loggers:
            logger = logging.getLogger(name)
            
            if level:
                logger.setLevel(LogLevel[level.upper()].value)
            
            self._loggers[name] = logger
        
        return self._loggers[name]
    
    def set_module_level(self, module_name: str, level: str):
        """
        设置模块日志级别
        
        Args:
            module_name: 模块名称
            level: 日志级别
        """
        if module_name in self._loggers:
            self._loggers[module_name].setLevel(LogLevel[level.upper()].value)
    
    def get_config(self) -> LogConfig:
        """获取当前配置"""
        return self._config
    
    def reset(self):
        """重置日志管理器"""
        self._loggers.clear()
        self._initialized = False
        
        root_logger = logging.getLogger()
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)


def setup_logging(level: str = 'INFO',
                 log_file: Optional[str] = None,
                 console_output: bool = True,
                 file_output: bool = True,
                 colored_console: bool = True,
                 **kwargs) -> LogManager:
    """
    设置全局日志配置
    
    Args:
        level: 日志级别
        log_file: 日志文件路径
        console_output: 是否输出到控制台
        file_output: 是否输出到文件
        colored_console: 是否使用彩色控制台输出
        **kwargs: 其他配置参数
        
    Returns:
        LogManager: 日志管理器实例
        
    Example:
        >>> setup_logging(level='DEBUG', log_file='logs/app.log')
    """
    config = LogConfig(
        level=level,
        log_file=log_file,
        console_output=console_output,
        file_output=file_output,
        colored_console=colored_console
    )
    
    manager = LogManager()
    manager.setup(config, **kwargs)
    return manager


def get_logger(name: str, level: Optional[str] = None) -> logging.Logger:
    """
    获取日志器
    
    Args:
        name: 日志器名称（通常使用 __name__）
        level: 日志级别（可选）
        
    Returns:
        logging.Logger: 日志器实例
        
    Example:
        >>> logger = get_logger(__name__)
        >>> logger.info('这是一条日志')
    """
    return LogManager().get_logger(name, level)


def log_function_call(logger: logging.Logger):
    """
    函数调用日志装饰器
    
    Args:
        logger: 日志器实例
        
    Example:
        >>> logger = get_logger(__name__)
        >>> @log_function_call(logger)
        ... def my_function(x, y):
        ...     return x + y
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            logger.debug(f"调用函数: {func.__name__}(args={args}, kwargs={kwargs})")
            try:
                result = func(*args, **kwargs)
                logger.debug(f"函数返回: {func.__name__} -> {result}")
                return result
            except Exception as e:
                logger.error(f"函数异常: {func.__name__} -> {e}")
                raise
        return wrapper
    return decorator


def log_execution_time(logger: logging.Logger):
    """
    执行时间日志装饰器
    
    Args:
        logger: 日志器实例
        
    Example:
        >>> logger = get_logger(__name__)
        >>> @log_execution_time(logger)
        ... def slow_function():
        ...     time.sleep(1)
    """
    import time
    
    def decorator(func):
        def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                execution_time = time.time() - start_time
                logger.info(f"执行时间: {func.__name__} 耗时 {execution_time:.3f} 秒")
                return result
            except Exception as e:
                execution_time = time.time() - start_time
                logger.error(f"执行失败: {func.__name__} 耗时 {execution_time:.3f} 秒, 错误: {e}")
                raise
        return wrapper
    return decorator


MODULE_LOG_LEVELS = {
    'modules.ner_processor': 'INFO',
    'modules.ocr_processor': 'INFO',
    'modules.paper_polisher': 'INFO',
    'modules.llm_client': 'WARNING',
    'modules.pdf_processor': 'INFO',
    'modules.word_processor': 'INFO',
    'modules.academic_note_generator': 'INFO',
    'modules.academic_summarizer': 'INFO',
}


def configure_module_logging():
    """
    配置模块日志级别
    
    根据预定义的模块日志级别配置各模块的日志输出
    """
    manager = LogManager()
    
    for module_name, level in MODULE_LOG_LEVELS.items():
        manager.set_module_level(module_name, level)


DEFAULT_LOG_FORMAT = '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s'
DEFAULT_DATE_FORMAT = '%Y-%m-%d %H:%M:%S'


if __name__ == "__main__":
    print("统一日志模块")
    print("="*60)
    print("\n使用方法:")
    print("```python")
    print("from utils.logger import setup_logging, get_logger")
    print("")
    print("# 设置全局日志配置")
    print("setup_logging(")
    print("    level='DEBUG',")
    print("    log_file='logs/app.log',")
    print("    console_output=True,")
    print("    file_output=True")
    print(")")
    print("")
    print("# 获取模块日志器")
    print("logger = get_logger(__name__)")
    print("")
    print("# 记录日志")
    print("logger.debug('调试信息')")
    print("logger.info('普通信息')")
    print("logger.warning('警告信息')")
    print("logger.error('错误信息')")
    print("logger.critical('严重错误')")
    print("")
    print("# 使用装饰器")
    print("@log_execution_time(logger)")
    print("def my_function():")
    print("    pass")
    print("```")
