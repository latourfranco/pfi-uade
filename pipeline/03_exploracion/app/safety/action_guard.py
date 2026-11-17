"""Módulo de protección de acciones del usuario para prevenir clics destructivos o compras reales."""

import logging
import re
from typing import Any, Dict, List, Optional, Pattern, Tuple
from playwright.async_api import Locator

logger = logging.getLogger(__name__)

# Expresiones regulares para detectar acciones de compra final / pasarela de pago
CHECKOUT_PATTERNS: List[str] = [
    r"\b(pagar|comprar|finalizar\s+compra|confirmar\s+compra|confirmar\s+orden|comprar\s+ahora)\b",
    r"\b(pagar\s+con\s+mercadopago|pagar\s+con\s+tarjeta|transferir\s+fondos|transferir\s+dinero)\b",
    r"\b(pay\s+now|place\s+order|confirm\s+order|complete\s+order|submit\s+payment|purchase\s+now|buy\s+now)\b",
    r"\b(proceed\s+to\s+payment|checkout\s+now)\b",
]

# Expresiones regulares para detectar acciones destructivas críticas e irreversibles
DESTRUCTIVE_PATTERNS: List[str] = [
    r"\b(eliminar\s+cuenta|borrar\s+cuenta|dar\s+de\s+baja|cancelar\s+suscripci[oó]n|vaciar\s+carrito)\b",
    r"\b(delete\s+account|terminate\s+account|cancel\s+subscription|empty\s+cart)\b",
]


class ActionGuard:
    """
    Guardia de acciones del navegador para prevenir la ejecución de operaciones destructivas
    o transacciones financieras reales durante la exploración autónoma.
    """

    def __init__(
        self,
        additional_patterns: Optional[List[str]] = None,
        allow_destructive: bool = False,
    ) -> None:
        """
        Inicializa el guardia de acciones.

        :param additional_patterns: Patrones regex adicionales a considerar como peligrosos.
        :param allow_destructive: Si es True, no bloquea las acciones (útil en entornos de prueba puros).
        """
        self.allow_destructive = allow_destructive
        all_patterns = CHECKOUT_PATTERNS + DESTRUCTIVE_PATTERNS + (additional_patterns or [])

        # Compilar patrones combinados con ignore case
        self._compiled_patterns: List[Pattern[str]] = [
            re.compile(pattern, re.IGNORECASE) for pattern in all_patterns
        ]

    def is_safe_action(
        self,
        element_text: Optional[str] = None,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> Tuple[bool, Optional[str]]:
        """
        Evalúa el texto y los atributos de un elemento para determinar si la acción es segura.

        :param element_text: Texto interno visible o valor del elemento.
        :param attributes: Diccionario opcional con atributos HTML (aria-label, title, name, etc.).
        :return: Tupla (es_seguro, razon_del_bloqueo).
        """
        if self.allow_destructive:
            return True, None

        # Consolidar todos los textos representativos del elemento
        text_candidates: List[str] = []
        if element_text:
            text_candidates.append(element_text)

        if attributes:
            for attr_name in ("aria-label", "title", "value", "placeholder", "name", "id"):
                val = attributes.get(attr_name)
                if isinstance(val, str) and val.strip():
                    text_candidates.append(val.strip())

        combined_text = " ".join(text_candidates).strip()
        if not combined_text:
            return True, None

        for pattern in self._compiled_patterns:
            match = pattern.search(combined_text)
            if match:
                matched_term = match.group(0)
                reason = (
                    f"Acción bloqueada por seguridad preventiva: término potencialmente peligroso "
                    f"detectado ('{matched_term}')."
                )
                logger.warning(f"[ActionGuard] {reason}")
                return False, reason

        return True, None

    async def inspect_locator(self, locator: Locator) -> Tuple[bool, Optional[str]]:
        """
        Inspecciona un Locator de Playwright antes de hacer clic o interactuar.

        :param locator: Localizador del elemento en el DOM.
        :return: Tupla (es_seguro, razon_del_bloqueo).
        """
        if self.allow_destructive:
            return True, None

        try:
            element_text = await locator.inner_text(timeout=1000)
        except Exception:
            try:
                element_text = await locator.input_value(timeout=500)
            except Exception:
                element_text = ""

        attributes: Dict[str, Any] = {}
        for attr in ("aria-label", "title", "value", "name", "id"):
            try:
                val = await locator.get_attribute(attr, timeout=500)
                if val:
                    attributes[attr] = val
            except Exception:
                pass

        return self.is_safe_action(element_text=element_text, attributes=attributes)
