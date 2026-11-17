"""Módulo de gestión del navegador e instrumentación visual de navegación."""

from app.browser.browser_manager import BrowserManager
from app.browser.obstacle_handler import ObstacleHandler
from app.browser.visual_highlighter import VisualHighlighter

__all__ = [
    "BrowserManager",
    "ObstacleHandler",
    "VisualHighlighter",
]
