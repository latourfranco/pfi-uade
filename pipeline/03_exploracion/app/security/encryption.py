"""Módulo criptográfico para el cifrado y descifrado seguro de credenciales con AES-256-GCM."""

import base64
import json
import os
import secrets
from typing import Any
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class EncryptionError(Exception):
    """Excepción lanzada cuando ocurre un error durante el cifrado o descifrado."""

    pass


def generate_aes_key() -> str:
    """
    Genera una clave criptográficamente segura de 32 bytes (256 bits) para AES-256.
    Retorna la clave codificada en formato hexadecimal (64 caracteres).
    """
    return secrets.token_hex(32)


def _normalize_key(key: str) -> bytes:
    """
    Convierte y valida una clave provista en formato hexadecimal o base64 a 32 bytes exactos.
    """
    if not isinstance(key, str) or not key.strip():
        raise EncryptionError("La clave de cifrado no puede estar vacía.")

    key_clean = key.strip()

    # Intento 1: decodificar como hexadecimal (64 caracteres para 32 bytes)
    if len(key_clean) == 64:
        try:
            key_bytes = bytes.fromhex(key_clean)
            if len(key_bytes) == 32:
                return key_bytes
        except ValueError:
            pass

    # Intento 2: decodificar como base64 estándar o urlsafe
    try:
        # Añadir padding si hiciera falta
        padded = key_clean + "=" * (-len(key_clean) % 4)
        key_bytes = base64.urlsafe_b64decode(padded)
        if len(key_bytes) == 32:
            return key_bytes
    except Exception:
        pass

    # Si se pasó como string UTF-8 directo de 32 bytes
    raw_bytes = key_clean.encode("utf-8")
    if len(raw_bytes) == 32:
        return raw_bytes

    raise EncryptionError(
        f"Longitud o formato de clave inválido. Se requieren 32 bytes (256 bits), "
        f"recibido: {len(key_clean)} caracteres."
    )


def encrypt_text(plaintext: str, key: str) -> str:
    """
    Cifra un texto plano utilizando AES-256-GCM con un nonce aleatorio de 12 bytes.

    Retorna un string codificado en base64 URL-safe conteniendo el nonce concatenado
    con el texto cifrado y su tag de autenticación (nonce + ciphertext + tag).
    """
    if not isinstance(plaintext, str):
        raise EncryptionError("El texto a cifrar debe ser una cadena de caracteres.")

    key_bytes = _normalize_key(key)
    aesgcm = AESGCM(key_bytes)

    # Nonce estándar recomendado para GCM: 12 bytes (96 bits)
    nonce = os.urandom(12)
    plaintext_bytes = plaintext.encode("utf-8")

    try:
        ciphertext_and_tag = aesgcm.encrypt(nonce, plaintext_bytes, None)
    except Exception as exc:
        raise EncryptionError(f"Error interno durante la operación de cifrado: {exc}") from exc

    # Empaquetar: nonce (12 bytes) + ciphertext_and_tag (variable + 16 bytes tag)
    payload = nonce + ciphertext_and_tag
    return base64.urlsafe_b64encode(payload).decode("utf-8")


def decrypt_text(encrypted_payload: str, key: str) -> str:
    """
    Descifra un payload generado por encrypt_text verificando la integridad del tag GCM.

    Lanza EncryptionError si la clave es incorrecta, si los datos han sido alterados,
    o si el formato está corrupto.
    """
    if not isinstance(encrypted_payload, str) or not encrypted_payload.strip():
        raise EncryptionError("El payload cifrado no puede estar vacío.")

    key_bytes = _normalize_key(key)
    aesgcm = AESGCM(key_bytes)

    try:
        padded = encrypted_payload.strip() + "=" * (-len(encrypted_payload.strip()) % 4)
        payload_bytes = base64.urlsafe_b64decode(padded)
    except Exception as exc:
        raise EncryptionError("El payload provisto no posee una codificación base64 válida.") from exc

    # Un payload válido debe tener al menos: 12 bytes (nonce) + 16 bytes (tag GCM) = 28 bytes
    if len(payload_bytes) < 28:
        raise EncryptionError("El payload cifrado está truncado o es demasiado corto.")

    nonce = payload_bytes[:12]
    ciphertext_and_tag = payload_bytes[12:]

    try:
        decrypted_bytes = aesgcm.decrypt(nonce, ciphertext_and_tag, None)
        return decrypted_bytes.decode("utf-8")
    except InvalidTag as exc:
        raise EncryptionError(
            "Fallo de autenticación de datos: la clave es incorrecta o el contenido fue alterado."
        ) from exc
    except UnicodeDecodeError as exc:
        raise EncryptionError("El contenido descifrado no corresponde a un texto UTF-8 válido.") from exc
    except Exception as exc:
        raise EncryptionError(f"Error inesperado al descifrar: {exc}") from exc


def encrypt_json(data: Any, key: str) -> str:
    """
    Serializa una estructura de datos a formato JSON y la cifra con AES-256-GCM.

    Útil para cifrar diccionarios de estado de sesión (Playwright storage_state) o metadatos complejos.
    """
    try:
        json_str = json.dumps(data, separators=(",", ":"), ensure_ascii=False)
    except Exception as exc:
        raise EncryptionError(f"Error al serializar el contenido a JSON: {exc}") from exc
    return encrypt_text(json_str, key)


def decrypt_json(encrypted_payload: str, key: str) -> Any:
    """
    Descifra un payload con AES-256-GCM y deserializa el texto plano resultante como JSON.

    Lanza EncryptionError si la clave o tag fallan o si el contenido descifrado no es un JSON válido.
    """
    decrypted_text = decrypt_text(encrypted_payload, key)
    try:
        return json.loads(decrypted_text)
    except Exception as exc:
        raise EncryptionError(f"El texto descifrado no contiene un JSON estructurado válido: {exc}") from exc
