@echo off
rem Pede permissao de administrador se ainda nao tiver
net session >nul 2>&1
if %errorlevel% neq 0 (
    powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

echo Iniciando o Cameratona...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$t = Get-ScheduledTask -TaskName Cameratona -ErrorAction SilentlyContinue;" ^
  "if (-not $t) { Write-Host 'Servico nao instalado. Rode instalar_servico.ps1 primeiro.' -ForegroundColor Red; exit 1 }" ^
  "Enable-ScheduledTask -TaskName Cameratona | Out-Null;" ^
  "Start-ScheduledTask -TaskName Cameratona;" ^
  "Start-Sleep -Seconds 2;" ^
  "Write-Host ('Estado: ' + (Get-ScheduledTask -TaskName Cameratona).State) -ForegroundColor Green;" ^
  "Write-Host 'A IA leva cerca de 30-60 s para carregar. Acompanhe pelo ThingsBoard ou por status_servico.bat.'"
echo.
pause
