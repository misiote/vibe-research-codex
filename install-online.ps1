$ErrorActionPreference = "Stop"
$PythonExe = $null
$PythonArgs = @()
foreach ($Name in @("python", "python3", "py")) {
    $Candidate = Get-Command $Name -ErrorAction SilentlyContinue
    if (-not $Candidate) { continue }
    $CandidateArgs = if ($Name -eq "py") { @("-3") } else { @() }
    & $Candidate.Source @CandidateArgs -c "import sys; raise SystemExit(0 if sys.version_info >= (3,9) else 2)" 2>$null
    if ($LASTEXITCODE -eq 0) { $PythonExe = $Candidate.Source; $PythonArgs = $CandidateArgs; break }
}
if (-not $PythonExe) { throw "Python 3.9+ is required. Install Python, then retry." }
$Bootstrap = [IO.Path]::GetTempFileName()
try {
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    Invoke-WebRequest -UseBasicParsing -TimeoutSec 60 -Uri "https://raw.githubusercontent.com/misiote/vibe-research-codex/main/scripts/bootstrap.py?t=$([DateTime]::UtcNow.Ticks)" -OutFile $Bootstrap
    & $PythonExe @PythonArgs -X utf8 $Bootstrap @args
    if ($LASTEXITCODE -ne 0) { throw "Vibe Research installation did not complete. See the error above." }
} finally {
    Remove-Item -LiteralPath $Bootstrap -Force -ErrorAction SilentlyContinue
}
