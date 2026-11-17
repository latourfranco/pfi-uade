import hashlib
import pytest
from app.anonymization import anonymize_user_id, is_valid_sha256
from app.config import Settings
from app.models import ClientSourceIntegration
from app.services.bigquery_service import BigQueryService


@pytest.mark.unit
def test_sha256_nist_vector():
    """
    Verifica la correctitud criptografica contra un vector de prueba estandar NIST para SHA-256.
    SHA256('abc') = ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad
    """
    expected = "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    result = anonymize_user_id(user_id="abc")
    assert result == expected
    assert is_valid_sha256(result)


@pytest.mark.unit
def test_sha256_determinism():
    """Verifica que el hashing sea estrictamente determinista ante el mismo identificador."""
    uid = "usr_authenticated_98765"
    h1 = anonymize_user_id(user_id=uid)
    h2 = anonymize_user_id(user_id=uid)
    assert h1 is not None
    assert h1 == h2
    assert len(h1) == 64


@pytest.mark.unit
def test_user_id_precedence_over_pseudo_id():
    """
    Verifica la prevalencia de COALESCE(user_id, user_pseudo_id):
    Si `user_id` esta presente, debe ignorarse `user_pseudo_id`.
    """
    h_only_user = anonymize_user_id(user_id="usr_primario")
    h_both = anonymize_user_id(user_id="usr_primario", user_pseudo_id="device_12345")
    assert h_both == h_only_user


@pytest.mark.unit
def test_fallback_to_user_pseudo_id():
    """Verifica el fallback hacia `user_pseudo_id` cuando `user_id` es None o vacio."""
    h_pseudo = anonymize_user_id(user_id=None, user_pseudo_id="device_abc_789")
    h_expected = hashlib.sha256("device_abc_789".encode("utf-8")).hexdigest()
    assert h_pseudo == h_expected

    # Caso user_id con solo espacios en blanco
    h_whitespace = anonymize_user_id(user_id="   ", user_pseudo_id="device_abc_789")
    assert h_whitespace == h_expected


@pytest.mark.unit
def test_null_and_empty_collision_resistance():
    """
    Verifica la resistencia a colisiones con nulos:
    Si ambos campos son nulos o vacios, la funcion retorna None para NO generar
    un hash ficticio compartido (evitando colapsar todos los anonimos en un unico usuario).
    """
    assert anonymize_user_id(user_id=None, user_pseudo_id=None) is None
    assert anonymize_user_id(user_id="", user_pseudo_id="") is None
    assert anonymize_user_id(user_id="  ", user_pseudo_id="  ") is None


@pytest.mark.unit
def test_collision_resistance_distinct_users():
    """Verifica que usuarios con nombres o IDs similares generen hashes distintos."""
    h1 = anonymize_user_id(user_id="usuario_1")
    h2 = anonymize_user_id(user_id="usuario_2")
    h3 = anonymize_user_id(user_id="Usuario_1")
    assert h1 != h2
    assert h1 != h3
    assert h2 != h3


@pytest.mark.unit
def test_avalanche_effect():
    """
    Verifica el efecto avalancha de SHA-256: cambiar un solo bit del input
    debe alterar una fraccion sustancial de los bits del hash resultante.
    """
    h1 = anonymize_user_id(user_id="customer_account_A")
    h2 = anonymize_user_id(user_id="customer_account_B")
    assert h1 is not None and h2 is not None

    b1 = bytes.fromhex(h1)
    b2 = bytes.fromhex(h2)

    # Calcular distancia de Hamming (bits distintos)
    differing_bits = sum(bin(byte1 ^ byte2).count("1") for byte1, byte2 in zip(b1, b2))
    # SHA-256 tiene 256 bits, el efecto avalancha tipico es ~50% de bits (~128)
    assert differing_bits > 80  # Mas del 30% de bits variaron ante 1 caracter modificado


@pytest.mark.unit
def test_is_valid_sha256_validator():
    """Verifica el validador de formato SHA-256."""
    assert is_valid_sha256("ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad") is True
    assert is_valid_sha256("INVALID_HASH") is False
    assert is_valid_sha256("ba7816bf") is False  # Incompleto
    assert is_valid_sha256(None) is False
    assert is_valid_sha256("") is False


@pytest.mark.unit
def test_bigquery_sql_hashing_expression(mock_settings: Settings, sample_clients: list[ClientSourceIntegration]):
    """
    Verifica que la consulta SQL generada por BigQueryService implemente de forma
    fidedigna la expresion de anonimizacion TO_HEX(SHA256(COALESCE(user_id, user_pseudo_id))).
    """
    service = BigQueryService(mock_settings)
    sql = service.build_merge_query(sample_clients[0])
    assert "TO_HEX(SHA256(COALESCE(user_id, user_pseudo_id))) AS id_usuario" in sql
