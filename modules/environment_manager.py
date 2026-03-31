# -*- coding: utf-8 -*-
"""
环境管理模块
实现环境无关性机制，确保工作区在不同环境中正常运行
"""

import os
import sys
import json
import platform
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class EnvironmentInfo:
    python_version: str
    platform_system: str
    platform_machine: str
    working_directory: str
    has_cuda: bool
    cuda_version: Optional[str]
    gpu_count: int
    memory_total_gb: float

class EnvironmentManager:
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if EnvironmentManager._initialized:
            return
        
        EnvironmentManager._initialized = True
        self._project_root = self._detect_project_root()
        self._config = self._load_config()
        self._env_info = self._detect_environment()
        self._dependencies_checked = False
        
        logger.info(f"环境管理器初始化完成")
        logger.info(f"项目根目录: {self._project_root}")
        logger.info(f"工作目录: {self._env_info.working_directory}")
    
    def _detect_project_root(self) -> Path:
        current = Path(__file__).resolve()
        
        while current.parent != current:
            if (current / "modules").exists() or (current / "config").exists():
                return current
            current = current.parent
        
        return Path(__file__).resolve().parent
    
    def _load_config(self) -> Dict:
        config_path = self._project_root / "config" / "environment_config.json"
        
        default_config = {
            "ndlocr_path": "external/ndlkotenocr-lite",
            "output_base": "output",
            "temp_dir": "temp",
            "cache_dir": "cache",
            "log_dir": "logs",
            "data_dir": "data",
            "models_dir": "models",
            "auto_install_dependencies": True,
            "required_packages": [
                "torch>=2.0.0",
                "torchvision>=0.15.0",
                "Pillow>=9.0.0",
                "opencv-python>=4.5.0",
                "numpy>=1.20.0",
                "PyYAML>=6.0",
                "tqdm>=4.64.0",
                "fitz",
                "lmdb>=1.4.0"
            ],
            "optional_packages": [
                "mmdet>=3.0.0",
                "mmcv>=2.0.0",
                "pytorch-lightning>=2.0.0",
                "onnx>=1.16.0",
                "onnxruntime>=1.18.0"
            ]
        }
        
        if config_path.exists():
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    loaded_config = json.load(f)
                    default_config.update(loaded_config)
            except Exception as e:
                logger.warning(f"加载配置文件失败，使用默认配置: {e}")
        
        return default_config
    
    def _detect_environment(self) -> EnvironmentInfo:
        import psutil
        
        has_cuda = False
        cuda_version = None
        gpu_count = 0
        
        try:
            import torch
            has_cuda = torch.cuda.is_available()
            if has_cuda:
                cuda_version = torch.version.cuda
                gpu_count = torch.cuda.device_count()
        except ImportError:
            pass
        
        memory = psutil.virtual_memory()
        
        return EnvironmentInfo(
            python_version=platform.python_version(),
            platform_system=platform.system(),
            platform_machine=platform.machine(),
            working_directory=str(Path.cwd()),
            has_cuda=has_cuda,
            cuda_version=cuda_version,
            gpu_count=gpu_count,
            memory_total_gb=memory.total / (1024**3)
        )
    
    @property
    def project_root(self) -> Path:
        return self._project_root
    
    @property
    def config(self) -> Dict:
        return self._config
    
    @property
    def env_info(self) -> EnvironmentInfo:
        return self._env_info
    
    def get_path(self, *parts, absolute: bool = True) -> Path:
        path = self._project_root.joinpath(*parts)
        return path.resolve() if absolute else path
    
    def get_relative_path(self, target: Path) -> Path:
        try:
            return target.relative_to(self._project_root)
        except ValueError:
            return target
    
    def get_ndlocr_path(self, *parts) -> Path:
        return self.get_path(self._config["ndlocr_path"], *parts)
    
    def get_output_path(self, *parts) -> Path:
        return self.get_path(self._config["output_base"], *parts)
    
    def get_temp_path(self, *parts) -> Path:
        return self.get_path(self._config["temp_dir"], *parts)
    
    def get_cache_path(self, *parts) -> Path:
        return self.get_path(self._config["cache_dir"], *parts)
    
    def get_log_path(self, *parts) -> Path:
        return self.get_path(self._config["log_dir"], *parts)
    
    def get_data_path(self, *parts) -> Path:
        return self.get_path(self._config["data_dir"], *parts)
    
    def get_models_path(self, *parts) -> Path:
        return self.get_path(self._config["models_dir"], *parts)
    
    def ensure_directories(self):
        dirs = [
            self.get_output_path(),
            self.get_temp_path(),
            self.get_cache_path(),
            self.get_log_path(),
            self.get_data_path(),
            self.get_models_path()
        ]
        
        for d in dirs:
            d.mkdir(parents=True, exist_ok=True)
        
        logger.info("工作目录结构已创建")
    
    def check_dependencies(self, install_missing: bool = None) -> Dict[str, Any]:
        if install_missing is None:
            install_missing = self._config.get("auto_install_dependencies", False)
        
        results = {
            "required": {},
            "optional": {},
            "missing_required": [],
            "missing_optional": [],
            "all_satisfied": True
        }
        
        for pkg in self._config["required_packages"]:
            pkg_name = pkg.split(">=")[0].split("==")[0].split("<")[0]
            try:
                __import__(pkg_name.replace("-", "_"))
                results["required"][pkg] = True
            except ImportError:
                results["required"][pkg] = False
                results["missing_required"].append(pkg)
                results["all_satisfied"] = False
        
        for pkg in self._config["optional_packages"]:
            pkg_name = pkg.split(">=")[0].split("==")[0].split("<")[0]
            try:
                __import__(pkg_name.replace("-", "_"))
                results["optional"][pkg] = True
            except ImportError:
                results["optional"][pkg] = False
                results["missing_optional"].append(pkg)
        
        if install_missing and results["missing_required"]:
            logger.info("正在安装缺失的依赖包...")
            self._install_packages(results["missing_required"])
        
        self._dependencies_checked = True
        return results
    
    def _install_packages(self, packages: List[str]):
        for pkg in packages:
            logger.info(f"安装: {pkg}")
            try:
                subprocess.check_call([
                    sys.executable, "-m", "pip", "install", pkg, "-q"
                ])
                logger.info(f"安装成功: {pkg}")
            except subprocess.CalledProcessError as e:
                logger.error(f"安装失败: {pkg}, 错误: {e}")
    
    def get_environment_report(self) -> str:
        report = []
        report.append("=" * 60)
        report.append("环境报告")
        report.append("=" * 60)
        report.append(f"Python版本: {self._env_info.python_version}")
        report.append(f"操作系统: {self._env_info.platform_system}")
        report.append(f"架构: {self._env_info.platform_machine}")
        report.append(f"项目根目录: {self._project_root}")
        report.append(f"工作目录: {self._env_info.working_directory}")
        report.append(f"总内存: {self._env_info.memory_total_gb:.2f} GB")
        report.append(f"CUDA可用: {self._env_info.has_cuda}")
        if self._env_info.has_cuda:
            report.append(f"CUDA版本: {self._env_info.cuda_version}")
            report.append(f"GPU数量: {self._env_info.gpu_count}")
        report.append("=" * 60)
        
        return "\n".join(report)
    
    def save_environment_config(self, output_path: Path = None):
        if output_path is None:
            output_path = self.get_config_path("current_environment.json")
        
        config_data = {
            "project_root": str(self._project_root),
            "environment_info": {
                "python_version": self._env_info.python_version,
                "platform_system": self._env_info.platform_system,
                "platform_machine": self._env_info.platform_machine,
                "has_cuda": self._env_info.has_cuda,
                "cuda_version": self._env_info.cuda_version,
                "gpu_count": self._env_info.gpu_count,
                "memory_total_gb": self._env_info.memory_total_gb
            },
            "paths": {
                "output": str(self.get_output_path()),
                "temp": str(self.get_temp_path()),
                "cache": str(self.get_cache_path()),
                "log": str(self.get_log_path()),
                "data": str(self.get_data_path()),
                "models": str(self.get_models_path()),
                "ndlocr": str(self.get_ndlocr_path())
            }
        }
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"环境配置已保存: {output_path}")
    
    def get_config_path(self, *parts) -> Path:
        return self.get_path("config", *parts)


def get_environment_manager() -> EnvironmentManager:
    return EnvironmentManager()


def get_project_root() -> Path:
    return get_environment_manager().project_root


def get_path(*parts, absolute: bool = True) -> Path:
    return get_environment_manager().get_path(*parts, absolute=absolute)


if __name__ == "__main__":
    env = EnvironmentManager()
    print(env.get_environment_report())
    
    env.ensure_directories()
    
    dep_results = env.check_dependencies(install_missing=False)
    print("\n依赖检查结果:")
    print(f"必需包满足: {dep_results['all_satisfied']}")
    if dep_results['missing_required']:
        print(f"缺失必需包: {dep_results['missing_required']}")
    if dep_results['missing_optional']:
        print(f"缺失可选包: {dep_results['missing_optional']}")
    
    env.save_environment_config()
