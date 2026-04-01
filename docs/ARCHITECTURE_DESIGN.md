# 架构设计文档

## 📋 文档信息

- **版本**: 1.0.0
- **创建日期**: 2026-04-01
- **状态**: ✅ 已确认
- **架构师**: AI History Research Tools Team

---

## 🏗️ 整体架构

### 架构概览图

```
┌─────────────────────────────────────────────────────────────────┐
│                    IntelligentResearchAssistant                 │
│                         (统一对外接口)                           │
└─────────────────────┬───────────────────────────────────────────┘
                      │
        ┌─────────────┼─────────────┐
        │             │             │
        ▼             ▼             ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│  Search层    │ │  Analysis层  │ │ Generation层 │
│  (搜索)      │ │  (分析)      │ │  (生成)      │
└──────┬───────┘ └──────┬───────┘ └──────┬───────┘
       │                │                │
       └────────────────┼────────────────┘
                        │
                        ▼
        ┌───────────────────────────────┐
        │         Core层                │
        │  (LLM/Cache/Config/Data)      │
        └───────────────┬───────────────┘
                        │
                        ▼
        ┌───────────────────────────────┐
        │       Storage层               │
        │  (Document/Report/Cache)      │
        └───────────────────────────────┘
```

### 分层职责

| 层级 | 职责 | 主要组件 |
|------|------|----------|
| **Core层** | 提供基础服务 | LLMManager, CacheManager, ConfigManager, DataModels |
| **Search层** | 多平台搜索 | ProjectFinder, PaperFinder, DocumentFetcher |
| **Analysis层** | 深度分析 | ProjectAnalyzer, PaperAnalyzer, LiteratureAnalyzer |
| **Generation层** | 内容生成 | ReportGenerator, ImprovementGenerator |
| **Storage层** | 数据持久化 | DocumentStore, ReportStore, CacheStore |

---

## 🔧 核心层设计

### 1. LLMManager (统一LLM管理器)

#### 设计目标
- 单例模式，全局唯一实例
- 统一API调用接口
- 自动重试和错误处理
- 支持多种LLM提供商

#### 接口定义

```python
class LLMManager:
    """统一LLM管理器 - 单例模式"""
    
    _instance = None
    
    @classmethod
    def get_instance(cls, api_provider='qwen', test_mode=False):
        """获取单例实例"""
        if cls._instance is None:
            cls._instance = cls(api_provider, test_mode)
        return cls._instance
    
    def __init__(self, api_provider='qwen', test_mode=False):
        """初始化LLM管理器"""
        if hasattr(self, 'initialized'):
            return
        
        self.api_provider = api_provider
        self.test_mode = test_mode
        self.client = self._init_client()
        self.call_count = 0
        self.initialized = True
    
    def call(
        self,
        prompt: str,
        system_prompt: str = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        **kwargs
    ) -> str:
        """
        统一的LLM调用接口
        
        Args:
            prompt: 用户提示词
            system_prompt: 系统提示词
            temperature: 温度参数
            max_tokens: 最大token数
            **kwargs: 其他参数
            
        Returns:
            str: LLM响应文本
        """
        if self.test_mode:
            return self._mock_response(prompt)
        
        try:
            self.call_count += 1
            response = self.client.call(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs
            )
            return response
        except Exception as e:
            return self._handle_error(e, prompt)
    
    def call_json(
        self,
        prompt: str,
        system_prompt: str = None,
        **kwargs
    ) -> dict:
        """
        调用LLM并返回JSON格式结果
        
        Args:
            prompt: 用户提示词
            system_prompt: 系统提示词
            **kwargs: 其他参数
            
        Returns:
            dict: JSON格式的响应
        """
        response = self.call(prompt, system_prompt, **kwargs)
        return self._parse_json_response(response)
```

#### 使用示例

```python
# 获取单例实例
llm = LLMManager.get_instance(api_provider='qwen')

# 调用LLM
response = llm.call(
    prompt="分析这个项目的特点",
    system_prompt="你是一个项目分析专家"
)

# 调用LLM并返回JSON
result = llm.call_json(
    prompt="分析这个项目的技术栈",
    system_prompt="返回JSON格式的分析结果"
)
```

### 2. CacheManager (统一缓存管理器)

#### 设计目标
- 统一缓存接口
- TTL过期机制
- 自动清理过期缓存
- 支持多种缓存后端

#### 接口定义

```python
class CacheManager:
    """统一缓存管理器"""
    
    def __init__(
        self,
        cache_dir: str = 'storage/cache',
        ttl_days: int = 7,
        max_size_mb: int = 100
    ):
        """
        初始化缓存管理器
        
        Args:
            cache_dir: 缓存目录
            ttl_days: 缓存有效期（天）
            max_size_mb: 最大缓存大小（MB）
        """
        self.cache_dir = Path(cache_dir)
        self.ttl_days = ttl_days
        self.max_size_mb = max_size_mb
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        self._cleanup_expired()
    
    def get(self, key: str) -> Optional[Any]:
        """
        获取缓存
        
        Args:
            key: 缓存键
            
        Returns:
            Optional[Any]: 缓存值，不存在或过期返回None
        """
        cache_file = self.cache_dir / f"{self._hash_key(key)}.json"
        
        if not cache_file.exists():
            return None
        
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 检查是否过期
            cached_time = datetime.fromisoformat(data['timestamp'])
            if datetime.now() - cached_time > timedelta(days=self.ttl_days):
                cache_file.unlink()
                return None
            
            return data['content']
        except Exception:
            return None
    
    def set(self, key: str, value: Any, metadata: dict = None):
        """
        设置缓存
        
        Args:
            key: 缓存键
            value: 缓存值
            metadata: 元数据
        """
        cache_file = self.cache_dir / f"{self._hash_key(key)}.json"
        
        data = {
            'key': key,
            'content': value,
            'timestamp': datetime.now().isoformat(),
            'metadata': metadata or {}
        }
        
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        # 检查缓存大小
        self._check_cache_size()
    
    def delete(self, key: str):
        """删除缓存"""
        cache_file = self.cache_dir / f"{self._hash_key(key)}.json"
        if cache_file.exists():
            cache_file.unlink()
    
    def clear(self):
        """清空所有缓存"""
        for cache_file in self.cache_dir.glob('*.json'):
            cache_file.unlink()
    
    def get_stats(self) -> dict:
        """获取缓存统计信息"""
        cache_files = list(self.cache_dir.glob('*.json'))
        total_size = sum(f.stat().st_size for f in cache_files)
        
        return {
            'total_files': len(cache_files),
            'total_size_mb': total_size / (1024 * 1024),
            'cache_dir': str(self.cache_dir)
        }
    
    def _hash_key(self, key: str) -> str:
        """生成缓存键的哈希值"""
        return hashlib.md5(key.encode()).hexdigest()
    
    def _cleanup_expired(self):
        """清理过期缓存"""
        for cache_file in self.cache_dir.glob('*.json'):
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                cached_time = datetime.fromisoformat(data['timestamp'])
                if datetime.now() - cached_time > timedelta(days=self.ttl_days):
                    cache_file.unlink()
            except Exception:
                pass
    
    def _check_cache_size(self):
        """检查缓存大小"""
        cache_files = list(self.cache_dir.glob('*.json'))
        total_size_mb = sum(f.stat().st_size for f in cache_files) / (1024 * 1024)
        
        if total_size_mb > self.max_size_mb:
            # 按时间排序，删除最旧的缓存
            cache_files.sort(key=lambda f: f.stat().st_mtime)
            while total_size_mb > self.max_size_mb * 0.8 and cache_files:
                oldest_file = cache_files.pop(0)
                total_size_mb -= oldest_file.stat().st_size / (1024 * 1024)
                oldest_file.unlink()
```

### 3. ConfigManager (统一配置管理器)

#### 设计目标
- 统一配置加载
- 配置验证
- 配置更新
- 支持多种配置源

#### 接口定义

```python
class ConfigManager:
    """统一配置管理器"""
    
    _instance = None
    
    @classmethod
    def get_instance(cls, config_file: str = None):
        """获取单例实例"""
        if cls._instance is None:
            cls._instance = cls(config_file)
        return cls._instance
    
    def __init__(self, config_file: str = None):
        """初始化配置管理器"""
        if hasattr(self, 'initialized'):
            return
        
        self.config_file = config_file or self._get_default_config_file()
        self.config = self._load_config()
        self.initialized = True
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        获取配置值
        
        Args:
            key: 配置键（支持点号分隔的路径）
            default: 默认值
            
        Returns:
            Any: 配置值
        """
        keys = key.split('.')
        value = self.config
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
    
    def set(self, key: str, value: Any):
        """
        设置配置值
        
        Args:
            key: 配置键
            value: 配置值
        """
        keys = key.split('.')
        config = self.config
        
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        
        config[keys[-1]] = value
        self._save_config()
    
    def get_api_config(self, provider: str) -> dict:
        """获取API配置"""
        return self.get(f'api_providers.{provider}', {})
    
    def get_search_config(self, platform: str) -> dict:
        """获取搜索配置"""
        return self.get(f'search_platforms.{platform}', {})
    
    def _load_config(self) -> dict:
        """加载配置文件"""
        if not os.path.exists(self.config_file):
            return self._get_default_config()
        
        with open(self.config_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def _save_config(self):
        """保存配置文件"""
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(self.config, f, ensure_ascii=False, indent=2)
    
    def _get_default_config_file(self) -> str:
        """获取默认配置文件路径"""
        return os.path.join(
            os.path.dirname(__file__),
            '..',
            'config',
            'default_config.json'
        )
    
    def _get_default_config(self) -> dict:
        """获取默认配置"""
        return {
            'api_providers': {
                'qwen': {
                    'provider': 'dashscope',
                    'model': 'qwen-plus',
                    'api_key_env': 'DASHSCOPE_API_KEY'
                },
                'openai': {
                    'provider': 'openai',
                    'model': 'gpt-4',
                    'api_key_env': 'OPENAI_API_KEY'
                },
                'minimax': {
                    'provider': 'minimax',
                    'model': 'abab6-chat',
                    'api_key_env': 'MINIMAX_API_KEY'
                }
            },
            'search_platforms': {
                'github': {
                    'enabled': True,
                    'base_url': 'https://api.github.com',
                    'rate_limit': 60
                },
                'arxiv': {
                    'enabled': True,
                    'base_url': 'http://export.arxiv.org/api/query',
                    'rate_limit': 30
                },
                'paperswithcode': {
                    'enabled': True,
                    'base_url': 'https://paperswithcode.com/api/v1',
                    'rate_limit': 30
                }
            },
            'cache': {
                'enabled': True,
                'ttl_days': 7,
                'max_size_mb': 100
            }
        }
```

### 4. DataModels (统一数据模型)

#### 设计目标
- 统一数据格式
- 类型安全
- 易于序列化
- 支持验证

#### 数据模型定义

```python
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional
from datetime import datetime
import json

@dataclass
class SearchResult:
    """统一搜索结果模型"""
    
    id: str
    title: str
    source: str  # 'github', 'arxiv', 'paperswithcode'
    url: str
    description: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    score: float = 0.0
    tags: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return asdict(self)
    
    def to_json(self) -> str:
        """转换为JSON字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)
    
    @classmethod
    def from_dict(cls, data: dict) -> 'SearchResult':
        """从字典创建实例"""
        return cls(**data)

@dataclass
class AnalysisResult:
    """统一分析结果模型"""
    
    source_id: str
    analysis_type: str  # 'project', 'paper', 'literature'
    summary: str
    key_findings: List[str] = field(default_factory=list)
    technical_points: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    confidence: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return asdict(self)
    
    def to_json(self) -> str:
        """转换为JSON字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)
    
    @classmethod
    def from_dict(cls, data: dict) -> 'AnalysisResult':
        """从字典创建实例"""
        return cls(**data)

@dataclass
class Report:
    """统一报告模型"""
    
    title: str
    content: str
    format: str  # 'markdown', 'json', 'html'
    sections: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return asdict(self)
    
    def to_json(self) -> str:
        """转换为JSON字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)
    
    def save(self, filepath: str):
        """保存报告到文件"""
        with open(filepath, 'w', encoding='utf-8') as f:
            if self.format == 'markdown':
                f.write(self.content)
            else:
                f.write(self.to_json())
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Report':
        """从字典创建实例"""
        return cls(**data)

@dataclass
class ImprovementSuggestion:
    """改进建议模型"""
    
    module_name: str
    context: str
    short_term: List[str] = field(default_factory=list)
    medium_term: List[str] = field(default_factory=list)
    long_term: List[str] = field(default_factory=list)
    code_examples: List[str] = field(default_factory=list)
    priority: str = 'medium'  # 'high', 'medium', 'low'
    confidence: float = 0.0
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> 'ImprovementSuggestion':
        """从字典创建实例"""
        return cls(**data)
```

---

## 🔍 搜索层设计

### 1. ProjectFinder (项目搜寻器)

#### 接口定义

```python
class ProjectFinder:
    """项目搜寻器"""
    
    def __init__(self):
        self.llm = LLMManager.get_instance()
        self.cache = CacheManager()
        self.adapters = {
            'github': GitHubAdapter(),
            'paperswithcode': PapersWithCodeAdapter()
        }
    
    def search(
        self,
        query: str,
        platforms: List[str] = None,
        limit: int = 50
    ) -> List[SearchResult]:
        """
        搜索项目
        
        Args:
            query: 搜索查询
            platforms: 平台列表
            limit: 结果数量限制
            
        Returns:
            List[SearchResult]: 搜索结果列表
        """
        if platforms is None:
            platforms = list(self.adapters.keys())
        
        # 检查缓存
        cache_key = f"project_search:{query}:{','.join(platforms)}:{limit}"
        cached = self.cache.get(cache_key)
        if cached:
            return [SearchResult.from_dict(r) for r in cached]
        
        # 执行搜索
        all_results = []
        for platform in platforms:
            if platform in self.adapters:
                adapter = self.adapters[platform]
                results = adapter.search(query, limit)
                all_results.extend(results)
        
        # 排序和限制
        all_results.sort(key=lambda x: x.score, reverse=True)
        results = all_results[:limit]
        
        # 缓存结果
        self.cache.set(cache_key, [r.to_dict() for r in results])
        
        return results
```

### 2. PaperFinder (论文搜寻器)

#### 接口定义

```python
class PaperFinder:
    """论文搜寻器"""
    
    def __init__(self):
        self.llm = LLMManager.get_instance()
        self.cache = CacheManager()
        self.adapters = {
            'arxiv': ArxivAdapter(),
            'paperswithcode': PapersWithCodeAdapter()
        }
    
    def search(
        self,
        query: str,
        sources: List[str] = None,
        limit: int = 50
    ) -> List[SearchResult]:
        """
        搜索论文
        
        Args:
            query: 搜索查询
            sources: 数据源列表
            limit: 结果数量限制
            
        Returns:
            List[SearchResult]: 搜索结果列表
        """
        if sources is None:
            sources = list(self.adapters.keys())
        
        # 检查缓存
        cache_key = f"paper_search:{query}:{','.join(sources)}:{limit}"
        cached = self.cache.get(cache_key)
        if cached:
            return [SearchResult.from_dict(r) for r in cached]
        
        # 执行搜索
        all_results = []
        for source in sources:
            if source in self.adapters:
                adapter = self.adapters[source]
                results = adapter.search(query, limit)
                all_results.extend(results)
        
        # 排序和限制
        all_results.sort(key=lambda x: x.score, reverse=True)
        results = all_results[:limit]
        
        # 缓存结果
        self.cache.set(cache_key, [r.to_dict() for r in results])
        
        return results
```

---

## 📊 分析层设计

### 1. ProjectAnalyzer (项目分析器)

#### 接口定义

```python
class ProjectAnalyzer:
    """项目分析器"""
    
    def __init__(self):
        self.llm = LLMManager.get_instance()
        self.cache = CacheManager()
    
    def analyze(
        self,
        project: SearchResult,
        analysis_depth: str = 'deep'
    ) -> AnalysisResult:
        """
        分析项目
        
        Args:
            project: 项目搜索结果
            analysis_depth: 分析深度 ('shallow', 'medium', 'deep')
            
        Returns:
            AnalysisResult: 分析结果
        """
        # 检查缓存
        cache_key = f"project_analysis:{project.id}:{analysis_depth}"
        cached = self.cache.get(cache_key)
        if cached:
            return AnalysisResult.from_dict(cached)
        
        # 获取README内容
        readme_content = self._fetch_readme(project.url)
        
        # 构建分析提示词
        prompt = self._build_analysis_prompt(project, readme_content, analysis_depth)
        
        # 调用LLM分析
        response = self.llm.call_json(
            prompt=prompt,
            system_prompt=self._get_system_prompt()
        )
        
        # 构建分析结果
        result = AnalysisResult(
            source_id=project.id,
            analysis_type='project',
            summary=response.get('summary', ''),
            key_findings=response.get('key_findings', []),
            technical_points=response.get('technical_points', []),
            recommendations=response.get('recommendations', []),
            confidence=response.get('confidence', 0.8)
        )
        
        # 缓存结果
        self.cache.set(cache_key, result.to_dict())
        
        return result
```

---

## 🎨 生成层设计

### 1. ReportGenerator (报告生成器)

#### 接口定义

```python
class ReportGenerator:
    """报告生成器"""
    
    def __init__(self):
        self.llm = LLMManager.get_instance()
        self.cache = CacheManager()
    
    def generate(
        self,
        search_results: List[SearchResult],
        analysis_results: List[AnalysisResult],
        format: str = 'markdown'
    ) -> Report:
        """
        生成综合报告
        
        Args:
            search_results: 搜索结果列表
            analysis_results: 分析结果列表
            format: 报告格式 ('markdown', 'json', 'html')
            
        Returns:
            Report: 生成的报告
        """
        # 构建报告提示词
        prompt = self._build_report_prompt(search_results, analysis_results)
        
        # 调用LLM生成报告
        content = self.llm.call(
            prompt=prompt,
            system_prompt=self._get_system_prompt()
        )
        
        # 构建报告对象
        report = Report(
            title=self._generate_title(search_results),
            content=content,
            format=format,
            sections=self._extract_sections(content)
        )
        
        return report
```

---

## 🔄 数据流转设计

### 完整工作流

```
用户请求
    ↓
IntelligentResearchAssistant.analyze_module_optimization()
    ↓
    ├─→ ProjectFinder.search() → List[SearchResult]
    │       ↓
    │   GitHubAdapter.search()
    │   PapersWithCodeAdapter.search()
    │       ↓
    │   CacheManager (缓存结果)
    │
    ├─→ PaperFinder.search() → List[SearchResult]
    │       ↓
    │   ArxivAdapter.search()
    │   PapersWithCodeAdapter.search()
    │       ↓
    │   CacheManager (缓存结果)
    │
    ├─→ ProjectAnalyzer.analyze() → List[AnalysisResult]
    │       ↓
    │   LLMManager.call_json()
    │       ↓
    │   CacheManager (缓存结果)
    │
    ├─→ PaperAnalyzer.analyze() → List[AnalysisResult]
    │       ↓
    │   LLMManager.call_json()
    │       ↓
    │   CacheManager (缓存结果)
    │
    ├─→ ReportGenerator.generate() → Report
    │       ↓
    │   LLMManager.call()
    │       ↓
    │   Markdown格式报告
    │
    └─→ ImprovementGenerator.generate() → ImprovementSuggestion
            ↓
        LLMManager.call_json()
            ↓
        改进建议
```

---

## ✅ 设计确认清单

### 核心层设计
- [x] LLMManager接口定义
- [x] CacheManager接口定义
- [x] ConfigManager接口定义
- [x] DataModels定义

### 搜索层设计
- [x] ProjectFinder接口定义
- [x] PaperFinder接口定义
- [x] DocumentFetcher接口定义

### 分析层设计
- [x] ProjectAnalyzer接口定义
- [x] PaperAnalyzer接口定义
- [x] LiteratureAnalyzer接口定义

### 生成层设计
- [x] ReportGenerator接口定义
- [x] ImprovementGenerator接口定义

### 数据流转设计
- [x] 完整工作流定义
- [x] 数据模型转换
- [x] 缓存策略

---

**架构师**: AI History Research Tools Team
**确认日期**: 2026-04-01
**下次审查**: 核心层开发完成后
