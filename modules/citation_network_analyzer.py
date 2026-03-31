"""
引文网络分析模块

分析和可视化学术文献的引文网络
支持构建知识图谱、识别学术流派等

核心功能：
- 从文献中提取引用关系
- 构建引文网络图谱
- 分析理论演进脉络
- 识别学术流派及其分支
- 发现边缘但有启发性的研究
- 可视化输出

依赖模块：
- data_structurer.py
"""

import re
import json
from typing import Dict, List, Optional, Any, Tuple, Set
from collections import defaultdict, Counter
from pathlib import Path
from datetime import datetime


class CitationNetworkAnalyzer:
    """引文网络分析器"""
    
    CITATION_PATTERNS = {
        'japanese': [
            r'(?:[^（）\(\)]+?)[\[（]([^）\)]+?)[\]）]',
            r'(?:[^""'']+?)「([^""''「」]+?)」',
            r'\[(\d+)\]',
            r'（\d+）'
        ],
        'chinese': [
            r'(?:[^（）\(\)]+?)[\[（]([^）\)]+?)[\]）]',
            r'(?:[^""'']+?)『([^""''『』]+?)』',
            r'\[(\d+)\]',
            r'（\d+）'
        ],
        'english': [
            r'\(([A-Za-z]+(?:,?\s*(?:et\s*al\.|&)?\s*[A-Za-z]+)?(?:\s*\(\d{4}\))?(?:,\s*\d+(?:-\d+)?)?)\)',
            r'\[(\d+)\]',
            r'([A-Za-z]+\s+et\s+al\.,?\s+\d{4})'
        ]
    }
    
    def __init__(self):
        """初始化引文网络分析器"""
        self.citation_graph = {
            'nodes': [],
            'edges': [],
            'metadata': {}
        }
        
        self.documents = {}
        self.citations = defaultdict(list)
        self.cited_by = defaultdict(list)
        
        self.academic_schools = []
        self.evolution_timeline = []
    
    def extract_citations(self, text: str, 
                         language: str = 'chinese') -> List[Dict[str, str]]:
        """
        从文献中提取引用关系
        
        Args:
            text: 文献文本
            language: 语言类型 ('chinese', 'japanese', 'english')
            
        Returns:
            list: 提取的引用列表
        """
        citations = []
        patterns = self.CITATION_PATTERNS.get(language, self.CITATION_PATTERNS['chinese'])
        
        for pattern in patterns:
            matches = re.findall(pattern, text)
            
            for match in matches:
                citation = self._parse_citation(match.strip())
                
                if citation and citation not in citations:
                    citations.append(citation)
        
        return citations
    
    def build_citation_graph(self, documents: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        构建引文网络图谱
        
        Args:
            documents: 文献列表，每项包含title、text、metadata
            
        Returns:
            dict: 引文图谱数据
        """
        nodes = []
        edges = []
        
        for i, doc in enumerate(documents):
            title = doc.get('title', f'文档{i}')
            doc_id = self._generate_doc_id(title)
            
            nodes.append({
                'id': doc_id,
                'label': title,
                'title': title,
                'authors': doc.get('authors', []),
                'year': doc.get('year', ''),
                'type': 'source',
                'metadata': doc.get('metadata', {})
            })
            
            self.documents[doc_id] = {
                'title': title,
                'text': doc.get('text', ''),
                'metadata': doc.get('metadata', {})
            }
        
        for doc_id, doc_data in self.documents.items():
            text = doc_data.get('text', '')
            
            citations = self.extract_citations(text)
            
            for cited_doc in citations:
                cited_title = cited_doc.get('title', '')
                
                cited_doc_id = None
                for existing_id, existing_doc in self.documents.items():
                    if cited_title and (
                        cited_title in existing_doc['title'] or 
                        existing_doc['title'] in cited_title
                    ):
                        cited_doc_id = existing_id
                        break
                
                if cited_doc_id and cited_doc_id != doc_id:
                    edges.append({
                        'source': doc_id,
                        'target': cited_doc_id,
                        'type': 'cites',
                        'strength': cited_doc.get('page', '')
                    })
                    
                    self.citations[doc_id].append(cited_doc_id)
                    self.cited_by[cited_doc_id].append(doc_id)
        
        for doc_id, doc_data in self.documents.items():
            if doc_id not in self.citations or not self.citations[doc_id]:
                for node in nodes:
                    if node['id'] == doc_id:
                        node['type'] = 'foundational'
        
        self.citation_graph = {
            'nodes': nodes,
            'edges': edges,
            'metadata': {
                'total_nodes': len(nodes),
                'total_edges': len(edges),
                'source_documents': len(documents)
            }
        }
        
        return self.citation_graph
    
    def analyze_academic_evolution(self) -> List[Dict[str, Any]]:
        """
        分析理论演进脉络
        
        Returns:
            list: 演进时间线
        """
        if not self.citation_graph['nodes']:
            return []
        
        timeline = []
        
        nodes_by_year = defaultdict(list)
        for node in self.citation_graph['nodes']:
            year = node.get('year', '')
            if year:
                nodes_by_year[year].append(node)
        
        sorted_years = sorted(nodes_by_year.keys())
        
        for year in sorted_years:
            year_nodes = nodes_by_year[year]
            
            works_count = len(year_nodes)
            
            foundational_works = [
                n for n in year_nodes 
                if n.get('type') == 'foundational'
            ]
            
            cited_by_count = 0
            for node in year_nodes:
                cited_by_count += len(self.cited_by.get(node['id'], []))
            
            timeline.append({
                'year': year,
                'works_count': works_count,
                'foundational_works': [
                    w['title'] for w in foundational_works
                ],
                'total_citations': cited_by_count,
                'key_works': [
                    n['title'] for n in year_nodes[:3]
                ]
            })
        
        self.evolution_timeline = timeline
        return timeline
    
    def identify_academic_schools(self) -> List[Dict[str, Any]]:
        """
        识别学术流派及其分支
        
        Returns:
            list: 学术流派列表
        """
        if not self.citation_graph['nodes']:
            return []
        
        schools = []
        
        citation_counts = {}
        for doc_id, cited_list in self.citations.items():
            citation_counts[doc_id] = len(cited_list)
        
        highly_cited = [
            (doc_id, count) 
            for doc_id, count in citation_counts.items() 
            if count >= 2
        ]
        highly_cited.sort(key=lambda x: x[1], reverse=True)
        
        for doc_id, count in highly_cited[:5]:
            for node in self.citation_graph['nodes']:
                if node['id'] == doc_id:
                    school_node = node
                    break
            
            members = []
            
            for edge in self.citation_graph['edges']:
                if edge['source'] == doc_id:
                    for node in self.citation_graph['nodes']:
                        if node['id'] == edge['target']:
                            members.append({
                                'id': node['id'],
                                'title': node['title'],
                                'authors': node.get('authors', []),
                                'year': node.get('year', '')
                            })
            
            schools.append({
                'id': f"school_{len(schools) + 1}",
                'founder': school_node['title'],
                'founder_id': doc_id,
                'members': members,
                'member_count': len(members),
                'citation_count': count,
                'description': f"以《{school_node['title']}》为核心的学术流派"
            })
        
        self.academic_schools = schools
        return schools
    
    def find_peripheral_works(self, 
                             centrality_threshold: float = 0.1) -> List[Dict[str, Any]]:
        """
        发现边缘但有启发性的研究
        
        Args:
            centrality_threshold: 中心性阈值
            
        Returns:
            list: 边缘作品列表
        """
        if not self.citation_graph['nodes']:
            return []
        
        centrality_scores = self._calculate_centrality()
        
        peripheral_works = []
        
        for node in self.citation_graph['nodes']:
            node_id = node['id']
            
            centrality = centrality_scores.get(node_id, 0)
            
            if centrality < centrality_threshold:
                cited_by_count = len(self.cited_by.get(node_id, []))
                
                if cited_by_count > 0:
                    peripheral_works.append({
                        'id': node_id,
                        'title': node['title'],
                        'authors': node.get('authors', []),
                        'year': node.get('year', ''),
                        'centrality': centrality,
                        'cited_by_count': cited_by_count,
                        'novelty_score': self._calculate_novelty(node_id)
                    })
        
        peripheral_works.sort(key=lambda x: x['novelty_score'], reverse=True)
        
        return peripheral_works[:10]
    
    def get_citation_statistics(self) -> Dict[str, Any]:
        """
        获取引文统计信息
        
        Returns:
            dict: 统计信息
        """
        if not self.citation_graph['nodes']:
            return {}
        
        all_citations = []
        for cited_list in self.citations.values():
            all_citations.extend(cited_list)
        
        citation_counts = Counter(all_citations)
        
        most_cited = []
        for doc_id, count in citation_counts.most_common(10):
            for node in self.citation_graph['nodes']:
                if node['id'] == doc_id:
                    most_cited.append({
                        'id': doc_id,
                        'title': node['title'],
                        'authors': node.get('authors', []),
                        'citation_count': count
                    })
                    break
        
        return {
            'total_documents': len(self.documents),
            'total_citations': len(all_citations),
            'avg_citations_per_doc': len(all_citations) / len(self.documents) if self.documents else 0,
            'most_cited_works': most_cited,
            'isolated_documents': len([
                n for n in self.citation_graph['nodes']
                if not self.citations.get(n['id']) and not self.cited_by.get(n['id'])
            ])
        }
    
    def generate_graph_export(self, format: str = 'json') -> str:
        """
        生成图谱导出数据
        
        Args:
            format: 导出格式 ('json', 'gexf', 'csv')
            
        Returns:
            str: 格式化后的图谱数据
        """
        if format == 'json':
            return json.dumps(self.citation_graph, ensure_ascii=False, indent=2)
        
        elif format == 'gexf':
            return self._export_as_gexf()
        
        elif format == 'csv':
            return self._export_as_csv()
        
        else:
            return json.dumps(self.citation_graph, ensure_ascii=False)
    
    def visualize_as_markdown(self) -> str:
        """
        生成Markdown格式的可视化报告
        
        Returns:
            str: Markdown报告
        """
        lines = [
            "# 引文网络分析报告",
            "",
            f"**分析时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "## 基本统计",
            "",
            f"- 总文档数: {self.citation_graph['metadata'].get('total_nodes', 0)}",
            f"- 总引用关系数: {self.citation_graph['metadata'].get('total_edges', 0)}",
            "",
            "## 引用统计",
            ""
        ]
        
        stats = self.get_citation_statistics()
        if stats.get('most_cited_works'):
            lines.append("### 高被引文献")
            lines.append("")
            for work in stats['most_cited_works'][:5]:
                authors = ', '.join(work.get('authors', [])[:2])
                lines.append(f"- **{work['title']}**")
                lines.append(f"  - 作者: {authors}")
                lines.append(f"  - 被引次数: {work['citation_count']}")
                lines.append("")
        
        if self.academic_schools:
            lines.extend([
                "## 学术流派",
                ""
            ])
            
            for school in self.academic_schools:
                lines.append(f"### {school['founder']}")
                lines.append(f"- 核心成员数: {school['member_count']}")
                lines.append(f"- 引用次数: {school['citation_count']}")
                lines.append(f"- 描述: {school['description']}")
                lines.append("")
        
        if self.evolution_timeline:
            lines.extend([
                "## 理论演进时间线",
                ""
            ])
            
            for entry in self.evolution_timeline[:10]:
                lines.append(f"### {entry['year']}年")
                lines.append(f"- 发表作品数: {entry['works_count']}")
                if entry.get('key_works'):
                    lines.append(f"- 重要作品: {', '.join(entry['key_works'][:2])}")
                lines.append("")
        
        if self.find_peripheral_works():
            lines.extend([
                "## 边缘创新研究",
                ""
            ])
            
            peripheral = self.find_peripheral_works()[:5]
            for work in peripheral:
                lines.append(f"- **{work['title']}**")
                lines.append(f"  - 发表年份: {work['year']}")
                lines.append(f"  - 创新性评分: {work['novelty_score']:.2f}")
                lines.append("")
        
        return '\n'.join(lines)
    
    def add_document(self, document: Dict[str, Any]) -> bool:
        """
        向网络中添加新文档
        
        Args:
            document: 文档数据
            
        Returns:
            bool: 是否添加成功
        """
        try:
            title = document.get('title')
            doc_id = self._generate_doc_id(title)
            
            if doc_id in self.documents:
                return False
            
            self.documents[doc_id] = {
                'title': title,
                'text': document.get('text', ''),
                'metadata': document.get('metadata', {})
            }
            
            node = {
                'id': doc_id,
                'label': title,
                'title': title,
                'authors': document.get('authors', []),
                'year': document.get('year', ''),
                'type': 'source',
                'metadata': document.get('metadata', {})
            }
            
            self.citation_graph['nodes'].append(node)
            self.citation_graph['metadata']['total_nodes'] += 1
            
            text = document.get('text', '')
            citations = self.extract_citations(text)
            
            for cited_doc in citations:
                cited_title = cited_doc.get('title', '')
                
                cited_doc_id = None
                for existing_id, existing_doc in self.documents.items():
                    if cited_title and (
                        cited_title in existing_doc['title'] or
                        existing_doc['title'] in cited_title
                    ):
                        cited_doc_id = existing_id
                        break
                
                if cited_doc_id:
                    edge = {
                        'source': doc_id,
                        'target': cited_doc_id,
                        'type': 'cites',
                        'strength': cited_doc.get('page', '')
                    }
                    
                    self.citation_graph['edges'].append(edge)
                    self.citation_graph['metadata']['total_edges'] += 1
                    
                    self.citations[doc_id].append(cited_doc_id)
                    self.cited_by[cited_doc_id].append(doc_id)
            
            return True
        except Exception as e:
            print(f"添加文档失败: {e}")
            return False
    
    def _parse_citation(self, citation_str: str) -> Dict[str, str]:
        """解析引用字符串"""
        citation = {'raw': citation_str}
        
        year_match = re.search(r'\d{4}', citation_str)
        if year_match:
            citation['year'] = year_match.group()
        
        title_match = re.search(r'[『""''「」（）(）《》]([^『""''「」（）(）《》]+)[』""''「」（）(）《》]', citation_str)
        if title_match:
            citation['title'] = title_match.group(1)
        else:
            citation['title'] = re.sub(r'\[\d+\]|\(\d{4}\)', '', citation_str).strip()
        
        page_match = re.search(r'[pp.]?\s*(\d+)(?:-(\d+))?', citation_str)
        if page_match:
            citation['page'] = page_match.group()
        
        return citation
    
    def _generate_doc_id(self, title: str) -> str:
        """生成文档ID"""
        import hashlib
        hash_obj = hashlib.md5(title.encode('utf-8'))
        return f"doc_{hash_obj.hexdigest()[:8]}"
    
    def _calculate_centrality(self) -> Dict[str, float]:
        """计算节点中心性"""
        centrality = {}
        
        for doc_id in self.documents.keys():
            cited_by_count = len(self.cited_by.get(doc_id, []))
            cites_count = len(self.citations.get(doc_id, []))
            
            centrality[doc_id] = (cited_by_count + cites_count) / (len(self.documents) * 2)
        
        return centrality
    
    def _calculate_novelty_score(self, doc_id: str) -> float:
        """计算创新性评分"""
        cited_by_count = len(self.cited_by.get(doc_id, []))
        cites_count = len(self.citations.get(doc_id, []))
        
        if cites_count > 0:
            novelty = cited_by_count / cites_count
        else:
            novelty = cited_by_count * 0.5
        
        return min(novelty, 1.0)
    
    def _export_as_gexf(self) -> str:
        """导出为GEXF格式（用于Gephi等工具）"""
        lines = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<gexf xmlns="http://www.gexf.net/1.3" version="1.3">',
            '  <graph mode="static" defaultedgettype="directed">',
            '    <attributes class="node">',
            '      <attribute id="0" title="title" type="string"/>',
            '      <attribute id="1" title="authors" type="string"/>',
            '      <attribute id="2" title="year" type="string"/>',
            '    </attributes>',
            '    <nodes>'
        ]
        
        for node in self.citation_graph['nodes']:
            lines.append(
                f'      <node id="{node["id"]}" label="{node["label"]}">'
            )
            lines.append(
                f'        <attvalues>'
            )
            lines.append(f'          <attvalue for="0" value="{node.get("title", "")}"/>')
            lines.append(f'          <attvalue for="1" value="{",".join(node.get("authors", []))}"/>')
            lines.append(f'          <attvalue for="2" value="{node.get("year", "")}"/>')
            lines.append(
                f'        </attvalues>'
            )
            lines.append(
                f'      </node>'
            )
        
        lines.append('    </nodes>')
        lines.append('    <edges>')
        
        for i, edge in enumerate(self.citation_graph['edges']):
            lines.append(
                f'      <edge id="{i}" source="{edge["source"]}" target="{edge["target"]}" />'
            )
        
        lines.append('    </edges>')
        lines.append('  </graph>')
        lines.append('</gexf>')
        
        return '\n'.join(lines)
    
    def _export_as_csv(self) -> str:
        """导出为CSV格式"""
        lines = ['Source,Target,Type']
        
        for edge in self.citation_graph['edges']:
            lines.append(
                f'"{edge["source"]}","{edge["target"]}","{edge["type"]}"'
            )
        
        return '\n'.join(lines)


def create_citation_analyzer() -> CitationNetworkAnalyzer:
    """
    工厂函数：创建引文网络分析器实例
    
    Returns:
        CitationNetworkAnalyzer: 分析器实例
    """
    return CitationNetworkAnalyzer()
