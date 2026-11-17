"""Pruebas unitarias para el módulo criptográfico AES-256-GCM."""

import base64
import pytest
from app.security.encryption import (
    EncryptionError,
    decrypt_json,
    decrypt_text,
    encrypt_json,
    encrypt_text,
    generate_aes_key,
)


@pytest.mark.unit
def test_generate_aes_key():
    """Verifica que generate_aes_key genere claves de 64 caracteres hex (32 bytes)."""
    key = generate_aes_key()
    assert isinstance(key, str)
    assert len(key) == 64
    raw_bytes = bytes.fromhex(key)
    assert len(raw_bytes) == 32


@pytest.mark.unit
def test_encryption_roundtrip():
    """Verifica el ciclo completo de cifrado y descifrado de texto plano."""
    key = generate_aes_key()
    plaintext = "ContraseñaUltraSecreta_123!@#"

    encrypted = encrypt_text(plaintext, key)
    assert isinstance(encrypted, str)
    assert encrypted != plaintext

    decrypted = decrypt_text(encrypted, key)
    assert decrypted == plaintext


@pytest.mark.unit
def test_encryption_with_base64_and_raw_keys():
    """Verifica el cifrado utilizando claves provistas en base64 y texto plano directo."""
    # Clave de 32 bytes en base64
    raw_32 = b"12345678901234567890123456789012"
    b64_key = base64.urlsafe_b64encode(raw_32).decode("utf-8")
    raw_str_key = raw_32.decode("utf-8")

    plaintext = "Prueba con formatos de clave"

    # Base64
    enc_b64 = encrypt_text(plaintext, b64_key)
    assert decrypt_text(enc_b64, b64_key) == plaintext

    # Raw string 32 bytes
    enc_raw = encrypt_text(plaintext, raw_str_key)
    assert decrypt_text(enc_raw, raw_str_key) == plaintext


@pytest.mark.unit
def test_tampered_ciphertext_detection():
    """Verifica que la modificación de un solo byte del payload cifrado falle por tag inválido."""
    key = generate_aes_key()
    encrypted = encrypt_text("Texto sensible", key)

    # Modificar el contenido base64 decodificado
    payload_bytes = bytearray(base64.urlsafe_b64decode(encrypted))
    payload_bytes[-1] ^= 0x01  # Alterar el último byte del tag GCM
    tampered_b64 = base64.urlsafe_b64encode(payload_bytes).decode("utf-8")

    with pytest.raises(EncryptionError, match="Fallo de autenticación de datos"):
        decrypt_text(tampered_b64, key)


@pytest.mark.unit
def test_decrypt_with_wrong_key():
    """Verifica que intentar descifrar con una clave distinta lance EncryptionError."""
    key1 = generate_aes_key()
    key2 = generate_aes_key()

    encrypted = encrypt_text("Mensaje para key1", key1)

    with pytest.raises(EncryptionError, match="Fallo de autenticación de datos"):
        decrypt_text(encrypted, key2)


@pytest.mark.unit
def test_invalid_key_raises_error():
    """Verifica validaciones ante claves vacías o de longitud incorrecta."""
    with pytest.raises(EncryptionError, match="no puede estar vacía"):
        encrypt_text("test", "")

    with pytest.raises(EncryptionError, match="Longitud o formato de clave inválido"):
        encrypt_text("test", "clave_corta_invalida")


@pytest.mark.unit
def test_invalid_payload_raises_error():
    """Verifica validaciones ante payloads vacíos, truncados o base64 inválido."""
    key = generate_aes_key()

    with pytest.raises(EncryptionError, match="no puede estar vacío"):
        decrypt_text("", key)

    with pytest.raises(EncryptionError, match="base64 válida"):
        decrypt_text("### NO ES BASE64 VÁLIDO ###", key)

    # Payload menor a 28 bytes
    short_payload = base64.urlsafe_b64encode(b"demasiado_corto").decode("utf-8")
    with pytest.raises(EncryptionError, match="truncado o es demasiado corto"):
        decrypt_text(short_payload, key)


@pytest.mark.unit
def test_non_string_plaintext_raises_error():
    """Verifica que encrypt_text requiera explícitamente un string."""
    key = generate_aes_key()
    with pytest.raises(EncryptionError, match="debe ser una cadena de caracteres"):
        encrypt_text(12345, key)  # type: ignore


@pytest.mark.unit
def test_encryption_with_invalid_hex_64_chars():
    """Verifica que una clave de 64 caracteres pero no hexadecimal lance EncryptionError."""
    invalid_64 = "z" * 64
    with pytest.raises(EncryptionError, match="Longitud o formato de clave inválido"):
        encrypt_text("test", invalid_64)


@pytest.mark.unit
def test_encryption_internal_encrypt_error(monkeypatch):
    """Verifica el manejo de excepciones internas durante el cifrado AESGCM."""
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    key = generate_aes_key()

    def mock_encrypt(self, nonce, data, associated_data):
        raise RuntimeError("Fallo criptográfico interno simulado")

    monkeypatch.setattr(AESGCM, "encrypt", mock_encrypt)
    with pytest.raises(EncryptionError, match="Error interno durante la operación de cifrado"):
        encrypt_text("texto plano", key)


@pytest.mark.unit
def test_decryption_invalid_utf8_payload(monkeypatch):
    """Verifica error cuando el payload descifrado no es texto UTF-8 válido."""
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    key = generate_aes_key()
    # Payload válido con nonce de 12 bytes y ciphertext simulado
    payload = base64.urlsafe_b64encode(b"012345678901" + b"simulated_ciphertext_and_tag_16b!").decode("utf-8")

    def mock_decrypt(self, nonce, data, associated_data):
        return b"\xff\xfe\xfd\x80"  # Bytes no decodificables en UTF-8

    monkeypatch.setattr(AESGCM, "decrypt", mock_decrypt)
    with pytest.raises(EncryptionError, match="no corresponde a un texto UTF-8 válido"):
        decrypt_text(payload, key)


@pytest.mark.unit
def test_decryption_unexpected_internal_error(monkeypatch):
    """Verifica error ante excepciones genéricas no previstas en decrypt."""
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    key = generate_aes_key()
    payload = base64.urlsafe_b64encode(b"012345678901" + b"simulated_ciphertext_and_tag_16b!").decode("utf-8")

    def mock_decrypt(self, nonce, data, associated_data):
        raise RuntimeError("Error inesperado en hardware")

    monkeypatch.setattr(AESGCM, "decrypt", mock_decrypt)
    with pytest.raises(EncryptionError, match="Error inesperado al descifrar"):
        decrypt_text(payload, key)


@pytest.mark.unit
def test_encrypt_decrypt_json_roundtrip():
    """Verifica el cifrado y descifrado de estructuras de datos arbitrarias como JSON."""
    key = generate_aes_key()
    sample_storage_state = {
        "cookies": [
            {
                "name": "session_id",
                "value": "xyz123abc",
                "domain": "shop.merch.google",
                "path": "/",
                "expires": 1800000000.0,
                "httpOnly": True,
                "secure": True,
            }
        ],
        "origins": [
            {
                "origin": "https://shop.merch.google",
                "localStorage": [{"name": "cart_id", "value": "cart_999"}],
            }
        ],
    }

    encrypted = encrypt_json(sample_storage_state, key)
    assert isinstance(encrypted, str)
    assert encrypted != ""

    decrypted = decrypt_json(encrypted, key)
    assert decrypted == sample_storage_state


@pytest.mark.unit
def test_encrypt_json_serialization_failure():
    """Verifica que objetos no serializables a JSON lancen EncryptionError."""
    key = generate_aes_key()

    class NonSerializable:
        pass

    with pytest.raises(EncryptionError, match="Error al serializar el contenido a JSON"):
        encrypt_json(NonSerializable(), key)


@pytest.mark.unit
def test_decrypt_json_invalid_structure():
    """Verifica que descifrar texto plano que no sea JSON válido lance EncryptionError."""
    key = generate_aes_key()
    encrypted_text = encrypt_text("esto no es un json válido", key)

    with pytest.raises(EncryptionError, match="no contiene un JSON estructurado válido"):
        decrypt_json(encrypted_text, key)
