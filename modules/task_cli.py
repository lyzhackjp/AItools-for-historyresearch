"""
命令行任务执行工具

提供命令行界面来执行各种任务
支持API和脚本两种执行模式

使用方法：
    python -m modules.task_cli --mode api --task ner --text "伊藤博文是明治维新的重要人物"
    python -m modules.task_cli --mode script --task summary --text "长文本内容..."
    python -m modules.task_cli --interactive
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

from modules.task_manager import TaskManager
from modules.secure_api_key_manager import get_secure_key_manager


def print_result(result: dict):
    """打印执行结果"""
    print("\n" + "=" * 60)
    print("执行结果")
    print("=" * 60)
    
    print(f"成功: {result.get('success')}")
    print(f"模式: {result.get('mode')}")
    
    if result.get('error'):
        print(f"错误: {result['error']}")
    
    if result.get('data'):
        data = result['data']
        if isinstance(data, dict):
            print("\n数据:")
            for key, value in data.items():
                if isinstance(value, (list, dict)):
                    print(f"  {key}: {json.dumps(value, ensure_ascii=False)[:200]}...")
                else:
                    print(f"  {key}: {str(value)[:200]}")
        else:
            print(f"\n数据: {str(data)[:500]}")
    
    if result.get('execution_time'):
        print(f"\n执行时间: {result['execution_time']:.2f}秒")


def execute_task(args):
    """执行单个任务"""
    manager = TaskManager(mode=args.mode, provider=args.provider)
    
    if args.preset:
        print(f"使用预设: {args.preset}")
    
    task_mapping = {
        'ner': lambda: manager.ner(args.text, preset=args.preset),
        'academic_note': lambda: manager.academic_note(args.text, source=args.source or "CLI输入", preset=args.preset),
        'paper_polish': lambda: manager.paper_polish(args.text, preset=args.preset),
        'summary': lambda: manager.summarize(args.text, max_length=args.max_length or 200, preset=args.preset),
        'ocr_correct': lambda: manager.ocr_correct(args.text, preset=args.preset),
        'citation': lambda: manager.citation_normalize(args.text, target_style=args.style or "gb7714"),
        'style_transfer': lambda: manager.style_transfer(args.text, target_style=args.target_style or "学术风格"),
    }
    
    if args.task not in task_mapping:
        print(f"错误: 未知任务类型 '{args.task}'")
        print(f"可用任务: {list(task_mapping.keys())}")
        return
    
    result = task_mapping[args.task]()
    print_result(result)
    
    if args.output:
        manager.export_results([result], args.output, format=args.format or 'json')
        print(f"\n结果已保存到: {args.output}")


def interactive_mode(args):
    """交互模式"""
    manager = TaskManager(mode=args.mode, provider=args.provider)
    
    print("=" * 60)
    print("历史研究AI辅助工具 - 交互模式")
    print("=" * 60)
    print(f"当前模式: {manager.mode}")
    print(f"当前提供商: {manager.provider}")
    print(f"可用任务: {manager.get_available_tasks()}")
    print("输入 'help' 查看帮助，'quit' 退出")
    print("=" * 60)
    
    while True:
        try:
            user_input = input("\n> ").strip()
            
            if not user_input:
                continue
            
            if user_input.lower() in ['quit', 'exit', 'q']:
                print("再见！")
                break
            
            if user_input.lower() == 'help':
                print_help()
                continue
            
            if user_input.lower() == 'status':
                print_status(manager)
                continue
            
            if user_input.lower() == 'stats':
                stats = manager.get_statistics()
                print(json.dumps(stats, indent=2, ensure_ascii=False))
                continue
            
            if user_input.lower().startswith('mode '):
                new_mode = user_input.split()[1]
                if new_mode in ['api', 'script']:
                    manager.set_mode(new_mode)
                    print(f"模式已切换为: {manager.mode}")
                else:
                    print("错误: 模式必须是 'api' 或 'script'")
                continue
            
            if user_input.lower().startswith('provider '):
                new_provider = user_input.split()[1]
                manager.set_provider(new_provider)
                print(f"提供商已切换为: {manager.provider}")
                continue
            
            parts = user_input.split(maxsplit=1)
            if len(parts) >= 2:
                task_type = parts[0]
                text = parts[1]
                
                method = getattr(manager, task_type, None)
                if method and callable(method):
                    result = method(text)
                    print_result(result)
                else:
                    print(f"错误: 未知任务类型 '{task_type}'")
            else:
                print("错误: 请输入任务类型和文本")
                print("格式: <任务类型> <文本>")
                print("例如: ner 伊藤博文是明治维新的重要人物")
        
        except KeyboardInterrupt:
            print("\n再见！")
            break
        except Exception as e:
            print(f"错误: {e}")


def print_help():
    """打印帮助信息"""
    help_text = """
可用命令：
  help                    - 显示此帮助信息
  status                  - 显示当前状态
  stats                   - 显示执行统计
  mode <api|script>       - 切换执行模式
  provider <name>         - 切换API提供商
  quit                    - 退出程序

任务格式：
  <任务类型> <文本>

可用任务：
  ner <文本>              - 命名实体识别
  academic_note <文本>    - 生成学术笔记
  paper_polish <文本>     - 论文润色
  summary <文本>          - 文本摘要
  ocr_correct <文本>      - OCR校正
  citation <引用>         - 引用规范化
  style_transfer <文本>   - 文风迁移

示例：
  ner 伊藤博文是明治维新的重要人物
  summary 这是一段很长的文本...
  mode script
  provider qwen
"""
    print(help_text)


def print_status(manager: TaskManager):
    """打印状态信息"""
    print("\n" + "=" * 60)
    print("当前状态")
    print("=" * 60)
    print(f"执行模式: {manager.mode}")
    print(f"API提供商: {manager.provider}")
    print(f"可用任务: {', '.join(manager.get_available_tasks())}")
    
    key_status = manager.get_api_key_status()
    print(f"\nAPI密钥状态:")
    for service, info in key_status.get('services', {}).items():
        status = "✓" if info.get('has_key') else "✗"
        print(f"  {service}: {status}")


def show_info(args):
    """显示系统信息"""
    print("=" * 60)
    print("历史研究AI辅助工具 - 系统信息")
    print("=" * 60)
    
    manager = TaskManager()
    
    print(f"\n执行模式: {manager.mode}")
    print(f"API提供商: {manager.provider}")
    print(f"可用任务: {manager.get_available_tasks()}")
    print(f"可用预设: {list(manager.get_presets().keys())}")
    
    key_manager = get_secure_key_manager()
    status = key_manager.get_status_report()
    
    print(f"\nSecrets路径: {status.get('secrets_path')}")
    print(f"已加载密钥数: {status.get('total_keys_loaded')}")
    
    print("\nAPI密钥状态:")
    for service, info in status.get('services', {}).items():
        status_icon = "✓" if info.get('has_key') else "✗"
        print(f"  {service}: {status_icon}")


def main():
    parser = argparse.ArgumentParser(
        description='历史研究AI辅助工具 - 命令行任务执行器',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 使用API模式执行NER任务
  python -m modules.task_cli --mode api --task ner --text "伊藤博文是明治维新的重要人物"
  
  # 使用脚本模式执行摘要任务
  python -m modules.task_cli --mode script --task summary --text "长文本内容..."
  
  # 使用预设配置
  python -m modules.task_cli --task ner --preset ner_detailed --text "..."
  
  # 交互模式
  python -m modules.task_cli --interactive
  
  # 显示系统信息
  python -m modules.task_cli --info
        """
    )
    
    parser.add_argument('--mode', '-m', default='script',
                       choices=['api', 'script'],
                       help='执行模式 (默认: script)')
    
    parser.add_argument('--provider', '-p', default='qwen',
                       help='API提供商 (默认: qwen)')
    
    parser.add_argument('--task', '-t',
                       choices=['ner', 'academic_note', 'paper_polish', 
                               'summary', 'ocr_correct', 'citation', 'style_transfer'],
                       help='任务类型')
    
    parser.add_argument('--text', '-x',
                       help='输入文本')
    
    parser.add_argument('--source', '-s',
                       help='来源信息（用于学术笔记生成）')
    
    parser.add_argument('--preset',
                       help='预设配置名称')
    
    parser.add_argument('--style',
                       help='引用格式（用于引用规范化）')
    
    parser.add_argument('--target-style',
                       help='目标文风（用于文风迁移）')
    
    parser.add_argument('--max-length', type=int,
                       help='最大长度（用于摘要）')
    
    parser.add_argument('--output', '-o',
                       help='输出文件路径')
    
    parser.add_argument('--format', '-f', default='json',
                       choices=['json', 'csv', 'txt'],
                       help='输出格式 (默认: json)')
    
    parser.add_argument('--interactive', '-i', action='store_true',
                       help='进入交互模式')
    
    parser.add_argument('--info', action='store_true',
                       help='显示系统信息')
    
    args = parser.parse_args()
    
    if args.info:
        show_info(args)
    elif args.interactive:
        interactive_mode(args)
    elif args.task and args.text:
        execute_task(args)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
