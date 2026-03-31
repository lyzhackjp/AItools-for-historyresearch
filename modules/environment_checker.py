"""
环境依赖检查模块

在执行主要任务前进行全面的环境依赖检查
自动生成环境检查报告
"""

import os
import sys
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Any
import json


class EnvironmentChecker:
    """环境依赖检查器"""
    
    def __init__(self):
        """初始化检查器"""
        self.base_dir = Path(__file__).parent.parent
        self.results = {
            'timestamp': datetime.now().strftime('%Y%m%d_%H%M%S'),
            'system': {},
            'python': {},
            'dependencies': {},
            'ndl_ocr': {},
            'config': {},
            'issues': [],
            'warnings': []
        }
        self.all_passed = True
    
    def check_all(self) -> Tuple[bool, str]:
        """
        执行所有检查
        
        Returns:
            Tuple[bool, str]: (是否全部通过, 报告内容)
        """
        print("="*60)
        print("环境依赖检查")
        print("="*60)
        print()
        
        self.check_system_info()
        self.check_python_version()
        self.check_dependencies()
        self.check_ndl_ocr()
        self.check_config()
        
        self.all_passed = len(self.results['issues']) == 0
        
        report = self.generate_report()
        self.save_report(report)
        
        return self.all_passed, report
    
    def check_system_info(self):
        """检查系统信息"""
        print("📋 检查系统信息...")
        
        try:
            import platform
            self.results['system'] = {
                'os': platform.system(),
                'os_version': platform.version(),
                'machine': platform.machine(),
                'processor': platform.processor()
            }
            print(f"   ✓ 操作系统: {self.results['system']['os']}")
            print(f"   ✓ 版本: {self.results['system']['os_version']}")
        except Exception as e:
            print(f"   ✗ 系统信息检查失败: {e}")
            self.results['issues'].append(f"系统信息检查失败: {e}")
    
    def check_python_version(self):
        """检查Python版本"""
        print("\n🐍 检查Python环境...")
        
        version = sys.version_info
        self.results['python'] = {
            'version': f"{version.major}.{version.minor}.{version.micro}",
            'executable': sys.executable
        }
        
        print(f"   ✓ Python版本: {self.results['python']['version']}")
        print(f"   ✓ 路径: {self.results['python']['executable']}")
        
        if version.major < 3 or (version.major == 3 and version.minor < 8):
            self.results['issues'].append(
                f"Python版本过低: {version.major}.{version.minor}，需要3.8以上"
            )
            print(f"   ✗ Python版本过低，需要3.8以上")
    
    def check_dependencies(self):
        """检查Python依赖包"""
        print("\n📦 检查Python依赖...")
        
        required_packages = {
            'flask': 'Flask Web框架',
            'docx': 'python-docx Word文档处理',
            'fitz': 'PyMuPDF PDF处理',
            'PIL': 'Pillow 图片处理',
            'pytesseract': 'Tesseract OCR接口',
            'openai': 'OpenAI API客户端',
            'anthropic': 'Anthropic API客户端',
            'requests': 'HTTP请求库',
            'dotenv': 'python-dotenv 环境变量'
        }
        
        for package, description in required_packages.items():
            try:
                if package == 'docx':
                    import docx
                    version = getattr(docx, '__version__', 'unknown')
                elif package == 'fitz':
                    import fitz
                    version = getattr(fitz, '__version__', 'unknown')
                elif package == 'PIL':
                    from PIL import Image
                    version = getattr(Image, '__version__', 'unknown')
                elif package == 'dotenv':
                    import dotenv
                    version = getattr(dotenv, '__version__', 'unknown')
                else:
                    module = __import__(package)
                    version = getattr(module, '__version__', 'unknown')
                
                self.results['dependencies'][package] = {
                    'installed': True,
                    'version': version,
                    'description': description
                }
                print(f"   ✓ {description}: {version}")
                
            except ImportError:
                self.results['dependencies'][package] = {
                    'installed': False,
                    'version': None,
                    'description': description
                }
                self.results['issues'].append(f"缺少依赖: {description}")
                print(f"   ✗ {description}: 未安装")
            except Exception as e:
                self.results['dependencies'][package] = {
                    'installed': False,
                    'version': None,
                    'description': description,
                    'error': str(e)
                }
                self.results['issues'].append(f"{description}检查失败: {e}")
                print(f"   ✗ {description}: 检查失败 - {e}")
    
    def check_ndl_ocr(self):
        """检查NDL OCR环境"""
        print("\n🔍 检查NDL OCR环境...")
        
        ndlocr_dir = self.base_dir / "ndlocr-lite"
        ndlocr_src = ndlocr_dir / "src" / "ocr.py"
        
        if not ndlocr_dir.exists():
            self.results['ndl_ocr'] = {
                'installed': False,
                'issue': 'NDL OCR目录不存在'
            }
            self.results['issues'].append(
                'NDL OCR未安装，请运行: git clone https://github.com/ndl-lab/ndlocr-lite'
            )
            print(f"   ✗ NDL OCR目录不存在")
            return
        
        if not ndlocr_src.exists():
            self.results['ndl_ocr'] = {
                'installed': False,
                'issue': 'ocr.py文件不存在'
            }
            self.results['issues'].append('NDL OCR源码不完整，ocr.py文件缺失')
            print(f"   ✗ ocr.py文件不存在")
            return
        
        self.results['ndl_ocr'] = {
            'installed': True,
            'path': str(ndlocr_src),
            'directory': str(ndlocr_dir)
        }
        print(f"   ✓ NDL OCR已安装")
        print(f"   ✓ 路径: {ndlocr_src}")
        
        self.check_ndl_ocr_dependencies()
    
    def check_ndl_ocr_dependencies(self):
        """检查NDL OCR依赖"""
        print("\n   📚 检查NDL OCR依赖...")
        
        ndlocr_dir = self.base_dir / "ndlocr-lite"
        requirements_file = ndlocr_dir / "requirements.txt"
        
        if not requirements_file.exists():
            self.results['ndl_ocr']['requirements_check'] = {
                'checked': False,
                'note': 'requirements.txt文件不存在'
            }
            print(f"   ⚠ requirements.txt不存在")
            return
        
        try:
            with open(requirements_file, 'r', encoding='utf-8') as f:
                requirements = {}
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        parts = line.split('==')
                        if len(parts) == 2:
                            requirements[parts[0]] = parts[1]
            
            installed_count = 0
            total_count = len(requirements)
            
            for package, version in requirements.items():
                try:
                    if package == 'flet':
                        import flet
                        installed_count += 1
                    elif package == 'dill':
                        import dill
                        installed_count += 1
                    elif package == 'lxml':
                        import lxml
                        installed_count += 1
                    elif package == 'networkx':
                        import networkx
                        installed_count += 1
                    elif package == 'onnxruntime':
                        import onnxruntime
                        installed_count += 1
                    elif package == 'pillow':
                        from PIL import Image
                        installed_count += 1
                    elif package == 'ordered-set':
                        import ordered_set
                        installed_count += 1
                    elif package == 'protobuf':
                        import google.protobuf
                        installed_count += 1
                    elif package == 'pyparsing':
                        import pyparsing
                        installed_count += 1
                    elif package == 'PyYAML':
                        import yaml
                        installed_count += 1
                    elif package == 'tqdm':
                        import tqdm
                        installed_count += 1
                    elif package == 'reportlab':
                        import reportlab
                        installed_count += 1
                    elif package == 'pypdfium2':
                        import pypdfium2
                        installed_count += 1
                    elif package == 'numpy':
                        import numpy
                        installed_count += 1
                    elif package == 'opencv-python-headless':
                        import cv2
                        installed_count += 1
                except ImportError:
                    pass
            
            self.results['ndl_ocr']['requirements_check'] = {
                'installed': installed_count,
                'total': total_count,
                'status': 'ok' if installed_count == total_count else 'partial'
            }
            
            if installed_count == total_count:
                print(f"   ✓ NDL OCR依赖完整 ({installed_count}/{total_count})")
            else:
                print(f"   ⚠ NDL OCR依赖部分安装 ({installed_count}/{total_count})")
                self.results['warnings'].append(
                    f'NDL OCR依赖未完全安装 ({installed_count}/{total_count})，'
                    f'建议运行: cd ndlocr-lite && pip install -r requirements.txt'
                )
                
        except Exception as e:
            self.results['ndl_ocr']['requirements_check'] = {
                'checked': False,
                'error': str(e)
            }
            print(f"   ⚠ NDL OCR依赖检查失败: {e}")
    
    def check_config(self):
        """检查配置文件"""
        print("\n⚙️ 检查配置文件...")
        
        env_file = self.base_dir / ".env"
        
        if not env_file.exists():
            env_example = self.base_dir / ".env.example"
            if env_example.exists():
                import shutil
                shutil.copy(env_example, env_file)
                print(f"   ✓ 已从.env.example创建.env文件")
                self.results['warnings'].append('已自动创建.env配置文件，请根据需要修改')
        
        try:
            from dotenv import load_dotenv
            load_dotenv()
            
            required_configs = {
                'LLM_PROVIDER': 'LLM提供商',
                'OPENAI_API_KEY': 'OpenAI API密钥',
                'DASHSCOPE_API_KEY': '阿里云API密钥'
            }
            
            for key, description in required_configs.items():
                value = os.getenv(key)
                if value:
                    display_value = value[:10] + '...' if len(value) > 10 else value
                    print(f"   ✓ {description}: 已配置")
                else:
                    print(f"   ⚠ {description}: 未配置")
            
            self.results['config'] = {
                'status': 'configured',
                'path': str(env_file)
            }
            
        except Exception as e:
            self.results['config'] = {
                'status': 'error',
                'error': str(e)
            }
            print(f"   ✗ 配置检查失败: {e}")
    
    def generate_report(self) -> str:
        """生成检查报告"""
        print("\n" + "="*60)
        print("检查结果汇总")
        print("="*60)
        
        if self.all_passed:
            print("\n✅ 所有检查通过！环境配置正确。")
        else:
            print(f"\n❌ 发现 {len(self.results['issues'])} 个问题：")
            for i, issue in enumerate(self.results['issues'], 1):
                print(f"   {i}. {issue}")
        
        if self.results['warnings']:
            print(f"\n⚠️  警告 ({len(self.results['warnings'])} 个)：")
            for i, warning in enumerate(self.results['warnings'], 1):
                print(f"   {i}. {warning}")
        
        report = f"""# 环境依赖检查报告

## 检查时间
{self.results['timestamp']}

## 系统信息
- 操作系统: {self.results['system'].get('os', 'Unknown')}
- 版本: {self.results['system'].get('os_version', 'Unknown')}
- 架构: {self.results['system'].get('machine', 'Unknown')}

## Python环境
- 版本: {self.results['python'].get('version', 'Unknown')}
- 路径: {self.results['python'].get('executable', 'Unknown')}

## Python依赖

### 核心依赖
"""
        
        for package, info in self.results['dependencies'].items():
            status = "✓ 已安装" if info['installed'] else "✗ 未安装"
            version = info.get('version', 'N/A')
            report += f"- {info['description']}: {status} (v{version})\n"
        
        report += f"""
## NDL OCR环境

### 安装状态
"""
        
        if self.results['ndl_ocr'].get('installed'):
            report += f"- ✓ NDL OCR: 已安装\n"
            report += f"- 路径: {self.results['ndl_ocr'].get('path', 'N/A')}\n"
            
            if 'requirements_check' in self.results['ndl_ocr']:
                check = self.results['ndl_ocr']['requirements_check']
                if check.get('checked'):
                    report += f"- 依赖状态: {check['installed']}/{check['total']}\n"
        else:
            report += f"- ✗ NDL OCR: 未安装\n"
            report += f"- 问题: {self.results['ndl_ocr'].get('issue', 'Unknown')}\n"
        
        report += f"""
## 配置文件

"""
        
        if self.results['config'].get('status') == 'configured':
            report += f"- ✓ 配置文件: 已就绪\n"
            report += f"- 路径: {self.results['config'].get('path', 'N/A')}\n"
        else:
            report += f"- ⚠ 配置文件: 需要配置\n"
        
        report += f"""
## 问题与警告

"""
        
        if self.results['issues']:
            report += f"### 发现的问题 ({len(self.results['issues'])}个)\n\n"
            for i, issue in enumerate(self.results['issues'], 1):
                report += f"{i}. {issue}\n\n"
        else:
            report += "### 问题\n\n无问题发现。\n\n"
        
        if self.results['warnings']:
            report += f"### 警告 ({len(self.results['warnings'])}个)\n\n"
            for i, warning in enumerate(self.results['warnings'], 1):
                report += f"{i}. {warning}\n\n"
        
        report += f"""
## 总结

**检查结果**: {'✅ 全部通过' if self.all_passed else f'❌ 发现{len(self.results["issues"])}个问题'}

**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

---

*本报告由环境依赖检查模块自动生成*
"""
        
        return report
    
    def save_report(self, report: str):
        """保存检查报告"""
        timestamp = self.results['timestamp']
        report_file = self.base_dir / f"{timestamp}_环境检查报告.md"
        
        try:
            with open(report_file, 'w', encoding='utf-8') as f:
                f.write(report)
            print(f"\n📄 报告已保存: {report_file}")
        except Exception as e:
            print(f"\n❌ 报告保存失败: {e}")
    
    def get_report_filename(self) -> str:
        """获取报告文件名"""
        return f"{self.results['timestamp']}_环境检查报告.md"


def run_environment_check(task_name: str = "任务") -> bool:
    """
    运行环境检查的便捷函数
    
    Args:
        task_name: 任务名称
        
    Returns:
        bool: 检查是否全部通过
    """
    checker = EnvironmentChecker()
    passed, report = checker.check_all()
    
    print("\n" + "="*60)
    if passed:
        print(f"✅ 环境检查通过，可以执行{task_name}")
    else:
        print(f"❌ 环境检查未通过，请先解决上述问题后再执行{task_name}")
        print("\n💡 解决方案：")
        for issue in checker.results['issues']:
            if 'NDL OCR未安装' in issue:
                print("   1. 运行: git clone https://github.com/ndl-lab/ndlocr-lite")
                print("   2. 进入目录: cd ndlocr-lite")
                print("   3. 安装依赖: pip install -r requirements.txt")
            elif '缺少依赖' in issue:
                print(f"   - 安装缺失的Python包")
            elif 'Python版本过低' in issue:
                print("   - 升级Python到3.8或更高版本")
    
    return passed


if __name__ == "__main__":
    passed = run_environment_check("PDF处理任务")
    sys.exit(0 if passed else 1)
