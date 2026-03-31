# 📋 日志管理工作流规范

## 🎯 目的

建立系统化的日志管理机制，确保所有重要工作活动都有详细记录，便于追踪、复盘和知识传承。

---

## 📅 适用范围

所有团队成员在进行以下工作活动时，必须生成详细日志记录：

1. **开发新功能** - 开发新模块、新工具、新特性
2. **调试旧功能** - 修复Bug、优化性能、解决技术问题
3. **文件整理** - 重构代码、重组目录、迁移文件

---

## 📁 目录结构

```
log/
├── feature_development/      # 功能开发日志
│   └── *.md
├── debugging/               # 调试日志
│   └── *.md
├── file_reorganization/     # 文件整理日志
│   └── *.md
├── templates/               # 日志模板
│   ├── feature_development_template.md
│   ├── debugging_template.md
│   └── file_reorganization_template.md
└── workflow_logger.py        # 日志管理模块
```

---

## 🚀 使用指南

### 方式一：使用Python模块（推荐）

```python
from log.workflow_logger import (
    create_feature_log,
    create_debug_log,
    create_reorganize_log,
    WorkflowLogger
)

# 1. 开发新功能
log_path = create_feature_log(
    task_name="用户认证模块开发",
    description="开发基于JWT的用户认证系统",
    tasks=[
        {"content": "创建用户模型", "status": "pending"},
        {"content": "实现登录接口", "status": "pending"},
        {"content": "添加JWT验证", "status": "pending"}
    ]
)

# 2. 调试旧功能
log_path = create_debug_log(
    task_name="登录失败问题排查",
    description="用户反馈登录失败，需要排查原因",
    details={
        "错误信息": "Authentication failed",
        "影响用户": "所有用户"
    }
)

# 3. 文件整理
log_path = create_reorganize_log(
    task_name="模块重组",
    description="重组项目目录结构",
    tasks=[
        {"content": "创建新目录", "status": "completed"},
        {"content": "移动文件", "status": "pending"},
        {"content": "更新导入", "status": "pending"}
    ]
)
```

### 方式二：使用WorkflowLogger类

```python
from log.workflow_logger import WorkflowLogger, LogType

logger = WorkflowLogger()

# 创建日志
log_path = logger.create_log(
    log_type=LogType.FEATURE_DEVELOPMENT,
    task_name="新功能开发",
    description="功能描述",
    tasks=[...],
    details={...}
)

# 更新日志
logger.update_log(log_path, {
    "execution_record": {
        "operation": "完成编码",
        "status": "✅",
        "notes": "所有代码已完成"
    }
})

# 标记完成
logger.complete_log(log_path, {
    "final_summary": {
        "总耗时": "2小时",
        "代码量": "500行"
    }
})

# 列出日志
logs = logger.list_logs()
for log in logs:
    print(f"{log['type']}: {log['name']}")
```

---

## 📝 日志内容要求

### 1. 功能开发日志

#### 必须包含
- ✅ 任务目标和背景
- ✅ 详细的任务清单
- ✅ 技术方案和设计
- ✅ 涉及的文件和模块
- ✅ 执行记录（时间、操作、状态）
- ✅ 问题与解决方案
- ✅ 最终成果总结

#### 可选包含
- 代码示例
- 测试用例
- 性能数据
- 截图或图表

### 2. 调试日志

#### 必须包含
- ✅ 问题描述和影响范围
- ✅ 错误信息和堆栈
- ✅ 调试步骤和分析过程
- ✅ 根本原因分析
- ✅ 解决方案和代码变更
- ✅ 测试验证结果

#### 可选包含
- 调试截图
- 性能对比
- 预防措施建议

### 3. 文件整理日志

#### 必须包含
- ✅ 整理原因和目标
- ✅ 整理前后的目录结构
- ✅ 详细的文件移动记录
- ✅ 路径更新列表
- ✅ 潜在风险评估
- ✅ 完成总结

#### 可选包含
- 自动化脚本
- 验证测试结果
- 后续注意事项

---

## 🔄 日志命名规范

### 命名格式
```
{日志类型}_{任务名称}_{时间戳}.md
```

### 示例
```
feature_development_用户认证模块_20260328_120000.md
debugging_登录失败问题_20260328_143000.md
file_reorganization_目录重组_20260328_160000.md
```

---

## 📤 日志同步机制

### 自动同步
每次创建或更新日志时，最新日志会自动同步到工作区根目录：

```
LATEST_WORK_LOG.md  ← 最新日志的副本
```

### 查看最新日志
```bash
# 直接查看
cat LATEST_WORK_LOG.md

# 或使用Python
from log.workflow_logger import WorkflowLogger
logger = WorkflowLogger()
latest = logger.latest_log_path
print(f"最新日志: {latest}")
```

---

## 🔍 日志管理最佳实践

### 1. 及时记录
- ✅ 每次重要操作后立即记录
- ✅ 遇到问题时立即记录
- ✅ 完成阶段性任务后更新状态

### 2. 详细描述
- ✅ 使用清晰的语言描述
- ✅ 提供足够的上下文
- ✅ 包含相关的代码片段

### 3. 分类归档
- ✅ 根据活动类型选择正确的日志类型
- ✅ 使用有意义的任务名称
- ✅ 及时完成和归档日志

### 4. 定期回顾
- ✅ 每周回顾本周的日志
- ✅ 总结经验教训
- ✅ 更新文档和流程

---

## ⚠️ 注意事项

1. **强制执行** - 所有适用范围内的活动必须创建日志
2. **及时更新** - 日志状态必须反映实际进展
3. **真实记录** - 如实记录问题和失败，避免隐瞒
4. **信息完整** - 包含足够的上下文信息，便于复盘
5. **团队可见** - 保持日志可访问，团队成员可见

---

## 📊 统计指标

### 日志统计（每月）
- 功能开发日志数量
- 调试日志数量
- 文件整理日志数量
- 平均完成时间
- 问题解决率

### 查看统计
```python
from log.workflow_logger import WorkflowLogger

logger = WorkflowLogger()
logs = logger.list_logs()

# 按类型统计
feature_count = len([l for l in logs if l['type'] == 'feature_development'])
debug_count = len([l for l in logs if l['type'] == 'debugging'])
reorganize_count = len([l for l in logs if l['type'] == 'file_reorganization'])

print(f"功能开发: {feature_count}")
print(f"调试: {debug_count}")
print(f"文件整理: {reorganize_count}")
```

---

## 🔗 相关文档

- [日志模板 - 功能开发](../log/templates/feature_development_template.md)
- [日志模板 - 调试](../log/templates/debugging_template.md)
- [日志模板 - 文件整理](../log/templates/file_reorganization_template.md)
- [日志管理模块源码](../log/workflow_logger.py)

---

## ✅ 检查清单

开始工作前：
- [ ] 确认是否需要创建日志
- [ ] 选择正确的日志类型
- [ ] 准备任务清单和目标

工作进行中：
- [ ] 记录每个重要步骤
- [ ] 记录遇到的问题
- [ ] 更新任务状态

工作完成后：
- [ ] 更新日志为完成状态
- [ ] 填写总结和经验教训
- [ ] 验证最新日志同步

---

**最后更新**: 2026-03-28  
**版本**: 1.0.0  
**维护者**: 团队所有成员
