#define SourceRoot "..\.."
#define AppVersion "1.1.0"

[Setup]
AppId={{76C5A1CF-54F9-4B49-8BE7-98F7FE15397A}
AppName=History Research AI Workbench
AppVersion={#AppVersion}
AppPublisher=History Research AI Tools
DefaultDirName={localappdata}\HistoryResearchAI
DefaultGroupName=History Research AI
DisableProgramGroupPage=yes
OutputDir={#SourceRoot}\dist-windows
OutputBaseFilename=HistoryResearchAI-Setup-{#AppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\scripts\windows\Start-HistoryResearchAI.cmd

[Files]
Source: "{#SourceRoot}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: ".git\*,.vscode\*,.runtime\*,.venv*\*,__pycache__\*,*.pyc,dist-windows\*,archive\*,archives\*,external\*,Book citation chain_books\*,ndl-search\*,ndlocr-lite\*,frontend\node_modules\*,frontend\.env*,frontend\vite-dev.*.log,secrets\*,temp\*,tmp\*,cache\*,logs\*,log\*,output\*,ocr_output\*,workflow_output\*,training_workflow_output\*,models\*,data\*,*.pdf,*.pptx"

[Icons]
Name: "{autoprograms}\History Research AI"; Filename: "{app}\scripts\windows\Start-HistoryResearchAI.cmd"; WorkingDir: "{app}"
Name: "{autoprograms}\Stop History Research AI"; Filename: "{app}\scripts\windows\Stop-HistoryResearchAI.cmd"; WorkingDir: "{app}"
Name: "{autodesktop}\History Research AI"; Filename: "{app}\scripts\windows\Start-HistoryResearchAI.cmd"; WorkingDir: "{app}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional icons:"; Flags: unchecked

[Run]
Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\scripts\windows\Initialize-HistoryResearchAI.ps1"""; Description: "Initialize Python runtime"; Flags: postinstall skipifsilent waituntilterminated
Filename: "{app}\scripts\windows\Start-HistoryResearchAI.cmd"; Description: "Start History Research AI"; Flags: postinstall nowait skipifsilent
