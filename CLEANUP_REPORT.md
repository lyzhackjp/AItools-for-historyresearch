# 待删除/归档文件报告

## 生成时间
2026-03-30

## 文件分类

### 1. 测试脚本文件 (建议删除)
这些文件是在开发和调试过程中创建的临时测试脚本，功能已完成验证，可以安全删除。

| 文件名 | 用途 | 状态 |
|--------|------|------|
| verify_track_changes.py | 验证修订模式 | 已完成 |
| test_track_changes.py | 测试修订模式 | 已完成 |
| check_footnotes.py | 检查脚注内容 | 已完成 |
| run_final_test.py | 最终测试 | 已完成 |
| verify_save.py | 验证保存 | 已完成 |
| test_direct_save.py | 测试直接保存 | 已完成 |
| quick_test.py | 快速测试 | 已完成 |
| test_single_para.py | 单段落测试 | 已完成 |
| test_polish_direct.py | 直接润色测试 | 已完成 |
| validate_final.py | 最终验证 | 已完成 |
| direct_test.py | 直接测试 | 已完成 |
| check_content.py | 内容检查 | 已完成 |
| final_v2_test.py | 最终v2测试 | 已完成 |
| full_diagnose.py | 完整诊断 | 已完成 |
| diagnose_para.py | 段落诊断 | 已完成 |
| final_test.py | 最终测试 | 已完成 |
| verify_fix.py | 验证修复 | 已完成 |
| compare_results.py | 结果对比 | 已完成 |
| test_optimized.py | 优化测试 | 已完成 |
| diagnose_polish.py | 润色诊断 | 已完成 |

### 2. 输出文件 (建议归档)
这些是测试过程中生成的输出文件，可以归档保留或删除。

| 文件路径 | 类型 | 建议 |
|----------|------|------|
| data/output/polished/*.docx | 润色输出 | 保留最新版本，删除旧版本 |
| data/output/polished/*.json | 测试报告 | 保留最新版本，删除旧版本 |

### 3. 核心模块文件 (保留)
这些是系统的核心功能模块，必须保留。

| 文件名 | 用途 | 状态 |
|--------|------|------|
| modules/paper_polisher.py | 学术润色模块(已更新) | 保留 |
| modules/paper_polisher_optimized.py | 优化版润色模块 | 保留 |
| modules/paper_polisher_enhanced.py | 增强版润色模块 | 保留 |
| modules/llm_client.py | LLM客户端 | 保留 |

## 建议操作

### 立即删除的文件
以下测试脚本可以立即删除：
- verify_track_changes.py
- test_track_changes.py
- check_footnotes.py
- run_final_test.py
- verify_save.py
- test_direct_save.py
- quick_test.py
- test_single_para.py
- test_polish_direct.py
- validate_final.py
- direct_test.py
- check_content.py
- final_v2_test.py
- full_diagnose.py
- diagnose_para.py
- final_test.py
- verify_fix.py
- compare_results.py
- test_optimized.py
- diagnose_polish.py

### 归档的文件
以下输出文件建议归档到 `archive/` 目录：
- data/output/polished/polished_*.docx (保留最新3个版本)
- data/output/polished/*_report_*.json (保留最新3个版本)

## 执行命令

如需执行删除，请运行以下命令：

```bash
# 创建归档目录
mkdir -p archive/test_scripts
mkdir -p archive/old_outputs

# 移动测试脚本到归档
mv verify_track_changes.py archive/test_scripts/
mv test_track_changes.py archive/test_scripts/
mv check_footnotes.py archive/test_scripts/
mv run_final_test.py archive/test_scripts/
mv verify_save.py archive/test_scripts/
mv test_direct_save.py archive/test_scripts/
mv quick_test.py archive/test_scripts/
mv test_single_para.py archive/test_scripts/
mv test_polish_direct.py archive/test_scripts/
mv validate_final.py archive/test_scripts/
mv direct_test.py archive/test_scripts/
mv check_content.py archive/test_scripts/
mv final_v2_test.py archive/test_scripts/
mv full_diagnose.py archive/test_scripts/
mv diagnose_para.py archive/test_scripts/
mv final_test.py archive/test_scripts/
mv verify_fix.py archive/test_scripts/
mv compare_results.py archive/test_scripts/
mv test_optimized.py archive/test_scripts/
mv diagnose_polish.py archive/test_scripts/
```

## 注意事项

1. 删除前请确认不再需要这些测试脚本
2. 建议先移动到归档目录，观察一段时间后再永久删除
3. 核心模块文件请勿删除
