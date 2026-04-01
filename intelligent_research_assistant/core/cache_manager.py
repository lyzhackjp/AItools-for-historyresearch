"""
统一缓存管理器

提供统一的缓存接口，支持TTL过期机制、自动清理、大小限制
"""

import os
import json
import hashlib
import shutil
from pathlib import Path
from typing import Optional, Any, Dict, List
from datetime import datetime, timedelta


class CacheManager:
    """
    统一缓存管理器
    
    功能：
    - 统一缓存接口
    - TTL过期机制
    - 自动清理过期缓存
    - 大小限制和自动清理
    - 缓存统计和监控
    """
    
    def __init__(
        self,
        cache_dir: str = None,
        ttl_days: int = 7,
        max_size_mb: int = 100,
        auto_cleanup: bool = True
    ):
        """
        初始化缓存管理器
        
        Args:
            cache_dir: 缓存目录
            ttl_days: 缓存有效期（天）
            max_size_mb: 最大缓存大小（MB）
            auto_cleanup: 是否自动清理过期缓存
        """
        if cache_dir is None:
            cache_dir = os.path.join(
                os.path.dirname(__file__),
                '..',
                'storage',
                'cache'
            )
        
        self.cache_dir = Path(cache_dir)
        self.ttl_days = ttl_days
        self.max_size_mb = max_size_mb
        self.auto_cleanup = auto_cleanup
        
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        self.hit_count = 0
        self.miss_count = 0
        
        if auto_cleanup:
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
            self.miss_count += 1
            return None
        
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            cached_time = datetime.fromisoformat(data['timestamp'])
            if datetime.now() - cached_time > timedelta(days=self.ttl_days):
                cache_file.unlink()
                self.miss_count += 1
                return None
            
            self.hit_count += 1
            return data['content']
            
        except Exception as e:
            print(f"[CacheManager] 读取缓存失败: {e}")
            self.miss_count += 1
            return None
    
    def set(
        self,
        key: str,
        value: Any,
        metadata: Dict[str, Any] = None,
        ttl_days: int = None
    ):
        """
        设置缓存
        
        Args:
            key: 缓存键
            value: 缓存值
            metadata: 元数据
            ttl_days: 自定义TTL（天）
        """
        cache_file = self.cache_dir / f"{self._hash_key(key)}.json"
        
        ttl = ttl_days if ttl_days is not None else self.ttl_days
        
        data = {
            'key': key,
            'content': value,
            'timestamp': datetime.now().isoformat(),
            'ttl_days': ttl,
            'metadata': metadata or {}
        }
        
        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            self._check_cache_size()
            
        except Exception as e:
            print(f"[CacheManager] 写入缓存失败: {e}")
    
    def delete(self, key: str) -> bool:
        """
        删除缓存
        
        Args:
            key: 缓存键
            
        Returns:
            bool: 是否成功删除
        """
        cache_file = self.cache_dir / f"{self._hash_key(key)}.json"
        
        if cache_file.exists():
            try:
                cache_file.unlink()
                return True
            except Exception as e:
                print(f"[CacheManager] 删除缓存失败: {e}")
                return False
        
        return False
    
    def exists(self, key: str) -> bool:
        """
        检查缓存是否存在
        
        Args:
            key: 缓存键
            
        Returns:
            bool: 是否存在
        """
        return self.get(key) is not None
    
    def clear(self):
        """清空所有缓存"""
        try:
            for cache_file in self.cache_dir.glob('*.json'):
                cache_file.unlink()
            
            print(f"[CacheManager] 已清空所有缓存")
            
        except Exception as e:
            print(f"[CacheManager] 清空缓存失败: {e}")
    
    def clear_by_prefix(self, prefix: str):
        """
        清除指定前缀的缓存
        
        Args:
            prefix: 缓存键前缀
        """
        count = 0
        
        for cache_file in self.cache_dir.glob('*.json'):
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                if data.get('key', '').startswith(prefix):
                    cache_file.unlink()
                    count += 1
                    
            except Exception:
                pass
        
        print(f"[CacheManager] 已清除 {count} 个前缀为 '{prefix}' 的缓存")
    
    def get_stats(self) -> Dict[str, Any]:
        """
        获取缓存统计信息
        
        Returns:
            dict: 统计信息
        """
        cache_files = list(self.cache_dir.glob('*.json'))
        total_size = sum(f.stat().st_size for f in cache_files)
        
        total_requests = self.hit_count + self.miss_count
        hit_rate = self.hit_count / total_requests if total_requests > 0 else 0
        
        return {
            'total_files': len(cache_files),
            'total_size_mb': round(total_size / (1024 * 1024), 2),
            'cache_dir': str(self.cache_dir),
            'ttl_days': self.ttl_days,
            'max_size_mb': self.max_size_mb,
            'hit_count': self.hit_count,
            'miss_count': self.miss_count,
            'hit_rate': round(hit_rate, 2),
            'auto_cleanup': self.auto_cleanup
        }
    
    def list_keys(self, prefix: str = None) -> List[str]:
        """
        列出所有缓存键
        
        Args:
            prefix: 缓存键前缀（可选）
            
        Returns:
            List[str]: 缓存键列表
        """
        keys = []
        
        for cache_file in self.cache_dir.glob('*.json'):
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                key = data.get('key', '')
                
                if prefix is None or key.startswith(prefix):
                    keys.append(key)
                    
            except Exception:
                pass
        
        return keys
    
    def get_metadata(self, key: str) -> Optional[Dict[str, Any]]:
        """
        获取缓存的元数据
        
        Args:
            key: 缓存键
            
        Returns:
            Optional[Dict]: 元数据
        """
        cache_file = self.cache_dir / f"{self._hash_key(key)}.json"
        
        if not cache_file.exists():
            return None
        
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            return {
                'key': data.get('key'),
                'timestamp': data.get('timestamp'),
                'ttl_days': data.get('ttl_days'),
                'metadata': data.get('metadata', {}),
                'file_size': cache_file.stat().st_size
            }
            
        except Exception as e:
            print(f"[CacheManager] 获取元数据失败: {e}")
            return None
    
    def update_ttl(self, key: str, ttl_days: int) -> bool:
        """
        更新缓存的TTL
        
        Args:
            key: 缓存键
            ttl_days: 新的TTL（天）
            
        Returns:
            bool: 是否成功更新
        """
        cache_file = self.cache_dir / f"{self._hash_key(key)}.json"
        
        if not cache_file.exists():
            return False
        
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            data['ttl_days'] = ttl_days
            
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            return True
            
        except Exception as e:
            print(f"[CacheManager] 更新TTL失败: {e}")
            return False
    
    def _hash_key(self, key: str) -> str:
        """
        生成缓存键的哈希值
        
        Args:
            key: 缓存键
            
        Returns:
            str: 哈希值
        """
        return hashlib.md5(key.encode()).hexdigest()
    
    def _cleanup_expired(self):
        """清理过期缓存"""
        count = 0
        
        for cache_file in self.cache_dir.glob('*.json'):
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                cached_time = datetime.fromisoformat(data['timestamp'])
                ttl = data.get('ttl_days', self.ttl_days)
                
                if datetime.now() - cached_time > timedelta(days=ttl):
                    cache_file.unlink()
                    count += 1
                    
            except Exception:
                pass
        
        if count > 0:
            print(f"[CacheManager] 已清理 {count} 个过期缓存")
    
    def _check_cache_size(self):
        """检查缓存大小并清理"""
        cache_files = list(self.cache_dir.glob('*.json'))
        total_size_mb = sum(f.stat().st_size for f in cache_files) / (1024 * 1024)
        
        if total_size_mb > self.max_size_mb:
            print(f"[CacheManager] 缓存大小 {total_size_mb:.2f}MB 超过限制 {self.max_size_mb}MB，开始清理...")
            
            cache_files.sort(key=lambda f: f.stat().st_mtime)
            
            while total_size_mb > self.max_size_mb * 0.8 and cache_files:
                oldest_file = cache_files.pop(0)
                file_size_mb = oldest_file.stat().st_size / (1024 * 1024)
                total_size_mb -= file_size_mb
                oldest_file.unlink()
            
            print(f"[CacheManager] 清理完成，当前大小 {total_size_mb:.2f}MB")
    
    def __repr__(self):
        stats = self.get_stats()
        return f"CacheManager(files={stats['total_files']}, size={stats['total_size_mb']}MB, hit_rate={stats['hit_rate']})"


def test_cache_manager():
    """测试缓存管理器"""
    print("\n=== 测试缓存管理器 ===\n")
    
    cache = CacheManager(ttl_days=7, max_size_mb=10)
    
    print(f"1. 初始化: {cache}")
    
    cache.set('test_key_1', {'data': '测试数据1'}, metadata={'source': 'test'})
    cache.set('test_key_2', {'data': '测试数据2'}, metadata={'source': 'test'})
    cache.set('test_key_3', {'data': '测试数据3'}, metadata={'source': 'test'})
    
    print(f"\n2. 设置缓存: 3个")
    
    value1 = cache.get('test_key_1')
    print(f"\n3. 获取缓存: {value1}")
    
    exists = cache.exists('test_key_1')
    print(f"\n4. 检查存在: {exists}")
    
    keys = cache.list_keys()
    print(f"\n5. 列出键: {keys}")
    
    metadata = cache.get_metadata('test_key_1')
    print(f"\n6. 元数据: {metadata}")
    
    stats = cache.get_stats()
    print(f"\n7. 统计信息:")
    for key, value in stats.items():
        print(f"   {key}: {value}")
    
    cache.delete('test_key_1')
    print(f"\n8. 删除缓存")
    
    cache.clear_by_prefix('test_key')
    print(f"\n9. 清除前缀缓存")
    
    print("\n✅ 测试完成")


if __name__ == '__main__':
    test_cache_manager()
