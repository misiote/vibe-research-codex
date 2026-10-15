$ErrorActionPreference = "Stop"
$ShareRoot = Split-Path -Parent $MyInvocation.MyCommand.Path

$CodexCommand = Get-Command codex -ErrorAction SilentlyContinue
$CodexExe = if ($CodexCommand) { $CodexCommand.Source } else { $null }
if (-not $CodexExe) {
    $Candidate = Join-Path $env:LOCALAPPDATA "Programs\OpenAI\Codex\bin\codex.exe"
    if (Test-Path $Candidate) { $CodexExe = $Candidate }
}
if (-not $CodexExe) {
    throw "没有找到 Codex CLI。请先安装 Codex，并重新打开 PowerShell。"
}

$PythonExe = $null
$PythonArgs = @()
$PythonCandidates = @()
if ($env:VIBE_RESEARCH_PYTHON) { $PythonCandidates += $env:VIBE_RESEARCH_PYTHON }
$PythonCommand = Get-Command python -ErrorAction SilentlyContinue
if ($PythonCommand) { $PythonCandidates += $PythonCommand.Source }
$PythonCandidates += Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
foreach ($Candidate in $PythonCandidates) {
    if (-not (Test-Path -LiteralPath $Candidate)) { continue }
    & $Candidate -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 9) else 2)" 2>$null
    if ($LASTEXITCODE -eq 0) { $PythonExe = $Candidate; break }
}
if (-not $PythonExe) {
    $PyCommand = Get-Command py -ErrorAction SilentlyContinue
    if ($PyCommand) {
        & $PyCommand.Source -3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 9) else 2)" 2>$null
        if ($LASTEXITCODE -eq 0) {
            $PythonExe = $PyCommand.Source
            $PythonArgs = @("-3")
        }
    }
}
if (-not $PythonExe) {
    throw "没有找到 Python 3.9+。请先从 python.org 或系统软件源安装 Python。"
}

& $PythonExe @PythonArgs -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 9) else 2)"
if ($LASTEXITCODE -ne 0) { throw "需要 Python 3.9 或更高版本。" }
$PythonArgs += @("-X", "utf8")
if (-not $env:CODEX_HOME) { $env:CODEX_HOME = Join-Path $env:USERPROFILE ".codex" }

& $CodexExe plugin marketplace add $ShareRoot
if ($LASTEXITCODE -ne 0) { throw "添加 Vibe Research marketplace 失败。" }
& $CodexExe plugin add "vibe-research@vibe-research-local"
if ($LASTEXITCODE -ne 0) { throw "安装 Vibe Research 插件失败。" }
$Workspace = if ($env:VIBE_RESEARCH_WORKSPACE) { $env:VIBE_RESEARCH_WORKSPACE } else { Join-Path $env:USERPROFILE "VibeResearch" }
& $PythonExe @PythonArgs (Join-Path $ShareRoot "plugins\vibe-research\scripts\install_cli.py") --workspace $Workspace
if ($LASTEXITCODE -ne 0) { throw "安装 vr-workbench 命令失败。" }
& $PythonExe @PythonArgs (Join-Path $ShareRoot "plugins\vibe-research\scripts\companion.py") --workspace $Workspace --check
if ($LASTEXITCODE -ne 0) {
    Write-Warning "悬浮研究伴侣尚未就绪；浏览器工作台仍可使用。请安装 GitHub Release 完整包，或安装 .NET 8 SDK 后重试。"
}

Write-Host ""
Write-Host "Vibe Research 已安装。重启 ChatGPT/Codex 后可点击插件默认提示；终端可运行 vr-workbench.cmd。"
