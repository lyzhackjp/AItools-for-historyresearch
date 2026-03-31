"""
NDL OCR服务心跳检测模块

监控NDL OCR服务的可用性和运行状态
支持心跳检测、自动重试和告警提示
"""

import os
import sys
import time
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
import threading


class NDLOCRHeartbeatMonitor:
    """NDL OCR服务心跳监控器"""
    
    HEARTBEAT_INTERVAL = 300  # 5分钟 = 300秒
    
    def __init__(self, ndlocr_path: Optional[str] = None, test_image: Optional[str] = None):
        """
        初始化心跳监控器
        
        Args:
            ndlocr_path: NDL OCR可执行文件路径
            test_image: 测试用图片路径（用于心跳测试）
        """
        self.base_dir = Path(__file__).parent.parent
        
        if ndlocr_path:
            self.ndlocr_path = Path(ndlocr_path)
        else:
            self.ndlocr_path = self.base_dir / "ndlocr-lite" / "src" / "ocr.py"
        
        self.test_image = test_image
        self.status = {
            'is_available': False,
            'last_check': None,
            'last_success': None,
            'consecutive_failures': 0,
            'total_checks': 0,
            'successful_checks': 0,
            'average_response_time': 0,
            'response_times': []
        }
        
        self._lock = threading.Lock()
        self._monitoring = False
        self._monitor_thread = None
    
    def check_service(self, timeout: int = 60) -> Tuple[bool, float, str]:
        """
        检查NDL OCR服务是否可用
        
        Args:
            timeout: 超时时间（秒）
            
        Returns:
            Tuple[bool, float, str]: (是否成功, 响应时间秒, 错误信息)
        """
        start_time = time.time()
        
        if not self.ndlocr_path.exists():
            return False, 0, f"NDL OCR路径不存在: {self.ndlocr_path}"
        
        test_image = self.test_image
        if not test_image:
            test_images = list(self.base_dir.glob("test Images/*.png"))
            if test_images:
                test_image = str(test_images[0])
        
        if not test_image:
            test_image = str(self.base_dir / "test Images" / "page_0001.png")
        
        if not Path(test_image).exists():
            return False, 0, f"测试图片不存在: {test_image}"
        
        try:
            python_exe = sys.executable
            
            cmd = [python_exe, str(self.ndlocr_path), 
                   "--sourceimg", test_image,
                   "--output", str(self.base_dir / "temp_heartbeat_check")]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            
            response_time = time.time() - start_time
            
            if result.returncode == 0:
                return True, response_time, ""
            else:
                error_msg = result.stderr if result.stderr else "未知错误"
                return False, response_time, error_msg
                
        except subprocess.TimeoutExpired:
            return False, timeout, "服务响应超时"
        except Exception as e:
            return False, time.time() - start_time, str(e)
        finally:
            with self._lock:
                self.status['last_check'] = datetime.now().isoformat()
                self.status['total_checks'] += 1
    
    def perform_heartbeat(self) -> Dict[str, Any]:
        """
        执行一次心跳检测
        
        Returns:
            Dict: 心跳检测结果
        """
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 执行心跳检测...")
        
        is_available, response_time, error = self.check_service()
        
        with self._lock:
            if is_available:
                self.status['is_available'] = True
                self.status['last_success'] = datetime.now().isoformat()
                self.status['successful_checks'] += 1
                self.status['consecutive_failures'] = 0
                self.status['response_times'].append(response_time)
                
                if len(self.status['response_times']) > 10:
                    self.status['response_times'].pop(0)
                
                self.status['average_response_time'] = sum(self.status['response_times']) / len(self.status['response_times'])
                
                print(f"   ✓ 服务正常 (响应时间: {response_time:.2f}秒)")
            else:
                self.status['consecutive_failures'] += 1
                print(f"   ✗ 服务异常: {error}")
        
        return {
            'timestamp': datetime.now().isoformat(),
            'available': is_available,
            'response_time': response_time,
            'error': error,
            'consecutive_failures': self.status['consecutive_failures']
        }
    
    def start_monitoring(self, interval: Optional[int] = None):
        """
        开始持续监控
        
        Args:
            interval: 心跳间隔（秒），默认5分钟
        """
        if self._monitoring:
            print("监控已在运行中")
            return
        
        if interval is None:
            interval = self.HEARTBEAT_INTERVAL
        
        self._monitoring = True
        self._monitor_thread = threading.Thread(target=self._monitor_loop, args=(interval,))
        self._monitor_thread.daemon = True
        self._monitor_thread.start()
        
        print(f"NDL OCR服务监控已启动 (心跳间隔: {interval}秒)")
    
    def stop_monitoring(self):
        """停止监控"""
        self._monitoring = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5)
        print("NDL OCR服务监控已停止")
    
    def _monitor_loop(self, interval: int):
        """监控循环"""
        while self._monitoring:
            result = self.perform_heartbeat()
            
            if not result['available']:
                if result['consecutive_failures'] >= 3:
                    self._send_alert(result)
            
            time.sleep(interval)
    
    def _send_alert(self, result: Dict[str, Any]):
        """发送告警"""
        print("\n" + "!"*60)
        print("⚠️  NDL OCR服务告警")
        print("!"*60)
        print(f"连续失败次数: {result['consecutive_failures']}")
        print(f"最后错误: {result['error']}")
        print(f"建议操作:")
        print("  1. 检查NDL OCR是否正确安装")
        print("  2. 检查系统资源是否充足")
        print("  3. 检查网络连接是否正常")
        print("  4. 查看详细日志进行故障排查")
        print("!"*60 + "\n")
    
    def get_status(self) -> Dict[str, Any]:
        """
        获取当前状态
        
        Returns:
            Dict: 状态信息
        """
        with self._lock:
            status = self.status.copy()
        
        status['uptime_percentage'] = (
            status['successful_checks'] / status['total_checks'] * 100
            if status['total_checks'] > 0 else 0
        )
        
        status['health_status'] = 'healthy' if status['is_available'] else 'unhealthy'
        if status['consecutive_failures'] > 0:
            status['health_status'] = 'degraded'
        if status['consecutive_failures'] >= 3:
            status['health_status'] = 'critical'
        
        return status
    
    def wait_for_service(self, max_wait: int = 600, check_interval: int = 30) -> bool:
        """
        等待服务可用
        
        Args:
            max_wait: 最大等待时间（秒）
            check_interval: 检查间隔（秒）
            
        Returns:
            bool: 服务是否在等待期间变为可用
        """
        print(f"等待NDL OCR服务可用 (最多等待{max_wait}秒)...")
        
        start_time = time.time()
        checks = 0
        
        while time.time() - start_time < max_wait:
            checks += 1
            print(f"[{checks}] 检查服务状态...", end=" ")
            
            is_available, response_time, error = self.check_service()
            
            if is_available:
                print(f"✓ 可用 (响应: {response_time:.2f}秒)")
                return True
            else:
                print(f"✗ 不可用")
            
            time.sleep(check_interval)
        
        print(f"等待超时 (已检查{checks}次)")
        return False
    
    def generate_report(self) -> str:
        """
        生成健康报告
        
        Returns:
            str: 健康报告内容
        """
        status = self.get_status()
        
        report = f"""# NDL OCR服务健康报告

## 生成时间
{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## 服务状态
- **当前状态**: {'✓ 可用' if status['is_available'] else '✗ 不可用'}
- **健康等级**: {status['health_status'].upper()}
- **连续失败次数**: {status['consecutive_failures']}

## 统计信息
- **总检查次数**: {status['total_checks']}
- **成功次数**: {status['successful_checks']}
- **可用率**: {status['uptime_percentage']:.1f}%
- **平均响应时间**: {status['average_response_time']:.2f}秒

## 最近检查
"""
        
        if status['last_check']:
            report += f"- **最后检查时间**: {status['last_check']}\n"
        if status['last_success']:
            report += f"- **最后成功时间**: {status['last_success']}\n"
        
        report += f"""
## 响应时间历史
"""
        
        if status['response_times']:
            for i, rt in enumerate(status['response_times'], 1):
                report += f"- 第{i}次: {rt:.2f}秒\n"
        else:
            report += "暂无历史数据\n"
        
        report += f"""
## 配置信息
- **NDL OCR路径**: {self.ndlocr_path}
- **心跳间隔**: {self.HEARTBEAT_INTERVAL}秒 (5分钟)

---

*本报告由NDL OCR心跳监控模块自动生成*
"""
        
        return report
    
    def save_report(self, filename: Optional[str] = None):
        """
        保存健康报告
        
        Args:
            filename: 文件名（可选）
        """
        if not filename:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"ndl_ocr_health_{timestamp}.md"
        
        report_path = self.base_dir / filename
        
        try:
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write(self.generate_report())
            print(f"健康报告已保存: {report_path}")
        except Exception as e:
            print(f"报告保存失败: {e}")


class NDLOCRBatchProcessor:
    """NDL OCR批量处理器（带心跳监控）"""
    
    def __init__(self, ndlocr_path: Optional[str] = None):
        """
        初始化批量处理器
        
        Args:
            ndlocr_path: NDL OCR路径
        """
        self.base_dir = Path(__file__).parent.parent
        self.ndlocr_path = ndlocr_path or (self.base_dir / "ndlocr-lite" / "src" / "ocr.py")
        self.monitor = NDLOCRHeartbeatMonitor(self.ndlocr_path)
        self.results = []
    
    def process_images(self, image_dir: str, output_dir: str, 
                     timeout: int = 60, 
                     enable_heartbeat: bool = True,
                     heartbeat_interval: int = 300) -> List[Dict[str, Any]]:
        """
        批量处理图片
        
        Args:
            image_dir: 图片目录
            output_dir: 输出目录
            timeout: 单个图片处理超时（秒）
            enable_heartbeat: 是否启用心跳监控
            heartbeat_interval: 心跳间隔（秒）
            
        Returns:
            List[Dict]: 处理结果列表
        """
        image_dir = Path(image_dir)
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        image_files = sorted(image_dir.glob("*.png"))
        
        print(f"\n开始批量处理 {len(image_files)} 张图片...")
        print(f"输出目录: {output_dir}")
        
        if enable_heartbeat:
            self.monitor.start_monitoring(heartbeat_interval)
        
        results = []
        start_time = time.time()
        
        for i, img_path in enumerate(image_files, 1):
            print(f"\n[{i}/{len(image_files)}] {img_path.name}...", end=" ", flush=True)
            
            result = {
                'filename': img_path.name,
                'index': i,
                'success': False,
                'output_path': None,
                'error': None
            }
            
            output_subdir = output_dir / f"page_{i:04d}"
            output_subdir.mkdir(exist_ok=True)
            
            try:
                python_exe = sys.executable
                cmd = [
                    python_exe,
                    str(self.ndlocr_path),
                    "--sourceimg", str(img_path),
                    "--output", str(output_subdir)
                ]
                
                proc_result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=timeout
                )
                
                if proc_result.returncode == 0:
                    txt_file = output_subdir / f"{img_path.stem}.txt"
                    if txt_file.exists():
                        with open(txt_file, 'r', encoding='utf-8') as f:
                            text = f.read()
                        result['success'] = True
                        result['char_count'] = len(text)
                        result['output_path'] = str(output_subdir)
                        print(f"✓ ({len(text)} 字符)")
                    else:
                        result['error'] = "输出文件未生成"
                        print("✗ (输出文件未生成)")
                else:
                    result['error'] = proc_result.stderr[:100] if proc_result.stderr else "未知错误"
                    print(f"✗ ({result['error'][:50]})")
                    
            except subprocess.TimeoutExpired:
                result['error'] = "处理超时"
                print("✗ (超时)")
            except Exception as e:
                result['error'] = str(e)
                print(f"✗ ({e})")
            
            results.append(result)
        
        if enable_heartbeat:
            self.monitor.stop_monitoring()
        
        elapsed = time.time() - start_time
        
        success_count = sum(1 for r in results if r['success'])
        
        print(f"\n{'='*60}")
        print(f"批量处理完成")
        print(f"{'='*60}")
        print(f"总计: {len(results)}")
        print(f"成功: {success_count}")
        print(f"失败: {len(results) - success_count}")
        print(f"耗时: {elapsed:.1f}秒")
        print(f"平均: {elapsed/len(results):.1f}秒/张")
        
        self.results = results
        return results


def quick_health_check() -> bool:
    """
    快速健康检查
    
    Returns:
        bool: 服务是否健康
    """
    print("="*60)
    print("NDL OCR服务快速检查")
    print("="*60)
    
    monitor = NDLOCRHeartbeatMonitor()
    is_available, response_time, error = monitor.check_service()
    
    if is_available:
        print(f"\n✅ NDL OCR服务运行正常")
        print(f"响应时间: {response_time:.2f}秒")
        return True
    else:
        print(f"\n❌ NDL OCR服务不可用")
        print(f"错误: {error}")
        print("\n建议:")
        print("1. 确认NDL OCR已正确安装")
        print("2. 检查测试图片是否存在")
        print("3. 查看完整错误信息进行排查")
        return False


if __name__ == "__main__":
    quick_health_check()
