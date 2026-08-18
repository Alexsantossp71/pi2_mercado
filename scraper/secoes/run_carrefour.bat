@echo off
set PYTHONIOENCODING=utf-8
cd /d "g:\pi 2 - 2026\scraper\secoes"
"C:\Program Files\Python310\python.exe" -u coletar_carrefour.py >> "g:\pi 2 - 2026\scraper\secoes\logs\carrefour_coleta.log" 2>> "g:\pi 2 - 2026\scraper\secoes\logs\carrefour_err.log"
