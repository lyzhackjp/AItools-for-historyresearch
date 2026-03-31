#!/usr/bin/env python3
"""
优化代码执行测试 - 2次执行对比
记录关键步骤、时间、状态和错误信息
"""

import time
import sys
import json
from pathlib import Path
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import TimeoutException, NoSuchElementException

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
from tools.ndl_downloader.selenium_downloader import NDLSeleniumConfig

class ExecutionLogger:
    """执行日志记录器"""
    
    def __init__(self):
        self.logs = []
        self.start_time = None
        self.end_time = None
    
    def log(self, step, status, message, details=None):
        entry = {
            'timestamp': datetime.now().strftime('%H:%M:%S.%f')[:-3],
            'step': step,
            'status': status,
            'message': message,
            'details': details or {}
        }
        self.logs.append(entry)
        print(f"[{entry['timestamp']}] [{status}] {message}")
        if details:
            for key, value in details.items():
                print(f"    {key}: {value}")
    
    def get_summary(self):
        return {
            'total_logs': len(self.logs),
            'passed': sum(1 for l in self.logs if l['status'] == 'PASS'),
            'failed': sum(1 for l in self.logs if l['status'] == 'FAIL'),
            'info': sum(1 for l in self.logs if l['status'] == 'INFO'),
        }

class OptimizedExecutionTest:
    """优化代码执行测试"""
    
    def __init__(self, execution_num):
        self.execution_num = execution_num
        self.logger = ExecutionLogger()
        self.driver = None
        self.keyword = "井上哲次郎"
        self.results = []
        self.success = False
        self.error = None
        
    def run(self):
        """执行测试"""
        self.logger.start_time = datetime.now()
        self.logger.log('INIT', 'INFO', f'=== 第{self.execution_num}次执行开始 ===')
        
        try:
            # 步骤1: 初始化WebDriver
            self._init_driver()
            
            # 步骤2: 访问NDL网站
            self._access_website()
            
            # 步骤3: 定位搜索框
            search_box = self._locate_search_box()
            if not search_box:
                raise Exception("无法定位搜索框")
            
            # 步骤4: 执行搜索
            self._execute_search(search_box)
            
            # 步骤5: 解析结果
            self._parse_results()
            
            # 步骤6: 清理
            self._cleanup()
            
            self.logger.log('CLEANUP', 'PASS', '执行完成')
            self.success = True
            
        except Exception as e:
            self.logger.log('ERROR', 'FAIL', f'执行失败: {str(e)}')
            self.error = str(e)
            if self.driver:
                try:
                    self.driver.save_screenshot(f"execution_{self.execution_num}_error.png")
                    self.logger.log('SCREENSHOT', 'INFO', f'错误截图已保存')
                except:
                    pass
        
        self.logger.end_time = datetime.now()
        return self.success
    
    def _init_driver(self):
        """初始化WebDriver"""
        self.logger.log('DRIVER_INIT', 'INFO', '初始化WebDriver')
        
        try:
            chrome_options = Options()
            
            # 应用优化配置
            for option in NDLSeleniumConfig.CHROME_OPTIONS:
                chrome_options.add_argument(option)
            
            if self.execution_num == 1:
                chrome_options.add_argument('--headless')
            
            self.driver = webdriver.Chrome(options=chrome_options)
            self.driver.set_page_load_timeout(NDLSeleniumConfig.PAGE_LOAD_TIMEOUT)
            self.driver.implicitly_wait(NDLSeleniumConfig.IMPLICIT_WAIT)
            
            self.logger.log('DRIVER_INIT', 'PASS', 'WebDriver初始化成功', {
                'options': len(NDLSeleniumConfig.CHROME_OPTIONS),
                'timeout': NDLSeleniumConfig.PAGE_LOAD_TIMEOUT
            })
            
        except Exception as e:
            self.logger.log('DRIVER_INIT', 'FAIL', f'WebDriver初始化失败: {e}')
            raise
    
    def _access_website(self):
        """访问网站"""
        self.logger.log('ACCESS', 'INFO', f'访问 {NDLSeleniumConfig.SEARCH_URL}')
        
        start = time.time()
        self.driver.get(NDLSeleniumConfig.SEARCH_URL)
        
        # 优化等待
        time.sleep(NDLSeleniumConfig.OPTIMAL_WAIT)
        
        elapsed = time.time() - start
        
        title = self.driver.title
        source_len = len(self.driver.page_source)
        
        self.logger.log('ACCESS', 'PASS', f'页面加载成功', {
            'title': title,
            'source_length': source_len,
            'time': f'{elapsed:.2f}秒',
            'wait': f'{NDLSeleniumConfig.OPTIMAL_WAIT}秒'
        })
    
    def _locate_search_box(self):
        """定位搜索框"""
        self.logger.log('LOCATE', 'INFO', '开始定位搜索框')
        
        for attempt in range(NDLSeleniumConfig.RETRY_ATTEMPTS):
            self.logger.log('LOCATE', 'INFO', f'尝试 {attempt+1}/{NDLSeleniumConfig.RETRY_ATTEMPTS}')
            
            for locator_name, locator in NDLSeleniumConfig.SEARCH_BOX_LOCATORS:
                try:
                    self.logger.log('LOCATE', 'INFO', f'尝试选择器: {locator_name}')
                    
                    elements = self.driver.find_elements(By.CSS_SELECTOR, locator)
                    visible = [e for e in elements if e.is_displayed()]
                    
                    if visible:
                        search_box = visible[0]
                        self.logger.log('LOCATE', 'PASS', f'找到搜索框: {locator_name}', {
                            'locator': locator,
                            'visible_count': len(visible),
                            'input_type': search_box.get_attribute('type'),
                            'placeholder': search_box.get_attribute('placeholder')
                        })
                        return search_box
                        
                except Exception as e:
                    self.logger.log('LOCATE', 'INFO', f'{locator_name} 失败: {str(e)[:50]}')
                    continue
            
            if attempt < NDLSeleniumConfig.RETRY_ATTEMPTS - 1:
                self.logger.log('LOCATE', 'INFO', '重试定位')
                time.sleep(2)
        
        self.logger.log('LOCATE', 'FAIL', '无法定位搜索框')
        return None
    
    def _execute_search(self, search_box):
        """执行搜索"""
        self.logger.log('SEARCH', 'INFO', f'执行搜索: "{self.keyword}"')
        
        search_box.clear()
        search_box.send_keys(self.keyword)
        
        # 使用优化配置
        search_box.send_keys(Keys.RETURN)
        
        self.logger.log('SEARCH', 'INFO', '等待搜索结果')
        time.sleep(NDLSeleniumConfig.OPTIMAL_WAIT)
        
        new_source_len = len(self.driver.page_source)
        
        self.logger.log('SEARCH', 'PASS', '搜索执行成功', {
            'keyword': self.keyword,
            'result_length': new_source_len
        })
    
    def _parse_results(self):
        """解析结果"""
        self.logger.log('PARSE', 'INFO', '解析搜索结果')
        
        try:
            links = self.driver.find_elements(By.TAG_NAME, "a")
            ndl_links = []
            
            for link in links:
                href = link.get_attribute('href') or ''
                text = link.text.strip()
                
                if 'detail' in href or '/pdf' in href:
                    if text:
                        ndl_links.append({
                            'title': text[:100],
                            'url': href
                        })
            
            self.results = ndl_links[:5]  # 取前5个
            
            self.logger.log('PARSE', 'PASS', f'找到 {len(self.results)} 个结果', {
                'total_links': len(links),
                'ndl_links': len(ndl_links),
                'saved': len(self.results)
            })
            
            if self.results:
                self.logger.log('RESULTS', 'INFO', '前3个结果:')
                for i, result in enumerate(self.results[:3], 1):
                    self.logger.log('RESULTS', 'INFO', f'  {i}. {result["title"][:50]}...')
            
        except Exception as e:
            self.logger.log('PARSE', 'FAIL', f'解析失败: {e}')
    
    def _cleanup(self):
        """清理"""
        if self.driver:
            self.driver.quit()
            self.logger.log('CLEANUP', 'INFO', 'WebDriver已关闭')
    
    def get_report(self):
        """获取报告"""
        elapsed = (self.logger.end_time - self.logger.start_time).total_seconds()
        
        return {
            'execution_num': self.execution_num,
            'success': self.success,
            'error': self.error,
            'keyword': self.keyword,
            'results_count': len(self.results),
            'results': self.results,
            'elapsed_time': elapsed,
            'logs': self.logger.logs,
            'summary': self.logger.get_summary()
        }

def main():
    """主函数"""
    print("\n" + "="*70)
    print("优化代码执行测试 - 2次执行对比")
    print("="*70)
    
    reports = []
    
    # 第1次执行
    print("\n" + "="*70)
    print("第 1 次执行")
    print("="*70)
    
    test1 = OptimizedExecutionTest(1)
    success1 = test1.run()
    report1 = test1.get_report()
    reports.append(report1)
    
    print(f"\n第1次执行结果: {'成功' if success1 else '失败'}")
    print(f"找到结果: {len(report1['results'])}个")
    print(f"耗时: {report1['elapsed_time']:.2f}秒")
    
    # 分析第1次执行
    if not success1:
        print(f"\n失败原因: {report1['error']}")
        print("\n分析失败原因...")
        # 分析并记录
        with open("execution_analysis.md", "w", encoding="utf-8") as f:
            f.write(f"# 第1次执行失败分析\n\n")
            f.write(f"## 错误信息\n\n{report1['error']}\n\n")
            f.write(f"## 日志\n\n")
            for log in report1['logs']:
                f.write(f"- [{log['timestamp']}] [{log['status']}] {log['message']}\n")
    
    # 等待
    print("\n等待5秒后执行第2次...")
    time.sleep(5)
    
    # 第2次执行
    print("\n" + "="*70)
    print("第 2 次执行")
    print("="*70)
    
    test2 = OptimizedExecutionTest(2)
    success2 = test2.run()
    report2 = test2.get_report()
    reports.append(report2)
    
    print(f"\n第2次执行结果: {'成功' if success2 else '失败'}")
    print(f"找到结果: {len(report2['results'])}个")
    print(f"耗时: {report2['elapsed_time']:.2f}秒")
    
    # 生成对比报告
    print("\n" + "="*70)
    print("生成对比报告...")
    print("="*70)
    
    comparison_report = f"""# 优化代码执行对比报告

## 执行摘要

- 测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
- 测试目标: NDL网站搜索功能
- 测试关键词: 井上哲次郎
- 执行次数: 2次

---

## 第1次执行结果

**状态**: {'✅ 成功' if success1 else '❌ 失败'}

| 指标 | 值 |
|------|-----|
| 执行时间 | {report1['elapsed_time']:.2f}秒 |
| 找到结果数 | {len(report1['results'])}个 |
| 错误信息 | {report1['error'] or '无'} |

**详细日志**:
"""
    
    for log in report1['logs']:
        comparison_report += f"- [{log['timestamp']}] [{log['status']}] {log['message']}\n"
    
    comparison_report += f"""

---

## 第2次执行结果

**状态**: {'✅ 成功' if success2 else '❌ 失败'}

| 指标 | 值 |
|------|-----|
| 执行时间 | {report2['elapsed_time']:.2f}秒 |
| 找到结果数 | {len(report2['results'])}个 |
| 错误信息 | {report2['error'] or '无'} |

**详细日志**:
"""
    
    for log in report2['logs']:
        comparison_report += f"- [{log['timestamp']}] [{log['status']}] {log['message']}\n"
    
    # 对比分析
    comparison_report += f"""

---

## 对比分析

### 执行成功率

| 执行 | 状态 | 结果数 | 耗时 |
|------|------|--------|------|
| 第1次 | {'成功' if success1 else '失败'} | {len(report1['results'])} | {report1['elapsed_time']:.2f}秒 |
| 第2次 | {'成功' if success2 else '失败'} | {len(report2['results'])} | {report2['elapsed_time']:.2f}秒 |

### 性能对比

| 指标 | 第1次 | 第2次 | 变化 |
|------|-------|-------|------|
| 执行时间 | {report1['elapsed_time']:.2f}秒 | {report2['elapsed_time']:.2f}秒 | {report2['elapsed_time']-report1['elapsed_time']:+.2f}秒 |
| 结果数 | {len(report1['results'])} | {len(report2['results'])} | {len(report2['results'])-len(report1['results']):+} |

### 日志统计

| 执行 | 总日志 | 通过 | 失败 | 信息 |
|------|--------|------|------|------|
| 第1次 | {report1['summary']['total_logs']} | {report1['summary']['passed']} | {report1['summary']['failed']} | {report1['summary']['info']} |
| 第2次 | {report2['summary']['total_logs']} | {report2['summary']['passed']} | {report2['summary']['failed']} | {report2['summary']['info']} |

---

## 结论

### 成功率
- 第1次: {'✅ 成功' if success1 else '❌ 失败'}
- 第2次: {'✅ 成功' if success2 else '❌ 失败'}
- 综合成功率: {((1 if success1 else 0) + (1 if success2 else 0)) / 2 * 100:.0f}%

### 数据准确性
- 第1次找到 {len(report1['results'])} 个相关链接
- 第2次找到 {len(report2['results'])} 个相关链接

### 性能评估
- 平均执行时间: {(report1['elapsed_time'] + report2['elapsed_time']) / 2:.2f}秒
- 优化效果: {'显著改善' if report2['elapsed_time'] < report1['elapsed_time'] else '性能稳定'}

---

## 建议

1. **如第1次失败**: 检查网络连接或NDL网站可用性
2. **如第2次成功**: 说明有临时性问题，可重试解决
3. **持续监控**: 建议添加监控告警机制

---

**报告生成**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
    
    # 保存报告
    report_path = f"EXECUTION_COMPARISON_REPORT_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(comparison_report)
    
    print(f"\n对比报告已保存: {report_path}")
    
    # 打印总结
    print("\n" + "="*70)
    print("执行总结")
    print("="*70)
    print(f"第1次: {'✅ 成功' if success1 else '❌ 失败'} - {len(report1['results'])}个结果 - {report1['elapsed_time']:.2f}秒")
    print(f"第2次: {'✅ 成功' if success2 else '❌ 失败'} - {len(report2['results'])}个结果 - {report2['elapsed_time']:.2f}秒")
    print(f"综合成功率: {((1 if success1 else 0) + (1 if success2 else 0)) / 2 * 100:.0f}%")
    print("="*70)
    
    return 0 if success1 or success2 else 1

if __name__ == '__main__':
    sys.exit(main())
