import hashlib
import re
from typing import Optional

SHA256_HEX_PATTERN = re.compile(r"^[0-9a-f]{64}$")


def anonymize_user_id(
    user_id: Optional[str] = None,
    user_pseudo_id: Optional[str] = None,
) -> Optional[str]:
    """
    Calcula el identificador anonimizado irreversible mediante SHA-256 en hexadecimal,
    replicando la semantica SQL de BigQuery:
        TO_HEX(SHA256(COALESCE(user_id, user_pseudo_id)))

    Reglas de resolucion:
    1. Si `user_id` es valido y no vacio, se utiliza con prioridad.
    2. Si `user_id` es None o vacio, se recurre a `user_pseudo_id`.
    3. Si ambos son None o vacios, retorna None para evitar colisiones ficticias
       entre usuarios anonimos (a diferencia de hashear un string vacio).
    """
    raw_id: Optional[str] = None

    if user_id and user_id.strip():
        raw_id = user_id.strip()
    elif user_pseudo_id and user_pseudo_id.strip():
        raw_id = user_pseudo_id.strip()

    if raw_id is None:
        return None

    digest = hashlib.sha256(raw_id.encode("utf-8")).hexdigest().lower()
    return digest


def is_valid_sha256(hash_str: Optional[str]) -> bool:
    """Verifica si una cadena cumple con el formato exacto de 64 caracteres hexadecimales SHA-256."""
    if not hash_str:
        return False
    return bool(SHA256_HEX_PATTERN.match(hash_str))
