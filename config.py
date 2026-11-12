import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

try:
    from dotenv import load_dotenv
    load_dotenv(BASE_DIR / '.env')
except ImportError:
    pass

class Config:
    # MySQL Configuration
    MYSQL_HOST = os.environ.get('MYSQL_HOST', '127.0.0.1')
    MYSQL_PORT = int(os.environ.get('MYSQL_PORT', 3306))
    MYSQL_USER = os.environ.get('MYSQL_USER', 'root')
    MYSQL_PASSWORD = os.environ.get('MYSQL_PASSWORD', '')
    MYSQL_DB = os.environ.get('MYSQL_DB', 'LumiSafeDB')
    
    # SQLite Fallback / Mirror Database
    SQLITE_PATH = BASE_DIR / 'lumisafe.db'
    
    # Active driver: 'mysql' or 'sqlite'
    DB_MODE = os.environ.get('DB_MODE', 'auto')
    
    # App Settings
    SECRET_KEY = os.environ.get('SECRET_KEY', 'lumisafe-super-secret-key-2026')
    DEBUG = True

