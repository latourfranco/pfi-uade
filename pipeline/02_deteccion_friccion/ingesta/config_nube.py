"""Configuración de conexión, leída de variables de entorno.

- Local: archivo .env en la raíz (no se versiona; plantilla en .env.example) y credenciales de Google
  con `gcloud auth application-default login`.
- Cloud Run: las variables las inyecta Secret Manager y Google autentica con la cuenta de servicio del
  servicio. No hay claves JSON en ningún caso.

Qué tabla de BigQuery corresponde a cada región NO está acá: vive en Supabase
(public.regiones_fuente_datos), así agregar una región es cargar una fila, sin redeploy.
"""
import os
from dataclasses import dataclass

from preprocesamiento.config import RAIZ

try:   # en Cloud Run no hay .env ni hace falta python-dotenv
    from dotenv import load_dotenv
    load_dotenv(os.path.join(RAIZ, ".env"))
except ImportError:
    pass


@dataclass(frozen=True)
class ConfigNube:
    supabase_db_url: str   # usuario modulo_friccion: solo lee las columnas de configuración que usa
    gcp_project: str       # proyecto donde corren (y se facturan) las consultas de BigQuery


def cargar_config() -> ConfigNube:
    faltan = [v for v in ("SUPABASE_DB_URL_MODULO", "GCP_PROJECT") if not os.environ.get(v)]
    if faltan:
        raise RuntimeError(f"Faltan variables de entorno: {', '.join(faltan)} (ver .env.example)")
    return ConfigNube(supabase_db_url=os.environ["SUPABASE_DB_URL_MODULO"],
                      gcp_project=os.environ["GCP_PROJECT"])
