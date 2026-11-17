"""Pruebas unitarias para AuthHandler (autenticación automatizada con credenciales AES)."""

from unittest.mock import AsyncMock, MagicMock
import pytest
from app.agent.auth_handler import AuthHandler
from app.models.client_config import ClientInterfaceConfig
from app.security.encryption import encrypt_text, generate_aes_key


@pytest.fixture
def sample_auth_config():
    """Configuración de cliente con autenticación válida."""
    aes_key = generate_aes_key()
    encrypted_pass = encrypt_text("PasswordSecreta999!", aes_key)
    config = ClientInterfaceConfig(
        client_id="cli-auth-test",
        base_url="https://staging.tienda.com",
        requires_authentication=True,
        test_username="usuario_qa",
        test_password_encrypted=encrypted_pass,
        login_url="/iniciar-sesion",
    )
    return config, aes_key


@pytest.mark.asyncio
@pytest.mark.unit
async def test_auth_not_required():
    """Verifica que si no requiere autenticación retorne True inmediatamente."""
    mock_page = MagicMock()
    config = ClientInterfaceConfig(
        client_id="cli-1",
        base_url="https://tienda.com",
        requires_authentication=False,
    )

    success = await AuthHandler.authenticate(mock_page, config)
    assert success is True


@pytest.mark.asyncio
@pytest.mark.unit
async def test_auth_missing_credentials():
    """Verifica retorno False cuando faltan credenciales en la configuración."""
    mock_page = MagicMock()
    config = ClientInterfaceConfig(
        client_id="cli-1",
        base_url="https://tienda.com",
        requires_authentication=True,
        test_username=None,
        test_password_encrypted=None,
    )

    success = await AuthHandler.authenticate(mock_page, config)
    assert success is False


@pytest.mark.asyncio
@pytest.mark.unit
async def test_auth_decryption_failure():
    """Verifica retorno False cuando falla el descifrado AES por clave inválida."""
    mock_page = MagicMock()
    config = ClientInterfaceConfig(
        client_id="cli-1",
        base_url="https://tienda.com",
        requires_authentication=True,
        test_username="test_user",
        test_password_encrypted="payload_cifrado_invalido",
    )

    success = await AuthHandler.authenticate(mock_page, config, encryption_key=generate_aes_key())
    assert success is False


@pytest.mark.asyncio
@pytest.mark.unit
async def test_auth_success_with_login_url(sample_auth_config):
    """Verifica el flujo exitoso de login navegando a login_url y enviando credenciales."""
    config, aes_key = sample_auth_config

    mock_page = MagicMock()
    mock_page.goto = AsyncMock()
    mock_page.wait_for_load_state = AsyncMock()

    mock_user_loc = AsyncMock()
    mock_user_loc.is_visible.return_value = True

    mock_pass_loc = AsyncMock()
    mock_pass_loc.is_visible.return_value = True

    mock_submit_loc = AsyncMock()
    mock_submit_loc.is_visible.return_value = True

    def _locator_mock(selector: str):
        wrapper = MagicMock()
        if "user" in selector or "email" in selector:
            wrapper.first = mock_user_loc
        elif "pass" in selector:
            wrapper.first = mock_pass_loc
        elif "submit" in selector or "Iniciar" in selector:
            wrapper.first = mock_submit_loc
        else:
            loc = AsyncMock()
            loc.is_visible.return_value = False
            wrapper.first = loc
        return wrapper

    mock_page.locator.side_effect = _locator_mock

    success = await AuthHandler.authenticate(mock_page, config, encryption_key=aes_key)

    assert success is True
    mock_page.goto.assert_awaited_once()
    mock_user_loc.fill.assert_awaited_once_with("usuario_qa")
    mock_pass_loc.fill.assert_awaited_once_with("PasswordSecreta999!")
    mock_submit_loc.click.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_auth_goto_exception_continues(sample_auth_config):
    """Verifica que si page.goto lanza excepción al ir a login_url, continúe con el formulario."""
    config, aes_key = sample_auth_config

    mock_page = MagicMock()
    mock_page.goto = AsyncMock(side_effect=Exception("Timeout al navegar a login_url"))
    mock_page.wait_for_load_state = AsyncMock()

    mock_user_loc = AsyncMock()
    mock_user_loc.is_visible.return_value = True
    mock_pass_loc = AsyncMock()
    mock_pass_loc.is_visible.return_value = True
    mock_submit_loc = AsyncMock()
    mock_submit_loc.is_visible.return_value = True

    def _locator_mock(selector: str):
        wrapper = MagicMock()
        if "user" in selector or "email" in selector:
            wrapper.first = mock_user_loc
        elif "pass" in selector:
            wrapper.first = mock_pass_loc
        else:
            wrapper.first = mock_submit_loc
        return wrapper

    mock_page.locator.side_effect = _locator_mock

    success = await AuthHandler.authenticate(mock_page, config, encryption_key=aes_key)
    assert success is True


@pytest.mark.asyncio
@pytest.mark.unit
async def test_auth_username_field_missing(sample_auth_config):
    """Verifica retorno False cuando no se encuentra ningún campo de usuario."""
    config, aes_key = sample_auth_config

    mock_page = MagicMock()
    mock_loc_hidden = AsyncMock()
    mock_loc_hidden.is_visible.return_value = False
    mock_wrapper = MagicMock()
    mock_wrapper.first = mock_loc_hidden
    mock_page.locator.return_value = mock_wrapper

    success = await AuthHandler.authenticate(mock_page, config, encryption_key=aes_key)
    assert success is False


@pytest.mark.asyncio
@pytest.mark.unit
async def test_auth_password_field_missing(sample_auth_config):
    """Verifica retorno False cuando se encuentra usuario pero ningún campo de contraseña."""
    config, aes_key = sample_auth_config

    mock_page = MagicMock()
    mock_user_loc = AsyncMock()
    mock_user_loc.is_visible.return_value = True

    mock_hidden_loc = AsyncMock()
    mock_hidden_loc.is_visible.return_value = False

    def _locator_mock(selector: str):
        wrapper = MagicMock()
        if "user" in selector or "email" in selector:
            wrapper.first = mock_user_loc
        else:
            wrapper.first = mock_hidden_loc
        return wrapper

    mock_page.locator.side_effect = _locator_mock

    success = await AuthHandler.authenticate(mock_page, config, encryption_key=aes_key)
    assert success is False


@pytest.mark.asyncio
@pytest.mark.unit
async def test_auth_submit_fallback_to_enter_success_and_failure(sample_auth_config):
    """Verifica el fallback a presionar Enter y el manejo si la pulsación de tecla falla."""
    config, aes_key = sample_auth_config

    mock_page = MagicMock()
    mock_page.wait_for_load_state = AsyncMock()
    mock_user_loc = AsyncMock()
    mock_user_loc.is_visible.return_value = True
    mock_pass_loc = AsyncMock()
    mock_pass_loc.is_visible.return_value = True
    mock_no_submit = AsyncMock()
    mock_no_submit.is_visible.return_value = False

    def _locator_mock(selector: str):
        wrapper = MagicMock()
        if "user" in selector or "email" in selector:
            wrapper.first = mock_user_loc
        elif "pass" in selector:
            wrapper.first = mock_pass_loc
        else:
            wrapper.first = mock_no_submit
        return wrapper

    mock_page.locator.side_effect = _locator_mock

    # Caso A: Enter tiene éxito
    mock_page.keyboard = AsyncMock()
    success_a = await AuthHandler.authenticate(mock_page, config, encryption_key=aes_key)
    assert success_a is True

    # Caso B: Enter lanza excepción
    mock_page.keyboard.press.side_effect = Exception("Teclado bloqueado")
    success_b = await AuthHandler.authenticate(mock_page, config, encryption_key=aes_key)
    assert success_b is False


@pytest.mark.asyncio
@pytest.mark.unit
async def test_auth_wait_for_load_state_times_out(sample_auth_config):
    """Verifica que si wait_for_load_state lanza timeout después del submit, la autenticación no se aborte."""
    config, aes_key = sample_auth_config

    mock_page = MagicMock()
    mock_page.wait_for_load_state = AsyncMock(side_effect=Exception("Timeout en wait_for_load_state"))

    mock_loc = AsyncMock()
    mock_loc.is_visible.return_value = True
    mock_wrapper = MagicMock()
    mock_wrapper.first = mock_loc
    mock_page.locator.return_value = mock_wrapper

    success = await AuthHandler.authenticate(mock_page, config, encryption_key=aes_key)
    assert success is True


@pytest.mark.asyncio
@pytest.mark.unit
async def test_inject_storage_state_jit_and_errors():
    """Verifica inyección JIT de cookies/localStorage con recarga y manejo seguro de fallos."""
    mock_context = AsyncMock()
    mock_page = MagicMock()
    mock_page.url = "https://shop.example.com/checkout"
    mock_page.evaluate = AsyncMock()
    mock_page.reload = AsyncMock()

    state = {
        "cookies": [{"name": "sid", "value": "abc", "domain": "shop.example.com", "path": "/"}],
        "origins": [
            {"origin": "https://shop.example.com", "localStorage": [{"name": "token", "value": "xyz"}]},
            "invalid_entry",
        ],
    }
    ok = await AuthHandler.inject_storage_state_jit(mock_context, mock_page, state)
    assert ok is True
    mock_context.add_cookies.assert_awaited_once_with(state["cookies"])
    mock_context.add_init_script.assert_awaited_once()
    mock_page.evaluate.assert_awaited_once()
    mock_page.reload.assert_awaited_once_with(wait_until="domcontentloaded")

    mock_context_fail = AsyncMock()
    mock_context_fail.add_cookies.side_effect = Exception("cookie error")
    assert await AuthHandler.inject_storage_state_jit(mock_context_fail, mock_page, state) is False


@pytest.mark.asyncio
@pytest.mark.unit
async def test_authenticate_two_step_and_rejected_login(sample_auth_config):
    """Verifica flujo en 2 pasos (email -> Next -> password) y rechazo con alerta de error."""
    config, aes_key = sample_auth_config
    mock_page = MagicMock()
    mock_page.goto = AsyncMock()
    mock_page.wait_for_load_state = AsyncMock()

    user_loc = AsyncMock()
    user_loc.is_visible.return_value = True
    next_loc = AsyncMock()
    next_loc.is_visible.return_value = True
    pass_loc = AsyncMock()
    pass_loc.is_visible.side_effect = [False] * 5 + [True, True]
    submit_loc = AsyncMock()
    submit_loc.is_visible.return_value = True
    err_loc = AsyncMock()
    err_loc.is_visible.return_value = True
    err_loc.inner_text.return_value = "Invalid password"

    def _loc_two_step(selector: str):
        w = MagicMock()
        w.count = AsyncMock(return_value=0)
        if "email" in selector or "user" in selector:
            w.first = user_loc
        elif "Next" in selector or "Continue" in selector or "Siguiente" in selector:
            w.first = next_loc
        elif "pass" in selector:
            w.first = pass_loc
        elif "submit" in selector or "Iniciar" in selector:
            w.first = submit_loc
        elif "alert" in selector or "error" in selector:
            w.first = err_loc
        else:
            empty = AsyncMock()
            empty.is_visible.return_value = False
            w.first = empty
        return w

    mock_page.locator.side_effect = _loc_two_step
    # Con alerta visible tras submit -> retorna False (credenciales rechazadas)
    ok = await AuthHandler.authenticate(
        mock_page, config, encryption_key=aes_key, navigate_to_login_url=False
    )
    assert ok is False
    mock_page.goto.assert_not_awaited()
    next_loc.click.assert_awaited_once()
    pass_loc.fill.assert_awaited_once_with("PasswordSecreta999!")


@pytest.mark.asyncio
@pytest.mark.unit
async def test_auth_handler_branch_coverage_edge_cases(sample_auth_config):
    """Cubre ramas de count>1 en _find_first_visible_element, origins vacíos en JIT y excepciones."""
    # 1. _find_first_visible_element con count() > 1 (nth(0) oculto, nth(1) visible) + count con excepción
    mock_page_nth = MagicMock()
    hid_cand = AsyncMock()
    hid_cand.is_visible.return_value = False
    vis_cand = AsyncMock()
    vis_cand.is_visible.return_value = True

    wrap_multi = MagicMock()
    wrap_multi.count = AsyncMock(return_value=2)
    wrap_multi.nth.side_effect = [hid_cand, vis_cand]
    wrap_err = MagicMock()
    wrap_err.count = AsyncMock(side_effect=Exception("count err"))
    first_fallback = AsyncMock()
    first_fallback.is_visible.return_value = False
    wrap_err.first = first_fallback

    mock_page_nth.locator.side_effect = [wrap_err, wrap_multi]
    found = await AuthHandler._find_first_visible_element(mock_page_nth, ["sel1", "sel2"], timeout_ms=200)
    assert found is vis_cand

    # 2. inject_storage_state_jit con about:blank, origins malformados/vacíos y fallo en evaluate
    mock_ctx = AsyncMock()
    mock_blank_page = MagicMock()
    mock_blank_page.url = "about:blank"
    mock_blank_page.evaluate = AsyncMock(side_effect=Exception("eval err"))
    mock_blank_page.reload = AsyncMock()
    state = {
        "cookies": [],
        "origins": [
            {"origin": "", "localStorage": [{"name": "a", "value": "b"}]},
            {"origin": "https://a.com", "localStorage": ["bad_item"]},
            {"origin": "https://a.com", "localStorage": [{"name": "k", "value": "v"}]},
        ],
    }
    assert await AuthHandler.inject_storage_state_jit(mock_ctx, mock_blank_page, state) is True
    mock_ctx.add_cookies.assert_not_awaited()
    mock_blank_page.reload.assert_not_awaited()

    # 3. authenticate: next_btn.click lanza error, luego pass_loc aparece, y err_loc.inner_text falla
    config, aes_key = sample_auth_config
    mock_page_2 = MagicMock()
    mock_page_2.goto = AsyncMock()
    mock_page_2.wait_for_load_state = AsyncMock(side_effect=Exception("wait timeout"))
    mock_page_2.keyboard = AsyncMock()

    user_ok = AsyncMock()
    user_ok.is_visible.return_value = True
    next_err = AsyncMock()
    next_err.is_visible.return_value = True
    next_err.click.side_effect = Exception("click err")
    pass_ok = AsyncMock()
    pass_ok.is_visible.side_effect = [False] * 5 + [True, Exception("detached")]
    submit_none = AsyncMock()
    submit_none.is_visible.return_value = False

    def _loc_edge(selector: str):
        w = MagicMock()
        w.count = AsyncMock(return_value=0)
        if "email" in selector or "user" in selector:
            w.first = user_ok
        elif "Next" in selector or "Continue" in selector or "Siguiente" in selector:
            w.first = next_err
        elif "pass" in selector:
            w.first = pass_ok
        else:
            w.first = submit_none
        return w

    mock_page_2.locator.side_effect = _loc_edge
    assert await AuthHandler.authenticate(mock_page_2, config, encryption_key=aes_key) is True
    mock_page_2.keyboard.press.assert_awaited_with("Enter")
