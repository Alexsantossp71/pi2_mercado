"""
Database Connection Helper for Dispensa Planejada FastAPI SGBD
"""

import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "dispensa.db"


def get_db_connection() -> sqlite3.Connection:
    if not DB_PATH.exists():
        raise FileNotFoundError(f"O banco de dados SGBD SQLite não foi encontrado em: {DB_PATH}. Execute 'python importar_json_para_sqlite.py' primeiro.")
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn
