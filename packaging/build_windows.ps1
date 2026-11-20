$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$PackageRoot = Join-Path $ProjectRoot "release\智教英航"
$FrontendDist = Join-Path $ProjectRoot "frontend\dist"

Push-Location (Join-Path $ProjectRoot "frontend")
try {
    $env:VITE_API_BASE_URL = "http://127.0.0.1:8001"
    pnpm run build
    if ($LASTEXITCODE -ne 0) { throw "前端构建失败。" }
} finally {
    Pop-Location
}

if (Test-Path $PackageRoot) {
    throw "发布目录已存在，请先检查并手动移走旧版本: $PackageRoot"
}
New-Item $PackageRoot -ItemType Directory -Force | Out-Null
$BackendPath = Join-Path $ProjectRoot "backend"
$RunnerPath = Join-Path $PSScriptRoot "run_local.py"
python -m PyInstaller --clean --noconfirm --onefile --name "智教英航" --paths $BackendPath --hidden-import app.main --collect-submodules app --add-data "$FrontendDist;frontend" --distpath $PackageRoot --workpath (Join-Path $ProjectRoot "release\build") --specpath (Join-Path $ProjectRoot "release\spec") $RunnerPath
if ($LASTEXITCODE -ne 0) { throw "Windows 程序构建失败。" }

$envFile = @"
DEEPSEEK_API_KEY=
DEEPSEEK_MODEL=deepseek-flash
ZHJ_DEMO_UPLOAD=0
"@
Set-Content (Join-Path $PackageRoot ".env.example") $envFile -Encoding UTF8
Copy-Item (Join-Path $PSScriptRoot "启动智教英航.bat") $PackageRoot
Copy-Item (Join-Path $PSScriptRoot "使用说明.txt") $PackageRoot
$ZipPath = Join-Path $ProjectRoot "release\智教英航-Windows.zip"
if (Test-Path $ZipPath) {
    throw "压缩包已存在，请先检查并手动移走旧版本: $ZipPath"
}
Compress-Archive -Path $PackageRoot -DestinationPath $ZipPath
Write-Host "已生成: $ProjectRoot\release\智教英航-Windows.zip"
