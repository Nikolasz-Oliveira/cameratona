<#
.SYNOPSIS
  Para e remove a tarefa do Cameratona criada por instalar_servico.ps1.

  Execute num PowerShell COMO ADMINISTRADOR:
    powershell -ExecutionPolicy Bypass -File scripts\windows\remover_servico.ps1
#>
param([string]$Nome = "Cameratona")

$ErrorActionPreference = "Stop"

if (-not (Get-ScheduledTask -TaskName $Nome -ErrorAction SilentlyContinue)) {
    Write-Host "Tarefa '$Nome' não está instalada."
    exit 0
}

Stop-ScheduledTask -TaskName $Nome -ErrorAction SilentlyContinue
Unregister-ScheduledTask -TaskName $Nome -Confirm:$false
Write-Host "Tarefa '$Nome' removida. Os totais salvos em data\estado.json foram mantidos." -ForegroundColor Green
