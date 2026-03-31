# -*- coding: utf-8 -*-
"""
完整整合方案模块
实现环境无关性、中间文件管理、NDLoCR接口隔离和流程自动化
"""

import os
import sys
import json
import platform
import subprocess
import shutil
import zipfile
import atexit
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple, Callable
from dataclasses import dataclass

sys.stdout.reconfigure(encoding='utf-8')

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
    
    def __new__(cls, config_path: str = None):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, config_path: str = None):
        if self._initialized:
            return
        
        self._initialized = True
        self._project_root = self._detect_project_root()
        self._config = self._load_config()
        self._env_info = self._detect_environment()
        self._dependencies_checked = False
        
        self.ensure_directories()
        
        logger.info(f"环境管理器初始化完成，项目根目录: {self._project_root}")
    
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
    
    def get_config_path(self, *parts) -> Path:
        return self.get_path("config", *parts)
    
    def ensure_directories(self):
        dirs = [
            self.get_output_path(),
            self.get_temp_path(),
            self.get_cache_path(),
            self.get_log_path(),
            self.get_data_path(),
            self.get_models_path(),
            self.get_config_path()
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
            },
            "ndlocr_models": self.get_ndlocr_models_info()
        }
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"环境配置已保存: {output_path}")
    
    def get_ndlocr_models_info(self) -> Dict:
        ndlocr_path = self.get_ndlocr_path()
        models_info = {
            "available": False,
            "detection_model": None,
            "recognition_model": None
        }
        
        model_dir = ndlocr_path / "src" / "model"
        if model_dir.exists():
            models_info["available"] = True
            
            det_model = model_dir / "rtmdet-s-1280x1280.onnx"
            rec_model = model_dir / "parseq-ndl-32x384-tiny-10.onnx"
            
            if det_model.exists():
                models_info["detection_model"] = str(det_model)
            if rec_model.exists():
                models_info["recognition_model"] = str(rec_model)
        
        return models_info


class IntermediateFileManager:
    
    def __init__(self, env_manager: EnvironmentManager):
        self.env_manager = env_manager
        self._temp_files: List[Path] = []
        self._temp_dirs: List[Path] = []
        self._registered_files: Dict[str, Path] = {}
        
        atexit.register(self.cleanup_all)
    
    def create_temp_file(self, suffix: str = None, prefix: str = "temp_") -> Path:
        temp_dir = self.env_manager.get_temp_path()
        temp_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{prefix}{timestamp}"
        if suffix:
            filename += suffix
        
        temp_file = temp_dir / filename
        temp_file.touch()
        
        self._temp_files.append(temp_file)
        logger.debug(f"创建临时文件: {temp_file}")
        
        return temp_file
    
    def create_temp_dir(self, prefix: str = "temp_") -> Path:
        temp_base = self.env_manager.get_temp_path()
        temp_base.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dir_name = f"{prefix}{timestamp}"
        
        temp_dir = temp_base / dir_name
        temp_dir.mkdir(parents=True, exist_ok=True)
        
        self._temp_dirs.append(temp_dir)
        logger.debug(f"创建临时目录: {temp_dir}")
        
        return temp_dir
    
    def register_file(self, name: str, path: Path):
        self._registered_files[name] = path
        logger.debug(f"注册文件: {name} -> {path}")
    
    def get_registered_file(self, name: str) -> Optional[Path]:
        return self._registered_files.get(name)
    
    def cleanup_temp_files(self):
        cleaned = 0
        for temp_file in self._temp_files:
            try:
                if temp_file.exists():
                    temp_file.unlink()
                    cleaned += 1
            except Exception as e:
                logger.warning(f"清理临时文件失败: {temp_file}, 错误: {e}")
        
        self._temp_files.clear()
        logger.info(f"已清理 {cleaned} 个临时文件")
        return cleaned
    
    def cleanup_temp_dirs(self):
        cleaned = 0
        for temp_dir in self._temp_dirs:
            try:
                if temp_dir.exists():
                    shutil.rmtree(temp_dir)
                    cleaned += 1
            except Exception as e:
                logger.warning(f"清理临时目录失败: {temp_dir}, 错误: {e}")
        
        self._temp_dirs.clear()
        logger.info(f"已清理 {cleaned} 个临时目录")
        return cleaned
    
    def cleanup_all(self):
        self.cleanup_temp_files()
        self.cleanup_temp_dirs()
    
    def archive_intermediate_files(self, output_path: Path = None):
        if output_path is None:
            output_path = self.env_manager.get_output_path(
                "archives", 
                f"intermediate_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
            )
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for name, path in self._registered_files.items():
                if path.exists():
                    zf.write(path, arcname=f"{name}{path.suffix}")
            
            temp_dir = self.env_manager.get_temp_path()
            if temp_dir.exists():
                for file_path in temp_dir.rglob("*"):
                    if file_path.is_file():
                        rel_path = file_path.relative_to(temp_dir)
                        zf.write(file_path, arcname=f"temp/{rel_path}")
        
        logger.info(f"中间文件已归档: {output_path}")
        return output_path
    
    def get_file_manifest(self) -> Dict:
        manifest = {
            "registered_files": {k: str(v) for k, v in self._registered_files.items()},
            "temp_files": [str(f) for f in self._temp_files],
            "temp_dirs": [str(d) for d in self._temp_dirs],
            "timestamp": datetime.now().isoformat()
        }
        return manifest


class NDLoCRInterface:
    
    def __init__(self, env_manager: EnvironmentManager):
        self.env_manager = env_manager
        self._ndlocr_path = None
        self._is_available = False
        self._models_loaded = False
        self._detection_model = None
        self._recognition_model = None
        
        self._check_availability()
    
    def _check_availability(self) -> bool:
        ndlocr_path = self.env_manager.get_ndlocr_path()
        
        if ndlocr_path.exists():
            self._ndlocr_path = ndlocr_path
            self._is_available = True
            logger.info(f"NDLoCR已检测到: {ndlocr_path}")
        else:
            self._is_available = False
            logger.warning("NDLoCR未检测到，部分功能将不可用")
        
        return self._is_available
    
    @property
    def is_available(self) -> bool:
        return self._is_available
    
    @property
    def ndlocr_path(self) -> Optional[Path]:
        return self._ndlocr_path
    
    def get_config_template(self) -> Dict:
        return {
            "ndlocr_path": "external/ndlkotenocr-lite",
            "description": "NDLoCR路径配置",
            "instructions": [
                "1. 从 https://github.com/ndl-lab/ndlkotenocr-lite 克隆或下载NDLoCR",
                "2. 将NDLoCR放置在指定的相对路径",
                "3. 确保模型文件存在于 src/model/ 目录下",
                "4. 运行环境检查验证配置"
            ],
            "required_files": [
                "src/model/rtmdet-s-1280x1280.onnx",
                "src/model/parseq-ndl-32x384-tiny-10.onnx",
                "src/config/ndl.yaml",
                "src/config/NDLmoji.yaml"
            ]
        }
    
    def validate_setup(self) -> Dict:
        results = {
            "available": self._is_available,
            "path": str(self._ndlocr_path) if self._ndlocr_path else None,
            "required_files": {},
            "all_valid": False
        }
        
        if not self._is_available:
            return results
        
        required_files = self.get_config_template()["required_files"]
        all_valid = True
        
        for file_path in required_files:
            full_path = self._ndlocr_path / file_path
            exists = full_path.exists()
            results["required_files"][file_path] = exists
            if not exists:
                all_valid = False
        
        results["all_valid"] = all_valid
        return results
    
    def load_models(self) -> bool:
        if not self._is_available:
            logger.warning("NDLoCR不可用，无法加载模型")
            return False
        
        if self._models_loaded:
            return True
        
        try:
            model_dir = self._ndlocr_path / "src" / "model"
            
            det_model_path = model_dir / "rtmdet-s-1280x1280.onnx"
            rec_model_path = model_dir / "parseq-ndl-32x384-tiny-10.onnx"
            
            if det_model_path.exists() and rec_model_path.exists():
                self._detection_model = str(det_model_path)
                self._recognition_model = str(rec_model_path)
                self._models_loaded = True
                logger.info("NDLoCR模型路径已加载")
                return True
            else:
                logger.error("NDLoCR模型文件缺失")
                return False
                
        except Exception as e:
            logger.error(f"加载NDLoCR模型失败: {e}")
            return False
    
    def get_detection_model_path(self) -> Optional[str]:
        return self._detection_model
    
    def get_recognition_model_path(self) -> Optional[str]:
        return self._recognition_model
    
    def create_mock_interface(self) -> Dict:
        return {
            "type": "mock",
            "detection_model": "mock_detection.onnx",
            "recognition_model": "mock_recognition.onnx",
            "message": "这是模拟接口，用于测试目的"
        }


class WorkflowAutomation:
    
    def __init__(self, env_manager: EnvironmentManager):
        self.env_manager = env_manager
        self.file_manager = IntermediateFileManager(env_manager)
        self.ndlocr_interface = NDLoCRInterface(env_manager)
        
        self._pipeline_steps: List[Dict] = []
        self._current_step = 0
        self._is_running = False
    
    def register_step(self, name: str, function: Callable, 
                     inputs: List[str] = None, outputs: List[str] = None):
        step = {
            "name": name,
            "function": function,
            "inputs": inputs or [],
            "outputs": outputs or [],
            "status": "pending"
        }
        self._pipeline_steps.append(step)
        logger.info(f"注册工作流步骤: {name}")
    
    def run_pipeline(self, *args, **kwargs) -> Dict:
        logger.info("=" * 60)
        logger.info("开始执行工作流")
        logger.info("=" * 60)
        
        results = {
            "start_time": datetime.now().isoformat(),
            "steps": [],
            "success": True
        }
        
        self._is_running = True
        self._current_step = 0
        
        for i, step in enumerate(self._pipeline_steps):
            self._current_step = i
            step["status"] = "running"
            
            logger.info(f"[{i+1}/{len(self._pipeline_steps)}] 执行: {step['name']}")
            
            try:
                step_result = step["function"](*args, **kwargs)
                step["status"] = "completed"
                
                results["steps"].append({
                    "name": step["name"],
                    "status": "completed",
                    "result": step_result
                })
                
                logger.info(f"[{i+1}/{len(self._pipeline_steps)}] 完成: {step['name']}")
                
            except Exception as e:
                step["status"] = "failed"
                results["success"] = False
                
                results["steps"].append({
                    "name": step["name"],
                    "status": "failed",
                    "error": str(e)
                })
                
                logger.error(f"[{i+1}/{len(self._pipeline_steps)}] 失败: {step['name']}, 错误: {e}")
                break
        
        self._is_running = False
        results["end_time"] = datetime.now().isoformat()
        
        logger.info("=" * 60)
        logger.info(f"工作流执行{'成功' if results['success'] else '失败'}")
        logger.info("=" * 60)
        
        return results
    
    def get_pipeline_status(self) -> Dict:
        return {
            "is_running": self._is_running,
            "current_step": self._current_step,
            "total_steps": len(self._pipeline_steps),
            "steps": [
                {"name": s["name"], "status": s["status"]}
                for s in self._pipeline_steps
            ]
        }
    
    def save_pipeline_config(self, output_path: Path = None):
        if output_path is None:
            output_path = self.env_manager.get_config_path("pipeline_config.json")
        
        config = {
            "steps": [
                {
                    "name": s["name"],
                    "inputs": s["inputs"],
                    "outputs": s["outputs"]
                }
                for s in self._pipeline_steps
            ],
            "timestamp": datetime.now().isoformat()
        }
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        
        logger.info(f"工作流配置已保存: {output_path}")


def create_integration_manager(config_path: str = None) -> Tuple[EnvironmentManager, IntermediateFileManager, NDLoCRInterface, WorkflowAutomation]:
    env_manager = EnvironmentManager(config_path)
    file_manager = IntermediateFileManager(env_manager)
    ndlocr_interface = NDLoCRInterface(env_manager)
    workflow = WorkflowAutomation(env_manager)
    
    return env_manager, file_manager, ndlocr_interface, workflow


def main():
    env_manager, file_manager, ndlocr_interface, workflow = create_integration_manager()
    
    print(env_manager.get_environment_report())
    
    dep_results = env_manager.check_dependencies(install_missing=False)
    print("\n依赖检查结果:")
    print(f"  必需依赖: {sum(dep_results['required'].values())}/{len(dep_results['required'])} 满足")
    print(f"  可选依赖: {sum(dep_results['optional'].values())}/{len(dep_results['optional'])} 满足")
    
    ndlocr_validation = ndlocr_interface.validate_setup()
    print("\nNDLoCR验证:")
    print(f"  可用: {ndlocr_validation['available']}")
    print(f"  配置完整: {ndlocr_validation['all_valid']}")
    
    env_manager.save_environment_config()
    
    print("\n整合管理器初始化完成")


if __name__ == "__main__":
    main()
