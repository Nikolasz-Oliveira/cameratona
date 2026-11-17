<#
.SYNOPSIS
  Instala o Cameratona para iniciar sozinho com o Windows (sem janela, sem precisar de login).

.DESCRIPTION
  Cria uma tarefa no Agendador de Tarefas do Windows que:
    - inicia no boot, mesmo sem ninguém logado (conta SYSTEM);
    - roda "python -X utf8 main.py --headless" (sem janela) a partir da pasta do projeto;
    - a cada 5 min confere se o programa está rodando e, se tiver fechado, inicia de novo
      (erros comuns já são tratados pelo próprio programa, que se reinicia sozinho);
    - não tem limite de tempo de execução.

  Para PARAR de vez use Disable-ScheduledTask (senão a verificação de 5 min inicia de novo).

  Execute num PowerShell COMO ADMINISTRADOR, a partir da pasta do projeto:
    powershell -ExecutionPolicy Bypass -File scripts\windows\instalar_servico.ps1

.PARAMETER Python
  Caminho do python.exe. Padrão: venv\Scripts\python.exe ou .venv\Scripts\python.exe do projeto.

.PARAMETER Nome
  Nome da tarefa. Padrão: Cameratona.
#>
param(
    [string]$Python = "",
    [string]$Nome = "Cameratona"
)

$ErrorActionPreference = "Stop"

$admin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
         ).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $admin) {
    Write-Error "Execute este script num PowerShell aberto como Administrador."
}

$Projeto = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path

if (-not $Python) {
    foreach ($c in @("venv\Scripts\python.exe", ".venv\Scripts\python.exe")) {
        $p = Join-Path $Projeto $c
        if (Test-Path $p) { $Python = $p; break }
    }
}
if (-not $Python -or -not (Test-Path $Python)) {
    Write-Error "python.exe do ambiente virtual não encontrado. Informe com -Python C:\caminho\python.exe"
}

if (-not (Test-Path (Join-Path $Projeto "config\settings.local.json"))) {
    Write-Warning "config\settings.local.json não existe: sem token do ThingsBoard os dados não serão enviados."
}

$action = New-ScheduledTaskAction -Execute $Python `
    -Argument "-X utf8 main.py --headless" `
    -WorkingDirectory $Projeto

$noBoot = New-ScheduledTaskTrigger -AtStartup
$noBoot.Delay = "PT30S"   # espera 30 s após o boot (rede e GPU prontas)

# "Cão de guarda": a cada 5 min tenta iniciar; se já estiver rodando, é ignorado (IgnoreNew)
$vigia = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) `
    -RepetitionInterval (New-TimeSpan -Minutes 5)

$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest

$settings = New-ScheduledTaskSettingsSet `
    -RestartCount 9999 -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit ([TimeSpan]::Zero) `
    -StartWhenAvailable `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -MultipleInstances IgnoreNew

Register-ScheduledTask -TaskName $Nome -Action $action -Trigger @($noBoot, $vigia) `
    -Principal $principal -Settings $settings `
    -Description "Cameratona - contagem de pessoas (envia ao ThingsBoard)" -Force | Out-Null

Write-Host ""
Write-Host "Tarefa '$Nome' instalada." -ForegroundColor Green
Write-Host "  Projeto : $Projeto"
Write-Host "  Python  : $Python"
Write-Host ""
Write-Host "Comandos úteis (PowerShell como Administrador):"
Write-Host "  Start-ScheduledTask -TaskName $Nome                                  # iniciar agora"
Write-Host "  Disable-ScheduledTask -TaskName $Nome; Stop-ScheduledTask -TaskName $Nome   # parar de vez"
Write-Host "  Enable-ScheduledTask -TaskName $Nome; Start-ScheduledTask -TaskName $Nome   # voltar a rodar"
Write-Host "  Get-ScheduledTask -TaskName $Nome | Get-ScheduledTaskInfo                  # status"
Write-Host "  Logs em: $Projeto\logs\"

$resp = Read-Host "Iniciar agora? (s/n)"
if ($resp -match "^[sS]") {
    Start-ScheduledTask -TaskName $Nome
    Write-Host "Iniciado. Acompanhe o log em $Projeto\logs\"
}
