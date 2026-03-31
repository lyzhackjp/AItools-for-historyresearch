# 学术润色模块临时文件删除脚本
# 生成日期: 2026-03-29
# 删除文件总数: 28个

# 警告：此脚本将永久删除文件，删除后无法恢复！

Write-Host "========================================" -ForegroundColor Yellow
Write-Host "学术润色模块临时文件删除脚本" -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Yellow
Write-Host ""

# 待删除文件清单
$filesToDelete = @(
    # 简化版脚本（5个）
    "polishing_simple.py",
    "polishing_direct.py",
    "polishing_debug.py",
    "polishing_with_heartbeat.py",
    "final_polished_doc.py",

    # 脚注检查脚本（8个）
    "check_footnotes.py",
    "check_footnotes2.py",
    "check_footnote_types.py",
    "inspect_footnotes.py",
    "verify_all_footnotes.py",
    "verify_footnotes.py",
    "debug_footnote_extraction.py",
    "debug_footnotes.py",

    # 脚注修复脚本（6个）
    "fix_footnotes.py",
    "fix_polished_footnotes.py",
    "fix_footnote_processor.py",
    "correct_footnote_implementation2.py",
    "correct_footnote_implementation3.py",

    # 脚注提取脚本（2个）
    "extract_footnotes_from_xml.py",
    "extract_footnotes_complete.py",

    # 文档处理器脚注测试（3个）
    "test_doc_processor_footnotes.py",
    "test_create_footnotes.py",
    "test_footnote_extraction.py",

    # 其他测试脚本（2个）
    "test_dashscope_direct.py",
    "test_llm_quick.py",

    # 辅助检查脚本（2个）
    "check_files.py",
    "check_docx_structure.py"
)

Write-Host "待删除文件清单：" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
$count = 1
foreach ($file in $filesToDelete) {
    Write-Host "$count. $file"
    $count++
}
Write-Host ""
Write-Host "总计: $($filesToDelete.Count) 个文件" -ForegroundColor Yellow
Write-Host ""

# 确认删除
$confirmation = Read-Host "确认删除以上 $($filesToDelete.Count) 个文件? (yes/no)"

if ($confirmation -eq "yes") {
    Write-Host ""
    Write-Host "开始删除文件..." -ForegroundColor Green

    $basePath = "c:\Users\lyzha\Desktop\AItools-for-historyresearch"
    $deletedCount = 0
    $failedCount = 0

    foreach ($file in $filesToDelete) {
        $filePath = Join-Path $basePath $file

        if (Test-Path $filePath) {
            try {
                Remove-Item $filePath -Force
                Write-Host "✓ 已删除: $file" -ForegroundColor Green
                $deletedCount++
            }
            catch {
                Write-Host "✗ 删除失败: $file - $_" -ForegroundColor Red
                $failedCount++
            }
        }
        else {
            Write-Host "- 文件不存在: $file" -ForegroundColor Gray
        }
    }

    Write-Host ""
    Write-Host "========================================" -ForegroundColor Green
    Write-Host "删除完成！" -ForegroundColor Green
    Write-Host "成功删除: $deletedCount 个文件" -ForegroundColor Green
    if ($failedCount -gt 0) {
        Write-Host "删除失败: $failedCount 个文件" -ForegroundColor Red
    }
    Write-Host "========================================" -ForegroundColor Green
}
else {
    Write-Host ""
    Write-Host "删除操作已取消。" -ForegroundColor Yellow
    Write-Host "如需手动删除，请在文件资源管理器中删除以上文件。" -ForegroundColor Yellow
}
