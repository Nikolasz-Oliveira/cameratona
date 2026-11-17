@echo off
rem Pede permissao de administrador se ainda nao tiver
net session >nul 2>&1
if %errorlevel% neq 0 (
    powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

echo Parando o Cameratona...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$t = Get-ScheduledTask -TaskName Cameratona -ErrorAction SilentlyContinue;" ^
  "if (-not $t) { Write-Host 'Servico nao instalado.' -ForegroundColor Yellow; exit 0 }" ^
  "Disable-ScheduledTask -TaskName Cameratona | Out-Null;" ^
  "Stop-ScheduledTask -TaskName Cameratona;" ^
  "Start-Sleep -Seconds 2;" ^
  "Write-Host ('Estado: ' + (Get-ScheduledTask -TaskName Cameratona).State) -ForegroundColor Green;" ^
  "Write-Host 'Parado. Ele NAO volta sozinho (nem ao reiniciar o PC) ate rodar iniciar_servico.bat.'"
echo.
pause
