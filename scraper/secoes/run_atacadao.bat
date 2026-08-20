@echo off
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
cd /d "g:\pi 2 - 2026\scraper\secoes"
"C:\Program Files\Python310\python.exe" -u coletar_atacadao.py >> "g:\pi 2 - 2026\scraper\secoes\logs\atacadao_coleta.log" 2>> "g:\pi 2 - 2026\scraper\secoes\logs\atacadao_err.log"
