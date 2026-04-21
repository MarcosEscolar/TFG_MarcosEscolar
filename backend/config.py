import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Supabase
    SUPABASE_URL     = os.getenv('SUPABASE_URL', 'https://vdktsekpmokvdviqeyzh.supabase.co')
    SUPABASE_ANON_KEY    = os.getenv('SUPABASE_ANON_KEY', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InZka3RzZWtwbW9rdmR2aXFleXpoIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzMxNTQwMjgsImV4cCI6MjA4ODczMDAyOH0.ePQhHxsusJ2y2Sp3H5vRy2cIqmULI3BtZO0KGSX4XTs')
    SUPABASE_SERVICE_KEY = os.getenv('SUPABASE_SERVICE_KEY', '')

    # Flask sessions (para el login que haremos después)
    SECRET_KEY = os.getenv('SECRET_KEY', 'geosfera-dev-secret-cambiar-en-produccion')

    # Flask
    DEBUG = os.getenv('DEBUG', 'True') == 'True'
    PORT  = int(os.getenv('PORT', 5000))
