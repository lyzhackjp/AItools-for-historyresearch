# 日本国立国会图书馆PDF资料下载工具使用指南

## 📖 概述

本工具用于从日本国立国会图书馆(NDL)网站下载无需登录的公开PDF资料。仅供学术研究使用，请遵守NDL的使用条款。

### 功能特点

- ✅ 自动搜索并下载公开PDF资料
- ✅ 1秒请求间隔控制，避免服务器负载
- ✅ 完善的错误处理和重试机制
- ✅ 下载进度实时显示
- ✅ 详细的日志记录
- ✅ 命令行参数支持
- ✅ 尊重robots.txt和使用条款

---

## 🔧 安装依赖

### 必需依赖

```bash
pip install requests
```

### 可选依赖（增强功能）

```bash
pip install requests[security]  # 支持更高级的SSL选项
```

---

## 🚀 快速开始

### 基本用法

```bash
# 搜索并下载资料
python ndl_pdf_downloader.py -k "井上哲次郎"

# 指定下载目录
python ndl_pdf_downloader.py -k "明治維新" -o ./my_downloads

# 只搜索不下载（测试用）
python ndl_pdf_downloader.py -k "武士道" --dry-run
```

---

## 📝 命令行参数

### 必需参数

| 参数 | 说明 | 示例 |
|------|------|------|
| `-k, --keyword` | 搜索关键词 | `-k "井上哲次郎"` |

### 可选参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `-o, --output` | `./downloads` | 下载目录 |
| `-i, --interval` | `1.0` | 请求间隔（秒） |
| `-n, --max-results` | `5` | 最大下载数量 |
| `-r, --max-retries` | `2` | 最大重试次数 |
| `-l, --log-file` | 无 | 日志文件路径 |
| `--dry-run` | False | 只搜索不下载 |

### 完整示例

```bash
# 完整参数示例
python ndl_pdf_downloader.py \
  -k "日本史" \
  -o "./downloads" \
  -i 1.0 \
  -n 10 \
  -r 2 \
  -l "download.log"
```

---

## 💻 Python API 使用

### 基本用法

```python
from ndl_pdf_downloader import NDLDownloader

downloader = NDLDownloader(
    output_dir="./downloads",
    interval=1.0
)

result = downloader.search_and_download(
    keyword="井上哲次郎",
    max_results=5,
    max_retries=2
)

print(f"下载成功: {result['downloaded']}")
print(f"下载失败: {result['failed']}")
```

### 只搜索不下载

```python
downloader = NDLDownloader(output_dir="./downloads")

items = downloader.search_items("井上哲次郎", max_results=10)

for item in items:
    print(f"标题: {item['title']}")
    print(f"ID: {item['id']}")
```

### 下载单个URL

```python
downloader = NDLDownloader(output_dir="./downloads")

success, message = downloader.download_by_url(
    "https://dl.ndl.go.jp/api/detail?id=...",
    max_retries=2
)

print(f"下载结果: {message}")
```

### 生成下载报告

```python
downloader = NDLDownloader(output_dir="./downloads")

# ... 执行下载 ...

report = downloader.generate_report()
downloader.save_report()

print(report)
```

---

## 📋 功能详解

### 1. 搜索功能

**搜索API**：
```python
items = downloader.search_items(keyword, max_results)
```

**返回值**：
```python
[
    {
        'id': '123456',
        'title': '倫理新説',
        'author': '井上哲次郎',
        'publisher': '大日本百科',
        'publication_date': '1887',
        ...
    },
    ...
]
```

### 2. PDF查找

**自动识别**：
- 直接PDF链接
- 元数据中的PDF URL
- 数字化页面中的PDF

**查找逻辑**：
1. 获取资料详情
2. 检查metadata中的PDF URL
3. 如果没有，访问数字化页面提取

### 3. 下载功能

**特性**：
- 流式下载，支持大文件
- 进度显示（百分比）
- 自动重试（默认2次）
- 文件完整性检查

**重试机制**：
- 网络错误自动重试
- 文件不完整自动重试
- 最多等待5秒后重试

### 4. 日志记录

**日志级别**：
- INFO: 正常信息
- WARNING: 警告信息
- ERROR: 错误信息
- DEBUG: 调试信息

**输出位置**：
- 控制台（始终输出）
- 文件（可选）

---

## ⚙️ 配置说明

### NDLConfig 类

```python
class NDLConfig:
    BASE_URL = "https://dl.ndl.go.jp"
    REQUEST_INTERVAL = 1.0  # 请求间隔
    TIMEOUT = 30  # 请求超时
    MAX_RETRIES = 3  # 最大重试次数
    
    HEADERS = {  # 浏览器模拟头
        'User-Agent': 'Mozilla/5.0...',
        'Accept': 'text/html,...',
        ...
    }
```

### 自定义配置

```python
# 修改请求间隔
downloader = NDLDownloader(interval=2.0)

# 修改超时时间
NDLConfig.TIMEOUT = 60

# 修改重试次数
NDLConfig.MAX_RETRIES = 5
```

---

## 📊 下载统计

### 返回结果结构

```python
{
    'success': True,
    'keyword': '井上哲次郎',
    'total_found': 5,
    'downloaded': 3,
    'skipped': 1,
    'failed': 1,
    'download_dir': './downloads',
    'downloaded_files': [
        './downloads/123456_倫理新説.pdf',
        ...
    ]
}
```

### 统计指标

| 指标 | 说明 |
|------|------|
| `total_found` | 搜索到的资料总数 |
| `downloaded` | 成功下载的数量 |
| `skipped` | 已存在跳过的数量 |
| `failed` | 下载失败的数量 |

---

## ⚠️ 注意事项

### 1. 合规使用

- ✅ 仅供学术研究使用
- ✅ 遵守1秒请求间隔
- ✅ 尊重robots.txt规则
- ✅ 不批量下载商业用途

### 2. 错误处理

```python
try:
    result = downloader.search_and_download(keyword)
except Exception as e:
    print(f"下载失败: {e}")
```

### 3. 网络问题

```python
# 网络不稳定时，建议增加重试次数
result = downloader.search_and_download(
    keyword,
    max_retries=3
)
```

### 4. 文件管理

```python
# 检查下载目录
import os
print(os.listdir('./downloads'))

# 检查文件完整性
import hashlib
with open('file.pdf', 'rb') as f:
    md5 = hashlib.md5(f.read()).hexdigest()
    print(f"MD5: {md5}")
```

---

## 🐛 故障排除

### 问题1: 搜索失败

**症状**：
```
搜索失败: HTTPSConnectionPool
```

**解决方案**：
1. 检查网络连接
2. 增加超时时间
3. 检查代理设置

### 问题2: 未找到PDF

**症状**：
```
未找到PDF URL
```

**解决方案**：
1. 确认资料确实提供PDF下载
2. 检查资料是否需要登录
3. 手动访问NDL网站确认

### 问题3: 下载中断

**症状**：
```
下载失败: ConnectionResetError
```

**解决方案**：
1. 增加重试次数
2. 增加请求间隔
3. 检查网络稳定性

### 问题4: 权限错误

**症状**：
```
PermissionError: [Errno 13]
```

**解决方案**：
1. 检查目录写入权限
2. 使用其他下载目录

---

## 📝 使用示例

### 示例1: 搜索书籍

```bash
python ndl_pdf_downloader.py -k "井上哲次郎 倫理新説" --dry-run
```

**输出**：
```
2024-03-27 10:00:00 - INFO - 搜索关键词: 井上哲次郎 倫理新説
2024-03-27 10:00:00 - INFO - 找到 3 个搜索结果
2024-03-27 10:00:00 - INFO - 
1. 倫理新説 (ID: 123456)
2. 日本倫理思想史 (ID: 789012)
3. 東洋倫理学史 (ID: 345678)
```

### 示例2: 下载书籍

```bash
python ndl_pdf_downloader.py -k "井上哲次郎 倫理新説" -n 2 -o "./downloads"
```

**输出**：
```
2024-03-27 10:00:00 - INFO - 开始搜索并下载: 井上哲次郎 倫理新説
2024-03-27 10:00:01 - INFO - 找到 2 个搜索结果
2024-03-27 10:00:02 - INFO - 处理进度: 1/2
2024-03-27 10:00:02 - INFO - 资料标题: 倫理新説
2024-03-27 10:00:02 - INFO - 资料ID: 123456
2024-03-27 10:00:02 - INFO - 开始下载: 123456_倫理新説.pdf
  下载进度: 45.2%
  下载进度: 100.0%
2024-03-27 10:00:05 - INFO - 下载完成: 123456_倫理新説.pdf (5,234,567 bytes)
```

### 示例3: Python脚本调用

```python
#!/usr/bin/env python3
from ndl_pdf_downloader import NDLDownloader
import sys

def main():
    keyword = "井上哲次郎 倫理新説"
    output_dir = "./downloads"
    
    print(f"开始下载: {keyword}")
    
    downloader = NDLDownloader(output_dir=output_dir)
    
    result = downloader.search_and_download(
        keyword=keyword,
        max_results=2,
        max_retries=2
    )
    
    if result['success']:
        print(f"\n✅ 下载成功!")
        print(f"下载目录: {result['download_dir']}")
        print(f"下载文件:")
        for filepath in result['downloaded_files']:
            print(f"  - {filepath}")
        return 0
    else:
        print(f"\n❌ 下载失败")
        print(f"原因: {result.get('message', '未知错误')}")
        return 1

if __name__ == '__main__':
    sys.exit(main())
```

---

## 📚 相关文档

- [NDL官方网站](https://dl.ndl.go.jp)
- [NDL使用条款](https://dl.ndl.go.jp/terms.html)
- [NDL API文档](https://dl.ndl.go.jp/api/)

---

## 📄 许可证

本工具仅供学术研究使用，请遵守相关版权法律和NDL使用条款。

---

## 🔄 更新日志

### v1.0.0 (2024-03-27)
- 初始版本
- 支持基本搜索和下载功能
- 实现1秒请求间隔控制
- 添加完善的错误处理

---

**版本**: 1.0.0  
**更新日期**: 2024年3月27日  
**作者**: History Research AI Tools
