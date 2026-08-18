@echo off
set PYTHONIOENCODING=utf-8
cd /d "g:\pi 2 - 2026\scraper\secoes"
"C:\Program Files\Python310\python.exe" -u coletar_pa.py >> "g:\pi 2 - 2026\scraper\secoes\logs\pa_coleta.log" 2>> "g:\pi 2 - 2026\scraper\secoes\logs\pa_err.log"
