"""
环境配置助手模块

自动化环境配置工具，支持GitHub插件下载、API Key配置、Ollama本地部署等
为研究工作提供一站式环境配置解决方案

核心功能：
- 自动下载GitHub插件（.xpi格式）
- 检查Ollama安装状态
- 配置本地模型环境
- 验证API连接
- 环境依赖全面检查

主要工具支持：
- Zotero插件安装
- 火山方舟API配置
- Ollama本地部署
- Docker环境检查

使用方法：
    from modules.setup_assistant import SetupAssistant
    
    assistant = SetupAssistant()
    assistant.check_all()
"""

import os
import sys
import json
import subprocess
import re
import urllib.request
import urllib.error
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
import platform
import socket

from modules.environment_checker import EnvironmentChecker


class SetupAssistant:
    """环境配置助手"""
    
    GITHUB_RELEASES_PATTERN = r'https://github\.com/[^/]+/[^/]+/releases/download/[^/]+/.*\.xpi'
    
    PLUGIN_INFO = {
        'zotero-ai-butler': {
            'repo': 'steven-jianhao-li/zotero-AI-Butler',
            'description': 'Zotero AI助手插件',
            'latest_tag': None
        },
        'jasminum': {
            'repo': 'l0o0/jasminum',
            'description': '中文学术文献元数据提取插件',
            'latest_tag': None
        }
    }
    
    def __init__(self, workspace_dir: Optional[str] = None):
        """
        初始化配置助手
        
        Args:
            workspace_dir: 工作区目录路径
        """
        self.workspace_dir = Path(workspace_dir) if workspace_dir else Path.cwd()
        self.env_checker = EnvironmentChecker()
        self.results = {
            'timestamp': datetime.now().strftime('%Y%m%d_%H%M%S'),
            'system_info': {},
            'ollama': {},
            'api_config': {},
            'plugins': {},
            'docker': {},
            'issues': [],
            'warnings': [],
            'recommendations': []
        }
        
    def check_all(self) -> Tuple[bool, str]:
        """
        执行全面环境检查
        
        Returns:
            Tuple[bool, str]: (是否全部通过, 报告内容)
        """
        print("="*60)
        print("🛠️  环境配置助手 - 全面检查")
        print("="*60)
        print()
        
        self.check_system_info()
        self.check_python_environment()
        self.check_ollama_setup()
        self.check_docker_setup()
        self.check_api_configuration()
        self.check_network_connectivity()
        
        self.analyze_results()
        
        report = self.generate_report()
        self.save_report(report)
        
        all_passed = len(self.results['issues']) == 0
        
        return all_passed, report
    
    def check_system_info(self):
        """检查系统信息"""
        print("📋 检查系统信息...")
        
        try:
            import platform
            
            self.results['system_info'] = {
                'os': platform.system(),
                'os_version': platform.version(),
                'machine': platform.machine(),
                'processor': platform.processor(),
                'python_version': sys.version,
                'hostname': socket.gethostname()
            }
            
            print(f"   ✓ 操作系统: {self.results['system_info']['os']}")
            print(f"   ✓ Python版本: {self.results['system_info']['python_version']}")
            
        except Exception as e:
            self.results['issues'].append(f"系统信息检查失败: {str(e)}")
            print(f"   ✗ 系统信息检查失败: {e}")
    
    def check_python_environment(self):
        """检查Python环境依赖"""
        print("\n🐍 检查Python环境...")
        
        required_packages = [
            'requests',
            'openai',
            'anthropic',
            'transformers',
            'torch'
        ]
        
        optional_packages = [
            'zotero',
            'pytesseract',
            'Pillow',
            'fitz',
            'python-docx'
        ]
        
        installed = {}
        
        for package in required_packages + optional_packages:
            try:
                __import__(package.replace('-', '_'))
                installed[package] = True
                print(f"   ✓ {package}")
            except ImportError:
                installed[package] = False
                if package in required_packages:
                    self.results['issues'].append(f"缺少必需包: {package}")
                    print(f"   ✗ {package} (必需)")
                else:
                    self.results['warnings'].append(f"缺少可选包: {package}")
                    print(f"   ⚠ {package} (可选)")
        
        self.results['python_packages'] = installed
    
    def check_ollama_setup(self) -> Dict[str, Any]:
        """
        检查Ollama安装状态
        
        Returns:
            dict: Ollama配置状态
        """
        print("\n🦙 检查Ollama配置...")
        
        ollama_status = {
            'installed': False,
            'running': False,
            'models': [],
            'version': None,
            'api_accessible': False,
            'endpoint': 'http://localhost:11434'
        }
        
        try:
            result = subprocess.run(
                ['ollama', '--version'],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0:
                ollama_status['installed'] = True
                ollama_status['version'] = result.stdout.strip()
                print(f"   ✓ Ollama已安装: {ollama_status['version']}")
            else:
                self.results['issues'].append("Ollama未安装或不可用")
                print(f"   ✗ Ollama未安装")
                
        except FileNotFoundError:
            self.results['issues'].append("Ollama命令未找到，请安装Ollama")
            print(f"   ✗ Ollama未安装")
        except Exception as e:
            self.results['warnings'].append(f"Ollama检查失败: {str(e)}")
            print(f"   ⚠ Ollama检查失败: {e}")
        
        if ollama_status['installed']:
            try:
                response = urllib.request.urlopen(
                    ollama_status['endpoint'] + '/api/tags',
                    timeout=3
                )
                if response.status == 200:
                    ollama_status['running'] = True
                    ollama_status['api_accessible'] = True
                    
                    models_data = json.loads(response.read().decode('utf-8'))
                    ollama_status['models'] = models_data.get('models', [])
                    
                    print(f"   ✓ Ollama服务运行中")
                    print(f"   ✓ 已加载模型: {len(ollama_status['models'])}个")
                    
                    for model in ollama_status['models']:
                        print(f"      - {model.get('name', 'unknown')}")
                        
            except Exception as e:
                self.results['warnings'].append(f"Ollama API不可访问: {str(e)}")
                print(f"   ⚠ Ollama服务未运行，请启动: ollama serve")
        
        if not ollama_status['installed']:
            self.results['recommendations'].append({
                'category': 'ollama',
                'priority': 'high',
                'message': '建议安装Ollama以支持本地大模型部署',
                'install_command': self._get_ollama_install_command()
            })
        
        self.results['ollama'] = ollama_status
        return ollama_status
    
    def check_docker_setup(self) -> Dict[str, Any]:
        """
        检查Docker安装状态
        
        Returns:
            dict: Docker配置状态
        """
        print("\n🐳 检查Docker配置...")
        
        docker_status = {
            'installed': False,
            'running': False,
            'version': None,
            'containers': []
        }
        
        try:
            result = subprocess.run(
                ['docker', '--version'],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0:
                docker_status['installed'] = True
                docker_status['version'] = result.stdout.strip()
                print(f"   ✓ Docker已安装: {docker_status['version']}")
                
        except FileNotFoundError:
            self.results['warnings'].append("Docker未安装（RAGFlow等功能需要Docker）")
            print(f"   ⚠ Docker未安装")
        except Exception as e:
            self.results['warnings'].append(f"Docker检查失败: {str(e)}")
            print(f"   ⚠ Docker检查失败: {e}")
        
        if docker_status['installed']:
            try:
                result = subprocess.run(
                    ['docker', 'ps'],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                
                if result.returncode == 0:
                    docker_status['running'] = True
                    
                    lines = result.stdout.strip().split('\n')
                    if len(lines) > 1:
                        for line in lines[1:]:
                            parts = line.split()
                            if parts:
                                docker_status['containers'].append({
                                    'id': parts[0],
                                    'name': parts[-1] if len(parts) > 1 else 'unknown'
                                })
                    
                    print(f"   ✓ Docker运行中")
                    print(f"   ✓ 运行中的容器: {len(docker_status['containers'])}个")
                    
            except Exception as e:
                print(f"   ⚠ 无法获取Docker容器状态: {e}")
        
        self.results['docker'] = docker_status
        return docker_status
    
    def check_api_configuration(self):
        """检查API配置"""
        print("\n🔑 检查API配置...")
        
        api_configs = {
            'volcano': {
                'name': '火山方舟',
                'env_var': 'VOLCANO_API_KEY',
                'check_url': 'https://console.volcengine.com/ark/region:ark+cn-beijing/apiKey'
            },
            'dashscope': {
                'name': '阿里云DashScope',
                'env_var': 'DASHSCOPE_API_KEY',
                'check_url': 'https://dashscope.console.aliyun.com/apiKey'
            },
            'minimax': {
                'name': 'MiniMax',
                'env_var': 'MINIMAX_API_KEY',
                'check_url': 'https://www.minimax.io/'
            },
            'openai': {
                'name': 'OpenAI',
                'env_var': 'OPENAI_API_KEY',
                'check_url': 'https://platform.openai.com/api-keys'
            }
        }
        
        configured_apis = []
        
        for api_id, config in api_configs.items():
            env_var = config['env_var']
            api_key = os.getenv(env_var)
            
            if api_key:
                configured_apis.append({
                    'id': api_id,
                    'name': config['name'],
                    'has_key': True,
                    'key_prefix': api_key[:8] + '...' if len(api_key) > 8 else '***',
                    'check_url': config['check_url']
                })
                print(f"   ✓ {config['name']} - 已配置")
            else:
                self.results['warnings'].append(f"未配置{config['name']} API密钥")
                print(f"   ⚠ {config['name']} - 未配置")
        
        self.results['api_config'] = {
            'configured': configured_apis,
            'total': len(configured_apis)
        }
        
        if len(configured_apis) == 0:
            self.results['recommendations'].append({
                'category': 'api',
                'priority': 'high',
                'message': '建议至少配置一个API密钥以使用AI功能',
                'apis': list(api_configs.values())
            })
    
    def check_network_connectivity(self):
        """检查网络连接"""
        print("\n🌐 检查网络连接...")
        
        test_urls = {
            'github': 'https://api.github.com',
            'huggingface': 'https://huggingface.co',
            'ollama': 'https://ollama.com'
        }
        
        connectivity = {}
        
        for service, url in test_urls.items():
            try:
                response = urllib.request.urlopen(url, timeout=5)
                connectivity[service] = {
                    'accessible': True,
                    'status_code': response.status
                }
                print(f"   ✓ {service} - 可访问")
            except Exception as e:
                connectivity[service] = {
                    'accessible': False,
                    'error': str(e)
                }
                self.results['warnings'].append(f"{service}不可访问: {str(e)}")
                print(f"   ⚠ {service} - 不可访问")
        
        self.results['network'] = connectivity
    
    def download_github_plugin(self, repo_url: str, output_dir: Optional[str] = None) -> Tuple[bool, str]:
        """
        下载GitHub插件
        
        Args:
            repo_url: GitHub仓库URL或'owner/repo'格式
            output_dir: 输出目录
            
        Returns:
            Tuple[bool, str]: (是否成功, 文件路径或错误信息)
        """
        print(f"\n📥 尝试下载插件: {repo_url}")
        
        try:
            if '/' in repo_url and 'github.com' not in repo_url:
                repo = repo_url
            elif 'github.com' in repo_url:
                parts = repo_url.replace('https://github.com/', '').split('/')
                repo = f"{parts[0]}/{parts[1]}"
            else:
                return False, "无效的仓库格式"
            
            api_url = f"https://api.github.com/repos/{repo}/releases/latest"
            
            with urllib.request.urlopen(api_url, timeout=10) as response:
                release_data = json.loads(response.read().decode('utf-8'))
            
            assets = release_data.get('assets', [])
            
            xpi_assets = [a for a in assets if a['name'].endswith('.xpi')]
            
            if not xpi_assets:
                return False, f"未找到.xpi插件文件，可用的资产: {[a['name'] for a in assets]}"
            
            asset = xpi_assets[0]
            download_url = asset['browser_download_url']
            
            output_dir = Path(output_dir) if output_dir else self.workspace_dir / 'downloads'
            output_dir.mkdir(parents=True, exist_ok=True)
            
            output_file = output_dir / asset['name']
            
            print(f"   📥 下载: {asset['name']}")
            urllib.request.urlretrieve(download_url, output_file)
            
            print(f"   ✓ 下载完成: {output_file}")
            
            return True, str(output_file)
            
        except urllib.error.HTTPError as e:
            error_msg = f"HTTP错误: {e.code} {e.reason}"
            self.results['issues'].append(error_msg)
            return False, error_msg
        except Exception as e:
            error_msg = f"下载失败: {str(e)}"
            self.results['issues'].append(error_msg)
            return False, error_msg
    
    def configure_environment(self, config_type: str, **kwargs) -> Tuple[bool, str]:
        """
        配置特定环境
        
        Args:
            config_type: 配置类型 ('ollama', 'api_key', 'environment_variable')
            **kwargs: 特定配置参数
            
        Returns:
            Tuple[bool, str]: (是否成功, 结果信息)
        """
        if config_type == 'ollama':
            return self._configure_ollama(**kwargs)
        elif config_type == 'api_key':
            return self._configure_api_key(**kwargs)
        elif config_type == 'environment_variable':
            return self._configure_env_variable(**kwargs)
        else:
            return False, f"未知的配置类型: {config_type}"
    
    def validate_api_connection(self, provider: str, api_key: Optional[str] = None,
                               test_endpoint: Optional[str] = None) -> Tuple[bool, str]:
        """
        验证API连接
        
        Args:
            provider: API提供商
            api_key: API密钥（可选）
            test_endpoint: 测试端点（可选）
            
        Returns:
            Tuple[bool, str]: (是否成功, 结果信息)
        """
        print(f"\n🔍 验证{provider} API连接...")
        
        api_key = api_key or os.getenv(f"{provider.upper()}_API_KEY")
        
        if not api_key:
            return False, f"未提供API密钥"
        
        test_endpoints = {
            'volcano': 'https://ark.cn-beijing.volces.com/api/v3/chat/completions',
            'dashscope': 'https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation',
            'minimax': 'https://api.minimax.chat/v1/text/chatcompletion_v2',
            'openai': 'https://api.openai.com/v1/chat/completions'
        }
        
        endpoint = test_endpoint or test_endpoints.get(provider.lower())
        
        if not endpoint:
            return False, f"未知的API提供商: {provider}"
        
        try:
            if provider.lower() == 'openai':
                test_payload = {
                    'model': 'gpt-3.5-turbo',
                    'messages': [{'role': 'user', 'content': 'test'}],
                    'max_tokens': 5
                }
            elif provider.lower() == 'dashscope':
                test_payload = {
                    'model': 'qwen-turbo',
                    'input': {'messages': [{'role': 'user', 'content': 'test'}]},
                    'parameters': {'max_tokens': 5}
                }
            else:
                test_payload = {'model': 'test', 'messages': [{'role': 'user', 'content': 'test'}]}
            
            request = urllib.request.Request(
                endpoint,
                data=json.dumps(test_payload).encode('utf-8'),
                headers={
                    'Content-Type': 'application/json',
                    'Authorization': f'Bearer {api_key}'
                },
                method='POST'
            )
            
            with urllib.request.urlopen(request, timeout=10) as response:
                if response.status == 200:
                    print(f"   ✓ API连接成功")
                    return True, "API连接验证成功"
                else:
                    msg = f"API返回状态码: {response.status}"
                    print(f"   ⚠ {msg}")
                    return False, msg
                    
        except urllib.error.HTTPError as e:
            error_body = e.read().decode('utf-8') if e.fp else ''
            msg = f"HTTP错误 {e.code}: {error_body[:200]}"
            self.results['warnings'].append(msg)
            print(f"   ⚠ {msg}")
            return False, msg
        except Exception as e:
            msg = f"连接失败: {str(e)}"
            self.results['warnings'].append(msg)
            print(f"   ✗ {msg}")
            return False, msg
    
    def generate_setup_script(self, script_type: str = 'bash') -> str:
        """
        生成环境配置脚本
        
        Args:
            script_type: 脚本类型 ('bash', 'powershell', 'batch')
            
        Returns:
            str: 脚本内容
        """
        if script_type == 'bash':
            return self._generate_bash_script()
        elif script_type == 'powershell':
            return self._generate_powershell_script()
        elif script_type == 'batch':
            return self._generate_batch_script()
        else:
            return ""
    
    def analyze_results(self):
        """分析检查结果，生成建议"""
        print("\n📊 分析检查结果...")
        
        if len(self.results['issues']) == 0 and len(self.results['warnings']) == 0:
            print("   ✓ 所有检查通过！")
        else:
            if self.results['issues']:
                print(f"   ✗ 发现 {len(self.results['issues'])} 个问题")
            if self.results['warnings']:
                print(f"   ⚠ 发现 {len(self.results['warnings'])} 个警告")
        
        if self.results['recommendations']:
            print(f"\n📝 建议: {len(self.results['recommendations'])}条")
    
    def generate_report(self) -> str:
        """生成检查报告"""
        report_lines = [
            "="*60,
            "🛠️  环境配置助手 - 检查报告",
            "="*60,
            f"检查时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "一、系统信息",
            "-"*40,
            f"操作系统: {self.results['system_info'].get('os', 'Unknown')}",
            f"Python版本: {self.results['system_info'].get('python_version', 'Unknown')}",
            "",
            "二、Ollama配置",
            "-"*40,
            f"安装状态: {'已安装' if self.results['ollama'].get('installed') else '未安装'}",
        ]
        
        if self.results['ollama'].get('installed'):
            report_lines.append(f"运行状态: {'运行中' if self.results['ollama'].get('running') else '未运行'}")
            report_lines.append(f"已加载模型: {len(self.results['ollama'].get('models', []))}个")
            
            for model in self.results['ollama'].get('models', []):
                report_lines.append(f"  - {model.get('name', 'unknown')}")
        
        report_lines.extend([
            "",
            "三、Docker配置",
            "-"*40,
            f"安装状态: {'已安装' if self.results['docker'].get('installed') else '未安装'}",
        ])
        
        if self.results['docker'].get('installed'):
            report_lines.append(f"运行状态: {'运行中' if self.results['docker'].get('running') else '未运行'}")
            report_lines.append(f"运行中的容器: {len(self.results['docker'].get('containers', []))}个")
        
        report_lines.extend([
            "",
            "四、API配置",
            "-"*40,
            f"已配置的API数量: {self.results['api_config'].get('total', 0)}",
        ])
        
        for api in self.results['api_config'].get('configured', []):
            report_lines.append(f"  ✓ {api['name']}: {api['key_prefix']}")
        
        report_lines.extend([
            "",
            "五、问题汇总",
            "-"*40,
        ])
        
        if self.results['issues']:
            for i, issue in enumerate(self.results['issues'], 1):
                report_lines.append(f"{i}. ❌ {issue}")
        else:
            report_lines.append("  ✓ 无问题")
        
        report_lines.extend([
            "",
            "六、警告汇总",
            "-"*40,
        ])
        
        if self.results['warnings']:
            for i, warning in enumerate(self.results['warnings'], 1):
                report_lines.append(f"{i}. ⚠ {warning}")
        else:
            report_lines.append("  ✓ 无警告")
        
        if self.results['recommendations']:
            report_lines.extend([
                "",
                "七、建议",
                "-"*40,
            ])
            
            for i, rec in enumerate(self.results['recommendations'], 1):
                report_lines.append(f"{i}. [{rec.get('priority', 'normal').upper()}] {rec.get('message', '')}")
        
        report_lines.extend([
            "",
            "="*60,
            "报告生成完毕",
            "="*60
        ])
        
        return "\n".join(report_lines)
    
    def save_report(self, report: str, filename: Optional[str] = None):
        """保存报告到文件"""
        if filename is None:
            filename = f"environment_report_{self.results['timestamp']}.txt"
        
        output_path = self.workspace_dir / filename
        
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(report)
            print(f"\n💾 报告已保存: {output_path}")
        except Exception as e:
            print(f"\n⚠ 保存报告失败: {e}")
    
    def _get_ollama_install_command(self) -> str:
        """获取Ollama安装命令"""
        system = self.results['system_info'].get('os', '').lower()
        
        if 'darwin' in system or 'mac' in system:
            return 'brew install ollama/tap/ollama'
        elif 'windows' in system:
            return '请访问 https://ollama.com/download 下载安装程序'
        else:
            return 'curl -fsSL https://ollama.com/install.sh | sh'
    
    def _configure_ollama(self, **kwargs) -> Tuple[bool, str]:
        """配置Ollama"""
        action = kwargs.get('action', 'check')
        
        if action == 'start':
            try:
                subprocess.Popen(['ollama', 'serve'])
                return True, "Ollama服务已启动"
            except Exception as e:
                return False, f"启动失败: {str(e)}"
        elif action == 'install_model':
            model_name = kwargs.get('model', 'qwen36-27b-academic')
            try:
                subprocess.run(['ollama', 'pull', model_name], check=True)
                return True, f"模型 {model_name} 安装成功"
            except Exception as e:
                return False, f"安装失败: {str(e)}"
        
        return False, "未指定操作"
    
    def _configure_api_key(self, **kwargs) -> Tuple[bool, str]:
        """配置API密钥"""
        provider = kwargs.get('provider', '')
        api_key = kwargs.get('api_key', '')
        
        if not provider or not api_key:
            return False, "缺少provider或api_key参数"
        
        env_var = f"{provider.upper()}_API_KEY"
        
        try:
            with open(self.workspace_dir / '.env', 'a') as f:
                f.write(f"\n{env_var}={api_key}\n")
            
            os.environ[env_var] = api_key
            
            return True, f"API密钥已保存到.env文件"
        except Exception as e:
            return False, f"保存失败: {str(e)}"
    
    def _configure_env_variable(self, **kwargs) -> Tuple[bool, str]:
        """配置环境变量"""
        var_name = kwargs.get('name', '')
        var_value = kwargs.get('value', '')
        
        if not var_name:
            return False, "缺少变量名"
        
        os.environ[var_name] = var_value
        
        return True, f"环境变量 {var_name} 已设置"
    
    def _generate_bash_script(self) -> str:
        """生成Bash脚本"""
        return '''#!/bin/bash

echo "AI史学工具环境配置脚本"
echo "======================="

echo ""
echo "1. 检查Python环境..."
python3 --version || echo "请安装Python 3.8+"

echo ""
echo "2. 安装依赖包..."
pip install -r requirements.txt || echo "依赖安装失败"

echo ""
echo "3. 检查Ollama..."
if ! command -v ollama &> /dev/null; then
    echo "Ollama未安装，安装中..."
    curl -fsSL https://ollama.com/install.sh | sh
fi

echo ""
echo "4. 启动Ollama服务..."
ollama serve &
sleep 2

echo ""
echo "5. 配置完成！"
echo "请运行 python main.py 开始使用"
'''

    def _generate_powershell_script(self) -> str:
        """生成PowerShell脚本"""
        return '''# AI史学工具环境配置脚本

Write-Host "AI史学工具环境配置脚本" -ForegroundColor Green
Write-Host "=======================" -ForegroundColor Green

Write-Host ""
Write-Host "1. 检查Python环境..." -ForegroundColor Cyan
try {
    python --version
} catch {
    Write-Host "请安装Python 3.8+" -ForegroundColor Red
}

Write-Host ""
Write-Host "2. 安装依赖包..." -ForegroundColor Cyan
pip install -r requirements.txt

Write-Host ""
Write-Host "3. 检查Ollama..." -ForegroundColor Cyan
if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
    Write-Host "Ollama未安装，请访问 https://ollama.com/download 下载" -ForegroundColor Yellow
} else {
    Write-Host "Ollama已安装" -ForegroundColor Green
}

Write-Host ""
Write-Host "4. 配置完成！" -ForegroundColor Green
Write-Host "请运行 python main.py 开始使用" -ForegroundColor Cyan
'''

    def _generate_batch_script(self) -> str:
        """生成批处理脚本"""
        return '''@echo off
echo AI史学工具环境配置脚本
echo =======================

echo.
echo 1. 检查Python环境...
python --version
if errorlevel 1 goto :python_missing

echo.
echo 2. 安装依赖包...
pip install -r requirements.txt

echo.
echo 3. 配置完成！
echo 请运行 python main.py 开始使用
goto :end

:python_missing
echo.
echo 错误: 请先安装Python 3.8+

:end
pause
'''


def create_setup_assistant(workspace_dir: Optional[str] = None) -> SetupAssistant:
    """
    工厂函数：创建环境配置助手实例
    
    Args:
        workspace_dir: 工作区目录路径
        
    Returns:
        SetupAssistant: 配置好的助手实例
    """
    return SetupAssistant(workspace_dir=workspace_dir)
