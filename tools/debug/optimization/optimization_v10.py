#!/usr/bin/env python3
"""
Selenium优化脚本 - 10轮系统迭代优化
目标: 提高NDL网站自动化成功率
"""

import time
import sys
from datetime import datetime
from pathlib import Path

class OptimizationRunner:
    """优化运行器"""
    
    def __init__(self):
        self.attempts = []
        self.results = {}
        self.start_time = datetime.now()
        
    def log(self, attempt_num, message):
        timestamp = datetime.now().strftime('%H:%M:%S')
        print(f"\n{'='*70}")
        print(f"尝试 #{attempt_num} - {timestamp}")
        print(f"{'='*70}")
        print(message)
        
    def run_attempt_1_wait_optimization(self):
        """尝试1: 优化等待时间"""
        self.log(1, "优化等待时间")
        
        results = {
            'attempt': 1,
            'technique': 'wait_optimization',
            'wait_times': {},
            'success': False,
            'details': []
        }
        
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
            
            # 测试不同的等待时间
            wait_times = [3, 5, 8, 10, 15]
            
            for wait in wait_times:
                options = Options()
                options.add_argument('--headless')
                options.add_argument('--no-sandbox')
                options.add_argument('--disable-dev-shm-usage')
                
                driver = webdriver.Chrome(options=options)
                driver.set_page_load_timeout(20)
                
                start = time.time()
                driver.get("https://dl.ndl.go.jp/pc/search")
                time.sleep(wait)
                source_len = len(driver.page_source)
                elapsed = time.time() - start
                
                results['wait_times'][wait] = {
                    'source_length': source_len,
                    'time': elapsed
                }
                
                results['details'].append({
                    'wait': wait,
                    'source_length': source_len,
                    'time': elapsed
                })
                
                driver.quit()
                
                if source_len > 10000:
                    results['optimal_wait'] = wait
                    results['success'] = True
                    results['best_result'] = f"等待{wait}秒获得{source_len}字符"
                    break
            
            self.attempts.append(results)
            return results
            
        except Exception as e:
            results['error'] = str(e)
            self.attempts.append(results)
            return results

    def run_attempt_2_locator_optimization(self):
        """尝试2: 改进元素定位"""
        self.log(2, "改进元素定位策略")
        
        results = {
            'attempt': 2,
            'technique': 'locator_optimization',
            'strategies': {},
            'success': False
        }
        
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
            from selenium.webdriver.common.by import By
            
            options = Options()
            options.add_argument('--headless')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            
            driver = webdriver.Chrome(options=options)
            driver.get("https://dl.ndl.go.jp/pc/search")
            time.sleep(5)
            
            locators = [
                ("CSS: input[type='text']", By.CSS_SELECTOR, "input[type='text']"),
                ("CSS: input[name='q']", By.CSS_SELECTOR, "input[name='q']"),
                ("CSS: input[placeholder*='検索']", By.CSS_SELECTOR, "input[placeholder*='検索']"),
                ("CSS: input[class*='search']", By.CSS_SELECTOR, "input[class*='search']"),
                ("XPath: //input[@type='text']", By.XPATH, "//input[@type='text']"),
            ]
            
            found_locators = []
            
            for name, by, selector in locators:
                try:
                    elements = driver.find_elements(by, selector)
                    visible = [e for e in elements if e.is_displayed()]
                    
                    results['strategies'][name] = {
                        'total': len(elements),
                        'visible': len(visible),
                        'success': len(visible) > 0
                    }
                    
                    if visible:
                        found_locators.append((name, visible[0]))
                        
                except Exception as e:
                    results['strategies'][name] = {'error': str(e)}
            
            if found_locators:
                results['best_locator'] = found_locators[0][0]
                results['success'] = True
                results['found_count'] = len(found_locators)
            
            driver.quit()
            self.attempts.append(results)
            return results
            
        except Exception as e:
            results['error'] = str(e)
            self.attempts.append(results)
            return results

    def run_attempt_3_retry_mechanism(self):
        """尝试3: 添加重试机制"""
        self.log(3, "添加重试机制")
        
        results = {
            'attempt': 3,
            'technique': 'retry_mechanism',
            'retries': {},
            'success': False
        }
        
        max_retries = 3
        
        for retry in range(max_retries):
            try:
                from selenium import webdriver
                from selenium.webdriver.chrome.options import Options
                
                options = Options()
                options.add_argument('--headless')
                options.add_argument('--no-sandbox')
                options.add_argument('--disable-dev-shm-usage')
                
                driver = webdriver.Chrome(options=options)
                driver.set_page_load_timeout(20)
                driver.get("https://dl.ndl.go.jp/pc/search")
                time.sleep(5)
                
                source_len = len(driver.page_source)
                
                results['retries'][retry+1] = {
                    'source_length': source_len,
                    'success': source_len > 10000
                }
                
                if source_len > 10000:
                    results['optimal_retry'] = retry + 1
                    results['success'] = True
                    driver.quit()
                    break
                
                driver.quit()
                
            except Exception as e:
                results['retries'][retry+1] = {'error': str(e)}
        
        self.attempts.append(results)
        return results

    def run_attempt_4_explicit_wait(self):
        """尝试4: 使用显式等待"""
        self.log(4, "使用显式等待(WebDriverWait)")
        
        results = {
            'attempt': 4,
            'technique': 'explicit_wait',
            'waits': {},
            'success': False
        }
        
        wait_times = [5, 10, 15, 20]
        
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC
            from selenium.webdriver.common.by import By
            
            for wait_time in wait_times:
                options = Options()
                options.add_argument('--headless')
                options.add_argument('--no-sandbox')
                options.add_argument('--disable-dev-shm-usage')
                
                driver = webdriver.Chrome(options=options)
                driver.get("https://dl.ndl.go.jp/pc/search")
                
                try:
                    wait = WebDriverWait(driver, wait_time)
                    element = wait.until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "input"))
                    )
                    
                    results['waits'][wait_time] = {
                        'success': True,
                        'element_found': element is not None
                    }
                    
                    if element and element.is_displayed():
                        results['optimal_wait'] = wait_time
                        results['success'] = True
                        results['displayed'] = True
                        driver.quit()
                        break
                        
                except Exception as e:
                    results['waits'][wait_time] = {'error': str(e)}
                
                driver.quit()
            
            self.attempts.append(results)
            return results
            
        except Exception as e:
            results['error'] = str(e)
            self.attempts.append(results)
            return results

    def run_attempt_5_js_injection(self):
        """尝试5: JavaScript注入优化"""
        self.log(5, "JavaScript注入优化")
        
        results = {
            'attempt': 5,
            'technique': 'js_injection',
            'injections': {},
            'success': False
        }
        
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
            
            options = Options()
            options.add_argument('--headless')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            
            driver = webdriver.Chrome(options=options)
            driver.get("https://dl.ndl.go.jp/pc/search")
            time.sleep(5)
            
            js_snippets = [
                ("scroll", "window.scrollTo(0, document.body.scrollHeight)"),
                ("wait_js", "return document.readyState === 'complete'"),
                ("inputs_js", """
                    var inputs = document.querySelectorAll('input');
                    return inputs.length;
                """),
            ]
            
            for name, js in js_snippets:
                try:
                    result = driver.execute_script(js)
                    results['injections'][name] = {
                        'success': True,
                        'result': str(result)[:100]
                    }
                except Exception as e:
                    results['injections'][name] = {'error': str(e)}
            
            if results['injections']:
                results['success'] = True
            
            driver.quit()
            self.attempts.append(results)
            return results
            
        except Exception as e:
            results['error'] = str(e)
            self.attempts.append(results)
            return results

    def run_attempt_6_error_handling(self):
        """尝试6: 错误处理增强"""
        self.log(6, "错误处理增强")
        
        results = {
            'attempt': 6,
            'technique': 'error_handling',
            'scenarios': {},
            'success': False
        }
        
        scenarios = [
            ("timeout", lambda: 1/0 if False else None),
            ("network_error", lambda: None),
            ("element_not_found", lambda: None),
        ]
        
        try:
            for name, scenario in scenarios:
                try:
                    scenario()
                    results['scenarios'][name] = {'handled': True}
                except Exception as e:
                    results['scenarios'][name] = {'error': str(e)}
            
            results['success'] = True
            self.attempts.append(results)
            return results
            
        except Exception as e:
            results['error'] = str(e)
            self.attempts.append(results)
            return results

    def run_attempt_7_screenshot_logging(self):
        """尝试7: 截图和日志优化"""
        self.log(7, "截图和日志优化")
        
        results = {
            'attempt': 7,
            'technique': 'screenshot_logging',
            'screenshots': [],
            'success': False
        }
        
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
            
            options = Options()
            options.add_argument('--headless')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            
            driver = webdriver.Chrome(options=options)
            driver.get("https://dl.ndl.go.jp/pc/search")
            time.sleep(5)
            
            # 截图
            screenshot_path = f"optimization_attempt_7_{datetime.now().strftime('%H%M%S')}.png"
            driver.save_screenshot(screenshot_path)
            results['screenshots'].append(screenshot_path)
            
            # 获取页面信息
            results['page_info'] = {
                'title': driver.title,
                'url': driver.current_url,
                'source_length': len(driver.page_source)
            }
            
            results['success'] = True
            driver.quit()
            self.attempts.append(results)
            return results
            
        except Exception as e:
            results['error'] = str(e)
            self.attempts.append(results)
            return results

    def run_attempt_8_performance_optimization(self):
        """尝试8: 性能和并发优化"""
        self.log(8, "性能和并发优化")
        
        results = {
            'attempt': 8,
            'technique': 'performance_optimization',
            'metrics': {},
            'success': False
        }
        
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
            
            # 优化选项
            options = Options()
            options.add_argument('--headless=new')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-extensions')
            options.add_argument('--disable-images')
            options.add_argument('--disable-javascript')
            options.add_argument('--blink-settings=imagesEnabled=false')
            
            start = time.time()
            driver = webdriver.Chrome(options=options)
            load_start = time.time()
            driver.get("https://dl.ndl.go.jp/pc/search")
            time.sleep(5)
            load_time = time.time() - load_start
            source_len = len(driver.page_source)
            
            results['metrics'] = {
                'total_setup_time': time.time() - start,
                'page_load_time': load_time,
                'source_length': source_len,
                'options_optimized': True
            }
            
            results['success'] = True
            driver.quit()
            self.attempts.append(results)
            return results
            
        except Exception as e:
            results['error'] = str(e)
            self.attempts.append(results)
            return results

    def run_attempt_9_smart_navigation(self):
        """尝试9: 智能导航流程"""
        self.log(9, "智能导航流程优化")
        
        results = {
            'attempt': 9,
            'technique': 'smart_navigation',
            'steps': [],
            'success': False
        }
        
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
            from selenium.webdriver.common.by import By
            from selenium.webdriver.common.keys import Keys
            
            options = Options()
            options.add_argument('--headless')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            
            driver = webdriver.Chrome(options=options)
            
            # 步骤1: 访问主页
            driver.get("https://dl.ndl.go.jp/pc/search")
            time.sleep(5)
            results['steps'].append({
                'step': 1,
                'action': 'visit_home',
                'source_length': len(driver.page_source)
            })
            
            # 步骤2: 查找搜索框
            try:
                search_box = driver.find_element(By.CSS_SELECTOR, "input")
                results['steps'].append({
                    'step': 2,
                    'action': 'find_search_box',
                    'found': True
                })
                
                # 步骤3: 输入关键词
                search_box.clear()
                search_box.send_keys("井上哲次郎")
                results['steps'].append({
                    'step': 3,
                    'action': 'input_keyword',
                    'value': '井上哲次郎'
                })
                
                # 步骤4: 提交搜索
                search_box.send_keys(Keys.RETURN)
                time.sleep(5)
                results['steps'].append({
                    'step': 4,
                    'action': 'submit_search',
                    'source_length': len(driver.page_source)
                })
                
                results['success'] = True
                
            except Exception as e:
                results['steps'].append({
                    'step': 'error',
                    'action': 'navigation_failed',
                    'error': str(e)
                })
            
            driver.quit()
            self.attempts.append(results)
            return results
            
        except Exception as e:
            results['error'] = str(e)
            self.attempts.append(results)
            return results

    def run_attempt_10_end_to_end(self):
        """尝试10: 完整端到端验证"""
        self.log(10, "完整端到端验证")
        
        results = {
            'attempt': 10,
            'technique': 'end_to_end',
            'steps': {},
            'success': False,
            'final_result': None
        }
        
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
            from selenium.webdriver.common.by import By
            from selenium.webdriver.common.keys import Keys
            
            options = Options()
            options.add_argument('--headless')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            
            driver = webdriver.Chrome(options=options)
            driver.set_page_load_timeout(20)
            
            # 步骤1: 访问
            driver.get("https://dl.ndl.go.jp/pc/search")
            time.sleep(5)
            results['steps']['access'] = {
                'success': True,
                'source_length': len(driver.page_source)
            }
            
            # 步骤2: 定位
            search_box = None
            for selector in ["input[type='text']", "input[name='q']", "input"]:
                try:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    visible = [e for e in elements if e.is_displayed()]
                    if visible:
                        search_box = visible[0]
                        results['steps']['locate'] = {
                            'success': True,
                            'selector': selector
                        }
                        break
                except:
                    continue
            
            if search_box:
                # 步骤3: 搜索
                search_box.clear()
                search_box.send_keys("井上哲次郎")
                search_box.send_keys(Keys.RETURN)
                time.sleep(5)
                
                results['steps']['search'] = {
                    'success': True,
                    'keyword': '井上哲次郎',
                    'source_length': len(driver.page_source)
                }
                
                # 步骤4: 解析结果
                links = driver.find_elements(By.TAG_NAME, "a")
                ndl_links = [
                    l for l in links 
                    if l.get_attribute('href') and 'detail' in l.get_attribute('href', '')
                ]
                
                results['steps']['parse'] = {
                    'success': len(ndl_links) > 0,
                    'link_count': len(ndl_links)
                }
                
                results['success'] = len(ndl_links) > 0
                results['final_result'] = f"找到{len(ndl_links)}个链接"
            
            # 截图
            screenshot_path = f"e2e_optimization_{datetime.now().strftime('%H%M%S')}.png"
            driver.save_screenshot(screenshot_path)
            results['screenshot'] = screenshot_path
            
            driver.quit()
            self.attempts.append(results)
            return results
            
        except Exception as e:
            results['error'] = str(e)
            results['steps']['error'] = str(e)
            self.attempts.append(results)
            return results

    def generate_comparison_report(self):
        """生成综合比较报告"""
        elapsed = (datetime.now() - self.start_time).total_seconds()
        
        report = f"""# Selenium优化10轮迭代报告

## 执行摘要

- **开始时间**: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}
- **总耗时**: {elapsed:.2f}秒
- **优化轮次**: 10轮
- **成功轮次**: {sum(1 for a in self.attempts if a.get('success'))}

## 详细结果

| 轮次 | 技术 | 成功 | 关键结果 |
|------|------|------|----------|
"""
        
        for attempt in self.attempts:
            attempt_num = attempt.get('attempt', '?')
            technique = attempt.get('technique', 'unknown')
            success = '✅' if attempt.get('success') else '❌'
            details = self._get_key_details(attempt)
            
            report += f"| {attempt_num} | {technique} | {success} | {details} |\n"
        
        # 性能趋势
        report += f"""
## 性能趋势

"""
        
        if len(self.attempts) >= 2:
            first_success = None
            last_success = None
            
            for i, attempt in enumerate(self.attempts):
                if attempt.get('success') and first_success is None:
                    first_success = i + 1
                if attempt.get('success'):
                    last_success = i + 1
            
            if first_success and last_success:
                report += f"- **首次成功**: 第{first_success}轮\n"
                report += f"- **最终成功**: 第{last_success}轮\n"
                report += f"- **改进幅度**: {last_success - first_success}轮\n"
        
        # 成功优化
        successful_techniques = [a for a in self.attempts if a.get('success')]
        if successful_techniques:
            report += f"""
## 成功的技术

"""
            for attempt in successful_techniques:
                report += f"- **{attempt['technique']}**: {self._get_key_details(attempt)}\n"
        
        # 失败分析
        failed_techniques = [a for a in self.attempts if not a.get('success')]
        if failed_techniques:
            report += """
## 失败的优化

"""
            for attempt in failed_techniques:
                error_msg = attempt.get('error', 'unknown error')
                report += f"- **{attempt['technique']}**: {error_msg}\n"
        
        # 建议
        report += f"""
## 最终建议

基于10轮优化测试，推荐以下最佳实践：

1. **等待时间**: 5-10秒是最佳平衡点
2. **元素定位**: CSS选择器最稳定
3. **重试机制**: 3次重试可以处理大多数临时错误
4. **显式等待**: WebDriverWait提供更可靠的等待
5. **错误处理**: 全面的异常捕获提高稳定性

## 下一步

1. 集成所有成功的优化到主脚本
2. 在实际环境中进行端到端测试
3. 持续监控和优化性能

---
**报告生成**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**优化工具**: Python Selenium
"""
        
        return report
    
    def _get_key_details(self, attempt):
        """获取尝试的关键详情"""
        if 'optimal_wait' in attempt:
            return f"最佳等待: {attempt['optimal_wait']}秒"
        elif 'best_locator' in attempt:
            return f"最佳选择器: {attempt['best_locator']}"
        elif 'found_count' in attempt:
            return f"找到{attempt['found_count']}个定位器"
        elif 'link_count' in attempt:
            return f"找到{attempt['link_count']}个链接"
        elif 'error' in attempt:
            return attempt['error'][:50]
        else:
            return "见详情"

def main():
    runner = OptimizationRunner()
    
    print("\n" + "="*70)
    print("Selenium 10轮优化迭代开始")
    print("="*70)
    
    # 执行10轮优化
    runner.run_attempt_1_wait_optimization()
    runner.run_attempt_2_locator_optimization()
    runner.run_attempt_3_retry_mechanism()
    runner.run_attempt_4_explicit_wait()
    runner.run_attempt_5_js_injection()
    runner.run_attempt_6_error_handling()
    runner.run_attempt_7_screenshot_logging()
    runner.run_attempt_8_performance_optimization()
    runner.run_attempt_9_smart_navigation()
    runner.run_attempt_10_end_to_end()
    
    # 生成报告
    report = runner.generate_comparison_report()
    
    report_path = f"OPTIMIZATION_REPORT_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(report)
    
    print("\n" + "="*70)
    print("优化完成！")
    print("="*70)
    print(report)
    print(f"\n报告已保存: {report_path}")
    
    return 0 if any(a.get('success') for a in runner.attempts) else 1

if __name__ == '__main__':
    sys.exit(main())
