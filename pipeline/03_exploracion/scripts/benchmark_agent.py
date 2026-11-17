#!/usr/bin/env python3
"""Arnés de ejecución para pruebas de performance y escalabilidad del módulo de Exploración Agéntica.

Evalúa la respuesta temporal, throughput, huella de memoria RAM y tasa de éxito
en los patrones de fricción definidos sobre el Google Merchandise Store.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import math
import os
import re
import sys
import time
import tracemalloc
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import psutil

# Asegurar que el root del proyecto esté en el PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.agent.trace_executor import TraceExecutor
from app.browser.browser_manager import BrowserManager
from app.models.exploration_report import ExplorationStatus
from app.models.session_trace import SessionTrace
from scripts.benchmark_friction_patterns import (
    get_benchmark_client_config,
    get_pattern_5_steps,
    get_pattern_10_steps,
    get_pattern_20_steps,
)

logger = logging.getLogger("benchmark_agent")


class ProcessTreeMemoryTracker:
    """Muestrea el consumo de memoria RSS de todo el árbol de procesos (Python + Node + Chromium)."""

    def __init__(self, interval_s: float = 0.05) -> None:
        self.interval_s = interval_s
        self.peak_rss_bytes = 0
        self._running = False
        self._task: asyncio.Task[None] | None = None

    def _get_current_rss(self) -> int:
        try:
            parent = psutil.Process(os.getpid())
            total = parent.memory_info().rss
            for child in parent.children(recursive=True):
                try:
                    total += child.memory_info().rss
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            return total
        except (psutil.Error, OSError):
            return 0

    async def _sample_loop(self) -> None:
        while self._running:
            rss = self._get_current_rss()
            self.peak_rss_bytes = max(self.peak_rss_bytes, rss)
            await asyncio.sleep(self.interval_s)

    def start(self) -> None:
        self.peak_rss_bytes = self._get_current_rss()
        self._running = True
        self._task = asyncio.create_task(self._sample_loop())

    async def stop(self) -> int:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        final_rss = self._get_current_rss()
        self.peak_rss_bytes = max(self.peak_rss_bytes, final_rss)
        return self.peak_rss_bytes


@dataclass
class IterationResult:
    """Resultado individual de una repetición de prueba."""

    escenario: str
    iteracion: int
    duracion_s: float
    eventos_completados: int
    eventos_totales: int
    segundos_por_evento: float
    ram_python_mb: float
    ram_total_mb: float
    capturas_generadas: int
    bytes_capturas_kb: float
    estado: str
    error: str | None = None

    @property
    def pasos_completados(self) -> int:
        """Alias retrocompatible para eventos_completados."""
        return self.eventos_completados

    @property
    def pasos_totales(self) -> int:
        """Alias retrocompatible para eventos_totales."""
        return self.eventos_totales

    @property
    def segundos_por_paso(self) -> float:
        """Alias retrocompatible para segundos_por_evento."""
        return self.segundos_por_evento


@dataclass
class ClientResult:
    """Resultado individual de un cliente en un escenario multi-inquilino (Fase 3)."""

    escenario: str
    iteracion: int
    cliente: str
    duracion_s: float
    eventos_completados: int
    eventos_totales: int
    segundos_por_evento: float
    estado: str


@dataclass
class ScenarioSummary:
    """Resumen estadístico consolidado tras n repeticiones de un escenario."""

    fase: str
    escenario: str
    clientes: int
    patrones_por_cliente: int
    eventos_por_patron: int
    total_eventos: int
    repeticiones: int
    duracion_media_s: float
    duracion_mediana_s: float
    duracion_p90_s: float
    duracion_min_s: float
    duracion_max_s: float
    duracion_std_s: float
    segundos_por_evento_medio: float
    ram_python_pico_mb: float
    ram_total_pico_mb: float
    tasa_exito_pct: float
    estado_general: str

    @property
    def pasos_por_patron(self) -> int:
        """Alias retrocompatible para eventos_por_patron."""
        return self.eventos_por_patron

    @property
    def total_pasos(self) -> int:
        """Alias retrocompatible para total_eventos."""
        return self.total_eventos

    @property
    def segundos_por_paso_medio(self) -> float:
        """Alias retrocompatible para segundos_por_evento_medio."""
        return self.segundos_por_evento_medio


def calculate_percentile(values: list[float], percentile: float) -> float:
    """Calcula el percentil p (0-100) sobre una lista de valores numéricos."""
    if not values:
        return 0.0
    sorted_v = sorted(values)
    k = (len(sorted_v) - 1) * (percentile / 100.0)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return sorted_v[int(k)]
    d0 = sorted_v[int(f)] * (c - k)
    d1 = sorted_v[int(c)] * (k - f)
    return d0 + d1


def calculate_summary(
    fase: str,
    escenario: str,
    clientes: int,
    patrones_por_cliente: int,
    eventos_por_patron: int,
    iterations: list[IterationResult],
) -> ScenarioSummary:
    """Calcula las métricas estadísticas sobre las repeticiones del escenario."""
    n = len(iterations)
    assert n > 0, "No hay iteraciones para calcular estadísticas."

    durations = [it.duracion_s for it in iterations]
    sec_per_events = [it.segundos_por_evento for it in iterations]
    rams_py = [it.ram_python_mb for it in iterations]
    rams_tot = [it.ram_total_mb for it in iterations]
    exitos = sum(1 for it in iterations if it.estado == ExplorationStatus.COMPLETED.value)

    mean_duration = sum(durations) / n
    median_duration = calculate_percentile(durations, 50.0)
    p90_duration = calculate_percentile(durations, 90.0)
    min_duration = min(durations)
    max_duration = max(durations)

    variance = sum((x - mean_duration) ** 2 for x in durations) / n
    std_duration = math.sqrt(variance)

    mean_sec_per_event = sum(sec_per_events) / n
    max_ram_py = max(rams_py)
    max_ram_tot = max(rams_tot)
    tasa_exito = (exitos / n) * 100.0

    estado_general = "Aprobado" if tasa_exito >= 80.0 else "Revisar"

    return ScenarioSummary(
        fase=fase,
        escenario=escenario,
        clientes=clientes,
        patrones_por_cliente=patrones_por_cliente,
        eventos_por_patron=eventos_por_patron,
        total_eventos=clientes * patrones_por_cliente * eventos_por_patron,
        repeticiones=n,
        duracion_media_s=round(mean_duration, 2),
        duracion_mediana_s=round(median_duration, 2),
        duracion_p90_s=round(p90_duration, 2),
        duracion_min_s=round(min_duration, 2),
        duracion_max_s=round(max_duration, 2),
        duracion_std_s=round(std_duration, 2),
        segundos_por_evento_medio=round(mean_sec_per_event, 2),
        ram_python_pico_mb=round(max_ram_py, 2),
        ram_total_pico_mb=round(max_ram_tot, 2),
        tasa_exito_pct=round(tasa_exito, 1),
        estado_general=estado_general,
    )


class AgentBenchmarkRunner:
    """Orquestador de pruebas de performance y escalabilidad del agente de navegación."""

    def __init__(
        self,
        repeats: int = 5,
        dry_run: bool = False,
        save_evidence: bool = False,
        evidence_dir: str = "./evidence_storage/benchmark",
    ) -> None:
        self.repeats = repeats
        self.dry_run = dry_run
        self.save_evidence = save_evidence
        self.evidence_dir = os.path.abspath(evidence_dir)
        self.client_config = get_benchmark_client_config()
        self.browser_manager: BrowserManager | None = None
        self.all_iterations: list[IterationResult] = []
        self.all_client_results: list[ClientResult] = []

    async def initialize(self) -> None:
        """Inicializa el BrowserManager y el proceso Chromium si no es dry-run."""
        if not self.dry_run:
            logger.info("[BenchmarkRunner] Inicializando motor Chromium para pruebas...")
            self.browser_manager = BrowserManager()
            await self.browser_manager.start()
            logger.info("[BenchmarkRunner] Navegador iniciado exitosamente.")

    async def shutdown(self) -> None:
        """Detiene el navegador al finalizar las suites."""
        if self.browser_manager:
            logger.info("[BenchmarkRunner] Cerrando motor Chromium...")
            await self.browser_manager.close()
            self.browser_manager = None

    @staticmethod
    def _write_file_bytes(filepath: str, data: bytes) -> None:
        with open(filepath, "wb") as f:
            f.write(data)

    async def run_single_pattern(
        self,
        pattern_factory: Callable[[int], SessionTrace],
        scenario_name: str,
        iteration_index: int,
    ) -> IterationResult:
        """Ejecuta una única iteración de un patrón de fricción midiendo tiempo y recursos."""
        pattern = pattern_factory(iteration_index)
        total_steps = len(pattern.events)

        capturas_count = 0
        total_capture_bytes = 0

        async def _benchmark_evidence_saver(data: bytes, filename: str, step: int) -> str:
            nonlocal capturas_count, total_capture_bytes
            capturas_count += 1
            total_capture_bytes += len(data)
            if self.save_evidence:
                os.makedirs(self.evidence_dir, exist_ok=True)
                filepath = os.path.join(self.evidence_dir, filename)
                await asyncio.to_thread(self._write_file_bytes, filepath, data)
                return filepath
            return f"mem://evidence/{filename}"

        if self.dry_run:
            tracemalloc.start()
            mem_tracker = ProcessTreeMemoryTracker()
            mem_tracker.start()
            start_t = time.perf_counter()
            await asyncio.sleep(0.05 * total_steps)
            elapsed = time.perf_counter() - start_t
            _, peak_py = tracemalloc.get_traced_memory()
            tracemalloc.stop()
            peak_tot = await mem_tracker.stop()

            sec_per_event = elapsed / total_steps if total_steps > 0 else 0.0
            res = IterationResult(
                escenario=scenario_name,
                iteracion=iteration_index,
                duracion_s=round(elapsed, 3),
                eventos_completados=total_steps,
                eventos_totales=total_steps,
                segundos_por_evento=round(sec_per_event, 2),
                ram_python_mb=round(peak_py / (1024 * 1024), 2),
                ram_total_mb=round(peak_tot / (1024 * 1024), 2),
                capturas_generadas=total_steps,
                bytes_capturas_kb=round(total_steps * 35.0, 1),
                estado=ExplorationStatus.COMPLETED.value,
            )
            self.all_iterations.append(res)
            return res

        assert self.browser_manager is not None, "El BrowserManager debe estar inicializado."

        executor = TraceExecutor(
            browser_manager=self.browser_manager,
            evidence_saver=_benchmark_evidence_saver,
        )

        tracemalloc.start()
        mem_tracker = ProcessTreeMemoryTracker()
        mem_tracker.start()
        start_t = time.perf_counter()
        error_str: str | None = None

        try:
            report = await executor.execute_trace(pattern, self.client_config)
            elapsed = time.perf_counter() - start_t
            _, peak_py = tracemalloc.get_traced_memory()
            tracemalloc.stop()
            peak_tot = await mem_tracker.stop()

            completed = report.completed_steps
            status_val = report.status.value
            error_str = report.error_message
        except Exception as exc:  # noqa: BLE001
            elapsed = time.perf_counter() - start_t
            _, peak_py = tracemalloc.get_traced_memory()
            tracemalloc.stop()
            peak_tot = await mem_tracker.stop()
            completed = 0
            status_val = ExplorationStatus.FAILED.value
            error_str = str(exc)

        sec_per_event = elapsed / completed if completed > 0 else 0.0

        result = IterationResult(
            escenario=scenario_name,
            iteracion=iteration_index,
            duracion_s=round(elapsed, 3),
            eventos_completados=completed,
            eventos_totales=total_steps,
            segundos_por_evento=round(sec_per_event, 2),
            ram_python_mb=round(peak_py / (1024 * 1024), 2),
            ram_total_mb=round(peak_tot / (1024 * 1024), 2),
            capturas_generadas=capturas_count,
            bytes_capturas_kb=round(total_capture_bytes / 1024, 1),
            estado=status_val,
            error=error_str,
        )
        self.all_iterations.append(result)
        return result

    async def run_scenario(
        self,
        fase: str,
        scenario_name: str,
        eventos_count: int,
        pattern_factory: Callable[[int], SessionTrace],
        on_iteration_done: Callable[[IterationResult], None] | None = None,
    ) -> ScenarioSummary:
        """Ejecuta las n repeticiones de un escenario dado."""
        iterations: list[IterationResult] = []
        logger.info(
            f"\n>>> Iniciando Escenario '{scenario_name}' ({eventos_count} eventos) - {self.repeats} repeticiones..."
        )

        for i in range(1, self.repeats + 1):
            res = await self.run_single_pattern(pattern_factory, scenario_name, i)
            iterations.append(res)
            if on_iteration_done:
                on_iteration_done(res)
            dur_str = format_num_es(res.duracion_s, 2)
            sec_str = format_num_es(res.segundos_por_evento, 2)
            ram_py_str = format_num_es(res.ram_python_mb, 2)
            ram_tot_str = format_num_es(res.ram_total_mb, 2)
            logger.info(
                f"  [{scenario_name}] Rep {i}/{self.repeats}: "
                f"{dur_str} s | {sec_str} s/evento | "
                f"RAM: Py={ram_py_str} MB, Tot={ram_tot_str} MB | "
                f"{res.eventos_completados}/{res.eventos_totales} | {res.estado}"
            )

        summary = calculate_summary(
            fase=fase,
            escenario=scenario_name,
            clientes=1,
            patrones_por_cliente=1,
            eventos_por_patron=eventos_count,
            iterations=iterations,
        )
        return summary

    async def run_phase_1(
        self,
        on_iteration_done: Callable[[IterationResult], None] | None = None,
    ) -> list[ScenarioSummary]:
        """Ejecuta la Fase 1 completa: Sensibilidad a la Longitud del Patrón (5, 10, 20 eventos)."""
        logger.info("\n" + "=" * 80)
        logger.info(" FASE 1: Sensibilidad a la Longitud del Patrón de Fricción (Cliente Único)")
        logger.info(f" Repeticiones por escenario: n={self.repeats} | Dry-Run: {self.dry_run}")
        logger.info("=" * 80)

        scenarios = [
            ("1cli-5eventos", 5, get_pattern_5_steps),
            ("1cli-10eventos", 10, get_pattern_10_steps),
            ("1cli-20eventos", 20, get_pattern_20_steps),
        ]

        summaries: list[ScenarioSummary] = []
        for name, steps, factory in scenarios:
            summary = await self.run_scenario(
                fase="Fase 1 (Longitud)",
                scenario_name=name,
                eventos_count=steps,
                pattern_factory=factory,
                on_iteration_done=on_iteration_done,
            )
            summaries.append(summary)

        return summaries

    async def run_batch_iteration(
        self,
        patterns_count: int,
        pattern_factory: Callable[[int], SessionTrace],
        scenario_name: str,
        iteration_index: int,
        concurrency_limit: int = 3,
    ) -> IterationResult:
        """Ejecuta una repetición de un lote de patrones de fricción con regulación de concurrencia."""
        patterns = [pattern_factory(i) for i in range(1, patterns_count + 1)]
        semaphore = asyncio.Semaphore(concurrency_limit)
        capturas_count = 0
        total_capture_bytes = 0

        async def _benchmark_evidence_saver(data: bytes, filename: str, step: int) -> str:
            nonlocal capturas_count, total_capture_bytes
            capturas_count += 1
            total_capture_bytes += len(data)
            if self.save_evidence:
                os.makedirs(self.evidence_dir, exist_ok=True)
                filepath = os.path.join(self.evidence_dir, filename)
                await asyncio.to_thread(self._write_file_bytes, filepath, data)
                return filepath
            return f"mem://evidence/{filename}"

        async def _execute_single_in_batch(p: SessionTrace) -> tuple[int, int, str, str | None]:
            async with semaphore:
                if self.dry_run:
                    await asyncio.sleep(0.04 * len(p.events))
                    return len(p.events), len(p.events), ExplorationStatus.COMPLETED.value, None

                assert self.browser_manager is not None, "El BrowserManager debe estar inicializado."
                executor = TraceExecutor(
                    browser_manager=self.browser_manager,
                    evidence_saver=_benchmark_evidence_saver,
                )
                try:
                    report = await executor.execute_trace(p, self.client_config)
                    return report.completed_steps, len(p.events), report.status.value, report.error_message
                except Exception as exc:  # noqa: BLE001
                    return 0, len(p.events), ExplorationStatus.FAILED.value, str(exc)

        tracemalloc.start()
        mem_tracker = ProcessTreeMemoryTracker()
        mem_tracker.start()
        start_t = time.perf_counter()

        tasks = [_execute_single_in_batch(p) for p in patterns]
        results = await asyncio.gather(*tasks)

        elapsed = time.perf_counter() - start_t
        _, peak_py = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        peak_tot = await mem_tracker.stop()

        completed_events_total = sum(r[0] for r in results)
        total_events_batch = sum(r[1] for r in results)
        has_failed = any(r[2] == ExplorationStatus.FAILED.value for r in results)
        has_partial = any(r[2] == ExplorationStatus.PARTIAL.value for r in results)

        if has_failed:
            status_val = ExplorationStatus.FAILED.value
        elif has_partial or completed_events_total < total_events_batch:
            status_val = ExplorationStatus.PARTIAL.value
        else:
            status_val = ExplorationStatus.COMPLETED.value

        sec_per_event = elapsed / completed_events_total if completed_events_total > 0 else 0.0

        errors = [r[3] for r in results if r[3] is not None]
        error_summary = "; ".join(errors) if errors else None

        result = IterationResult(
            escenario=scenario_name,
            iteracion=iteration_index,
            duracion_s=round(elapsed, 3),
            eventos_completados=completed_events_total,
            eventos_totales=total_events_batch,
            segundos_por_evento=round(sec_per_event, 2),
            ram_python_mb=round(peak_py / (1024 * 1024), 2),
            ram_total_mb=round(peak_tot / (1024 * 1024), 2),
            capturas_generadas=capturas_count if not self.dry_run else total_events_batch,
            bytes_capturas_kb=round(total_capture_bytes / 1024, 1) if not self.dry_run else round(total_events_batch * 35.0, 1),
            estado=status_val,
            error=error_summary,
        )
        self.all_iterations.append(result)
        return result

    async def run_batch_scenario(
        self,
        fase: str,
        scenario_name: str,
        patterns_count: int,
        events_per_pattern: int,
        pattern_factory: Callable[[int], SessionTrace],
        concurrency_limit: int = 3,
        on_iteration_done: Callable[[IterationResult], None] | None = None,
    ) -> ScenarioSummary:
        """Ejecuta las n repeticiones de un escenario de lote (batch)."""
        iterations: list[IterationResult] = []
        total_events = patterns_count * events_per_pattern
        logger.info(
            f"\n>>> Iniciando Escenario '{scenario_name}' ({patterns_count} patrones, {total_events} eventos totales) "
            f"[Concurrencia máx: {concurrency_limit}] - {self.repeats} repeticiones..."
        )

        for i in range(1, self.repeats + 1):
            res = await self.run_batch_iteration(
                patterns_count=patterns_count,
                pattern_factory=pattern_factory,
                scenario_name=scenario_name,
                iteration_index=i,
                concurrency_limit=concurrency_limit,
            )
            iterations.append(res)
            if on_iteration_done:
                on_iteration_done(res)
            dur_str = format_num_es(res.duracion_s, 2)
            sec_str = format_num_es(res.segundos_por_evento, 2)
            ram_py_str = format_num_es(res.ram_python_mb, 2)
            ram_tot_str = format_num_es(res.ram_total_mb, 2)
            logger.info(
                f"  [{scenario_name}] Rep {i}/{self.repeats}: "
                f"{dur_str} s | {sec_str} s/evento | "
                f"RAM: Py={ram_py_str} MB, Tot={ram_tot_str} MB | "
                f"{res.eventos_completados}/{res.eventos_totales} | {res.estado}"
            )

        summary = calculate_summary(
            fase=fase,
            escenario=scenario_name,
            clientes=1,
            patrones_por_cliente=patterns_count,
            eventos_por_patron=events_per_pattern,
            iterations=iterations,
        )
        return summary

    async def run_phase_2(
        self,
        on_iteration_done: Callable[[IterationResult], None] | None = None,
    ) -> list[ScenarioSummary]:
        """Ejecuta la Fase 2: Sensibilidad al Volumen de Patrones por Lote (1, 5 y 10 patrones de 10 eventos c/u)."""
        logger.info("\n" + "=" * 80)
        logger.info(" FASE 2: Sensibilidad al Volumen de Patrones por Lote (Escalamiento Intra-Cliente)")
        logger.info(f" Regulación por semáforo: MAX_CONCURRENCY = 3 | Repeticiones: n={self.repeats} | Dry-Run: {self.dry_run}")
        logger.info("=" * 80)

        # 3 escalones definidos: 1, 5 y 10 patrones de 10 eventos cada uno
        scenarios = [
            ("1cli-1patron", 1, 10, get_pattern_10_steps),
            ("1cli-5patrones", 5, 10, get_pattern_10_steps),
            ("1cli-10patrones", 10, 10, get_pattern_10_steps),
        ]

        summaries: list[ScenarioSummary] = []
        for name, p_count, e_per_p, factory in scenarios:
            summary = await self.run_batch_scenario(
                fase="Fase 2 (Volumen)",
                scenario_name=name,
                patterns_count=p_count,
                events_per_pattern=e_per_p,
                pattern_factory=factory,
                concurrency_limit=3,
                on_iteration_done=on_iteration_done,
            )
            summaries.append(summary)

        return summaries

    async def run_multiclient_iteration(
        self,
        clients_count: int,
        patterns_per_client: int,
        events_per_pattern: int,
        pattern_factory: Callable[[int], SessionTrace],
        scenario_name: str,
        iteration_index: int,
        concurrency_per_client: int = 3,
        global_concurrency_limit: int = 6,
    ) -> tuple[IterationResult, list[ClientResult]]:
        """Ejecuta una iteración multi-inquilino midiendo latencia por cliente y global."""
        global_semaphore = asyncio.Semaphore(global_concurrency_limit)
        capturas_count = 0
        total_capture_bytes = 0

        async def _benchmark_evidence_saver(data: bytes, filename: str, step: int) -> str:
            nonlocal capturas_count, total_capture_bytes
            capturas_count += 1
            total_capture_bytes += len(data)
            if self.save_evidence:
                os.makedirs(self.evidence_dir, exist_ok=True)
                filepath = os.path.join(self.evidence_dir, filename)
                await asyncio.to_thread(self._write_file_bytes, filepath, data)
                return filepath
            return f"mem://evidence/{filename}"

        async def _execute_single_pattern(
            p: SessionTrace,
            client_sem: asyncio.Semaphore,
        ) -> tuple[int, int, str, str | None]:
            async with client_sem, global_semaphore:
                if self.dry_run:
                    await asyncio.sleep(0.04 * len(p.events))
                    return len(p.events), len(p.events), ExplorationStatus.COMPLETED.value, None

                assert self.browser_manager is not None, "El BrowserManager debe estar inicializado."
                executor = TraceExecutor(
                    browser_manager=self.browser_manager,
                    evidence_saver=_benchmark_evidence_saver,
                )
                try:
                    report = await executor.execute_trace(p, self.client_config)
                    return report.completed_steps, len(p.events), report.status.value, report.error_message
                except Exception as exc:  # noqa: BLE001
                    return 0, len(p.events), ExplorationStatus.FAILED.value, str(exc)

        async def _run_client(c_idx: int) -> ClientResult:
            c_name = f"Cliente {c_idx}"
            c_semaphore = asyncio.Semaphore(concurrency_per_client)
            c_patterns = [pattern_factory(p) for p in range(1, patterns_per_client + 1)]
            c_start = time.perf_counter()

            tasks = [_execute_single_pattern(p, c_semaphore) for p in c_patterns]
            c_results = await asyncio.gather(*tasks)

            c_elapsed = time.perf_counter() - c_start
            c_completed_events = sum(r[0] for r in c_results)
            c_total_events = sum(r[1] for r in c_results)
            has_failed = any(r[2] == ExplorationStatus.FAILED.value for r in c_results)
            has_partial = any(r[2] == ExplorationStatus.PARTIAL.value for r in c_results)

            if has_failed:
                c_status = ExplorationStatus.FAILED.value
            elif has_partial or c_completed_events < c_total_events:
                c_status = ExplorationStatus.PARTIAL.value
            else:
                c_status = ExplorationStatus.COMPLETED.value

            sec_ev = c_elapsed / c_completed_events if c_completed_events > 0 else 0.0

            return ClientResult(
                escenario=scenario_name,
                iteracion=iteration_index,
                cliente=c_name,
                duracion_s=round(c_elapsed, 3),
                eventos_completados=c_completed_events,
                eventos_totales=c_total_events,
                segundos_por_evento=round(sec_ev, 2),
                estado=c_status,
            )

        tracemalloc.start()
        mem_tracker = ProcessTreeMemoryTracker()
        mem_tracker.start()
        start_t = time.perf_counter()

        client_tasks = [_run_client(c) for c in range(1, clients_count + 1)]
        client_res_list = await asyncio.gather(*client_tasks)

        elapsed = time.perf_counter() - start_t
        _, peak_py = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        peak_tot = await mem_tracker.stop()

        completed_events_total = sum(cr.eventos_completados for cr in client_res_list)
        total_events_batch = sum(cr.eventos_totales for cr in client_res_list)
        has_failed = any(cr.estado == ExplorationStatus.FAILED.value for cr in client_res_list)
        has_partial = any(cr.estado == ExplorationStatus.PARTIAL.value for cr in client_res_list)

        if has_failed:
            status_val = ExplorationStatus.FAILED.value
        elif has_partial or completed_events_total < total_events_batch:
            status_val = ExplorationStatus.PARTIAL.value
        else:
            status_val = ExplorationStatus.COMPLETED.value

        sec_per_event = elapsed / completed_events_total if completed_events_total > 0 else 0.0

        it_result = IterationResult(
            escenario=scenario_name,
            iteracion=iteration_index,
            duracion_s=round(elapsed, 3),
            eventos_completados=completed_events_total,
            eventos_totales=total_events_batch,
            segundos_por_evento=round(sec_per_event, 2),
            ram_python_mb=round(peak_py / (1024 * 1024), 2),
            ram_total_mb=round(peak_tot / (1024 * 1024), 2),
            capturas_generadas=capturas_count if not self.dry_run else total_events_batch,
            bytes_capturas_kb=round(total_capture_bytes / 1024, 1) if not self.dry_run else round(total_events_batch * 35.0, 1),
            estado=status_val,
        )
        self.all_iterations.append(it_result)
        self.all_client_results.extend(client_res_list)
        return it_result, client_res_list

    async def run_multiclient_scenario(
        self,
        fase: str,
        scenario_name: str,
        clients_count: int,
        patterns_per_client: int,
        events_per_pattern: int,
        pattern_factory: Callable[[int], SessionTrace],
        concurrency_per_client: int = 3,
        global_concurrency_limit: int = 6,
        on_iteration_done: Callable[[IterationResult], None] | None = None,
    ) -> ScenarioSummary:
        """Ejecuta las n repeticiones de un escenario multi-inquilino."""
        iterations: list[IterationResult] = []
        total_events = clients_count * patterns_per_client * events_per_pattern
        logger.info(
            f"\n>>> Iniciando Escenario Multi-Inquilino '{scenario_name}' "
            f"({clients_count} clientes, {patterns_per_client} patrones/cli, {total_events} eventos totales) "
            f"[Concurrencia cliente: {concurrency_per_client}, Global: {global_concurrency_limit}] - {self.repeats} repeticiones..."
        )

        for i in range(1, self.repeats + 1):
            it_res, client_res = await self.run_multiclient_iteration(
                clients_count=clients_count,
                patterns_per_client=patterns_per_client,
                events_per_pattern=events_per_pattern,
                pattern_factory=pattern_factory,
                scenario_name=scenario_name,
                iteration_index=i,
                concurrency_per_client=concurrency_per_client,
                global_concurrency_limit=global_concurrency_limit,
            )
            iterations.append(it_res)
            if on_iteration_done:
                on_iteration_done(it_res)
            dur_str = format_num_es(it_res.duracion_s, 2)
            sec_str = format_num_es(it_res.segundos_por_evento, 2)
            ram_py_str = format_num_es(it_res.ram_python_mb, 2)
            ram_tot_str = format_num_es(it_res.ram_total_mb, 2)
            client_durations_str = ", ".join(f"{c.cliente}: {format_num_es(c.duracion_s, 1)}s" for c in client_res)
            logger.info(
                f"  [{scenario_name}] Rep {i}/{self.repeats}: Global={dur_str} s | {sec_str} s/evento | "
                f"RAM: Py={ram_py_str} MB, Tot={ram_tot_str} MB | Clientes: [{client_durations_str}] | {it_res.estado}"
            )

        summary = calculate_summary(
            fase=fase,
            escenario=scenario_name,
            clientes=clients_count,
            patrones_por_cliente=patterns_per_client,
            eventos_por_patron=events_per_pattern,
            iterations=iterations,
        )
        return summary

    async def run_isolated_multiclient_iteration(
        self,
        clients_count: int,
        patterns_per_client: int,
        events_per_pattern: int,
        scenario_name: str,
        iteration_index: int,
    ) -> tuple[IterationResult, list[ClientResult]]:
        """Lanza N subprocesos autónomos en paralelo, simulando instancias efímeras de Cloud Run."""
        worker_script = os.path.abspath(__file__)
        python_bin = sys.executable

        async def _spawn_worker(client_id: int) -> dict[str, Any]:
            cmd = [
                python_bin,
                worker_script,
                "--worker-instance",
                "--client-id",
                str(client_id),
                "--patterns-per-client",
                str(patterns_per_client),
                "--events-per-pattern",
                str(events_per_pattern),
                "--scenario-name",
                scenario_name,
                "--iteration-index",
                str(iteration_index),
            ]
            if self.dry_run:
                cmd.append("--dry-run")
            if self.save_evidence:
                cmd.append("--save-evidence")

            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()
            if proc.returncode != 0:
                err_text = stderr.decode().strip()
                logger.error(f"[Instancia Cliente {client_id}] Falló (código {proc.returncode}): {err_text}")
                return {
                    "client_id": client_id,
                    "cliente": f"Cliente {client_id}",
                    "duracion_s": 0.0,
                    "eventos_completados": 0,
                    "eventos_totales": patterns_per_client * events_per_pattern,
                    "segundos_por_evento": 0.0,
                    "ram_python_mb": 0.0,
                    "ram_total_mb": 0.0,
                    "capturas_count": 0,
                    "capturas_bytes": 0,
                    "estado": "FAILED",
                    "error": err_text,
                }

            for line in stdout.decode().splitlines():
                if "\"__type__\": \"WORKER_RESULT\"" in line:
                    return json.loads(line)

            return {
                "client_id": client_id,
                "cliente": f"Cliente {client_id}",
                "duracion_s": 0.0,
                "eventos_completados": 0,
                "eventos_totales": patterns_per_client * events_per_pattern,
                "segundos_por_evento": 0.0,
                "ram_python_mb": 0.0,
                "ram_total_mb": 0.0,
                "capturas_count": 0,
                "capturas_bytes": 0,
                "estado": "FAILED",
                "error": "No se encontró el resultado JSON del worker.",
            }

        start_t = time.perf_counter()
        worker_tasks = [_spawn_worker(c) for c in range(1, clients_count + 1)]
        raw_results = await asyncio.gather(*worker_tasks)
        elapsed = time.perf_counter() - start_t

        client_res_list = [
            ClientResult(
                escenario=scenario_name,
                iteracion=iteration_index,
                cliente=r["cliente"],
                duracion_s=round(r["duracion_s"], 3),
                eventos_completados=r["eventos_completados"],
                eventos_totales=r["eventos_totales"],
                segundos_por_evento=round(r["segundos_por_evento"], 2),
                estado=r["estado"],
            )
            for r in raw_results
        ]
        completed_events_total = sum(r["eventos_completados"] for r in raw_results)
        total_events_batch = sum(r["eventos_totales"] for r in raw_results)
        has_failed = any(r["estado"] == ExplorationStatus.FAILED.value for r in raw_results)
        has_partial = any(r["estado"] == ExplorationStatus.PARTIAL.value for r in raw_results)
        status_val = ExplorationStatus.COMPLETED.value if not has_failed and not has_partial else ExplorationStatus.FAILED.value

        sec_per_event = elapsed / completed_events_total if completed_events_total > 0 else 0.0
        avg_py_ram = sum(r["ram_python_mb"] for r in raw_results) / len(raw_results) if raw_results else 0.0
        avg_tot_ram = sum(r["ram_total_mb"] for r in raw_results) / len(raw_results) if raw_results else 0.0
        total_captures = sum(r.get("capturas_count", 0) for r in raw_results)
        total_capture_bytes = sum(r.get("capturas_bytes", 0) for r in raw_results)

        it_result = IterationResult(
            escenario=scenario_name,
            iteracion=iteration_index,
            duracion_s=round(elapsed, 3),
            eventos_completados=completed_events_total,
            eventos_totales=total_events_batch,
            segundos_por_evento=round(sec_per_event, 2),
            ram_python_mb=round(avg_py_ram, 2),
            ram_total_mb=round(avg_tot_ram, 2),
            capturas_generadas=total_captures,
            bytes_capturas_kb=round(total_capture_bytes / 1024, 1),
            estado=status_val,
        )
        self.all_iterations.append(it_result)
        self.all_client_results.extend(client_res_list)
        return it_result, client_res_list

    async def run_isolated_multiclient_scenario(
        self,
        fase: str,
        scenario_name: str,
        clients_count: int,
        patterns_per_client: int,
        events_per_pattern: int,
        on_iteration_done: Callable[[IterationResult], None] | None = None,
    ) -> ScenarioSummary:
        """Ejecuta repeticiones de un escenario multi-inquilino de instancias aisladas de Cloud Run."""
        iterations: list[IterationResult] = []
        total_events = clients_count * patterns_per_client * events_per_pattern
        logger.info(
            f"\n>>> Iniciando Escenario Multi-Inquilino (Instancias Aisladas Cloud Run) '{scenario_name}' "
            f"({clients_count} instancias, {patterns_per_client} patrones/instancia, {total_events} eventos totales) "
            f"- {self.repeats} repeticiones..."
        )

        for i in range(1, self.repeats + 1):
            it_res, client_res = await self.run_isolated_multiclient_iteration(
                clients_count=clients_count,
                patterns_per_client=patterns_per_client,
                events_per_pattern=events_per_pattern,
                scenario_name=scenario_name,
                iteration_index=i,
            )
            iterations.append(it_res)
            if on_iteration_done:
                on_iteration_done(it_res)
            dur_str = format_num_es(it_res.duracion_s, 2)
            sec_str = format_num_es(it_res.segundos_por_evento, 2)
            ram_py_str = format_num_es(it_res.ram_python_mb, 2)
            ram_tot_str = format_num_es(it_res.ram_total_mb, 2)
            client_durations_str = ", ".join(f"{c.cliente}: {format_num_es(c.duracion_s, 1)}s" for c in client_res)
            logger.info(
                f"  [{scenario_name}] Rep {i}/{self.repeats}: Global={dur_str} s | {sec_str} s/evento | "
                f"RAM Instancia Promedio: Py={ram_py_str} MB, Tot={ram_tot_str} MB | Clientes: [{client_durations_str}] | {it_res.estado}"
            )

        summary = calculate_summary(
            fase=fase,
            escenario=scenario_name,
            clientes=clients_count,
            patrones_por_cliente=patterns_per_client,
            eventos_por_patron=events_per_pattern,
            iterations=iterations,
        )
        return summary

    async def run_phase_3(
        self,
        on_iteration_done: Callable[[IterationResult], None] | None = None,
    ) -> list[ScenarioSummary]:
        """Ejecuta la Fase 3: Escalabilidad Multi-Inquilino (1, 2 y 3 instancias aisladas de Cloud Run)."""
        logger.info("\n" + "=" * 80)
        logger.info(" FASE 3: Escalabilidad Multi-Inquilino (Instancias Aisladas de Cloud Run)")
        logger.info(f" 3 patrones/instancia (10 ev/patrón) | Escalones: 1, 2 y 3 clientes | Repeticiones: n={self.repeats}")
        logger.info("=" * 80)

        # 3 escalones definidos: 1, 2 y 3 clientes (3 patrones de 10 eventos c/u en instancias separadas)
        scenarios = [
            ("1cli-3patrones", 1, 3, 10),
            ("2cli-3patrones", 2, 3, 10),
            ("3cli-3patrones", 3, 3, 10),
        ]

        summaries: list[ScenarioSummary] = []
        for name, c_count, p_per_c, e_per_p in scenarios:
            summary = await self.run_isolated_multiclient_scenario(
                fase="Fase 3 (Multi-Inquilino)",
                scenario_name=name,
                clients_count=c_count,
                patterns_per_client=p_per_c,
                events_per_pattern=e_per_p,
                on_iteration_done=on_iteration_done,
            )
            summaries.append(summary)

        return summaries


def format_num_es(val: float, decimals: int = 2) -> str:
    """Formatea valores numéricos con coma decimal y punto de miles (convención en español)."""
    if isinstance(val, int) and decimals == 0:
        return f"{val:,}".replace(",", ".")
    formatted = f"{val:,.{decimals}f}"
    parts = formatted.split(".")
    integer_part = parts[0].replace(",", ".")
    if len(parts) > 1:
        return f"{integer_part},{parts[1]}"
    return integer_part


def parse_float_es(text: str) -> float:
    """Parsea un número en formato español (coma decimal, punto de miles) a float."""
    clean = text.strip().replace(".", "").replace(",", ".")
    clean = re.sub(r"[^\d.-]", "", clean)
    return float(clean)


def format_markdown_table(
    summaries: list[ScenarioSummary],
    iterations: list[IterationResult] | None = None,
    client_results: list[ClientResult] | None = None,
) -> str:
    """Genera la tabla comparativa cuantitativa en formato GitHub Flavored Markdown con notación decimal en español."""
    headers = [
        "Fase",
        "Escenario",
        "Clientes",
        "Patrones/Cli",
        "Eventos/Patrón",
        "Total Eventos",
        "Duración Media (s)",
        "Mediana (s)",
        "P90 (s)",
        "Tiempo / Evento (s/evento)",
        "RAM Python (MB)",
        "RAM Total (MB)",
        "Tasa Éxito",
        "Estado",
    ]
    aligns = [
        ":---",
        ":---",
        ":---:",
        ":---:",
        ":---:",
        ":---:",
        ":---:",
        ":---:",
        ":---:",
        ":---:",
        ":---:",
        ":---:",
        ":---:",
        ":---:",
    ]

    lines = [
        "### Resultados Cuantitativos de Performance y Escalabilidad (Exploración Agéntica)",
        "",
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(aligns) + " |",
    ]

    for s in summaries:
        dur_media = format_num_es(s.duracion_media_s, 2)
        dur_mediana = format_num_es(s.duracion_mediana_s, 2)
        dur_p90 = format_num_es(s.duracion_p90_s, 2)
        sec_evento = format_num_es(s.segundos_por_evento_medio, 2)
        ram_py = format_num_es(s.ram_python_pico_mb, 2)
        ram_tot = format_num_es(s.ram_total_pico_mb, 2)
        exito = format_num_es(s.tasa_exito_pct, 1)
        total_p = format_num_es(s.total_eventos, 0)

        row = (
            f"| {s.fase} | {s.escenario} | {s.clientes} | {s.patrones_por_cliente} | "
            f"{s.eventos_por_patron} | {total_p} | {dur_media} s | "
            f"{dur_mediana} s | {dur_p90} s | "
            f"{sec_evento} s/evento | {ram_py} MB | {ram_tot} MB | "
            f"{exito}% | **{s.estado_general}** |"
        )
        lines.append(row)

    if iterations:
        lines.extend([
            "",
            "### Desglose Detallado por Repetición",
            "",
            "| Escenario | Repetición | Duración (s) | Eventos | Tiempo / Evento (s/evento) | RAM Python (MB) | RAM Total (MB) | Capturas WebP | Estado |",
            "| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |",
        ])
        for it in iterations:
            dur = format_num_es(it.duracion_s, 2)
            sec_evento = format_num_es(it.segundos_por_evento, 2)
            ram_py = format_num_es(it.ram_python_mb, 2)
            ram_tot = format_num_es(it.ram_total_mb, 2)
            kb = format_num_es(it.bytes_capturas_kb, 1)

            row = (
                f"| {it.escenario} | Rep {it.iteracion} | {dur} s | "
                f"{it.eventos_completados}/{it.eventos_totales} | {sec_evento} s/evento | "
                f"{ram_py} MB | {ram_tot} MB | {it.capturas_generadas} ({kb} KB) | "
                f"**{it.estado}** |"
            )
            lines.append(row)

    if client_results:
        lines.extend([
            "",
            "### Desglose por Cliente (Fase 3: Multi-Inquilino)",
            "",
            "| Escenario | Repetición | Cliente | Duración (s) | Eventos | Tiempo / Evento (s/evento) | Estado |",
            "| :--- | :---: | :---: | :---: | :---: | :---: | :---: |",
        ])
        for cr in client_results:
            dur = format_num_es(cr.duracion_s, 2)
            sec_ev = format_num_es(cr.segundos_por_evento, 2)
            row = (
                f"| {cr.escenario} | Rep {cr.iteracion} | {cr.cliente} | {dur} s | "
                f"{cr.eventos_completados}/{cr.eventos_totales} | {sec_ev} s/evento | "
                f"**{cr.estado}** |"
            )
            lines.append(row)

    return "\n".join(lines)


def parse_existing_markdown_results(
    filepath: str,
) -> tuple[list[ScenarioSummary], list[IterationResult], list[ClientResult]]:
    """Parsea resúmenes, iteraciones y resultados por cliente desde el archivo Markdown si existe."""
    if not os.path.exists(filepath):
        return [], [], []

    with open(filepath, encoding="utf-8") as f:
        content = f.read()

    summaries: list[ScenarioSummary] = []
    iterations: list[IterationResult] = []
    client_results: list[ClientResult] = []

    # 1. Parsear tabla consolidada
    summary_match = re.search(
        r"### Resultados Cuantitativos de Performance.*?\n\n(.*?)(?=\n\n###|\Z)",
        content,
        re.DOTALL,
    )
    if summary_match:
        table_text = summary_match.group(1).strip()
        lines = [line.strip() for line in table_text.splitlines() if line.startswith("|")]
        for line in lines[2:]:
            cols = [c.strip() for c in line.split("|")[1:-1]]
            if len(cols) >= 14:
                try:
                    fase = cols[0]
                    esc = cols[1]
                    clientes = int(cols[2])
                    patrones = int(cols[3])
                    eventos_patron = int(cols[4])
                    total_ev = int(cols[5].replace(".", ""))
                    dur_media = parse_float_es(cols[6])
                    dur_mediana = parse_float_es(cols[7])
                    dur_p90 = parse_float_es(cols[8])
                    sec_ev = parse_float_es(cols[9])
                    ram_py = parse_float_es(cols[10])
                    ram_tot = parse_float_es(cols[11])
                    tasa_ex = parse_float_es(cols[12])
                    estado = cols[13].replace("*", "")

                    summaries.append(
                        ScenarioSummary(
                            fase=fase,
                            escenario=esc,
                            clientes=clientes,
                            patrones_por_cliente=patrones,
                            eventos_por_patron=eventos_patron,
                            total_eventos=total_ev,
                            repeticiones=5,
                            duracion_media_s=dur_media,
                            duracion_mediana_s=dur_mediana,
                            duracion_p90_s=dur_p90,
                            duracion_min_s=dur_media,
                            duracion_max_s=dur_p90,
                            duracion_std_s=0.0,
                            segundos_por_evento_medio=sec_ev,
                            ram_python_pico_mb=ram_py,
                            ram_total_pico_mb=ram_tot,
                            tasa_exito_pct=tasa_ex,
                            estado_general=estado,
                        )
                    )
                except (ValueError, IndexError):
                    continue

    # 2. Parsear desglose de repeticiones
    iter_match = re.search(
        r"### Desglose Detallado por Repetición.*?\n\n(.*?)(?=\n\n###|\Z)",
        content,
        re.DOTALL,
    )
    if iter_match:
        table_text = iter_match.group(1).strip()
        lines = [line.strip() for line in table_text.splitlines() if line.startswith("|")]
        for line in lines[2:]:
            cols = [c.strip() for c in line.split("|")[1:-1]]
            if len(cols) >= 9:
                try:
                    esc = cols[0]
                    rep_num = int(re.sub(r"\D", "", cols[1]))
                    dur_s = parse_float_es(cols[2])
                    ev_parts = cols[3].split("/")
                    ev_comp = int(ev_parts[0])
                    ev_tot = int(ev_parts[1]) if len(ev_parts) > 1 else ev_comp
                    sec_ev = parse_float_es(cols[4])
                    ram_py = parse_float_es(cols[5])
                    ram_tot = parse_float_es(cols[6])
                    capt_match = re.search(r"(\d+)\s*\(([\d,.]+)\s*KB\)", cols[7])
                    capt_count = int(capt_match.group(1)) if capt_match else 0
                    capt_kb = parse_float_es(capt_match.group(2)) if capt_match else 0.0
                    estado = cols[8].replace("*", "")

                    iterations.append(
                        IterationResult(
                            escenario=esc,
                            iteracion=rep_num,
                            duracion_s=dur_s,
                            eventos_completados=ev_comp,
                            eventos_totales=ev_tot,
                            segundos_por_evento=sec_ev,
                            ram_python_mb=ram_py,
                            ram_total_mb=ram_tot,
                            capturas_generadas=capt_count,
                            bytes_capturas_kb=capt_kb,
                            estado=estado,
                        )
                    )
                except (ValueError, IndexError):
                    continue

    # 3. Parsear desglose por cliente (Fase 3)
    client_match = re.search(
        r"### Desglose por Cliente.*?\n\n(.*?)(?=\n\n|\Z)",
        content,
        re.DOTALL,
    )
    if client_match:
        table_text = client_match.group(1).strip()
        lines = [line.strip() for line in table_text.splitlines() if line.startswith("|")]
        for line in lines[2:]:
            cols = [c.strip() for c in line.split("|")[1:-1]]
            if len(cols) >= 7:
                try:
                    esc = cols[0]
                    rep_num = int(re.sub(r"\D", "", cols[1]))
                    c_name = cols[2]
                    dur_s = parse_float_es(cols[3])
                    ev_parts = cols[4].split("/")
                    ev_comp = int(ev_parts[0])
                    ev_tot = int(ev_parts[1]) if len(ev_parts) > 1 else ev_comp
                    sec_ev = parse_float_es(cols[5])
                    estado = cols[6].replace("*", "")

                    client_results.append(
                        ClientResult(
                            escenario=esc,
                            iteracion=rep_num,
                            cliente=c_name,
                            duracion_s=dur_s,
                            eventos_completados=ev_comp,
                            eventos_totales=ev_tot,
                            segundos_por_evento=sec_ev,
                            estado=estado,
                        )
                    )
                except (ValueError, IndexError):
                    continue

    return summaries, iterations, client_results



async def run_worker_instance(args: argparse.Namespace) -> int:
    """Ejecuta una instancia autónoma de cliente (simulación de contenedor Cloud Run)."""
    client_id = args.client_id
    c_name = f"Cliente {client_id}"
    patterns_count = args.patterns_per_client
    events_per_p = args.events_per_pattern

    client_config = get_benchmark_client_config()
    capturas_count = 0
    total_capture_bytes = 0

    def _write_bytes(fpath: str, b: bytes) -> None:
        with open(fpath, "wb") as f:
            f.write(b)

    async def _worker_evidence_saver(data: bytes, filename: str, step: int) -> str:
        nonlocal capturas_count, total_capture_bytes
        capturas_count += 1
        total_capture_bytes += len(data)
        if args.save_evidence:
            ev_dir = "./evidence_storage/benchmark"
            os.makedirs(ev_dir, exist_ok=True)
            filepath = os.path.join(ev_dir, filename)
            await asyncio.to_thread(_write_bytes, filepath, data)
            return filepath
        return f"mem://evidence/{filename}"

    if args.dry_run:
        total_ev = patterns_count * events_per_p
        await asyncio.sleep(0.04 * total_ev)
        result = {
            "__type__": "WORKER_RESULT",
            "client_id": client_id,
            "cliente": c_name,
            "duracion_s": 24.5 + (client_id * 0.15),
            "eventos_completados": total_ev,
            "eventos_totales": total_ev,
            "segundos_por_evento": 0.82,
            "ram_python_mb": 58.5,
            "ram_total_mb": 1580.0 + (client_id * 10),
            "capturas_count": total_ev,
            "capturas_bytes": total_ev * 35000,
            "estado": ExplorationStatus.COMPLETED.value,
            "error": None,
        }
        print(json.dumps(result))
        return 0

    tracemalloc.start()
    mem_tracker = ProcessTreeMemoryTracker()
    mem_tracker.start()
    start_t = time.perf_counter()

    browser_manager = BrowserManager()
    await browser_manager.start()

    sem = asyncio.Semaphore(3)

    async def _exec_pattern(p_idx: int) -> tuple[int, int, str, str | None]:
        async with sem:
            trace = get_pattern_10_steps(p_idx)
            executor = TraceExecutor(
                browser_manager=browser_manager,
                evidence_saver=_worker_evidence_saver,
            )
            try:
                report = await executor.execute_trace(trace, client_config)
                return report.completed_steps, len(trace.events), report.status.value, report.error_message
            except Exception as exc:  # noqa: BLE001
                return 0, len(trace.events), ExplorationStatus.FAILED.value, str(exc)

    tasks = [_exec_pattern(p) for p in range(1, patterns_count + 1)]
    pattern_results = await asyncio.gather(*tasks)

    await browser_manager.close()
    elapsed = time.perf_counter() - start_t
    _, peak_py = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    peak_tot = await mem_tracker.stop()

    completed_events = sum(r[0] for r in pattern_results)
    total_events = sum(r[1] for r in pattern_results)
    has_failed = any(r[2] == ExplorationStatus.FAILED.value for r in pattern_results)
    has_partial = any(r[2] == ExplorationStatus.PARTIAL.value for r in pattern_results)

    if has_failed:
        status_val = ExplorationStatus.FAILED.value
    elif has_partial or completed_events < total_events:
        status_val = ExplorationStatus.PARTIAL.value
    else:
        status_val = ExplorationStatus.COMPLETED.value

    sec_ev = elapsed / completed_events if completed_events > 0 else 0.0

    result = {
        "__type__": "WORKER_RESULT",
        "client_id": client_id,
        "cliente": c_name,
        "duracion_s": round(elapsed, 3),
        "eventos_completados": completed_events,
        "eventos_totales": total_events,
        "segundos_por_evento": round(sec_ev, 2),
        "ram_python_mb": round(peak_py / (1024 * 1024), 2),
        "ram_total_mb": round(peak_tot / (1024 * 1024), 2),
        "capturas_count": capturas_count,
        "capturas_bytes": total_capture_bytes,
        "estado": status_val,
        "error": None,
    }
    print(json.dumps(result))
    return 0

async def main_async(args: argparse.Namespace) -> str | None:
    """Punto de entrada asíncrono para la ejecución CLI."""
    runner = AgentBenchmarkRunner(
        repeats=args.repeats,
        dry_run=args.dry_run,
        save_evidence=args.save_evidence,
    )
    await runner.initialize()

    summaries: list[ScenarioSummary] = []
    try:
        if args.phase in ("1", "all"):
            phase1_summaries = await runner.run_phase_1()
            summaries.extend(phase1_summaries)
        if args.phase in ("2", "all"):
            phase2_summaries = await runner.run_phase_2()
            summaries.extend(phase2_summaries)
        if args.phase in ("3", "all"):
            phase3_summaries = await runner.run_phase_3()
            summaries.extend(phase3_summaries)
    finally:
        await runner.shutdown()

    output_path = os.path.abspath(args.output_file)
    final_summaries = list(summaries)
    final_iterations = list(runner.all_iterations)
    final_client_results = list(runner.all_client_results)

    if args.phase != "all" and os.path.exists(output_path):
        prev_summaries, prev_iterations, prev_clients = parse_existing_markdown_results(output_path)
        if args.phase == "3":
            preserved_summaries = [s for s in prev_summaries if "Fase 3" not in s.fase and "3patrones" not in s.escenario]
            preserved_iterations = [it for it in prev_iterations if "3patrones" not in it.escenario]
            preserved_clients = [cr for cr in prev_clients if "3patrones" not in cr.escenario]
        else:
            ran_scenarios = {s.escenario for s in summaries}
            preserved_summaries = [s for s in prev_summaries if s.escenario not in ran_scenarios]
            preserved_iterations = [it for it in prev_iterations if it.escenario not in ran_scenarios]
            preserved_clients = [cr for cr in prev_clients if cr.escenario not in ran_scenarios]
        final_summaries = preserved_summaries + final_summaries
        final_iterations = preserved_iterations + final_iterations
        final_client_results = preserved_clients + final_client_results

    if final_summaries:
        return format_markdown_table(final_summaries, final_iterations, final_client_results)
    return None


def main() -> int:
    """Función de entrada para terminal."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    parser = argparse.ArgumentParser(
        description="Benchmark de Performance y Escalabilidad: Exploración Agéntica",
    )
    parser.add_argument(
        "--phase",
        choices=["1", "2", "3", "4", "all"],
        default="1",
        help="Fase de experimentación a ejecutar (por defecto Fase 1).",
    )
    parser.add_argument(
        "--repeats",
        type=int,
        default=5,
        help="Cantidad de repeticiones independientes por escenario (n=5 por defecto).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Ejecuta en modo simulación rápida sin instanciar Playwright Chromium.",
    )
    parser.add_argument(
        "--save-evidence",
        action="store_true",
        help="Guarda las capturas WebP en disco (en ./evidence_storage/benchmark/) para inspección visual.",
    )
    parser.add_argument(
        "--output-file",
        default="benchmark_agent_results.md",
        help="Ruta del archivo Markdown para exportar la tabla de resultados.",
    )

    parser.add_argument(
        "--worker-instance",
        action="store_true",
        help="Ejecuta una instancia aislada de worker para un cliente específico.",
    )
    parser.add_argument("--client-id", type=int, default=1, help="Identificador numérico del cliente.")
    parser.add_argument("--patterns-per-client", type=int, default=3, help="Cantidad de patrones de fricción a ejecutar.")
    parser.add_argument("--events-per-pattern", type=int, default=10, help="Cantidad de eventos por patrón de fricción.")
    parser.add_argument("--scenario-name", default="isolated-scenario", help="Nombre del escenario.")
    parser.add_argument("--iteration-index", type=int, default=1, help="Índice de la repetición.")

    args = parser.parse_args()
    if args.worker_instance:
        return asyncio.run(run_worker_instance(args))

    md_table = asyncio.run(main_async(args))

    if md_table:
        print("\n" + "=" * 90)
        print(" RESULTADOS CONSOLIDADOS DEL BENCHMARK")
        print("=" * 90)
        print(md_table)
        print("\n")

        output_path = os.path.abspath(args.output_file)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(md_table + "\n")
        print(f"[OK] Resultados exportados exitosamente en: {output_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
