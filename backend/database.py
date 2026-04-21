from supabase import create_client, Client
from config import Config

_client: Client = None

def get_db() -> Client:
    """
    Devuelve el cliente Supabase singleton.
    Usa la service_role key si está disponible (recomendado para el backend),
    o la anon key como fallback.
    """
    global _client
    if _client is None:
        key = Config.SUPABASE_SERVICE_KEY if Config.SUPABASE_SERVICE_KEY else Config.SUPABASE_ANON_KEY
        if not key:
            raise RuntimeError(
                "No se encontró ninguna clave de Supabase. "
                "Define SUPABASE_SERVICE_KEY o SUPABASE_ANON_KEY en el archivo .env"
            )
        _client = create_client(Config.SUPABASE_URL, key)
    return _client
