# Executor do SquadForce: sobe o backend (FastAPI) e a interface de produção (vite preview) e abre o navegador.
# Uso: atalho "SquadForce" na área de trabalho, ou
#   powershell -NoProfile -ExecutionPolicy Bypass -File scripts\launcher\iniciar-jogo.ps1
# Fechar: pressione Enter nesta janela (encerra servidor e interface).

$ErrorActionPreference = "Stop"
$Host.UI.RawUI.WindowTitle = "SquadForce"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$Frontend = Join-Path $Root "frontend"
$Python = Join-Path $Root ".venv\Scripts\python.exe"
$ApiPort = if ($env:SQUADFORCE_API_PORT) { [int]$env:SQUADFORCE_API_PORT } else { 8000 }
$UiPort = if ($env:SQUADFORCE_UI_PORT) { [int]$env:SQUADFORCE_UI_PORT } else { 5173 }
$ApiUrl = "http://127.0.0.1:$ApiPort/api/health"
$UiUrl = "http://localhost:$UiPort/"
$env:SQUADFORCE_BACKEND_URL = "http://127.0.0.1:$ApiPort"  # proxy /api e /ws da interface
$LogDir = Join-Path $env:TEMP "squadforce"
New-Item -ItemType Directory -Force $LogDir | Out-Null

function Write-Step($msg) { Write-Host "  > $msg" -ForegroundColor Green }
function Stop-Fail($msg) {
    Write-Host ""
    Write-Host "  ERRO: $msg" -ForegroundColor Red
    Write-Host "  Registros em: $LogDir"
    Read-Host "  Pressione Enter para fechar"
    exit 1
}
function Test-Url($url) {
    try { return (Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 $url).StatusCode -eq 200 } catch { return $false }
}
function Wait-Url($url, $seconds, $proc) {
    $deadline = (Get-Date).AddSeconds($seconds)
    while ((Get-Date) -lt $deadline) {
        if (Test-Url $url) { return $true }
        if ($proc -and $proc.HasExited) { return $false }
        Start-Sleep -Milliseconds 400
    }
    return $false
}

function Get-PortProcess($port) {
    $c = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($c) { return Get-CimInstance Win32_Process -Filter "ProcessId=$($c.OwningProcess)" }
    return $null
}
# Porta ocupada: pergunta se reinicia (um processo antigo pode estar com código desatualizado).
function Confirm-Restart($port, $what) {
    $p = Get-PortProcess $port
    if (-not $p) { return $false }
    Write-Host ""
    Write-Host "  Já existe um(a) $what na porta $port (processo $($p.ProcessId), iniciado em $($p.CreationDate))." -ForegroundColor Yellow
    if ($port -eq $ApiPort) { Write-Host "  Reiniciar encerra qualquer partida em andamento nele." -ForegroundColor Yellow }
    $answer = Read-Host "  Reiniciar com a versão atual do jogo? (S/N)"
    if ($answer -match '^[sS]') {
        & taskkill.exe /PID $p.ProcessId /T /F *> $null
        Start-Sleep -Seconds 1
        return $true
    }
    return $false
}
Write-Host ""
Write-Host "  SQUADFORCE" -ForegroundColor Green
Write-Host "  ----------"

# 1. Pré-requisitos
if (-not (Test-Path $Python)) { Stop-Fail "Ambiente Python (.venv) não encontrado em $Python." }
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) { Stop-Fail "Node.js/npm não encontrado no PATH." }
if (-not (Test-Path (Join-Path $Frontend "node_modules"))) {
    Write-Step "Instalando dependências da interface (primeira execução)..."
    Push-Location $Frontend; npm install --no-fund --no-audit | Out-Null; $ok = $?; Pop-Location
    if (-not $ok) { Stop-Fail "npm install falhou." }
}

# 2. Build de produção da interface (só quando o código mudou)
$dist = Join-Path $Frontend "dist\index.html"
$needBuild = -not (Test-Path $dist)
if (-not $needBuild) {
    $built = (Get-Item $dist).LastWriteTime
    $newer = Get-ChildItem (Join-Path $Frontend "src") -Recurse -File | Where-Object { $_.LastWriteTime -gt $built } | Select-Object -First 1
    $needBuild = $null -ne $newer
}
if ($needBuild) {
    Write-Step "Preparando a interface (build de produção)..."
    Push-Location $Frontend; npm run build *> (Join-Path $LogDir "build.log"); $ok = $?; Pop-Location
    if (-not $ok) { Stop-Fail "Falha no build da interface (veja build.log)." }
}

# 3. Backend (reaproveita se já estiver no ar)
$api = $null
if ((Test-Url $ApiUrl) -and -not (Confirm-Restart $ApiPort "servidor do jogo")) {
    Write-Step "Servidor já em execução na porta $ApiPort."
} else {
    Write-Step "Iniciando o servidor do jogo..."
    $api = Start-Process -FilePath $Python -ArgumentList "-m", "services.gateway", "--port", $ApiPort `
        -WorkingDirectory $Root -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput (Join-Path $LogDir "servidor.log") -RedirectStandardError (Join-Path $LogDir "servidor-erros.log")
    if (-not (Wait-Url $ApiUrl 40 $api)) { Stop-Fail "O servidor não respondeu (veja servidor-erros.log)." }
}

# 4. Interface (reaproveita se já estiver no ar)
$ui = $null
if ((Test-Url $UiUrl) -and -not (Confirm-Restart $UiPort "interface")) {
    Write-Step "Interface já em execução na porta $UiPort."
} else {
    Write-Step "Iniciando a interface..."
    $ui = Start-Process -FilePath "cmd.exe" -ArgumentList "/c", "npx vite preview --port $UiPort --strictPort" `
        -WorkingDirectory $Frontend -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput (Join-Path $LogDir "interface.log") -RedirectStandardError (Join-Path $LogDir "interface-erros.log")
    if (-not (Wait-Url $UiUrl 40 $ui)) { Stop-Fail "A interface não respondeu (veja interface-erros.log)." }
}

# 5. Abre o jogo
Write-Step "Abrindo o jogo no navegador: $UiUrl"
if (-not $env:SQUADFORCE_NO_BROWSER) { Start-Process $UiUrl }
Write-Host ""
Write-Host "  O jogo está rodando. Mantenha esta janela aberta enquanto joga." -ForegroundColor Yellow
Write-Host "  Para encerrar, pressione Enter aqui." -ForegroundColor Yellow
Write-Host ""
try {
    Read-Host | Out-Null
} finally {
    foreach ($p in @($ui, $api)) {
        if ($p -and -not $p.HasExited) { & taskkill.exe /PID $p.Id /T /F *> $null }
    }
    Write-Host "  Jogo encerrado."
}
