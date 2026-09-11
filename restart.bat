@echo off
setlocal enabledelayedexpansion

docker compose down
docker compose up --build -d

echo.
echo [restart] waiting for qwen-tts service: http://127.0.0.1:8000/health ...

set /a tries=0
:wait_tts
set "code="
for /f %%C in ('curl.exe -s --noproxy "*" -o NUL -w "%%{http_code}" http://127.0.0.1:8000/health 2^>NUL') do set "code=%%C"
if "!code!"=="200" (
    echo [restart] qwen-tts is READY.
    goto tts_ready
)
set /a tries+=1
if !tries! GEQ 240 (
    echo [restart] TIMEOUT: qwen-tts /health not ready, check: docker logs qwen-tts
    endlocal
    exit /b 1
)
echo [restart] waiting... attempt !tries!
timeout /t 5 /nobreak >NUL
goto wait_tts

:tts_ready
echo [restart] all services are up.
endlocal
exit /b 0
