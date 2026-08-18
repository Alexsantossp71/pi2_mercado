@echo off
REM Servidor local para testar o Dispensa Planejada (webapp)
REM Abre: http://localhost:8000
cd /d "%~dp0"
start "" http://localhost:8000
python -m http.server 8000
