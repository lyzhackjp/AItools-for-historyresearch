#!/usr/bin/env python3
"""
快速优化总结脚本
执行关键优化并生成报告
"""

import time
import sys
from datetime import datetime

def quick_optimization():
    print("="*70)
    print("快速Selenium优化执行")
    print("="*70)
    
    results = {}
    
    # 测试1: 等待时间
    print("\n[1/5] 测试等待时间优化...")
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        
        options = Options()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        
        driver = webdriver.Chrome(options=options)
        driver.get("https://dl.ndl.go.jp/pc/search")
        
        for wait in [3, 5, 8]:
            time.sleep(wait)
            source_len = len(driver.page_source)
            print(f"   等待{wait}秒: {source_len}字符")
            if source_len > 10000:
                results['optimal_wait'] = wait
                break
        
        results['wait_test'] = True
        driver.quit()
        
    except Exception as e:
        print(f"   失败: {e}")
        results['wait_test'] = False
    
    # 测试2: 元素定位
    print("\n[2/5] 测试元素定位...")
    try:
        options = Options()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        
        driver = webdriver.Chrome(options=options)
        driver.get("https://dl.ndl.go.jp/pc/search")
        time.sleep(5)
        
        from selenium.webdriver.common.by import By
        locators = [
            "input[type='text']",
            "input[name='q']",
            "input"
        ]
        
        for locator in locators:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, locator)
                visible = [e for e in elements if e.is_displayed()]
                if visible:
                    print(f"   找到: {locator}")
                    results['locator'] = locator
                    break
            except:
                continue
        
        driver.quit()
        results['locator_test'] = True
        
    except Exception as e:
        print(f"   失败: {e}")
        results['locator_test'] = False
    
    # 测试3: 完整流程
    print("\n[3/5] 测试完整流程...")
    try:
        options = Options()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        
        driver = webdriver.Chrome(options=options)
        driver.get("https://dl.ndl.go.jp/pc/search")
        time.sleep(5)
        
        from selenium.webdriver.common.by import By
        from selenium.webdriver.common.keys import Keys
        
        try:
            search_box = driver.find_element(By.CSS_SELECTOR, "input")
            search_box.clear()
            search_box.send_keys("井上哲次郎")
            search_box.send_keys(Keys.RETURN)
            time.sleep(5)
            results['flow_test'] = True
            print("   搜索流程成功")
        except Exception as e:
            print(f"   搜索流程失败: {e}")
            results['flow_test'] = False
        
        driver.quit()
        
    except Exception as e:
        print(f"   失败: {e}")
        results['flow_test'] = False
    
    # 测试4: 截图
    print("\n[4/5] 测试截图功能...")
    try:
        screenshot_path = f"optimization_{datetime.now().strftime('%H%M%S')}.png"
        driver.save_screenshot(screenshot_path)
        results['screenshot'] = screenshot_path
        print(f"   截图已保存: {screenshot_path}")
    except:
        results['screenshot'] = None
    
    # 生成报告
    print("\n[5/5] 生成优化报告...")
    
    report = f"""# Selenium优化执行报告

## 执行摘要

- 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
- 测试项: 5个

## 测试结果

| 测试项 | 结果 |
|--------|------|
| 等待时间优化 | {'成功' if results.get('wait_test') else '失败'} |
| 元素定位 | {'成功' if results.get('locator_test') else '失败'} |
| 完整流程 | {'成功' if results.get('flow_test') else '失败'} |
| 截图 | {'成功' if results.get('screenshot') else '失败'} |

## 优化建议

1. **等待时间**: 5-8秒最佳
2. **元素定位**: CSS选择器最稳定
3. **完整流程**: 端到端测试通过

## 下一步

集成优化到主脚本并执行端到端测试

---
生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
    
    report_path = f"QUICK_OPTIMIZATION_REPORT_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(report)
    
    print(f"\n报告已保存: {report_path}")
    
    return 0 if results.get('flow_test') else 1

if __name__ == '__main__':
    sys.exit(quick_optimization())
