# ============================================================
#  Sistema de RH — instala o servidor para iniciar junto com o Windows
#  Nao rode este arquivo direto: use o instalar-servico.bat (como Administrador)
# ============================================================
$ErrorActionPreference = "Stop"
$TAREFA = "RH"
$pasta  = $PSScriptRoot

# Remove instalacao anterior que usava o nome antigo, se existir
Unregister-ScheduledTask -TaskName "Sistema RH" -Confirm:$false -ErrorAction SilentlyContinue

# Localiza o Python
$py = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $py) { $py = "C:\Python314\python.exe" }
if (-not (Test-Path $py)) {
    Write-Host "ERRO: Python nao encontrado. Instale o Python ou ajuste o caminho." -ForegroundColor Red
    exit 1
}
if (-not (Test-Path (Join-Path $pasta "server.py"))) {
    Write-Host "ERRO: server.py nao encontrado em $pasta" -ForegroundColor Red
    exit 1
}
if (-not (Test-Path (Join-Path $pasta "config.json"))) {
    Write-Host "ERRO: config.json nao encontrado. Configure a senha do MySQL antes." -ForegroundColor Red
    exit 1
}

Write-Host "Python : $py"
Write-Host "Pasta  : $pasta"
Write-Host ""

# ------------------------------------------------------------
# O servico roda como SYSTEM, que NAO enxerga pacotes instalados
# so no perfil do usuario. Garante o PyMySQL para todos os usuarios.
# ------------------------------------------------------------
$siteGeral = & $py -c "import sysconfig; print(sysconfig.get_paths()['purelib'])"
if (-not (Test-Path (Join-Path $siteGeral "pymysql"))) {
    Write-Host "Instalando o driver PyMySQL para todos os usuarios (necessario p/ o servico)..."
    & $py -m pip install --ignore-installed --quiet PyMySQL
    if (-not (Test-Path (Join-Path $siteGeral "pymysql"))) {
        Write-Host "ERRO: nao foi possivel instalar o PyMySQL em $siteGeral" -ForegroundColor Red
        exit 1
    }
    Write-Host "PyMySQL instalado em $siteGeral" -ForegroundColor Green
} else {
    Write-Host "PyMySQL ja disponivel para todos os usuarios. OK"
}
Write-Host ""

# O que executar: python server.py --log  (--log = sem janela, grava em servidor.log)
$acao = New-ScheduledTaskAction -Execute $py `
    -Argument ("`"" + (Join-Path $pasta "server.py") + "`" --log") `
    -WorkingDirectory $pasta

# Quando: no boot do Windows (nao precisa ninguem logar)
$gatilho = New-ScheduledTaskTrigger -AtStartup

# Como: conta SYSTEM, com privilegios altos
$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest

# Ajustes: sem limite de tempo, reinicia ate 3x se falhar, roda mesmo em bateria
$config = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable `
    -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit (New-TimeSpan -Seconds 0)

Register-ScheduledTask -TaskName $TAREFA -Action $acao -Trigger $gatilho `
    -Principal $principal -Settings $config -Description "Servidor do Sistema de RH (Python + MySQL)" -Force | Out-Null

Write-Host "Tarefa '$TAREFA' registrada." -ForegroundColor Green

# Marca onde comeca esta tentativa no log, para mostrar so o que for novo
$log = Join-Path $pasta "servidor.log"
$linhasAntes = 0
if (Test-Path $log) { $linhasAntes = (Get-Content $log).Count }

Start-ScheduledTask -TaskName $TAREFA
Start-Sleep -Seconds 6
Write-Host "Estado atual: $((Get-ScheduledTask -TaskName $TAREFA).State)"

# Confirma que a porta esta respondendo
$porta = (Get-Content (Join-Path $pasta "config.json") -Raw | ConvertFrom-Json).server.port
try {
    $null = Invoke-WebRequest -Uri "http://localhost:$porta/api/candidatos" -UseBasicParsing -TimeoutSec 10
    Write-Host ""
    Write-Host "==============================================" -ForegroundColor Green
    Write-Host " OK! O servidor esta no ar." -ForegroundColor Green
    Write-Host " Neste computador: http://localhost:$porta" -ForegroundColor Green
    Write-Host " Ele subira sozinho toda vez que o Windows ligar." -ForegroundColor Green
    Write-Host "==============================================" -ForegroundColor Green
} catch {
    Write-Host ""
    Write-Host "A tarefa foi criada, mas o servidor nao respondeu." -ForegroundColor Yellow
    Write-Host "Motivo (ultimas linhas do servidor.log):" -ForegroundColor Yellow
    Write-Host "----------------------------------------------"
    if (Test-Path $log) {
        Get-Content $log | Select-Object -Skip $linhasAntes | Select-Object -Last 15 | ForEach-Object { Write-Host "  $_" }
    } else {
        Write-Host "  (o servidor.log nem chegou a ser criado)"
    }
    Write-Host "----------------------------------------------"
}
