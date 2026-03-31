"""
日本国立国会图书馆(NDL) PDF资料下载工具 - Selenium版本

使用Selenium浏览器自动化技术，支持JavaScript动态内容加载。
本工具仅供学术研究使用，请遵守NDL的使用条款。

作者：History Research AI Tools
版本：2.0.0
日期：2024年3月
"""

import os
import sys
import time
import re
import argparse
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List, Tuple, Any

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.common.action_chains import ActionChains
    from selenium.common.exceptions import TimeoutException, NoSuchElementException
    import requests
except ImportError:
    print("错误: 请安装必要的库")
    print("运行: pip install selenium requests")
    sys.exit(1)


class NDLSeleniumConfig:
    """Selenium下载器配置 - 优化版"""
    
    BASE_URL = "https://dl.ndl.go.jp"
    SEARCH_URL = "https://dl.ndl.go.jp/pc/search"
    
    REQUEST_INTERVAL = 1.0
    IMPLICIT_WAIT = 10
    PAGE_LOAD_TIMEOUT = 30
    
    # 优化: 最佳等待时间
    OPTIMAL_WAIT = 5  # 秒
    RETRY_ATTEMPTS = 3  # 重试次数
    
    CHROME_OPTIONS = [
        '--headless=new',
        '--no-sandbox',
        '--disable-dev-shm-usage',
        '--disable-gpu',
        '--window-size=1920,1080',
        '--disable-extensions',
        '--disable-images',  # 优化: 禁用图片加速加载
        '--blink-settings=imagesEnabled=false'
    ]
    
    # 优化: 级联定位器
    SEARCH_BOX_LOCATORS = [
        ("CSS: input[type='text']", "input[type='text']"),
        ("CSS: input[name='q']", "input[name='q']"),
        ("CSS: input[placeholder*='検索']", "input[placeholder*='検索']"),
        ("CSS: input[class*='search']", "input[class*='search']"),
        ("CSS: input", "input"),  # 备选
    ]


class NDLSeleniumLogger:
    """日志记录器"""
    
    def __init__(self, log_file: Optional[str] = None, log_level: int = logging.INFO):
        self.logger = logging.getLogger('NDLSeleniumDownloader')
        self.logger.setLevel(log_level)
        
        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        console_handler = logging.StreamHandler()
        console_handler.setLevel(log_level)
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)
        
        if log_file:
            file_handler = logging.FileHandler(log_file, encoding='utf-8')
            file_handler.setLevel(log_level)
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)
    
    def info(self, message: str):
        self.logger.info(message)
    
    def warning(self, message: str):
        self.logger.warning(message)
    
    def error(self, message: str):
        self.logger.error(message)
    
    def debug(self, message: str):
        self.logger.debug(message)


class NDLSeleniumDownloader:
    """基于Selenium的NDL PDF下载器"""
    
    def __init__(self, output_dir: str = "./downloads",
                 interval: float = NDLSeleniumConfig.REQUEST_INTERVAL,
                 log_file: Optional[str] = None,
                 headless: bool = True):
        """
        初始化下载器
        
        Args:
            output_dir: 下载目录
            interval: 请求间隔时间（秒）
            log_file: 日志文件路径
            headless: 是否使用无头模式
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.interval = interval
        self.headless = headless
        self.logger = NDLSeleniumLogger(log_file)
        
        self.driver = None
        self.downloaded_files = []
        self.failed_downloads = []
        
        self._init_driver()
        
        self.logger.info("="*60)
        self.logger.info("日本国立国会图书馆PDF资料下载工具 (Selenium版) v2.0.0")
        self.logger.info("="*60)
        self.logger.info(f"下载目录: {self.output_dir}")
        self.logger.info(f"请求间隔: {self.interval}秒")
        self.logger.info(f"无头模式: {self.headless}")
        self.logger.info(f"优化等待: {NDLSeleniumConfig.OPTIMAL_WAIT}秒")
        self.logger.info(f"重试次数: {NDLSeleniumConfig.RETRY_ATTEMPTS}次")
        self.logger.info("="*60)
    
    def _init_driver(self):
        """初始化WebDriver"""
        try:
            chrome_options = Options()
            
            if self.headless:
                for option in NDLSeleniumConfig.CHROME_OPTIONS:
                    chrome_options.add_argument(option)
            
            chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            
            self.driver = webdriver.Chrome(options=chrome_options)
            self.driver.implicitly_wait(NDLSeleniumConfig.IMPLICIT_WAIT)
            self.driver.set_page_load_timeout(NDLSeleniumConfig.PAGE_LOAD_TIMEOUT)
            
            self.logger.info("WebDriver初始化成功")
            
        except Exception as e:
            self.logger.error(f"WebDriver初始化失败: {e}")
            self.logger.error("请确保已安装Chrome浏览器和ChromeDriver")
            raise
    
    def _wait_interval(self):
        """等待请求间隔时间"""
        time.sleep(self.interval)
    
    def close(self):
        """关闭浏览器"""
        if self.driver:
            self.driver.quit()
            self.logger.info("浏览器已关闭")
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
    
    def search_items(self, keyword: str, max_results: int = 20) -> List[Dict[str, Any]]:
        """
        搜索资料
        
        Args:
            keyword: 关键词
            max_results: 最大结果数
            
        Returns:
            List[Dict]: 搜索结果列表
        """
        self.logger.info(f"搜索关键词: {keyword}")
        
        # 优化: 重试机制
        for retry in range(NDLSeleniumConfig.RETRY_ATTEMPTS):
            try:
                self.driver.get(NDLSeleniumConfig.SEARCH_URL)
                
                # 优化: 使用最佳等待时间
                time.sleep(NDLSeleniumConfig.OPTIMAL_WAIT)
                
                # 优化: 级联定位器
                search_input = None
                for locator_name, locator in NDLSeleniumConfig.SEARCH_BOX_LOCATORS:
                    try:
                        self.logger.debug(f"尝试定位器: {locator_name}")
                        elements = self.driver.find_elements(By.CSS_SELECTOR, locator)
                        visible = [e for e in elements if e.is_displayed()]
                        if visible:
                            search_input = visible[0]
                            self.logger.info(f"找到搜索框: {locator_name}")
                            break
                    except:
                        continue
                
                if not search_input:
                    self.logger.error("未找到搜索框")
                    continue
                
                # 输入关键词
                search_input.clear()
                search_input.send_keys(keyword)
                
                # 提交搜索
                from selenium.webdriver.common.keys import Keys
                search_input.send_keys(Keys.RETURN)
                
                # 优化: 等待
                time.sleep(NDLSeleniumConfig.OPTIMAL_WAIT)
                
                # 解析结果
                items = self._parse_search_results(max_results)
                
                if items:
                    self.logger.info(f"找到 {len(items)} 个结果")
                    return items
                elif retry < NDLSeleniumConfig.RETRY_ATTEMPTS - 1:
                    self.logger.warning(f"结果为空，重试 ({retry+1}/{NDLSeleniumConfig.RETRY_ATTEMPTS})")
                    continue
                    
            except Exception as e:
                self.logger.error(f"搜索失败 (尝试 {retry+1}/{NDLSeleniumConfig.RETRY_ATTEMPTS}): {e}")
                if retry < NDLSeleniumConfig.RETRY_ATTEMPTS - 1:
                    continue
                    
        self.logger.error("搜索最终失败")
        return []
    
    def _parse_search_results(self, max_results: int) -> List[Dict[str, Any]]:
        """解析搜索结果页面"""
        items = []
        
        try:
            result_elements = self.driver.find_elements(
                By.CSS_SELECTOR,
                "li.item, li.search-result-item, li.detail-item, div.result-item"
            )
            
            if not result_elements:
                self.logger.debug("未找到标准结果元素，尝试备选选择器")
                result_elements = self.driver.find_elements(By.TAG_NAME, "li")
            
            for elem in result_elements[:max_results]:
                try:
                    title_elem = elem.find_element(
                        By.CSS_SELECTOR,
                        "h3, h4, a.title, a.item-title, a"
                    )
                    title = title_elem.text.strip() if title_elem else '未知标题'
                    
                    link_elem = elem.find_element(By.CSS_SELECTOR, "a[href*='detail'], a[href*='id=']")
                    link = link_elem.get_attribute('href') if link_elem else ''
                    
                    if link and not link.startswith('http'):
                        link = NDLSeleniumConfig.BASE_URL + link
                    
                    item_id_match = re.search(r'[?&/]id=([A-Za-z0-9]+)', link)
                    item_id = item_id_match.group(1) if item_id_match else ''
                    
                    author_elem = elem.find_elements(By.CSS_SELECTOR, "span.author, span.creator, p.author")
                    author = author_elem[0].text.strip() if author_elem else ''
                    
                    item = {
                        'id': item_id,
                        'title': title,
                        'author': author,
                        'url': link
                    }
                    
                    items.append(item)
                    
                except NoSuchElementException:
                    continue
                except Exception as e:
                    self.logger.debug(f"解析项目失败: {e}")
                    continue
            
        except Exception as e:
            self.logger.error(f"解析搜索结果失败: {e}")
        
        return items
    
    def find_pdf_url(self, item_url: str) -> Optional[str]:
        """
        查找资料的PDF下载URL
        
        Args:
            item_url: 资料详情页面URL
            
        Returns:
            Optional[str]: PDF下载URL
        """
        self.logger.debug(f"查找PDF URL: {item_url}")
        
        try:
            self.driver.get(item_url)
            self._wait_interval()
            
            wait = WebDriverWait(self.driver, 10)
            
            pdf_url = None
            
            try:
                download_link = wait.until(
                    EC.element_to_be_clickable(
                        (By.CSS_SELECTOR, "a[href*='.pdf'], a.download-pdf, a[download]")
                    )
                )
                pdf_url = download_link.get_attribute('href')
                
            except TimeoutException:
                self.logger.debug("未找到直接下载链接，尝试其他方法")
                
                try:
                    pdf_links = self.driver.find_elements(
                        By.CSS_SELECTOR,
                        "a[href*='download'], a[href*='pdf'], iframe[src*='pdf']"
                    )
                    
                    for link in pdf_links:
                        href = link.get_attribute('href') or link.get_attribute('src')
                        if href and ('.pdf' in href.lower() or 'download' in href.lower()):
                            pdf_url = href
                            break
                            
                except Exception:
                    pass
            
            if pdf_url and not pdf_url.startswith('http'):
                pdf_url = NDLSeleniumConfig.BASE_URL + pdf_url
            
            if pdf_url:
                self.logger.debug(f"找到PDF URL: {pdf_url}")
            else:
                self.logger.debug(f"未找到PDF URL: {item_url}")
            
            return pdf_url
            
        except Exception as e:
            self.logger.error(f"查找PDF失败: {e}")
            return None
    
    def download_file(self, url: str, filename: str,
                     max_retries: int = 2) -> Tuple[bool, str]:
        """
        下载文件
        
        Args:
            url: 文件URL
            filename: 保存文件名
            max_retries: 最大重试次数
            
        Returns:
            Tuple[bool, str]: (是否成功, 消息)
        """
        filepath = self.output_dir / filename
        
        if filepath.exists():
            self.logger.info(f"文件已存在，跳过: {filename}")
            return True, "已存在"
        
        self.logger.info(f"开始下载: {filename}")
        
        for attempt in range(max_retries):
            try:
                response = requests.get(
                    url,
                    timeout=30,
                    stream=True,
                    headers={
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                    }
                )
                response.raise_for_status()
                
                total_size = int(response.headers.get('content-length', 0))
                downloaded = 0
                chunk_size = 8192
                
                with open(filepath, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=chunk_size):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            
                            if total_size > 0:
                                progress = (downloaded / total_size) * 100
                                print(f"\r  下载进度: {progress:.1f}%", end='', flush=True)
                
                print()
                
                if downloaded < 1000:
                    self.logger.warning(f"文件可能无效: {filename}")
                    filepath.unlink()
                    return False, "下载文件无效"
                
                self.logger.info(f"下载完成: {filename} ({downloaded:,} bytes)")
                self.downloaded_files.append(str(filepath))
                
                return True, "成功"
                
            except Exception as e:
                self.logger.error(f"下载失败 (尝试 {attempt + 1}/{max_retries}): {e}")
                
                if filepath.exists():
                    try:
                        filepath.unlink()
                    except:
                        pass
                
                if attempt == max_retries - 1:
                    self.failed_downloads.append({
                        'url': url,
                        'filename': filename,
                        'error': str(e)
                    })
                    return False, f"下载失败: {e}"
                
                self.logger.info("等待5秒后重试...")
                time.sleep(5)
        
        return False, "达到最大重试次数"
    
    def search_and_download(self, keyword: str,
                          max_results: int = 5,
                          max_retries: int = 2) -> Dict[str, Any]:
        """
        搜索并下载资料
        
        Args:
            keyword: 搜索关键词
            max_results: 最大下载数
            max_retries: 最大重试次数
            
        Returns:
            Dict: 下载结果统计
        """
        self.logger.info("="*60)
        self.logger.info(f"开始搜索并下载: {keyword}")
        self.logger.info("="*60)
        
        items = self.search_items(keyword, max_results)
        
        if not items:
            self.logger.warning("未找到任何资料")
            return {
                'success': False,
                'keyword': keyword,
                'total_found': 0,
                'downloaded': 0,
                'failed': 0,
                'message': '未找到任何资料'
            }
        
        success_count = 0
        failed_count = 0
        skipped_count = 0
        
        for i, item in enumerate(items, 1):
            self.logger.info(f"\n处理进度: {i}/{len(items)}")
            
            item_id = item.get('id', '')
            title = item.get('title', '未知标题')
            url = item.get('url', '')
            
            self.logger.info(f"资料标题: {title}")
            self.logger.info(f"资料ID: {item_id}")
            
            if not url:
                self.logger.warning("无详情URL，跳过")
                failed_count += 1
                continue
            
            pdf_url = self.find_pdf_url(url)
            
            if not pdf_url:
                self.logger.warning("未找到PDF URL，跳过")
                failed_count += 1
                continue
            
            safe_title = re.sub(r'[<>:"/\\|?*]', '_', title)[:50]
            filename = f"{item_id}_{safe_title}.pdf"
            
            success, message = self.download_file(pdf_url, filename, max_retries)
            
            if success:
                if message == "已存在":
                    skipped_count += 1
                else:
                    success_count += 1
            else:
                failed_count += 1
        
        result = {
            'success': success_count > 0,
            'keyword': keyword,
            'total_found': len(items),
            'downloaded': success_count,
            'skipped': skipped_count,
            'failed': failed_count,
            'download_dir': str(self.output_dir),
            'downloaded_files': self.downloaded_files
        }
        
        self.logger.info("\n" + "="*60)
        self.logger.info("下载完成统计")
        self.logger.info("="*60)
        self.logger.info(f"搜索关键词: {keyword}")
        self.logger.info(f"找到资料: {len(items)} 个")
        self.logger.info(f"成功下载: {success_count} 个")
        self.logger.info(f"已跳过: {skipped_count} 个")
        self.logger.info(f"下载失败: {failed_count} 个")
        self.logger.info(f"下载目录: {self.output_dir}")
        self.logger.info("="*60)
        
        return result
    
    def generate_report(self) -> str:
        """生成下载报告"""
        report = f"""# NDL PDF下载报告 (Selenium版)

## 下载时间
{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## 下载配置
- 下载目录: {self.output_dir}
- 请求间隔: {self.interval}秒
- 最大重试: {max_retries}次
- 无头模式: {self.headless}

## 下载统计
- 成功下载: {len(self.downloaded_files)} 个
- 下载失败: {len(self.failed_downloads)} 个

## 下载文件
"""
        
        for filepath in self.downloaded_files:
            filepath_obj = Path(filepath)
            size = filepath_obj.stat().st_size if filepath_obj.exists() else 0
            report += f"- {filepath_obj.name} ({size:,} bytes)\n"
        
        if self.failed_downloads:
            report += f"""
## 下载失败
"""
            for item in self.failed_downloads:
                report += f"- {item['filename']}: {item['error']}\n"
        
        report += f"""
---
本报告由 NDL PDF下载工具 (Selenium版) 自动生成
"""
        
        return report
    
    def save_report(self, filename: Optional[str] = None):
        """保存下载报告"""
        if not filename:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"download_report_selenium_{timestamp}.md"
        
        filepath = self.output_dir / filename
        
        report = self.generate_report()
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(report)
        
        self.logger.info(f"报告已保存: {filepath}")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='日本国立国会图书馆PDF资料下载工具 (Selenium版)'
    )
    
    parser.add_argument(
        '-k', '--keyword',
        required=True,
        help='搜索关键词'
    )
    
    parser.add_argument(
        '-o', '--output',
        default='./downloads',
        help='下载目录 (默认: ./downloads)'
    )
    
    parser.add_argument(
        '-i', '--interval',
        type=float,
        default=1.0,
        help='请求间隔秒数 (默认: 1.0)'
    )
    
    parser.add_argument(
        '-n', '--max-results',
        type=int,
        default=5,
        help='最大下载数量 (默认: 5)'
    )
    
    parser.add_argument(
        '-r', '--max-retries',
        type=int,
        default=2,
        help='最大重试次数 (默认: 2)'
    )
    
    parser.add_argument(
        '-l', '--log-file',
        help='日志文件路径'
    )
    
    parser.add_argument(
        '--no-headless',
        action='store_true',
        help='不使用无头模式（显示浏览器窗口）'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='只搜索不下载'
    )
    
    args = parser.parse_args()
    
    downloader = NDLSeleniumDownloader(
        output_dir=args.output,
        interval=args.interval,
        log_file=args.log_file,
        headless=not args.no_headless
    )
    
    try:
        if args.dry_run:
            downloader.logger.info("干运行模式：只搜索不下载")
            items = downloader.search_items(args.keyword, args.max_results)
            
            downloader.logger.info(f"\n搜索到 {len(items)} 个结果:")
            for i, item in enumerate(items, 1):
                title = item.get('title', '未知标题')
                item_id = item.get('id', 'N/A')
                author = item.get('author', '')
                downloader.logger.info(f"{i}. {title} (ID: {item_id}) {f'by {author}' if author else ''}")
            
            return 0
        
        result = downloader.search_and_download(
            keyword=args.keyword,
            max_results=args.max_results,
            max_retries=args.max_retries
        )
        
        downloader.save_report()
        
        if result['downloaded'] > 0:
            downloader.logger.info("\n✅ 下载成功!")
            return 0
        else:
            downloader.logger.error("\n❌ 下载失败")
            return 1
            
    finally:
        downloader.close()


if __name__ == '__main__':
    sys.exit(main())
