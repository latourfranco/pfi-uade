"""Módulo central con lógica de negocio y procesamiento de insights."""

from app.core.processor import InsightProcessor
from app.core.prompt_builder import PromptBuilder

__all__ = ["InsightProcessor", "PromptBuilder"]
