"""
NDL Selenium调试脚本 - 详细版本
执行非headless模式，优化搜索框定位，实现智能等待

调试时间: 2024-03-27
调试目标: 井上哲次郎 倫理新説
"""

import time
import sys
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import TimeoutException, NoSuchElementException

class NDLDebugLogger:
    """调试日志记录器"""
    
    def __init__(self):
        self.log_entries = []
        self.start_time = datetime.now()
    
    def log(self, level, message, details=None):
        timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
        entry = {
            'time': timestamp,
            'level': level,
            'message': message,
            'details': details
        }
        self.log_entries.append(entry)
        
        prefix = {
            'INFO': '[ℹ️ INFO]',
            'SUCCESS': '[✅ SUCCESS]',
            'WARNING': '[⚠️ WARNING]',
            'ERROR': '[❌ ERROR]',
            'DEBUG': '[🔍 DEBUG]'
        }
        
        print(f"{prefix.get(level, '[❓]')} {message}")
        if details:
            print(f"       详情: {details}")
    
    def get_report(self):
        """生成调试报告"""
        elapsed = (datetime.now() - self.start_time).total_seconds()
        
        report = f"""# NDL Selenium详细调试报告

## 基本信息
- 调试时间: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}
- 总耗时: {elapsed:.2f} 秒
- 日志条目: {len(self.log_entries)} 条

## 执行步骤
"""
        
        for i, entry in enumerate(self.log_entries, 1):
            report += f"\n### {i}. {entry['time']} - {entry['level']}\n"
            report += f"- 操作: {entry['message']}\n"
            if entry['details']:
                report += f"- 详情: {entry['details']}\n"
        
        report += f"""
## 统计数据
- INFO级别: {sum(1 for e in self.log_entries if e['level'] == 'INFO')}
- SUCCESS级别: {sum(1 for e in self.log_entries if e['level'] == 'SUCCESS')}
- WARNING级别: {sum(1 for e in self.log_entries if e['level'] == 'WARNING')}
- ERROR级别: {sum(1 for e in self.log_entries if e['level'] == 'ERROR')}
- DEBUG级别: {sum(1 for e in self.log_entries if e['level'] == 'DEBUG')}
"""
        
        return report

def main():
    logger = NDLDebugLogger()
    driver = None
    
    try:
        logger.log('INFO', '开始NDL Selenium详细调试')
        logger.log('INFO', f'调试目标: 井上哲次郎 倫理新説')
        
        # ===== 步骤1: 初始化WebDriver =====
        logger.log('INFO', '步骤1: 初始化Chrome WebDriver')
        
        chrome_options = Options()
        
        # 尝试非headless模式（显示浏览器窗口）
        logger.log('DEBUG', '配置Chrome选项 - 使用非headless模式')
        chrome_options.add_argument('--start-maximized')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        
        # 禁用自动化检测
        chrome_options.add_experimental_option('excludeSwitches', ['enable-automation'])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        logger.log('SUCCESS', 'Chrome选项配置完成')
        
        try:
            logger.log('INFO', '初始化WebDriver...')
            driver = webdriver.Chrome(options=chrome_options)
            driver.set_page_load_timeout(30)
            logger.log('SUCCESS', 'WebDriver初始化成功')
        except Exception as e:
            logger.log('ERROR', 'WebDriver初始化失败', str(e))
            return 1
        
        # ===== 步骤2: 访问搜索页面 =====
        logger.log('INFO', '步骤2: 访问NDL搜索页面')
        
        search_url = "https://dl.ndl.go.jp/pc/search"
        
        try:
            logger.log('DEBUG', f'访问URL: {search_url}')
            driver.get(search_url)
            
            # 等待页面基本加载
            time.sleep(3)
            
            page_title = driver.title
            page_url = driver.current_url
            page_source_len = len(driver.page_source)
            
            logger.log('SUCCESS', f'页面加载成功')
            logger.log('INFO', f'页面标题: {page_title}')
            logger.log('INFO', f'当前URL: {page_url}')
            logger.log('INFO', f'源码长度: {page_source_len} 字符')
            
            if page_source_len > 10000:
                logger.log('SUCCESS', '页面内容丰富，JavaScript已执行')
            else:
                logger.log('WARNING', '页面内容较少，可能未完全加载')
                
        except Exception as e:
            logger.log('ERROR', '页面访问失败', str(e))
            return 1
        
        # ===== 步骤3: 分析页面结构 =====
        logger.log('INFO', '步骤3: 分析页面结构')
        
        try:
            # 查找所有input元素
            all_inputs = driver.find_elements(By.TAG_NAME, 'input')
            logger.log('INFO', f'找到 {len(all_inputs)} 个input元素')
            
            for i, inp in enumerate(all_inputs[:10]):
                inp_type = inp.get_attribute('type')
                inp_name = inp.get_attribute('name')
                inp_id = inp.get_attribute('id')
                inp_class = inp.get_attribute('class')
                inp_placeholder = inp.get_attribute('placeholder')
                
                logger.log('DEBUG', f'Input #{i+1}', 
                    f'type={inp_type}, name={inp_name}, id={inp_id}')
                logger.log('DEBUG', f'         class={inp_class}')
                logger.log('DEBUG', f'         placeholder={inp_placeholder}')
            
            # 查找所有button元素
            all_buttons = driver.find_elements(By.TAG_NAME, 'button')
            logger.log('INFO', f'找到 {len(all_buttons)} 个button元素')
            
            for i, btn in enumerate(all_buttons[:10]):
                btn_text = btn.text.strip()
                btn_class = btn.get_attribute('class')
                btn_type = btn.get_attribute('type')
                
                logger.log('DEBUG', f'Button #{i+1}', 
                    f'text="{btn_text[:30]}", type={btn_type}')
                logger.log('DEBUG', f'           class={btn_class}')
            
            # 尝试多种搜索框定位方法
            search_selectors = [
                ("input[type='text']", "CSS: input[type='text']"),
                ("input[type='search']", "CSS: input[type='search']"),
                ("input[name='q']", "CSS: input[name='q']"),
                ("input[placeholder*='検索']", "CSS: 搜索占位符"),
                ("input[placeholder*='search']", "CSS: search占位符"),
                ("input[id*='search']", "CSS: id包含search"),
                ("input[class*='search']", "CSS: class包含search"),
            ]
            
            search_input = None
            
            for selector, desc in search_selectors:
                try:
                    logger.log('DEBUG', f'尝试定位器: {desc}')
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    
                    if elements:
                        search_input = elements[0]
                        logger.log('SUCCESS', f'找到搜索框: {desc}')
                        logger.log('INFO', f'元素标签: {search_input.tag_name}')
                        logger.log('INFO', f'元素类型: {search_input.get_attribute("type")}')
                        logger.log('INFO', f'元素占位符: {search_input.get_attribute("placeholder")}')
                        break
                    else:
                        logger.log('DEBUG', f'未找到: {desc}')
                        
                except Exception as e:
                    logger.log('DEBUG', f'选择器失败: {desc}', str(e))
                    continue
            
            if not search_input:
                logger.log('WARNING', '未找到标准搜索框，尝试备选方法')
                
                # 尝试查找第一个可见的input
                for inp in all_inputs:
                    try:
                        inp_type = inp.get_attribute('type')
                        if inp_type in ['text', 'search', None]:
                            is_displayed = inp.is_displayed()
                            is_enabled = inp.is_enabled()
                            
                            if is_displayed and is_enabled:
                                search_input = inp
                                logger.log('SUCCESS', f'使用备选搜索框')
                                logger.log('INFO', f'元素类型: {inp_type}')
                                break
                    except:
                        continue
            
        except Exception as e:
            logger.log('ERROR', '页面结构分析失败', str(e))
        
        # ===== 步骤4: 执行搜索操作 =====
        if search_input:
            logger.log('INFO', '步骤4: 执行搜索操作')
            
            try:
                # 清空搜索框
                logger.log('DEBUG', '清空搜索框')
                search_input.clear()
                
                # 输入搜索关键词
                keyword = "井上哲次郎"
                logger.log('INFO', f'输入关键词: {keyword}')
                search_input.send_keys(keyword)
                
                time.sleep(0.5)
                
                # 尝试多种提交方法
                submit_methods = [
                    ("Keys.RETURN", "按回车键"),
                    ("Keys.ENTER", "按Enter键"),
                    ("button[type='submit']", "点击提交按钮"),
                    ("button.search-btn", "点击搜索按钮"),
                    ("input[type='submit']", "点击提交input"),
                ]
                
                search_success = False
                
                for method, desc in submit_methods:
                    if search_success:
                        break
                    
                    try:
                        logger.log('DEBUG', f'尝试提交方法: {desc}')
                        
                        if 'RETURN' in method or 'ENTER' in method:
                            search_input.send_keys(Keys.RETURN)
                        elif "button[type='submit']" in method:
                            btns = driver.find_elements(By.CSS_SELECTOR, "button[type='submit']")
                            if btns:
                                btns[0].click()
                        elif "button.search" in method:
                            btns = driver.find_elements(By.CSS_SELECTOR, "button.search")
                            if btns:
                                btns[0].click()
                        elif "input[type='submit']" in method:
                            inputs = driver.find_elements(By.CSS_SELECTOR, "input[type='submit']")
                            if inputs:
                                inputs[0].click()
                        
                        logger.log('DEBUG', f'等待搜索结果加载...')
                        time.sleep(3)
                        
                        # 检查是否成功加载了搜索结果
                        current_url = driver.current_url
                        page_source_len = len(driver.page_source)
                        
                        if 'search' in current_url.lower() or page_source_len > 15000:
                            logger.log('SUCCESS', f'搜索成功: {desc}')
                            logger.log('INFO', f'当前URL: {current_url}')
                            logger.log('INFO', f'页面长度: {page_source_len}')
                            search_success = True
                            
                    except Exception as e:
                        logger.log('DEBUG', f'方法失败: {desc}', str(e))
                        continue
                
                if not search_success:
                    logger.log('WARNING', '所有提交方法均未成功')
                    
            except Exception as e:
                logger.log('ERROR', '搜索操作失败', str(e))
        else:
            logger.log('ERROR', '无法执行搜索：未找到搜索框')
        
        # ===== 步骤5: 分析搜索结果 =====
        if search_success or len(driver.page_source) > 15000:
            logger.log('INFO', '步骤5: 分析搜索结果')
            
            try:
                time.sleep(2)
                
                # 查找搜索结果列表
                result_selectors = [
                    ("li.item", "li.item"),
                    ("li.search-result", "li.search-result"),
                    ("div.result-item", "div.result-item"),
                    ("ul li", "ul li"),
                    (".items li", ".items li"),
                ]
                
                result_items = []
                
                for selector, desc in result_selectors:
                    try:
                        elements = driver.find_elements(By.CSS_SELECTOR, selector)
                        if elements:
                            logger.log('INFO', f'找到结果选择器: {desc}, 数量: {len(elements)}')
                            result_items = elements[:10]
                            break
                    except:
                        continue
                
                if result_items:
                    logger.log('SUCCESS', f'找到 {len(result_items)} 个搜索结果')
                    
                    for i, item in enumerate(result_items, 1):
                        try:
                            # 提取标题
                            title_elem = item.find_element(By.CSS_SELECTOR, "a, h3, h4, .title")
                            title = title_elem.text.strip() if title_elem else "N/A"
                            
                            # 提取链接
                            link_elem = item.find_element(By.CSS_SELECTOR, "a[href]")
                            link = link_elem.get_attribute('href') if link_elem else "N/A"
                            
                            # 提取作者
                            try:
                                author_elem = item.find_element(By.CSS_SELECTOR, ".author, .creator, span:nth-child(2)")
                                author = author_elem.text.strip()
                            except:
                                author = "N/A"
                            
                            logger.log('INFO', f'结果 #{i}', 
                                f'标题: {title[:50]}..., 作者: {author}')
                            logger.log('DEBUG', f'         链接: {link[:80]}')
                            
                        except Exception as e:
                            logger.log('DEBUG', f'解析结果 #{i} 失败', str(e))
                            continue
                else:
                    logger.log('WARNING', '未找到标准搜索结果元素')
                    
                    # 尝试查找所有链接
                    all_links = driver.find_elements(By.TAG_NAME, 'a')
                    logger.log('INFO', f'页面共有 {len(all_links)} 个链接')
                    
                    # 筛选可能的详情链接
                    detail_links = [
                        link for link in all_links 
                        if 'detail' in link.get_attribute('href', '').lower() or
                           'id=' in link.get_attribute('href', '')
                    ]
                    
                    if detail_links:
                        logger.log('INFO', f'找到 {len(detail_links)} 个可能的详情链接')
                        for link in detail_links[:5]:
                            href = link.get_attribute('href')
                            text = link.text.strip()[:30]
                            logger.log('DEBUG', f'  - {href[:80]}')
                            logger.log('DEBUG', f'    {text}')
                    else:
                        logger.log('WARNING', '未找到任何详情链接')
                        
            except Exception as e:
                logger.log('ERROR', '搜索结果分析失败', str(e))
        
        # ===== 步骤6: 截图保存 =====
        logger.log('INFO', '步骤6: 保存调试截图')
        
        try:
            screenshot_path = f"debug_screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            driver.save_screenshot(screenshot_path)
            logger.log('SUCCESS', f'截图已保存: {screenshot_path}')
        except Exception as e:
            logger.log('WARNING', '截图保存失败', str(e))
        
        # ===== 完成 =====
        logger.log('INFO', '调试完成')
        
        # 生成并保存报告
        report = logger.get_report()
        report_path = f"DEBUG_REPORT_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(report)
        
        logger.log('SUCCESS', f'调试报告已保存: {report_path}')
        
        return 0
        
    except Exception as e:
        logger.log('ERROR', '调试过程异常', str(e))
        import traceback
        traceback.print_exc()
        return 1
        
    finally:
        if driver:
            logger.log('INFO', '关闭浏览器...')
            driver.quit()
            logger.log('SUCCESS', '浏览器已关闭')

if __name__ == '__main__':
    sys.exit(main())
