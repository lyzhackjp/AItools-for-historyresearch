# Windows 安装程序构建说明

本工作区已支持“后端 + React 前端”同源运行：构建后的 `frontend/dist` 会由 Flask 直接托管，客户安装后只需要启动本地服务并在浏览器中使用 UI。

## 开发机生成安装包

1. 安装 Node.js 18+。
2. 安装 Inno Setup 6。
3. 在仓库根目录运行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\windows\Build-WindowsInstaller.ps1
```

生成结果位于：

```text
dist-windows\HistoryResearchAI-Setup-1.1.0.exe
```

如果只想验证前端构建，不生成 `.exe`：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\windows\Build-WindowsInstaller.ps1 -SkipInstaller
```

## 客户端安装后的使用方式

安装程序会创建开始菜单快捷方式：

- `History Research AI`：启动后端并打开 UI。
- `Stop History Research AI`：停止后台后端服务。

首次启动会在安装目录下创建 `.runtime\venv` 并安装 `requirements.txt` 中的 Python 依赖。真实 API 密钥、私密史料、缓存、输出目录和 `secrets/` 不会被打包进安装程序。

## 打包策略

- 包含：后端源码、前端 `dist`、配置模板、文档和启动脚本。
- 排除：`.git`、`frontend/node_modules`、`.env*`、`secrets/`、缓存、日志、输出、模型、数据目录、PDF/PPTX 等可能包含用户材料或体积过大的文件。
- 生产运行：Flask 设置 `HISTORY_RESEARCH_SERVE_FRONTEND=1`，根路径返回 React UI，API 保持在 `/api/...`。
