"""
日志管理工作流模块

提供统一的日志记录接口，用于：
1. 开发新功能 - feature_development
2. 调试旧功能 - debugging
3. 文件整理 - file_reorganization

所有日志自动归档到 log/ 目录，最新日志同步到根目录。

作者：History Research AI Tools
版本：1.0.0
日期：2026-03-28
"""

import os
import sys
import json
import shutil
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List
from enum import Enum


class LogType(Enum):
    """日志类型枚举"""
    FEATURE_DEVELOPMENT = "feature_development"
    DEBUGGING = "debugging"
    FILE_REORGANIZATION = "file_reorganization"


class WorkflowLogger:
    """日志管理工作流类"""
    
    def __init__(self, base_dir: Optional[str] = None):
        """
        初始化日志管理器
        
        Args:
            base_dir: 工作区根目录路径，默认为当前脚本所在目录
        """
        if base_dir is None:
            base_dir = Path(__file__).parent.parent
        self.base_dir = Path(base_dir)
        self.log_dir = self.base_dir / "log"
        self.latest_log_path = self.base_dir / "LATEST_WORK_LOG.md"
        
        self._ensure_log_directories()
    
    def _ensure_log_directories(self):
        """确保日志目录存在"""
        subdirs = ["feature_development", "debugging", "file_reorganization", "templates"]
        for subdir in subdirs:
            (self.log_dir / subdir).mkdir(parents=True, exist_ok=True)
    
    def _get_timestamp(self) -> str:
        """获取当前时间戳"""
        return datetime.now().strftime("%Y%m%d_%H%M%S")
    
    def _get_date_formatted(self) -> str:
        """获取格式化日期"""
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    def _generate_log_filename(self, log_type: LogType, task_name: str) -> str:
        """
        生成日志文件名
        
        Args:
            log_type: 日志类型
            task_name: 任务名称
            
        Returns:
            str: 日志文件名
        """
        timestamp = self._get_timestamp()
        safe_name = task_name.replace(" ", "_").replace("/", "_").replace("\\", "_")
        return f"{log_type.value}_{safe_name}_{timestamp}.md"
    
    def _generate_markdown_content(self, log_type: LogType, task_name: str, 
                                   description: str, details: Optional[Dict[str, Any]] = None,
                                   tasks: Optional[List[Dict[str, str]]] = None) -> str:
        """
        生成Markdown格式的日志内容
        
        Args:
            log_type: 日志类型
            task_name: 任务名称
            description: 任务描述
            details: 详细信息字典
            tasks: 任务列表
            
        Returns:
            str: Markdown格式的日志内容
        """
        log_type_names = {
            LogType.FEATURE_DEVELOPMENT: "开发新功能",
            LogType.DEBUGGING: "调试旧功能",
            LogType.FILE_REORGANIZATION: "文件整理"
        }
        
        content = []
        content.append(f"# {log_type_names[log_type]}: {task_name}")
        content.append("")
        content.append(f"**创建时间**: {self._get_date_formatted()}")
        content.append(f"**日志类型**: {log_type_names[log_type]}")
        content.append(f"**任务状态**: 进行中")
        content.append("")
        content.append("---")
        content.append("")
        content.append("## 📋 任务概述")
        content.append("")
        content.append(description)
        content.append("")
        
        if tasks:
            content.append("## 📝 执行任务清单")
            content.append("")
            for i, task in enumerate(tasks, 1):
                status = task.get("status", "pending")
                status_icon = {"pending": "⏳", "in_progress": "🔄", "completed": "✅", "failed": "❌"}.get(status, "❓")
                content.append(f"{i}. {status_icon} **{task['content']}**")
                if task.get("notes"):
                    content.append(f"   - 备注: {task['notes']}")
            content.append("")
        
        if details:
            content.append("## 🔍 详细信息")
            content.append("")
            for key, value in details.items():
                if isinstance(value, dict):
                    content.append(f"### {key}")
                    for k, v in value.items():
                        content.append(f"- {k}: `{v}`")
                    content.append("")
                elif isinstance(value, list):
                    content.append(f"### {key}")
                    for item in value:
                        content.append(f"- {item}")
                    content.append("")
                else:
                    content.append(f"- **{key}**: `{value}`")
            content.append("")
        
        content.append("---")
        content.append("")
        content.append("## 📊 执行记录")
        content.append("")
        content.append("| 时间 | 操作 | 状态 | 备注 |")
        content.append("|------|------|------|------|")
        content.append(f"| {self._get_date_formatted()} | 任务创建 | ✅ | 日志创建 |")
        content.append("")
        
        content.append("---")
        content.append("")
        content.append("## 💡 问题与解决方案")
        content.append("")
        content.append("*记录工作过程中遇到的问题和解决方案*")
        content.append("")
        
        content.append("---")
        content.append("")
        content.append("## 📈 成果与收获")
        content.append("")
        content.append("*记录工作完成后的成果和学习收获*")
        content.append("")
        
        content.append("---")
        content.append("")
        content.append("## 🔄 下一步计划")
        content.append("")
        content.append("*记录后续需要完成的工作*")
        content.append("")
        
        return "\n".join(content)
    
    def create_log(self, log_type: LogType, task_name: str, 
                   description: str, details: Optional[Dict[str, Any]] = None,
                   tasks: Optional[List[Dict[str, str]]] = None) -> str:
        """
        创建新日志
        
        Args:
            log_type: 日志类型
            task_name: 任务名称
            description: 任务描述
            details: 详细信息字典
            tasks: 任务列表
            
        Returns:
            str: 日志文件路径
        """
        log_filename = self._generate_log_filename(log_type, task_name)
        log_path = self.log_dir / log_type.value / log_filename
        
        content = self._generate_markdown_content(
            log_type, task_name, description, details, tasks
        )
        
        with open(log_path, "w", encoding="utf-8") as f:
            f.write(content)
        
        self._sync_latest_log(log_path)
        
        return str(log_path)
    
    def _sync_latest_log(self, log_path: Path):
        """
        同步最新日志到根目录
        
        Args:
            log_path: 日志文件路径
        """
        try:
            shutil.copy2(log_path, self.latest_log_path)
            print(f"✅ 最新日志已同步到: {self.latest_log_path}")
        except Exception as e:
            print(f"⚠️ 同步日志失败: {e}")
    
    def update_log(self, log_path: str, new_entry: Dict[str, Any]):
        """
        更新日志文件
        
        Args:
            log_path: 日志文件路径
            new_entry: 新增条目
            
        Returns:
            bool: 是否更新成功
        """
        try:
            with open(log_path, "r", encoding="utf-8") as f:
                content = f.read()
            
            timestamp = self._get_date_formatted()
            
            if "execution_record" in new_entry:
                record = new_entry["execution_record"]
                entry = f"| {timestamp} | {record.get('operation', '')} | {record.get('status', '')} | {record.get('notes', '')} |\n"
                
                if "| 时间 | 操作 | 状态 | 备注 |" in content:
                    lines = content.split("\n")
                    insert_idx = None
                    for i, line in enumerate(lines):
                        if line.startswith("| ---"):
                            insert_idx = i + 1
                            break
                    
                    if insert_idx:
                        lines.insert(insert_idx, entry)
                        content = "\n".join(lines)
            
            if "problem" in new_entry:
                problem = new_entry["problem"]
                content += f"\n### 问题 {timestamp}\n"
                content += f"- **问题描述**: {problem.get('description', '')}\n"
                content += f"- **解决方案**: {problem.get('solution', '')}\n"
                content += f"- **结果**: {problem.get('result', '')}\n"
            
            if "result" in new_entry:
                content += f"\n### 成果 {timestamp}\n"
                for key, value in new_entry["result"].items():
                    content += f"- **{key}**: {value}\n"
            
            if "next_step" in new_entry:
                content += f"\n### 下一步计划 {timestamp}\n"
                content += f"- {new_entry['next_step']}\n"
            
            if "task_update" in new_entry:
                task = new_entry["task_update"]
                task_num = task.get("number", "")
                new_status = task.get("status", "")
                content = content.replace(
                    f"{task_num}.",
                    f"{task_num}."
                )
                status_icon = {"pending": "⏳", "in_progress": "🔄", "completed": "✅", "failed": "❌"}.get(new_status, "")
                content = content.replace(
                    f"{status_icon} **{task['content']}**",
                    f"{status_icon} **{task['content']}** (更新: {timestamp})"
                )
            
            with open(log_path, "w", encoding="utf-8") as f:
                f.write(content)
            
            if str(log_path) == str(self.latest_log_path) or \
               Path(log_path).name in str(self.latest_log_path):
                self._sync_latest_log(Path(log_path))
            
            return True
            
        except Exception as e:
            print(f"❌ 更新日志失败: {e}")
            return False
    
    def complete_log(self, log_path: str, summary: Dict[str, Any]):
        """
        标记日志为完成状态
        
        Args:
            log_path: 日志文件路径
            summary: 完成总结
            
        Returns:
            bool: 是否成功
        """
        try:
            with open(log_path, "r", encoding="utf-8") as f:
                content = f.read()
            
            content = content.replace(
                "**任务状态**: 进行中",
                "**任务状态**: ✅ 已完成"
            )
            
            timestamp = self._get_date_formatted()
            
            if "final_summary" in summary:
                content += f"\n\n## ✅ 任务完成总结\n"
                for key, value in summary["final_summary"].items():
                    content += f"- **{key}**: {value}\n"
            
            content += f"\n**完成时间**: {timestamp}\n"
            
            with open(log_path, "w", encoding="utf-8") as f:
                f.write(content)
            
            self._sync_latest_log(Path(log_path))
            
            return True
            
        except Exception as e:
            print(f"❌ 完成日志标记失败: {e}")
            return False
    
    def list_logs(self, log_type: Optional[LogType] = None) -> List[Dict[str, str]]:
        """
        列出日志文件
        
        Args:
            log_type: 日志类型过滤，None表示所有类型
            
        Returns:
            List[Dict[str, str]]: 日志文件列表
        """
        logs = []
        
        if log_type:
            search_dirs = [self.log_dir / log_type.value]
        else:
            search_dirs = [
                self.log_dir / "feature_development",
                self.log_dir / "debugging",
                self.log_dir / "file_reorganization"
            ]
        
        for search_dir in search_dirs:
            if search_dir.exists():
                for log_file in sorted(search_dir.glob("*.md"), reverse=True):
                    logs.append({
                        "name": log_file.name,
                        "path": str(log_file),
                        "type": search_dir.name,
                        "modified": datetime.fromtimestamp(log_file.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                        "size": f"{log_file.stat().st_size / 1024:.1f} KB"
                    })
        
        return logs


def create_feature_log(task_name: str, description: str, 
                      tasks: Optional[List[Dict[str, str]]] = None,
                      details: Optional[Dict[str, Any]] = None) -> str:
    """
    快捷函数：创建功能开发日志
    
    Args:
        task_name: 任务名称
        description: 任务描述
        tasks: 任务列表
        details: 详细信息
        
    Returns:
        str: 日志文件路径
    """
    logger = WorkflowLogger()
    return logger.create_log(
        LogType.FEATURE_DEVELOPMENT,
        task_name,
        description,
        tasks=tasks,
        details=details
    )


def create_debug_log(task_name: str, description: str,
                    details: Optional[Dict[str, Any]] = None,
                    tasks: Optional[List[Dict[str, str]]] = None) -> str:
    """
    快捷函数：创建调试日志
    
    Args:
        task_name: 任务名称
        description: 任务描述
        details: 详细信息
        tasks: 任务列表
        
    Returns:
        str: 日志文件路径
    """
    logger = WorkflowLogger()
    return logger.create_log(
        LogType.DEBUGGING,
        task_name,
        description,
        details=details,
        tasks=tasks
    )


def create_reorganize_log(task_name: str, description: str,
                          tasks: Optional[List[Dict[str, str]]] = None,
                          details: Optional[Dict[str, Any]] = None) -> str:
    """
    快捷函数：创建文件整理日志
    
    Args:
        task_name: 任务名称
        description: 任务描述
        tasks: 任务列表
        details: 详细信息
        
    Returns:
        str: 日志文件路径
    """
    logger = WorkflowLogger()
    return logger.create_log(
        LogType.FILE_REORGANIZATION,
        task_name,
        description,
        tasks=tasks,
        details=details
    )


if __name__ == "__main__":
    print("=" * 60)
    print("日志管理工作流 - 快速测试")
    print("=" * 60)
    
    logger = WorkflowLogger()
    
    test_tasks = [
        {"content": "创建日志目录结构", "status": "completed", "notes": "已完成"},
        {"content": "创建日志管理模块", "status": "in_progress", "notes": "开发中"},
        {"content": "创建日志模板", "status": "pending", "notes": ""},
        {"content": "更新配置文件", "status": "pending", "notes": ""}
    ]
    
    test_details = {
        "基本信息": {
            "工作区": "AItools-for-historyresearch",
            "版本": "1.0.0",
            "创建者": "AI Assistant"
        },
        "日志类型": ["功能开发", "调试", "文件整理"]
    }
    
    print("\n创建功能开发日志...")
    log_path = create_feature_log(
        "日志管理系统实施",
        "建立系统化的日志管理机制，包含功能开发、调试和文件整理三大类日志",
        tasks=test_tasks,
        details=test_details
    )
    print(f"✅ 日志创建成功: {log_path}")
    
    print("\n列出所有日志...")
    logs = logger.list_logs()
    print(f"找到 {len(logs)} 个日志文件:")
    for log in logs[:5]:
        print(f"  - [{log['type']}] {log['name']}")
    
    print("\n" + "=" * 60)
    print("测试完成！")
    print("=" * 60)
