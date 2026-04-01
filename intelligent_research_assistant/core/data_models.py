"""
统一数据模型

提供统一的数据结构，支持类型安全、序列化和验证
"""

import json
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path


@dataclass
class SearchResult:
    """
    统一搜索结果模型
    
    用于表示从各个平台搜索到的项目或论文
    """
    
    id: str
    title: str
    source: str
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
    
    @classmethod
    def from_json(cls, json_str: str) -> 'SearchResult':
        """从JSON字符串创建实例"""
        data = json.loads(json_str)
        return cls.from_dict(data)
    
    def __repr__(self):
        return f"SearchResult(id={self.id}, title={self.title[:30]}..., source={self.source})"


@dataclass
class AnalysisResult:
    """
    统一分析结果模型
    
    用于表示对项目或论文的深度分析结果
    """
    
    source_id: str
    analysis_type: str
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
    
    @classmethod
    def from_json(cls, json_str: str) -> 'AnalysisResult':
        """从JSON字符串创建实例"""
        data = json.loads(json_str)
        return cls.from_dict(data)
    
    def __repr__(self):
        return f"AnalysisResult(source_id={self.source_id}, type={self.analysis_type}, confidence={self.confidence})"


@dataclass
class Report:
    """
    统一报告模型
    
    用于表示生成的综合报告
    """
    
    title: str
    content: str
    format: str = 'markdown'
    sections: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return asdict(self)
    
    def to_json(self) -> str:
        """转换为JSON字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Report':
        """从字典创建实例"""
        return cls(**data)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'Report':
        """从JSON字符串创建实例"""
        data = json.loads(json_str)
        return cls.from_dict(data)
    
    def save(self, filepath: str):
        """
        保存报告到文件
        
        Args:
            filepath: 文件路径
        """
        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            if self.format == 'markdown':
                f.write(self.content)
            else:
                f.write(self.to_json())
    
    @classmethod
    def load(cls, filepath: str) -> 'Report':
        """
        从文件加载报告
        
        Args:
            filepath: 文件路径
            
        Returns:
            Report: 报告实例
        """
        filepath = Path(filepath)
        
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        if filepath.suffix == '.json':
            return cls.from_json(content)
        else:
            return cls(
                title=filepath.stem,
                content=content,
                format='markdown'
            )
    
    def __repr__(self):
        return f"Report(title={self.title}, format={self.format}, sections={len(self.sections)})"


@dataclass
class ImprovementSuggestion:
    """
    改进建议模型
    
    用于表示针对模块或项目的改进建议
    """
    
    module_name: str
    context: str
    short_term: List[str] = field(default_factory=list)
    medium_term: List[str] = field(default_factory=list)
    long_term: List[str] = field(default_factory=list)
    code_examples: List[str] = field(default_factory=list)
    priority: str = 'medium'
    confidence: float = 0.0
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return asdict(self)
    
    def to_json(self) -> str:
        """转换为JSON字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)
    
    @classmethod
    def from_dict(cls, data: dict) -> 'ImprovementSuggestion':
        """从字典创建实例"""
        return cls(**data)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'ImprovementSuggestion':
        """从JSON字符串创建实例"""
        data = json.loads(json_str)
        return cls.from_dict(data)
    
    def __repr__(self):
        return f"ImprovementSuggestion(module={self.module_name}, priority={self.priority}, confidence={self.confidence})"


@dataclass
class TrendAnalysis:
    """
    趋势分析模型
    
    用于表示技术趋势分析结果
    """
    
    technology: str
    time_range: str
    overview: str
    key_trends: List[str] = field(default_factory=list)
    emerging_technologies: List[str] = field(default_factory=list)
    declining_technologies: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    statistics: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return asdict(self)
    
    def to_json(self) -> str:
        """转换为JSON字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)
    
    @classmethod
    def from_dict(cls, data: dict) -> 'TrendAnalysis':
        """从字典创建实例"""
        return cls(**data)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'TrendAnalysis':
        """从JSON字符串创建实例"""
        data = json.loads(json_str)
        return cls.from_dict(data)
    
    def __repr__(self):
        return f"TrendAnalysis(tech={self.technology}, range={self.time_range})"


@dataclass
class CompetitorAnalysis:
    """
    竞品分析模型
    
    用于表示竞品分析结果
    """
    
    product_type: str
    competitors: List[Dict[str, Any]] = field(default_factory=list)
    comparison_matrix: Dict[str, Any] = field(default_factory=dict)
    strengths: List[str] = field(default_factory=list)
    weaknesses: List[str] = field(default_factory=list)
    opportunities: List[str] = field(default_factory=list)
    threats: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return asdict(self)
    
    def to_json(self) -> str:
        """转换为JSON字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)
    
    @classmethod
    def from_dict(cls, data: dict) -> 'CompetitorAnalysis':
        """从字典创建实例"""
        return cls(**data)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'CompetitorAnalysis':
        """从JSON字符串创建实例"""
        data = json.loads(json_str)
        return cls.from_dict(data)
    
    def __repr__(self):
        return f"CompetitorAnalysis(type={self.product_type}, competitors={len(self.competitors)})"


def test_data_models():
    """测试数据模型"""
    print("\n=== 测试数据模型 ===\n")
    
    search_result = SearchResult(
        id='test-001',
        title='测试项目',
        source='github',
        url='https://github.com/test/test',
        description='这是一个测试项目',
        score=0.95,
        tags=['python', 'ai']
    )
    print(f"1. SearchResult: {search_result}")
    print(f"   JSON: {search_result.to_json()[:100]}...")
    
    analysis_result = AnalysisResult(
        source_id='test-001',
        analysis_type='project',
        summary='这是一个优秀的项目',
        key_findings=['发现1', '发现2'],
        technical_points=['技术点1', '技术点2'],
        recommendations=['建议1', '建议2'],
        confidence=0.85
    )
    print(f"\n2. AnalysisResult: {analysis_result}")
    
    report = Report(
        title='测试报告',
        content='# 测试报告\n\n这是一个测试报告内容。',
        format='markdown',
        sections=[{'title': '概述', 'content': '测试概述'}]
    )
    print(f"\n3. Report: {report}")
    
    suggestion = ImprovementSuggestion(
        module_name='test_module',
        context='测试上下文',
        short_term=['短期建议1'],
        medium_term=['中期建议1'],
        long_term=['长期建议1'],
        priority='high',
        confidence=0.9
    )
    print(f"\n4. ImprovementSuggestion: {suggestion}")
    
    trend = TrendAnalysis(
        technology='AI',
        time_range='12months',
        overview='AI技术快速发展',
        key_trends=['趋势1', '趋势2'],
        emerging_technologies=['新技术1'],
        declining_technologies=['旧技术1']
    )
    print(f"\n5. TrendAnalysis: {trend}")
    
    competitor = CompetitorAnalysis(
        product_type='OCR工具',
        competitors=[{'name': '竞品1', 'features': ['特性1']}],
        strengths=['优势1'],
        weaknesses=['劣势1'],
        opportunities=['机会1'],
        threats=['威胁1']
    )
    print(f"\n6. CompetitorAnalysis: {competitor}")
    
    print("\n✅ 测试完成")


if __name__ == '__main__':
    test_data_models()
