#!/usr/bin/env python3
"""快速验证优化代码"""
import sys
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from tools.ndl_downloader.selenium_downloader import NDLSeleniumConfig

print("=== 快速验证测试 ===")
print(f"等待时间: {NDLSeleniumConfig.OPTIMAL_WAIT}秒")
print(f"重试次数: {NDLSeleniumConfig.RETRY_ATTEMPTS}次")
print(f"定位器数量: {len(NDLSeleniumConfig.SEARCH_BOX_LOCATORS)}")

# 初始化
options = Options()
for opt in NDLSeleniumConfig.CHROME_OPTIONS:
    options.add_argument(opt)

driver = webdriver.Chrome(options=options)
print("\n✅ WebDriver初始化成功")

# 访问
print("\n访问NDL网站...")
driver.get(NDLSeleniumConfig.SEARCH_URL)
time.sleep(NDLSeleniumConfig.OPTIMAL_WAIT)
print(f"✅ 页面加载完成 (等待{NDLSeleniumConfig.OPTIMAL_WAIT}秒)")

# 定位
print("\n定位搜索框...")
for name, locator in NDLSeleniumConfig.SEARCH_BOX_LOCATORS:
    try:
        elements = driver.find_elements(By.CSS_SELECTOR, locator)
        visible = [e for e in elements if e.is_displayed()]
        if visible:
            print(f"✅ 找到: {name}")
            search_box = visible[0]
            break
    except:
        continue

# 搜索
if 'search_box' in dir():
    print("\n执行搜索...")
    search_box.send_keys("井上哲次郎")
    search_box.send_keys(Keys.RETURN)
    time.sleep(NDLSeleniumConfig.OPTIMAL_WAIT)
    print("✅ 搜索完成")
    
    # 解析
    links = driver.find_elements(By.TAG_NAME, "a")
    ndl_links = [l for l in links if 'detail' in l.get_attribute('href', '')]
    print(f"\n找到 {len(ndl_links)} 个相关链接")
else:
    print("❌ 未找到搜索框")

driver.quit()
print("\n=== 验证完成 ===")
