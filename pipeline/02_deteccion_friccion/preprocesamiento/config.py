# =============================================================================
# CONFIGURACIÓN — preprocesamiento común del módulo de detección de fricción.
# Cada valor con su fuente (§N del PLAN, en el respaldo del repo).
# =============================================================================
import os

# Raíz del repo (absoluta): el .env local y la carpeta de modelos locales salen de acá.
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# --- Sesiones (§3.3) -----------------------------------------------------------
MIN_EVENTS_PER_SESSION = 4        # Sesiones con < 4 eventos se descartan

# --- Normalización de rutas (§3.2) --------------------------------------------
# Un segmento es {param} si es numérico/hash o si el lugar donde aparece (el prefijo ya
# convertido en plantilla, o la clave del query string) toma más de esta cantidad de valores
# distintos: eso es un parámetro (ej. /product/<slug>, ?keyword=<texto>), no un lugar del sitio.
ROUTE_PARAM_MIN_VALORES = 50
