@echo off
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$t = Get-ScheduledTask -TaskName Cameratona -ErrorAction SilentlyContinue;" ^
  "if (-not $t) { Write-Host 'Servico nao instalado.' -ForegroundColor Yellow }" ^
  "else { $i = $t | Get-ScheduledTaskInfo;" ^
  "  Write-Host ('Estado         : ' + $t.State);" ^
  "  Write-Host ('Ultimo inicio  : ' + $i.LastRunTime) }" ^
  "$log = Join-Path '%~dp0..\..\logs' ('fluxo_' + (Get-Date -Format 'yyyy-MM-dd') + '.log');" ^
  "if (Test-Path $log) { Write-Host ''; Write-Host '--- Ultimas linhas do log de hoje ---'; Get-Content $log -Tail 15 -Encoding UTF8 }" ^
  "else { Write-Host 'Sem log de hoje ainda.' }"
echo.
pause
