"""
日本国立国会图书馆(NDL) PDF资料下载工具 - 增强版

用于下载日本国立国会图书馆网站(https://dl.ndl.go.jp)上无需登录的公开PDF资料。
本工具仅供学术研究使用，请遵守NDL的使用条款和robots.txt规则。

增强功能：
- 支持直接URL访问
- 增强的PDF查找功能
- Web页面解析支持
- 更健壮的错误处理

作者：History Research AI Tools
版本：1.1.0
日期：2024年3月
"""

import os
import sys
import time
import json
import re
import argparse
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List, Tuple, Any
from urllib.parse import urljoin, urlparse, parse_qs

try:
    import requests
    from bs4 import BeautifulSoup
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
except ImportError:
    print("错误: 请安装必要的库")
    print("运行: pip install requests beautifulsoup4")
    sys.exit(1)


class NDLConfig:
    """NDL下载器配置"""
    
    BASE_URL = "https://dl.ndl.go.jp"
    SEARCH_URL = "https://dl.ndl.go.jp/pc/search"
    API_URL = "https://dl.ndl.go.jp/api"
    
    REQUEST_INTERVAL = 1.0
    
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'ja,en-US;q=0.7,en;q=0.3',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1',
        'Cache-Control': 'max-age=0',
    }
    
    TIMEOUT = 30
    MAX_RETRIES = 3


class NDLLogger:
    """日志记录器"""
    
    def __init__(self, log_file: Optional[str] = None, log_level: int = logging.INFO):
        self.logger = logging.getLogger('NDLDownloader')
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


class NDLDownloader:
    """日本国立国会图书馆PDF资料下载器"""
    
    def __init__(self, output_dir: str = "./downloads", 
                 interval: float = NDLConfig.REQUEST_INTERVAL,
                 log_file: Optional[str] = None):
        """
        初始化下载器
        
        Args:
            output_dir: 下载目录
            interval: 请求间隔时间（秒）
            log_file: 日志文件路径
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.interval = interval
        self.logger = NDLLogger(log_file)
        
        self.session = self._create_session()
        self.downloaded_files = []
        self.failed_downloads = []
        
        self.logger.info("="*60)
        self.logger.info("日本国立国会图书馆PDF资料下载工具 v1.1.0")
        self.logger.info("="*60)
        self.logger.info(f"下载目录: {self.output_dir}")
        self.logger.info(f"请求间隔: {self.interval}秒")
        self.logger.info("="*60)
    
    def _create_session(self) -> requests.Session:
        """创建HTTP会话"""
        session = requests.Session()
        
        adapter = HTTPAdapter(
            max_retries=Retry(
                total=NDLConfig.MAX_RETRIES,
                backoff_factor=0.5,
                status_forcelist=[429, 500, 502, 503, 504]
            )
        )
        session.mount('http://', adapter)
        session.mount('https://', adapter)
        
        session.headers.update(NDLConfig.HEADERS)
        
        return session
    
    def _wait_interval(self):
        """等待请求间隔时间"""
        time.sleep(self.interval)
    
    def search_items(self, keyword: str, max_results: int = 20) -> List[Dict[str, Any]]:
        """
        搜索资料
        
        Args:
            keyword: 搜索关键词
            max_results: 最大结果数
            
        Returns:
            List[Dict]: 搜索结果列表
        """
        self.logger.info(f"搜索关键词: {keyword}")
        
        search_url = NDLConfig.SEARCH_URL
        
        params = {
            'q': keyword,
            'page': 1,
            'size': min(max_results, 50),
            'searchScope': 'detail',
            'lang': 'jp',
            'hasAccess': '0'
        }
        
        try:
            self._wait_interval()
            response = self.session.get(
                search_url,
                params=params,
                timeout=NDLConfig.TIMEOUT
            )
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            items = []
            
            item_cards = soup.find_all('li', class_=['item', 'search-result-item', 'detail-item'])
            
            for card in item_cards:
                try:
                    title_elem = card.find(['h3', 'h4', 'a'], class_=['title', 'item-title'])
                    if not title_elem:
                        title_elem = card.find(['h3', 'h4', 'a'])
                    
                    title = title_elem.get_text(strip=True) if title_elem else '未知标题'
                    
                    link_elem = card.find('a', href=True)
                    link = link_elem['href'] if link_elem else ''
                    
                    if link and not link.startswith('http'):
                        link = urljoin(NDLConfig.BASE_URL, link)
                    
                    item_id_match = re.search(r'[?&/]id=([A-Za-z0-9]+)', link)
                    item_id = item_id_match.group(1) if item_id_match else ''
                    
                    author_elem = card.find(['span', 'p'], class_=['author', 'creator'])
                    author = author_elem.get_text(strip=True) if author_elem else ''
                    
                    date_elem = card.find(['span', 'p'], class_=['date', 'publication-date'])
                    date = date_elem.get_text(strip=True) if date_elem else ''
                    
                    item = {
                        'id': item_id,
                        'title': title,
                        'author': author,
                        'date': date,
                        'url': link
                    }
                    
                    items.append(item)
                    
                except Exception as e:
                    self.logger.debug(f"解析项目失败: {e}")
                    continue
            
            if not items:
                self.logger.warning("未在页面中找到搜索结果，尝试备选解析方法")
                
                links = soup.find_all('a', href=re.compile(r'/detail|open.*[?&]id='))
                
                for link in links[:max_results]:
                    try:
                        href = link.get('href', '')
                        if href and not href.startswith('http'):
                            href = urljoin(NDLConfig.BASE_URL, href)
                        
                        item_id_match = re.search(r'[?&/]id=([A-Za-z0-9]+)', href)
                        item_id = item_id_match.group(1) if item_id_match else ''
                        
                        title = link.get_text(strip=True) or '未知标题'
                        
                        items.append({
                            'id': item_id,
                            'title': title,
                            'author': '',
                            'date': '',
                            'url': href
                        })
                    except Exception:
                        continue
            
            self.logger.info(f"找到 {len(items)} 个搜索结果")
            
            return items
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"搜索失败: {e}")
            return []
        except Exception as e:
            self.logger.error(f"解析页面失败: {e}")
            return []
    
    def get_item_detail(self, item_id: str) -> Optional[Dict[str, Any]]:
        """
        获取资料详情
        
        Args:
            item_id: 资料ID
            
        Returns:
            Optional[Dict]: 资料详情
        """
        self.logger.debug(f"获取资料详情: {item_id}")
        
        detail_url = f"{NDLConfig.BASE_URL}/api/detail?id={item_id}"
        
        try:
            self._wait_interval()
            response = self.session.get(
                detail_url,
                timeout=NDLConfig.TIMEOUT
            )
            
            if response.status_code == 200:
                try:
                    return response.json()
                except:
                    return None
            else:
                return None
                
        except requests.exceptions.RequestException as e:
            self.logger.debug(f"API详情获取失败: {e}")
            return None
    
    def find_pdf_url(self, item_id: str, detail_url: str = "") -> Optional[str]:
        """
        查找资料的PDF下载URL
        
        Args:
            item_id: 资料ID
            detail_url: 详情页面URL
            
        Returns:
            Optional[str]: PDF下载URL
        """
        self.logger.debug(f"查找PDF URL: {item_id}")
        
        if not detail_url:
            detail_url = f"{NDLConfig.BASE_URL}/detail/{item_id}"
        
        try:
            self._wait_interval()
            response = self.session.get(
                detail_url,
                timeout=NDLConfig.TIMEOUT
            )
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            pdf_patterns = [
                r'href=["\']([^"\']+\.pdf[^"\']*)["\']',
                r'"downloadUrl"\s*:\s*["\']([^"\']+\.pdf[^"\']*)["\']',
                r'"pdfUrl"\s*:\s*["\']([^"\']*\.pdf[^"\']*)["\']',
                r'src=["\']([^"\']+\.pdf[^"\']*)["\']'
            ]
            
            for pattern in pdf_patterns:
                matches = re.findall(pattern, response.text, re.IGNORECASE)
                if matches:
                    pdf_url = matches[0]
                    if not pdf_url.startswith('http'):
                        pdf_url = urljoin(detail_url, pdf_url)
                    return pdf_url
            
            download_link = soup.find('a', href=re.compile(r'\.pdf', re.IGNORECASE))
            if download_link:
                href = download_link.get('href', '')
                if not href.startswith('http'):
                    href = urljoin(detail_url, href)
                return href
            
            player_iframe = soup.find('iframe', src=re.compile(r'player|viewer|digital'))
            if player_iframe:
                iframe_url = player_iframe.get('src', '')
                if not iframe_url.startswith('http'):
                    iframe_url = urljoin(detail_url, iframe_url)
                
                pdf_url = self._find_pdf_in_viewer(iframe_url)
                if pdf_url:
                    return pdf_url
            
            return None
            
        except requests.exceptions.RequestException as e:
            self.logger.debug(f"详情页面获取失败: {e}")
            return None
        except Exception as e:
            self.logger.debug(f"PDF查找失败: {e}")
            return None
    
    def _find_pdf_in_viewer(self, viewer_url: str) -> Optional[str]:
        """
        在查看器页面中查找PDF URL
        
        Args:
            viewer_url: 查看器URL
            
        Returns:
            Optional[str]: PDF URL
        """
        try:
            self._wait_interval()
            response = self.session.get(
                viewer_url,
                timeout=NDLConfig.TIMEOUT
            )
            
            pdf_pattern = r'["\']([^"\']+\.pdf[^"\']*)["\']'
            matches = re.findall(pdf_pattern, response.text, re.IGNORECASE)
            
            if matches:
                pdf_url = matches[0]
                if not pdf_url.startswith('http'):
                    pdf_url = urljoin(viewer_url, pdf_url)
                return pdf_url
            
            return None
            
        except Exception:
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
                self._wait_interval()
                
                response = self.session.get(
                    url,
                    timeout=NDLConfig.TIMEOUT,
                    stream=True
                )
                response.raise_for_status()
                
                content_type = response.headers.get('content-type', '')
                if 'html' in content_type.lower():
                    self.logger.warning("服务器返回HTML页面，可能不是有效的PDF")
                
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
                
            except requests.exceptions.RequestException as e:
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
            
            pdf_url = self.find_pdf_url(item_id, url)
            
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
        report = f"""# NDL PDF下载报告

## 下载时间
{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## 下载配置
- 下载目录: {self.output_dir}
- 请求间隔: {self.interval}秒
- 最大重试: {NDLConfig.MAX_RETRIES}次

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
本报告由 NDL PDF下载工具 自动生成
"""
        
        return report
    
    def save_report(self, filename: Optional[str] = None):
        """保存下载报告"""
        if not filename:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"download_report_{timestamp}.md"
        
        filepath = self.output_dir / filename
        
        report = self.generate_report()
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(report)
        
        self.logger.info(f"报告已保存: {filepath}")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='日本国立国会图书馆PDF资料下载工具',
        formatter_class=argparse.RawDescriptionHelpFormatter
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
        '--dry-run',
        action='store_true',
        help='只搜索不下载'
    )
    
    args = parser.parse_args()
    
    downloader = NDLDownloader(
        output_dir=args.output,
        interval=args.interval,
        log_file=args.log_file
    )
    
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


if __name__ == '__main__':
    sys.exit(main())
