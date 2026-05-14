import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Supabase — deben definirse en .env o en las variables de entorno de Render
    SUPABASE_URL         = os.getenv('SUPABASE_URL', '')
    SUPABASE_ANON_KEY    = os.getenv('SUPABASE_ANON_KEY', '')
    SUPABASE_SERVICE_KEY = os.getenv('SUPABASE_SERVICE_KEY', '')

    # Flask — genera un valor seguro con: python -c "import secrets; print(secrets.token_hex(32))"
    SECRET_KEY = os.getenv('SECRET_KEY', '')

    # Flask
    DEBUG = os.getenv('DEBUG', 'False') == 'True'
    PORT  = int(os.getenv('PORT', 5000))
