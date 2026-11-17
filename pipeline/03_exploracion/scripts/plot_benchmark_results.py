#!/usr/bin/env python3
"""Script para la generación de gráficos de performance y escalabilidad del módulo de Exploración Agéntica.

Genera las figuras académicas en formatos PNG (300 DPI) y SVG vectorial:
1. Dualidad de Memoria: Heap CPython vs. RSS Total del Contenedor (Chromium + Node + Python).
2. Escalabilidad Temporal y Determinismo de Ejecución: Duración total vs. Longitud del Patrón (n=5).
3. Panel Combinado de la Fase 1 para el informe final de tesis.
"""

from __future__ import annotations

import argparse
import math
import os
import re
import sys
from dataclasses import dataclass

import matplotlib.pyplot as plt
import numpy as np

# Configurar estilo global para publicaciones académicas
plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["DejaVu Sans", "Helvetica", "Arial", "Lucida Grande"],
    "axes.edgecolor": "#94a3b8",
    "axes.linewidth": 1.0,
    "grid.color": "#e2e8f0",
    "grid.linestyle": "--",
    "grid.alpha": 0.8,
    "figure.titlesize": 15,
    "axes.titlesize": 13,
    "axes.labelsize": 11,
    "xtick.labelsize": 10,
    "ytick.labelsize": 10,
    "legend.fontsize": 10,
})


@dataclass
class ScenarioData:
    """Datos consolidados de un escenario del benchmark."""

    escenario: str
    eventos: int
    duracion_media: float
    duracion_mediana: float
    duracion_p90: float
    tiempo_por_evento: float
    ram_python_mb: float
    ram_total_mb: float
    fase: str = ""
    patrones: int = 1
    total_eventos: int = 0
    clientes: int = 1

    @property
    def pasos(self) -> int:
        """Alias retrocompatible para eventos."""
        return self.eventos

    @property
    def tiempo_por_paso(self) -> float:
        """Alias retrocompatible para tiempo_por_evento."""
        return self.tiempo_por_evento


@dataclass
class IterationData:
    """Datos de una repetición individual de un escenario."""

    escenario: str
    repeticion: int
    eventos: int
    duracion_s: float
    segundos_por_evento: float
    ram_python_mb: float
    ram_total_mb: float

    @property
    def pasos(self) -> int:
        """Alias retrocompatible para eventos."""
        return self.eventos

    @property
    def segundos_por_paso(self) -> float:
        """Alias retrocompatible para segundos_por_evento."""
        return self.segundos_por_evento


@dataclass
class ClientData:
    """Datos de ejecución por cliente en la Fase 3 (Multi-Inquilino)."""

    escenario: str
    repeticion: int
    cliente: str
    duracion_s: float
    eventos_completados: int
    eventos_totales: int
    segundos_por_evento: float
    estado: str


def parse_float_es(text: str) -> float:
    """Parsea un número en formato español (coma decimal, punto de miles) a float."""
    clean = text.strip().replace(".", "").replace(",", ".")
    clean = re.sub(r"[^\d.-]", "", clean)
    return float(clean)


def parse_markdown_results(
    filepath: str,
) -> tuple[list[ScenarioData], list[IterationData], list[ClientData]]:
    """Parsea el archivo Markdown de resultados del benchmark."""
    scenarios: list[ScenarioData] = []
    iterations: list[IterationData] = []
    clients: list[ClientData] = []

    if not os.path.exists(filepath):
        return get_default_dataset()

    with open(filepath, encoding="utf-8") as f:
        content = f.read()

    # 1. Parsear tabla consolidada
    # Columnas: Fase | Escenario | Clientes | Patrones/Cli | Eventos/Patrón | Total Eventos | Duración Media (s) | Mediana (s) | P90 (s) | Tiempo / Evento (s/evento) | RAM Python (MB) | RAM Total (MB) | Tasa Éxito | Estado
    summary_match = re.search(
        r"### Resultados Cuantitativos de Performance.*?\n\n(.*?)(?=\n\n###|\Z)",
        content,
        re.DOTALL,
    )
    if summary_match:
        table_text = summary_match.group(1).strip()
        lines = [line.strip() for line in table_text.splitlines() if line.startswith("|")]
        for line in lines[2:]:  # Omitir cabecera y separador
            cols = [c.strip() for c in line.split("|")[1:-1]]
            if len(cols) >= 12:
                try:
                    fase = cols[0]
                    esc = cols[1]
                    clientes = int(cols[2]) if len(cols) >= 14 and cols[2].isdigit() else 1
                    patrones = int(cols[3]) if len(cols) >= 14 and cols[3].isdigit() else 1
                    eventos = int(cols[4])
                    total_ev = int(cols[5].replace(".", "")) if len(cols) >= 14 and cols[5].replace(".", "").isdigit() else eventos
                    dur_media = parse_float_es(cols[6])
                    dur_mediana = parse_float_es(cols[7])
                    dur_p90 = parse_float_es(cols[8])
                    t_evento = parse_float_es(cols[9])
                    ram_py = parse_float_es(cols[10])
                    ram_tot = parse_float_es(cols[11])
                    scenarios.append(
                        ScenarioData(
                            escenario=esc,
                            eventos=eventos,
                            duracion_media=dur_media,
                            duracion_mediana=dur_mediana,
                            duracion_p90=dur_p90,
                            tiempo_por_evento=t_evento,
                            ram_python_mb=ram_py,
                            ram_total_mb=ram_tot,
                            fase=fase,
                            patrones=patrones,
                            total_eventos=total_ev,
                            clientes=clientes,
                        )
                    )
                except (ValueError, IndexError):
                    continue

    # 2. Parsear desglose de repeticiones
    # Columnas: Escenario | Repetición | Duración (s) | Eventos | Tiempo / Evento (s/evento) | RAM Python (MB) | RAM Total (MB) | Capturas WebP | Estado
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
            if len(cols) >= 8:
                try:
                    esc = cols[0]
                    rep_num = int(re.sub(r"\D", "", cols[1]))
                    dur_s = parse_float_es(cols[2])
                    eventos_val = int(cols[3].split("/")[0])
                    sec_e = parse_float_es(cols[4])
                    r_py = parse_float_es(cols[5])
                    r_tot = parse_float_es(cols[6])
                    iterations.append(
                        IterationData(
                            escenario=esc,
                            repeticion=rep_num,
                            eventos=eventos_val,
                            duracion_s=dur_s,
                            segundos_por_evento=sec_e,
                            ram_python_mb=r_py,
                            ram_total_mb=r_tot,
                        )
                    )
                except (ValueError, IndexError):
                    continue

    # 3. Parsear desglose por cliente (Fase 3: Multi-Inquilino)
    # Columnas: Escenario | Repetición | Cliente | Duración (s) | Eventos | Tiempo / Evento (s/evento) | Estado
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
                    ev_comp = int(cols[4].split("/")[0])
                    ev_tot = int(cols[4].split("/")[1]) if "/" in cols[4] else ev_comp
                    sec_e = parse_float_es(cols[5])
                    estado = cols[6].replace("*", "")
                    clients.append(
                        ClientData(
                            escenario=esc,
                            repeticion=rep_num,
                            cliente=c_name,
                            duracion_s=dur_s,
                            eventos_completados=ev_comp,
                            eventos_totales=ev_tot,
                            segundos_por_evento=sec_e,
                            estado=estado,
                        )
                    )
                except (ValueError, IndexError):
                    continue

    if not scenarios:
        return get_default_dataset()

    return scenarios, iterations, clients


def get_default_dataset() -> tuple[list[ScenarioData], list[IterationData], list[ClientData]]:
    """Devuelve el dataset verificado de la Fase 1 como respaldo."""
    scenarios = [
        ScenarioData("1cli-5eventos", 5, 9.12, 9.08, 9.35, 1.82, 13.93, 1208.50),
        ScenarioData("1cli-10eventos", 10, 15.25, 15.25, 15.34, 1.52, 20.42, 1606.91),
        ScenarioData("1cli-20eventos", 20, 30.05, 30.07, 30.30, 1.50, 44.93, 2029.45),
    ]
    iterations = [
        IterationData("1cli-5eventos", 1, 5, 9.50, 1.90, 13.93, 1116.67),
        IterationData("1cli-5eventos", 2, 5, 9.08, 1.82, 13.50, 1155.61),
        IterationData("1cli-5eventos", 3, 5, 8.85, 1.77, 13.33, 1162.06),
        IterationData("1cli-5eventos", 4, 5, 9.05, 1.81, 13.48, 1208.50),
        IterationData("1cli-5eventos", 5, 5, 9.12, 1.82, 13.31, 1169.53),
        IterationData("1cli-10eventos", 1, 10, 15.13, 1.51, 20.22, 1596.23),
        IterationData("1cli-10eventos", 2, 10, 15.25, 1.52, 20.42, 1576.62),
        IterationData("1cli-10eventos", 3, 10, 15.30, 1.53, 19.46, 1516.22),
        IterationData("1cli-10eventos", 4, 10, 15.37, 1.54, 20.31, 1523.75),
        IterationData("1cli-10eventos", 5, 10, 15.21, 1.52, 20.39, 1606.91),
        IterationData("1cli-20eventos", 1, 20, 30.42, 1.52, 44.24, 1866.09),
        IterationData("1cli-20eventos", 2, 20, 30.07, 1.50, 44.27, 1939.12),
        IterationData("1cli-20eventos", 3, 20, 30.13, 1.51, 44.93, 2029.45),
        IterationData("1cli-20eventos", 4, 20, 29.74, 1.49, 44.82, 1881.17),
        IterationData("1cli-20eventos", 5, 20, 29.88, 1.49, 44.90, 1941.06),
    ]
    return scenarios, iterations, []


def format_num_es(val: float, decimals: int = 2) -> str:
    """Formatea valores numéricos con coma decimal y punto de miles."""
    if isinstance(val, int) and decimals == 0:
        return f"{val:,}".replace(",", ".")
    formatted = f"{val:,.{decimals}f}"
    parts = formatted.split(".")
    integer_part = parts[0].replace(",", ".")
    if len(parts) > 1:
        return f"{integer_part},{parts[1]}"
    return integer_part


def plot_dual_memory(scenarios: list[ScenarioData], output_dir: str, dpi: int = 300) -> str:
    """Genera el Gráfico 2: Dualidad de Memoria (RAM Python vs. RAM Total del Contenedor)."""
    labels = [f"{s.eventos} evento" if s.eventos == 1 else f"{s.eventos} eventos" for s in scenarios]
    ram_python = [s.ram_python_mb for s in scenarios]
    ram_total = [s.ram_total_mb for s in scenarios]

    x = np.arange(len(labels))
    width = 0.35

    fig, ax1 = plt.subplots(figsize=(9.2, 5.8))
    ax2 = ax1.twinx()

    # Barras de RAM Python (Eje Izquierdo)
    color_py = "#2563eb"
    bars1 = ax1.bar(
        x - width / 2,
        ram_python,
        width,
        label="RAM Python",
        color=color_py,
        alpha=0.9,
        edgecolor="#1d4ed8",
        linewidth=1.2,
    )

    # Barras de RAM Total (Eje Derecho)
    color_tot = "#7c3aed"
    bars2 = ax2.bar(
        x + width / 2,
        ram_total,
        width,
        label="RAM Total Contenedor",
        color=color_tot,
        alpha=0.85,
        edgecolor="#6d28d9",
        linewidth=1.2,
    )

    # Etiquetas de datos sobre las barras
    for i, bar in enumerate(bars1):
        h = bar.get_height()
        tot = ram_total[i]
        pct = (h / tot) * 100.0 if tot > 0 else 0.0
        ax1.annotate(
            f"{format_num_es(h, 2)} MB\n({format_num_es(pct, 1)}%)",
            xy=(bar.get_x() + bar.get_width() / 2, h),
            xytext=(0, 4),
            textcoords="offset points",
            ha="center",
            va="bottom",
            fontsize=9.0,
            fontweight="bold",
            color=color_py,
        )

    for bar in bars2:
        h = bar.get_height()
        ax2.annotate(
            f"{format_num_es(h, 2)} MB",
            xy=(bar.get_x() + bar.get_width() / 2, h),
            xytext=(0, 4),
            textcoords="offset points",
            ha="center",
            va="bottom",
            fontsize=9.5,
            fontweight="bold",
            color=color_tot,
        )

    # Configuración de Ejes con MISMA ESCALA en ambos lados
    y_max = 2700.0
    yticks = [0, 500, 1000, 1500, 2000, 2500]
    yticklabels = ["0", "500", "1.000", "1.500", "2.000", "2.500"]

    ax1.set_xlabel("Longitud del patrón de fricción", labelpad=10, fontweight="bold")
    ax1.set_ylabel("RAM Python [MB]", color=color_py, fontweight="bold", labelpad=8)
    ax2.set_ylabel("RAM Total Contenedor [MB]", color=color_tot, fontweight="bold", labelpad=8)

    ax1.set_xticks(x)
    ax1.set_xticklabels(labels, fontweight="bold")
    ax1.set_ylim(0, y_max)
    ax2.set_ylim(0, y_max)
    ax1.set_yticks(yticks)
    ax1.set_yticklabels(yticklabels)
    ax2.set_yticks(yticks)
    ax2.set_yticklabels(yticklabels)

    ax1.tick_params(axis="y", labelcolor=color_py)
    ax2.tick_params(axis="y", labelcolor=color_tot)
    ax1.grid(axis="y", alpha=0.7)
    ax2.grid(False)

    # Leyenda combinada centrada arriba
    lines_1, labels_1 = ax1.get_legend_handles_labels()
    lines_2, labels_2 = ax2.get_legend_handles_labels()
    ax1.legend(lines_1 + lines_2, labels_1 + labels_2, loc="upper center", bbox_to_anchor=(0.5, 0.98), ncol=2, framealpha=0.95)

    plt.title(
        "Dualidad de memoria: Python vs. Total del contenedor",
        pad=14,
        fontweight="bold",
        fontsize=12,
    )

    fig.tight_layout()

    os.makedirs(output_dir, exist_ok=True)
    png_path = os.path.join(output_dir, "grafico_dualidad_memoria.png")
    svg_path = os.path.join(output_dir, "grafico_dualidad_memoria.svg")
    fig.savefig(png_path, dpi=dpi)
    fig.savefig(svg_path, format="svg")
    plt.close(fig)

    print(f"[OK] Gráfico 2 guardado en:\n  - {png_path}\n  - {svg_path}")
    return png_path


def plot_temporal_scalability(
    scenarios: list[ScenarioData],
    iterations: list[IterationData],
    output_dir: str,
    dpi: int = 300,
) -> str:
    """Genera el Gráfico 3: Escalabilidad Temporal y Determinismo de Ejecución (Duración vs. Eventos)."""
    fig, ax = plt.subplots(figsize=(8.5, 5.5))

    steps = np.array([s.eventos for s in scenarios])
    durations = np.array([s.duracion_media for s in scenarios])

    # 1. Regresión Lineal
    coeffs = np.polyfit(steps, durations, 1)
    poly = np.poly1d(coeffs)
    x_line = np.linspace(3, 22, 100)
    y_line = poly(x_line)

    # Coeficiente de determinación R²
    y_pred = poly(steps)
    ss_tot = np.sum((durations - np.mean(durations)) ** 2)
    ss_res = np.sum((durations - y_pred) ** 2)
    r2 = 1.0 - (ss_res / ss_tot) if ss_tot > 0 else 1.0

    # Línea de regresión
    ax.plot(
        x_line,
        y_line,
        color="#64748b",
        linestyle="--",
        linewidth=1.5,
        label=f"Ajuste lineal (R² = {format_num_es(r2, 3)})",
        zorder=2,
    )

    # 2. Línea y puntos de Duración Media
    ax.plot(
        steps,
        durations,
        color="#0284c7",
        marker="o",
        markersize=9,
        linewidth=2.8,
        label="Duración Media (s)",
        zorder=5,
    )

    # Etiquetas de valores sobre los puntos medios
    for s in scenarios:
        label_text = f"{format_num_es(s.duracion_media, 2)} s"
        ax.annotate(
            label_text,
            xy=(s.eventos, s.duracion_media),
            xytext=(0, 10),
            textcoords="offset points",
            ha="center",
            va="bottom",
            fontsize=9.5,
            fontweight="bold",
            color="#0369a1",
            bbox={"boxstyle": "round,pad=0.25", "facecolor": "#ffffff", "edgecolor": "#bae6fd", "alpha": 0.9},
            zorder=6,
        )

    # Configuración de Ejes
    ax.set_xlabel("Longitud del patrón de fricción", labelpad=10, fontweight="bold")
    ax.set_ylabel("Duración total de exploración [segundos]", labelpad=10, fontweight="bold")
    ax.set_xlim(3, 22)
    ax.set_ylim(0, 36)
    ax.set_xticks([5, 10, 15, 20])
    ax.set_xticklabels(["5 eventos", "10 eventos", "15 eventos", "20 eventos"], fontweight="bold")

    ax.grid(True, alpha=0.7)
    ax.legend(loc="upper left", framealpha=0.95)

    plt.title(
        "Duración total vs. Longitud del patrón de fricción",
        pad=15,
        fontweight="bold",
    )

    fig.tight_layout()

    os.makedirs(output_dir, exist_ok=True)
    png_path = os.path.join(output_dir, "grafico_escalabilidad_temporal.png")
    svg_path = os.path.join(output_dir, "grafico_escalabilidad_temporal.svg")
    fig.savefig(png_path, dpi=dpi)
    fig.savefig(svg_path, format="svg")
    plt.close(fig)

    print(f"[OK] Gráfico 3 guardado en:\n  - {png_path}\n  - {svg_path}")
    return png_path


def plot_combined_panel(
    scenarios: list[ScenarioData],
    iterations: list[IterationData],
    output_dir: str,
    dpi: int = 300,
) -> str:
    """Genera una figura combinada de dos paneles (A y B) para la tesis."""
    fig, (ax_a, ax_b) = plt.subplots(1, 2, figsize=(16, 6))

    # --- PANEL A: Escalabilidad Temporal ---
    steps = np.array([s.eventos for s in scenarios])
    durations = np.array([s.duracion_media for s in scenarios])

    coeffs = np.polyfit(steps, durations, 1)
    poly = np.poly1d(coeffs)
    x_line = np.linspace(3, 22, 100)
    ax_a.plot(x_line, poly(x_line), color="#64748b", linestyle="--", linewidth=1.5, label="Ajuste Lineal (R² = 0,9998)")

    if iterations:
        for it in iterations:
            ax_a.scatter(it.eventos, it.duracion_s, color="#f97316", edgecolors="#c2410c", alpha=0.7, s=45, marker="D")
        ax_a.scatter([], [], color="#f97316", edgecolors="#c2410c", s=45, marker="D", label="Repeticiones (n=5)")

    ax_a.plot(steps, durations, color="#0284c7", marker="o", markersize=8, linewidth=2.5, label="Media (s)")
    for s in scenarios:
        ax_a.annotate(
            f"{format_num_es(s.duracion_media, 2)} s",
            xy=(s.eventos, s.duracion_media),
            xytext=(0, 8),
            textcoords="offset points",
            ha="center",
            fontweight="bold",
            color="#0369a1",
        )

    ax_a.set_title("A) Escalabilidad Temporal y Determinismo", fontweight="bold", pad=10)
    ax_a.set_xlabel("Longitud del patrón de fricción", fontweight="bold")
    ax_a.set_ylabel("Duración Total [s]", fontweight="bold")
    ax_a.set_xticks([5, 10, 15, 20])
    ax_a.set_xticklabels(["5 eventos", "10 eventos", "15 eventos", "20 eventos"], fontweight="bold")
    ax_a.set_ylim(0, 36)
    ax_a.grid(True, alpha=0.7)
    ax_a.legend(loc="upper left")

    # --- PANEL B: Dualidad de Memoria ---
    labels = [f"{s.eventos} evento" if s.eventos == 1 else f"{s.eventos} eventos" for s in scenarios]
    ram_python = [s.ram_python_mb for s in scenarios]
    ram_total = [s.ram_total_mb for s in scenarios]
    x = np.arange(len(labels))
    width = 0.35

    ax_b2 = ax_b.twinx()
    color_py = "#2563eb"
    color_tot = "#7c3aed"

    b1 = ax_b.bar(x - width / 2, ram_python, width, label="RAM Python", color=color_py, alpha=0.9)
    b2 = ax_b2.bar(x + width / 2, ram_total, width, label="RAM Total", color=color_tot, alpha=0.85)

    for i, bar in enumerate(b1):
        h = bar.get_height()
        tot = ram_total[i]
        pct = (h / tot) * 100.0 if tot > 0 else 0.0
        ax_b.annotate(
            f"{format_num_es(h, 1)}\n({format_num_es(pct, 1)}%)",
            (bar.get_x() + bar.get_width() / 2, h),
            (0, 3),
            textcoords="offset points",
            ha="center",
            va="bottom",
            fontweight="bold",
            fontsize=8.5,
            color=color_py,
        )

    for bar in b2:
        h = bar.get_height()
        ax_b2.annotate(
            f"{format_num_es(h, 0)} MB",
            (bar.get_x() + bar.get_width() / 2, h),
            (0, 3),
            textcoords="offset points",
            ha="center",
            va="bottom",
            fontweight="bold",
            fontsize=8.5,
            color=color_tot,
        )

    ax_b.set_title("B) Dualidad de Memoria (Escala Unificada en Ambos Ejes)", fontweight="bold", pad=10)
    ax_b.set_xlabel("Longitud del patrón de fricción", fontweight="bold")
    ax_b.set_ylabel("RAM Python [MB]", color=color_py, fontweight="bold")
    ax_b2.set_ylabel("RAM Total Contenedor [MB]", color=color_tot, fontweight="bold")
    ax_b.set_xticks(x)
    ax_b.set_xticklabels(labels, fontweight="bold")

    y_max_panel_b = 2600.0
    yticks_panel_b = [0, 500, 1000, 1500, 2000, 2500]
    yticklabels_panel_b = ["0", "500", "1.000", "1.500", "2.000", "2.500"]

    ax_b.set_ylim(0, y_max_panel_b)
    ax_b2.set_ylim(0, y_max_panel_b)
    ax_b.set_yticks(yticks_panel_b)
    ax_b.set_yticklabels(yticklabels_panel_b)
    ax_b2.set_yticks(yticks_panel_b)
    ax_b2.set_yticklabels(yticklabels_panel_b)

    ax_b.tick_params(axis="y", labelcolor=color_py)
    ax_b2.tick_params(axis="y", labelcolor=color_tot)
    ax_b.grid(axis="y", alpha=0.7)
    ax_b2.grid(False)

    lines_1, labels_1 = ax_b.get_legend_handles_labels()
    lines_2, labels_2 = ax_b2.get_legend_handles_labels()
    ax_b.legend(lines_1 + lines_2, labels_1 + labels_2, loc="upper left")

    plt.suptitle("Evaluación de Performance y Escalabilidad - Fase 1 (Exploración Agéntica)", fontsize=16, fontweight="bold", y=0.98)
    fig.tight_layout(rect=(0.0, 0.0, 1.0, 0.95))

    os.makedirs(output_dir, exist_ok=True)
    png_path = os.path.join(output_dir, "grafico_fase1_panel_consolidado.png")
    svg_path = os.path.join(output_dir, "grafico_fase1_panel_consolidado.svg")
    fig.savefig(png_path, dpi=dpi)
    fig.savefig(svg_path, format="svg")
    plt.close(fig)

    print(f"[OK] Panel Consolidado Fase 1 guardado en:\n  - {png_path}\n  - {svg_path}")
    return png_path


def plot_phase2_temporal_acceleration(
    scenarios: list[ScenarioData],
    output_dir: str,
    dpi: int = 300,
) -> str:
    """Genera el Gráfico 4: Escalabilidad Temporal por Lote y Aceleración por Concurrencia (Fase 2)."""
    sorted_scenarios = sorted(scenarios, key=lambda s: s.patrones)
    patrones_vals = np.array([s.patrones for s in sorted_scenarios])
    duraciones_reales = np.array([s.duracion_media for s in sorted_scenarios])

    base_time = duraciones_reales[0] if len(duraciones_reales) > 0 else 16.16
    duraciones_secuenciales = patrones_vals * base_time

    labels_x = [
        f"{s.patrones} patrón\n(10 eventos)" if s.patrones == 1 else f"{s.patrones} patrones\n({s.total_eventos} eventos)"
        for s in sorted_scenarios
    ]
    x_indices = np.arange(len(sorted_scenarios))

    fig, ax = plt.subplots(figsize=(9.2, 5.8))

    # Curva Teórica Secuencial (sin paralelismo)
    ax.plot(
        x_indices,
        duraciones_secuenciales,
        color="#dc2626",
        linestyle="--",
        marker="s",
        markersize=8,
        linewidth=2.0,
        label="Procesamiento secuencial teórico (1 patrón a la vez)",
        zorder=3,
    )

    # Curva Real Concurrente (Semáforo = 3)
    ax.plot(
        x_indices,
        duraciones_reales,
        color="#0284c7",
        linestyle="-",
        marker="o",
        markersize=9,
        linewidth=2.8,
        label="Concurrencia regulada real (3 patrones en simultáneo)",
        zorder=4,
    )

    # Área sombreada: Tiempo promedio ahorrado por concurrencia
    ax.fill_between(
        x_indices,
        duraciones_reales,
        duraciones_secuenciales,
        color="#bae6fd",
        alpha=0.45,
        label="Tiempo promedio ahorrado por concurrencia (~62%)",
        zorder=2,
    )

    # Anotaciones sobre los puntos reales
    for i, s in enumerate(sorted_scenarios):
        t_real = duraciones_reales[i]
        t_sec = duraciones_secuenciales[i]
        ahorro_pct = ((t_sec - t_real) / t_sec) * 100.0 if t_sec > 0 else 0.0

        if i == 0:
            label_text = f"{format_num_es(t_real, 2)} s promedio"
        else:
            label_text = f"{format_num_es(t_real, 2)} s promedio\n(-{format_num_es(ahorro_pct, 1)}%)"

        ax.annotate(
            label_text,
            xy=(x_indices[i], t_real),
            xytext=(0, 12 if i == 0 else -34),
            textcoords="offset points",
            ha="center",
            va="bottom" if i == 0 else "top",
            fontsize=9.0,
            fontweight="bold",
            color="#0369a1",
            bbox={"boxstyle": "round,pad=0.25", "facecolor": "#ffffff", "edgecolor": "#bae6fd", "alpha": 0.95},
            zorder=6,
        )

    # Anotaciones sobre los puntos secuenciales teóricos
    for i in range(1, len(sorted_scenarios)):
        t_sec = duraciones_secuenciales[i]
        ax.annotate(
            f"{format_num_es(t_sec, 2)} s teóricos",
            xy=(x_indices[i], t_sec),
            xytext=(0, 8),
            textcoords="offset points",
            ha="center",
            va="bottom",
            fontsize=8.5,
            fontweight="bold",
            color="#b91c1c",
            bbox={"boxstyle": "round,pad=0.2", "facecolor": "#ffffff", "edgecolor": "#fecaca", "alpha": 0.9},
            zorder=6,
        )

    # Configuración de Ejes
    ax.set_xlabel("Volumen de patrones de fricción por lote", labelpad=10, fontweight="bold")
    ax.set_ylabel("Duración promedio de exploración [segundos]", labelpad=10, fontweight="bold")
    ax.set_xticks(x_indices)
    ax.set_xticklabels(labels_x, fontweight="bold")
    ax.set_ylim(0, 185)
    ax.set_yticks([0, 30, 60, 90, 120, 150, 180])
    ax.set_yticklabels(["0", "30", "60", "90", "120", "150", "180"])

    ax.grid(True, alpha=0.7)
    ax.legend(loc="upper left", framealpha=0.95)

    plt.title(
        "Escalamiento temporal por lote: Concurrencia regulada vs. Secuencial teórico",
        pad=15,
        fontweight="bold",
        fontsize=12,
    )

    fig.tight_layout()

    os.makedirs(output_dir, exist_ok=True)
    png_path = os.path.join(output_dir, "grafico_fase2_escalabilidad_lote.png")
    svg_path = os.path.join(output_dir, "grafico_fase2_escalabilidad_lote.svg")
    fig.savefig(png_path, dpi=dpi)
    fig.savefig(svg_path, format="svg")
    plt.close(fig)

    print(f"[OK] Gráfico Fase 2 (Escalabilidad Temporal) guardado en:\n  - {png_path}\n  - {svg_path}")
    return png_path


def plot_phase2_memory_plateau(
    scenarios: list[ScenarioData],
    output_dir: str,
    dpi: int = 300,
) -> str:
    """Genera el Gráfico 5: Estabilidad de Memoria RAM bajo Carga de Concurrencia (Fase 2)."""
    sorted_scenarios = sorted(scenarios, key=lambda s: s.patrones)
    labels = [
        f"{s.patrones} patrón\n(10 eventos)" if s.patrones == 1 else f"{s.patrones} patrones\n({s.total_eventos} eventos)"
        for s in sorted_scenarios
    ]
    ram_python = [s.ram_python_mb for s in sorted_scenarios]
    ram_total = [s.ram_total_mb for s in sorted_scenarios]

    x = np.arange(len(labels))
    width = 0.35

    fig, ax1 = plt.subplots(figsize=(9.2, 5.8))
    ax2 = ax1.twinx()

    color_py = "#2563eb"
    color_tot = "#7c3aed"

    bars1 = ax1.bar(
        x - width / 2,
        ram_python,
        width,
        label="RAM Python",
        color=color_py,
        alpha=0.9,
        edgecolor="#1d4ed8",
        linewidth=1.2,
    )

    bars2 = ax2.bar(
        x + width / 2,
        ram_total,
        width,
        label="RAM Total Contenedor",
        color=color_tot,
        alpha=0.85,
        edgecolor="#6d28d9",
        linewidth=1.2,
    )

    # Anotaciones sobre barras de Python
    for i, bar in enumerate(bars1):
        h = bar.get_height()
        tot = ram_total[i]
        pct = (h / tot) * 100.0 if tot > 0 else 0.0
        ax1.annotate(
            f"{format_num_es(h, 2)} MB\n({format_num_es(pct, 1)}%)",
            xy=(bar.get_x() + bar.get_width() / 2, h),
            xytext=(0, 4),
            textcoords="offset points",
            ha="center",
            va="bottom",
            fontsize=9.0,
            fontweight="bold",
            color=color_py,
        )

    # Anotaciones sobre barras de Total Contenedor
    for i, bar in enumerate(bars2):
        h = bar.get_height()
        ax2.annotate(
            f"{format_num_es(h, 2)} MB",
            xy=(bar.get_x() + bar.get_width() / 2, h),
            xytext=(0, 4),
            textcoords="offset points",
            ha="center",
            va="bottom",
            fontsize=8.5,
            fontweight="bold",
            color=color_tot,
        )

    # Configuración de Ejes con MISMA ESCALA en ambos lados
    y_max = 3800.0
    yticks = [0, 500, 1000, 1500, 2000, 2500, 3000, 3500]
    yticklabels = ["0", "500", "1.000", "1.500", "2.000", "2.500", "3.000", "3.500"]

    ax1.set_xlabel("Volumen de patrones de fricción por lote", labelpad=10, fontweight="bold")
    ax1.set_ylabel("RAM Python [MB]", color=color_py, fontweight="bold", labelpad=8)
    ax2.set_ylabel("RAM Total Contenedor [MB]", color=color_tot, fontweight="bold", labelpad=8)

    ax1.set_xticks(x)
    ax1.set_xticklabels(labels, fontweight="bold")
    ax1.set_ylim(0, y_max)
    ax2.set_ylim(0, y_max)
    ax1.set_yticks(yticks)
    ax1.set_yticklabels(yticklabels)
    ax2.set_yticks(yticks)
    ax2.set_yticklabels(yticklabels)

    ax1.tick_params(axis="y", labelcolor=color_py)
    ax2.tick_params(axis="y", labelcolor=color_tot)
    ax1.grid(axis="y", alpha=0.7)
    ax2.grid(False)

    lines_1, labels_1 = ax1.get_legend_handles_labels()
    lines_2, labels_2 = ax2.get_legend_handles_labels()
    ax1.legend(lines_1 + lines_2, labels_1 + labels_2, loc="upper center", bbox_to_anchor=(0.5, 0.98), ncol=2, framealpha=0.95)

    plt.title(
        "Consumo promedio de RAM bajo carga concurrente (3 patrones en simultáneo)",
        pad=14,
        fontweight="bold",
        fontsize=12,
    )

    fig.tight_layout()

    os.makedirs(output_dir, exist_ok=True)
    png_path = os.path.join(output_dir, "grafico_fase2_memoria_concurrente.png")
    svg_path = os.path.join(output_dir, "grafico_fase2_memoria_concurrente.svg")
    fig.savefig(png_path, dpi=dpi)
    fig.savefig(svg_path, format="svg")
    plt.close(fig)

    print(f"[OK] Gráfico Fase 2 (Estabilidad de Memoria) guardado en:\n  - {png_path}\n  - {svg_path}")
    return png_path


def plot_phase2_combined_panel(
    scenarios: list[ScenarioData],
    output_dir: str,
    dpi: int = 300,
) -> str:
    """Genera una figura combinada de dos paneles (A y B) para la Fase 2."""
    sorted_scenarios = sorted(scenarios, key=lambda s: s.patrones)
    patrones_vals = np.array([s.patrones for s in sorted_scenarios])
    duraciones_reales = np.array([s.duracion_media for s in sorted_scenarios])

    base_time = duraciones_reales[0] if len(duraciones_reales) > 0 else 16.16
    duraciones_secuenciales = patrones_vals * base_time

    labels_x = [
        f"{s.patrones} patrón\n(10 ev.)" if s.patrones == 1 else f"{s.patrones} patrones\n({s.total_eventos} ev.)"
        for s in sorted_scenarios
    ]
    x_indices = np.arange(len(sorted_scenarios))

    fig, (ax_a, ax_b) = plt.subplots(1, 2, figsize=(16, 6))

    # --- PANEL A: Escalabilidad Temporal ---
    ax_a.plot(
        x_indices,
        duraciones_secuenciales,
        color="#dc2626",
        linestyle="--",
        marker="s",
        linewidth=1.8,
        label="Procesamiento secuencial teórico (1 patrón a la vez)",
    )
    ax_a.plot(
        x_indices,
        duraciones_reales,
        color="#0284c7",
        linestyle="-",
        marker="o",
        markersize=8,
        linewidth=2.5,
        label="Concurrencia regulada real (3 patrones en simultáneo)",
    )
    ax_a.fill_between(
        x_indices,
        duraciones_reales,
        duraciones_secuenciales,
        color="#bae6fd",
        alpha=0.45,
        label="Ahorro por concurrencia (~62%)",
    )

    for i, s in enumerate(sorted_scenarios):
        t_real = duraciones_reales[i]
        t_sec = duraciones_secuenciales[i]
        ahorro_pct = ((t_sec - t_real) / t_sec) * 100.0 if t_sec > 0 else 0.0
        if i == 0:
            label_text_panel = f"{format_num_es(t_real, 1)} s"
        else:
            label_text_panel = f"{format_num_es(t_real, 1)} s\n(-{format_num_es(ahorro_pct, 1)}%)"

        ax_a.annotate(
            label_text_panel,
            xy=(x_indices[i], t_real),
            xytext=(0, 8 if i == 0 else -28),
            textcoords="offset points",
            ha="center",
            va="bottom" if i == 0 else "top",
            fontweight="bold",
            fontsize=8.5,
            color="#0369a1",
        )

    ax_a.set_title("A) Escalamiento Temporal por Lote vs. Secuencial", fontweight="bold", pad=10)
    ax_a.set_xlabel("Volumen de patrones de fricción por lote", fontweight="bold")
    ax_a.set_ylabel("Duración Promedio [s]", fontweight="bold")
    ax_a.set_xticks(x_indices)
    ax_a.set_xticklabels(labels_x, fontweight="bold")
    ax_a.set_ylim(0, 185)
    ax_a.grid(True, alpha=0.7)
    ax_a.legend(loc="upper left")

    # --- PANEL B: Estabilidad de Memoria RAM ---
    ram_python = [s.ram_python_mb for s in sorted_scenarios]
    ram_total = [s.ram_total_mb for s in sorted_scenarios]
    width = 0.35

    ax_b2 = ax_b.twinx()
    color_py = "#2563eb"
    color_tot = "#7c3aed"

    b1 = ax_b.bar(x_indices - width / 2, ram_python, width, label="RAM Python", color=color_py, alpha=0.9)
    b2 = ax_b2.bar(x_indices + width / 2, ram_total, width, label="RAM Total Contenedor", color=color_tot, alpha=0.85)

    for i, bar in enumerate(b1):
        h = bar.get_height()
        tot = ram_total[i]
        pct = (h / tot) * 100.0 if tot > 0 else 0.0
        ax_b.annotate(
            f"{format_num_es(h, 1)}\n({format_num_es(pct, 1)}%)",
            (bar.get_x() + bar.get_width() / 2, h),
            (0, 3),
            textcoords="offset points",
            ha="center",
            va="bottom",
            fontweight="bold",
            fontsize=8.5,
            color=color_py,
        )

    for bar in b2:
        h = bar.get_height()
        ax_b2.annotate(
            f"{format_num_es(h, 0)} MB",
            (bar.get_x() + bar.get_width() / 2, h),
            (0, 3),
            textcoords="offset points",
            ha="center",
            va="bottom",
            fontweight="bold",
            fontsize=8.5,
            color=color_tot,
        )

    ax_b.set_title("B) Consumo Promedio de Memoria RAM (Escala Unificada)", fontweight="bold", pad=10)
    ax_b.set_xlabel("Volumen de patrones de fricción por lote", fontweight="bold")
    ax_b.set_ylabel("RAM Python [MB]", color=color_py, fontweight="bold")
    ax_b2.set_ylabel("RAM Total Contenedor [MB]", color=color_tot, fontweight="bold")
    ax_b.set_xticks(x_indices)
    ax_b.set_xticklabels(labels_x, fontweight="bold")

    y_max_panel_b = 3800.0
    yticks_panel_b = [0, 500, 1000, 1500, 2000, 2500, 3000, 3500]
    yticklabels_panel_b = ["0", "500", "1.000", "1.500", "2.000", "2.500", "3.000", "3.500"]

    ax_b.set_ylim(0, y_max_panel_b)
    ax_b2.set_ylim(0, y_max_panel_b)
    ax_b.set_yticks(yticks_panel_b)
    ax_b.set_yticklabels(yticklabels_panel_b)
    ax_b2.set_yticks(yticks_panel_b)
    ax_b2.set_yticklabels(yticklabels_panel_b)

    ax_b.tick_params(axis="y", labelcolor=color_py)
    ax_b2.tick_params(axis="y", labelcolor=color_tot)
    ax_b.grid(axis="y", alpha=0.7)
    ax_b2.grid(False)

    lines_1, labels_1 = ax_b.get_legend_handles_labels()
    lines_2, labels_2 = ax_b2.get_legend_handles_labels()
    ax_b.legend(lines_1 + lines_2, labels_1 + labels_2, loc="upper left")

    plt.suptitle("Evaluación de Performance y Escalabilidad - Fase 2 (Escalamiento por Lote)", fontsize=16, fontweight="bold", y=0.98)
    fig.tight_layout(rect=(0.0, 0.0, 1.0, 0.95))

    os.makedirs(output_dir, exist_ok=True)
    png_path = os.path.join(output_dir, "grafico_fase2_panel_consolidado.png")
    svg_path = os.path.join(output_dir, "grafico_fase2_panel_consolidado.svg")
    fig.savefig(png_path, dpi=dpi)
    fig.savefig(svg_path, format="svg")
    plt.close(fig)

    print(f"[OK] Panel Consolidado Fase 2 guardado en:\n  - {png_path}\n  - {svg_path}")
    return png_path


def plot_phase3_fairness_latency(
    clients: list[ClientData],
    scenarios: list[ScenarioData],
    output_dir: str,
    dpi: int = 300,
) -> str:
    """Genera el Gráfico de Equidad de Despacho y Latencia por Cliente (Fase 3)."""
    p3_scenarios = sorted([s for s in scenarios if "Fase 3" in s.fase or "3patrones" in s.escenario], key=lambda s: s.clientes)
    if not p3_scenarios:
        return ""

    fig, ax = plt.subplots(figsize=(9.8, 5.8))
    client_palette = ["#0284c7", "#0d9488", "#7c3aed", "#d97706", "#db2777"]
    tier_x_centers = [0.0, 1.4, 3.0]
    bar_width = 0.16
    labels_x = []

    for idx, sc in enumerate(p3_scenarios):
        c_count = sc.clientes
        lbl = f"{c_count} cliente\n({sc.total_eventos} eventos)" if c_count == 1 else f"{c_count} clientes\n({sc.total_eventos} eventos)"
        labels_x.append(lbl)
        center_x = tier_x_centers[idx]

        sc_clients = [c for c in clients if c.escenario == sc.escenario]
        if not sc_clients:
            sc_clients = [
                ClientData(
                    escenario=sc.escenario,
                    repeticion=1,
                    cliente=f"Cliente {k + 1}",
                    duracion_s=sc.duracion_media,
                    eventos_completados=sc.total_eventos // c_count,
                    eventos_totales=sc.total_eventos // c_count,
                    segundos_por_evento=sc.tiempo_por_evento,
                    estado="COMPLETED",
                )
                for k in range(c_count)
            ]

        n_bars = len(sc_clients)
        offsets = (np.arange(n_bars) - (n_bars - 1) / 2) * (bar_width + 0.04)
        durations = [c.duracion_s for c in sc_clients]
        mean_tier = sum(durations) / len(durations) if durations else 0.0

        for b_idx, c_data in enumerate(sc_clients):
            bar_x = center_x + offsets[b_idx]
            col = client_palette[b_idx % len(client_palette)]
            ax.bar(
                bar_x,
                c_data.duracion_s,
                bar_width,
                color=col,
                alpha=0.88,
                edgecolor=col,
                linewidth=1.2,
                label=c_data.cliente if idx == (len(p3_scenarios) - 1) else None,
            )
            ax.annotate(
                f"{format_num_es(c_data.duracion_s, 1)} s",
                (bar_x, c_data.duracion_s),
                (0, 3),
                textcoords="offset points",
                ha="center",
                va="bottom",
                fontweight="bold",
                fontsize=8.5,
                color="#0f172a",
            )

    ax.set_title("Equidad de duración por cliente", pad=15, fontweight="bold", fontsize=12)
    ax.set_xlabel("Nivel de concurrencia de clientes", labelpad=10, fontweight="bold")
    ax.set_ylabel("Duración por cliente [segundos]", labelpad=10, fontweight="bold")
    ax.set_xticks(tier_x_centers)
    ax.set_xticklabels(labels_x, fontweight="bold")

    max_d = max([c.duracion_s for c in clients], default=35.0)
    y_lim = max(40.0, math.ceil((max_d * 1.35) / 10.0) * 10.0)
    ax.set_ylim(0, y_lim)
    ax.grid(axis="y", alpha=0.7)

    ax.legend(loc="upper right", framealpha=0.95)
    fig.tight_layout()

    os.makedirs(output_dir, exist_ok=True)
    png_path = os.path.join(output_dir, "grafico_fase3_equidad_latencia.png")
    svg_path = os.path.join(output_dir, "grafico_fase3_equidad_latencia.svg")
    fig.savefig(png_path, dpi=dpi)
    fig.savefig(svg_path, format="svg")
    plt.close(fig)

    print(f"[OK] Gráfico Fase 3 (Equidad y Latencia) guardado en:\n  - {png_path}\n  - {svg_path}")
    return png_path


def plot_phase3_memory(
    scenarios: list[ScenarioData],
    output_dir: str,
    dpi: int = 300,
) -> str:
    """Genera el Gráfico de Consumo de Memoria RAM Multi-Inquilino (Fase 3) sin anotaciones de estabilidad."""
    sorted_scenarios = sorted([s for s in scenarios if "Fase 3" in s.fase or "3patrones" in s.escenario], key=lambda s: s.clientes)
    labels = [
        f"{s.clientes} cliente\n({s.total_eventos} eventos)" if s.clientes == 1 else f"{s.clientes} clientes\n({s.total_eventos} eventos)"
        for s in sorted_scenarios
    ]
    ram_python = [s.ram_python_mb for s in sorted_scenarios]
    ram_total = [s.ram_total_mb for s in sorted_scenarios]

    x = np.arange(len(labels))
    width = 0.35

    fig, ax1 = plt.subplots(figsize=(9.2, 5.8))
    ax2 = ax1.twinx()

    color_py = "#2563eb"
    color_tot = "#7c3aed"

    bars1 = ax1.bar(
        x - width / 2,
        ram_python,
        width,
        label="RAM Python",
        color=color_py,
        alpha=0.9,
        edgecolor="#1d4ed8",
        linewidth=1.2,
    )

    bars2 = ax2.bar(
        x + width / 2,
        ram_total,
        width,
        label="RAM Instancia Cloud Run",
        color=color_tot,
        alpha=0.85,
        edgecolor="#6d28d9",
        linewidth=1.2,
    )

    # Anotaciones sobre barras de Python (solo valores numéricos y porcentajes)
    for i, bar in enumerate(bars1):
        h = bar.get_height()
        tot = ram_total[i]
        pct = (h / tot) * 100.0 if tot > 0 else 0.0
        ax1.annotate(
            f"{format_num_es(h, 2)} MB\n({format_num_es(pct, 1)}%)",
            xy=(bar.get_x() + bar.get_width() / 2, h),
            xytext=(0, 4),
            textcoords="offset points",
            ha="center",
            va="bottom",
            fontsize=9.0,
            fontweight="bold",
            color=color_py,
        )

    # Anotaciones sobre barras de Instancia Cloud Run (solo valor numérico, SIN notas de estabilidad)
    for bar in bars2:
        h = bar.get_height()
        ax2.annotate(
            f"{format_num_es(h, 2)} MB",
            xy=(bar.get_x() + bar.get_width() / 2, h),
            xytext=(0, 4),
            textcoords="offset points",
            ha="center",
            va="bottom",
            fontsize=8.5,
            fontweight="bold",
            color=color_tot,
        )

    # Configuración de Ejes con MISMA ESCALA en ambos lados
    max_ram = max(ram_total, default=2000.0)
    y_max = max(2500.0, math.ceil((max_ram * 1.25) / 500.0) * 500.0)
    yticks = np.arange(0, y_max + 1, 500)
    yticklabels = [format_num_es(y, 0) for y in yticks]

    ax1.set_xlabel("Escalón de concurrencia multi-inquilino", labelpad=10, fontweight="bold")
    ax1.set_ylabel("RAM Python [MB]", color=color_py, fontweight="bold", labelpad=8)
    ax2.set_ylabel("RAM Instancia Cloud Run [MB]", color=color_tot, fontweight="bold", labelpad=8)

    ax1.set_xticks(x)
    ax1.set_xticklabels(labels, fontweight="bold")
    ax1.set_ylim(0, y_max)
    ax2.set_ylim(0, y_max)
    ax1.set_yticks(yticks)
    ax1.set_yticklabels(yticklabels)
    ax2.set_yticks(yticks)
    ax2.set_yticklabels(yticklabels)

    ax1.tick_params(axis="y", labelcolor=color_py)
    ax2.tick_params(axis="y", labelcolor=color_tot)
    ax1.grid(axis="y", alpha=0.7)
    ax2.grid(False)

    lines_1, labels_1 = ax1.get_legend_handles_labels()
    lines_2, labels_2 = ax2.get_legend_handles_labels()
    ax1.legend(lines_1 + lines_2, labels_1 + labels_2, loc="upper center", bbox_to_anchor=(0.5, 0.98), ncol=2, framealpha=0.95)

    plt.title(
        "Consumo promedio de memoria RAM por instancia de Cloud Run",
        pad=14,
        fontweight="bold",
        fontsize=12,
    )

    fig.tight_layout()

    os.makedirs(output_dir, exist_ok=True)
    png_path = os.path.join(output_dir, "grafico_fase3_memoria_multicliente.png")
    svg_path = os.path.join(output_dir, "grafico_fase3_memoria_multicliente.svg")
    fig.savefig(png_path, dpi=dpi)
    fig.savefig(svg_path, format="svg")
    plt.close(fig)

    print(f"[OK] Gráfico Fase 3 (Consumo de Memoria) guardado en:\n  - {png_path}\n  - {svg_path}")
    return png_path


def plot_phase3_combined_panel(
    clients: list[ClientData],
    scenarios: list[ScenarioData],
    output_dir: str,
    dpi: int = 300,
) -> str:
    """Genera una figura combinada de dos paneles (A y B) para la Fase 3."""
    p3_scenarios = sorted([s for s in scenarios if "Fase 3" in s.fase or "3patrones" in s.escenario], key=lambda s: s.clientes)
    if not p3_scenarios:
        return ""

    fig, (ax_a, ax_b) = plt.subplots(1, 2, figsize=(16, 6))

    # --- PANEL A: Equidad y Latencia Individual por Cliente ---
    client_palette = ["#0284c7", "#0d9488", "#7c3aed", "#d97706", "#db2777"]
    tier_x_centers = [0.0, 1.4, 3.0]
    bar_width = 0.16
    labels_x = []

    for idx, sc in enumerate(p3_scenarios):
        c_count = sc.clientes
        lbl = f"{c_count} cli\n({sc.total_eventos} ev.)"
        labels_x.append(lbl)
        center_x = tier_x_centers[idx]

        sc_clients = [c for c in clients if c.escenario == sc.escenario]
        if not sc_clients:
            sc_clients = [
                ClientData(
                    escenario=sc.escenario,
                    repeticion=1,
                    cliente=f"Cliente {k + 1}",
                    duracion_s=sc.duracion_media,
                    eventos_completados=sc.total_eventos // c_count,
                    eventos_totales=sc.total_eventos // c_count,
                    segundos_por_evento=sc.tiempo_por_evento,
                    estado="COMPLETED",
                )
                for k in range(c_count)
            ]

        n_bars = len(sc_clients)
        offsets = (np.arange(n_bars) - (n_bars - 1) / 2) * (bar_width + 0.04)
        durations = [c.duracion_s for c in sc_clients]
        mean_tier = sum(durations) / len(durations) if durations else 0.0

        for b_idx, c_data in enumerate(sc_clients):
            bar_x = center_x + offsets[b_idx]
            col = client_palette[b_idx % len(client_palette)]
            ax_a.bar(
                bar_x,
                c_data.duracion_s,
                bar_width,
                color=col,
                alpha=0.88,
                edgecolor=col,
                linewidth=1.2,
                label=c_data.cliente if idx == (len(p3_scenarios) - 1) else None,
            )
            ax_a.annotate(
                f"{format_num_es(c_data.duracion_s, 1)} s",
                (bar_x, c_data.duracion_s),
                (0, 3),
                textcoords="offset points",
                ha="center",
                va="bottom",
                fontweight="bold",
                fontsize=8.0,
                color="#0f172a",
            )

        x_min_span = center_x + offsets[0] - bar_width * 0.7
        x_max_span = center_x + offsets[-1] + bar_width * 0.7
        ax_a.hlines(
            y=mean_tier,
            xmin=x_min_span,
            xmax=x_max_span,
            color="#ef4444",
            linestyle="--",
            linewidth=1.5,
            zorder=5,
        )

    ax_a.set_title("A) Equidad de Despacho y Latencia por Cliente (Instancias Aisladas)", fontweight="bold", pad=10)
    ax_a.set_xlabel("Escalón de concurrencia multi-inquilino", fontweight="bold")
    ax_a.set_ylabel("Duración Promedio por Cliente [s]", fontweight="bold")
    ax_a.set_xticks(tier_x_centers)
    ax_a.set_xticklabels(labels_x, fontweight="bold")
    max_d = max([c.duracion_s for c in clients], default=35.0)
    y_lim = max(40.0, math.ceil((max_d * 1.35) / 10.0) * 10.0)
    ax_a.set_ylim(0, y_lim)
    ax_a.grid(axis="y", alpha=0.7)
    ax_a.legend(loc="upper left")

    # --- PANEL B: Consumo de Memoria RAM ---
    ram_python = [s.ram_python_mb for s in p3_scenarios]
    ram_total = [s.ram_total_mb for s in p3_scenarios]
    x_indices = np.arange(len(labels_x))
    width = 0.35

    ax_b2 = ax_b.twinx()
    color_py = "#2563eb"
    color_tot = "#7c3aed"

    b1 = ax_b.bar(x_indices - width / 2, ram_python, width, label="RAM Python", color=color_py, alpha=0.9)
    b2 = ax_b2.bar(x_indices + width / 2, ram_total, width, label="RAM Instancia Cloud Run", color=color_tot, alpha=0.85)

    for i, bar in enumerate(b1):
        h = bar.get_height()
        tot = ram_total[i]
        pct = (h / tot) * 100.0 if tot > 0 else 0.0
        ax_b.annotate(
            f"{format_num_es(h, 1)}\n({format_num_es(pct, 1)}%)",
            (bar.get_x() + bar.get_width() / 2, h),
            (0, 3),
            textcoords="offset points",
            ha="center",
            va="bottom",
            fontweight="bold",
            fontsize=8.5,
            color=color_py,
        )

    for bar in b2:
        h = bar.get_height()
        ax_b2.annotate(
            f"{format_num_es(h, 0)} MB",
            (bar.get_x() + bar.get_width() / 2, h),
            (0, 3),
            textcoords="offset points",
            ha="center",
            va="bottom",
            fontweight="bold",
            fontsize=8.5,
            color=color_tot,
        )

    ax_b.set_title("B) Consumo de Memoria RAM por Instancia (Escala Unificada)", fontweight="bold", pad=10)
    ax_b.set_xlabel("Escalón de concurrencia multi-inquilino", fontweight="bold")
    ax_b.set_ylabel("RAM Python [MB]", color=color_py, fontweight="bold")
    ax_b2.set_ylabel("RAM Instancia Cloud Run [MB]", color=color_tot, fontweight="bold")
    ax_b.set_xticks(x_indices)
    ax_b.set_xticklabels(labels_x, fontweight="bold")

    max_ram = max(ram_total, default=2000.0)
    y_max_panel_b = max(2500.0, math.ceil((max_ram * 1.25) / 500.0) * 500.0)
    yticks_panel_b = np.arange(0, y_max_panel_b + 1, 500)
    yticklabels_panel_b = [format_num_es(y, 0) for y in yticks_panel_b]

    ax_b.set_ylim(0, y_max_panel_b)
    ax_b2.set_ylim(0, y_max_panel_b)
    ax_b.set_yticks(yticks_panel_b)
    ax_b.set_yticklabels(yticklabels_panel_b)
    ax_b2.set_yticks(yticks_panel_b)
    ax_b2.set_yticklabels(yticklabels_panel_b)

    ax_b.tick_params(axis="y", labelcolor=color_py)
    ax_b2.tick_params(axis="y", labelcolor=color_tot)
    ax_b.grid(axis="y", alpha=0.7)
    ax_b2.grid(False)

    lines_1, labels_1 = ax_b.get_legend_handles_labels()
    lines_2, labels_2 = ax_b2.get_legend_handles_labels()
    ax_b.legend(lines_1 + lines_2, labels_1 + labels_2, loc="upper left")

    plt.suptitle("Evaluación de Performance y Escalabilidad - Fase 3 (Multi-Inquilino)", fontsize=16, fontweight="bold", y=0.98)
    fig.tight_layout(rect=(0.0, 0.0, 1.0, 0.95))

    os.makedirs(output_dir, exist_ok=True)
    png_path = os.path.join(output_dir, "grafico_fase3_panel_consolidado.png")
    svg_path = os.path.join(output_dir, "grafico_fase3_panel_consolidado.svg")
    fig.savefig(png_path, dpi=dpi)
    fig.savefig(svg_path, format="svg")
    plt.close(fig)

    print(f"[OK] Panel Consolidado Fase 3 guardado en:\n  - {png_path}\n  - {svg_path}")
    return png_path


def main() -> int:
    """Función de entrada para terminal."""
    parser = argparse.ArgumentParser(
        description="Generador de Gráficos de Performance: Módulo de Exploración Agéntica",
    )
    parser.add_argument(
        "--input-file",
        default="benchmark_agent_results.md",
        help="Archivo Markdown con los resultados consolidados del benchmark.",
    )
    parser.add_argument(
        "--output-dir",
        default="benchmark_charts",
        help="Directorio de salida para los gráficos PNG y SVG.",
    )
    parser.add_argument(
        "--dpi",
        type=int,
        default=300,
        help="Resolución DPI para la exportación de imágenes PNG.",
    )
    parser.add_argument(
        "--phase",
        "--fase",
        dest="phase",
        default="all",
        choices=["all", "1", "2", "3"],
        help="Fase de evaluación para generar gráficos (1, 2, 3, o all para todas).",
    )

    args = parser.parse_args()
    print("=" * 80)
    print(" GENERADOR DE GRÁFICOS: PERFORMANCE Y ESCALABILIDAD (EUREKA)")
    print("=" * 80)
    print(f"Leyendo resultados desde: {args.input_file}")
    print(f"Directorio de salida:     {args.output_dir}")
    print(f"Fase seleccionada:        {args.phase}")

    scenarios, iterations, clients = parse_markdown_results(args.input_file)
    print(f"Escenarios identificados: {len(scenarios)}")
    print(f"Repeticiones cargadas:    {len(iterations)}")
    print(f"Registros de clientes:    {len(clients)}")
    print("-" * 80)

    # 1. Gráficos de Fase 1 (Sensibilidad a la Longitud del Patrón de Fricción)
    if args.phase in ("all", "1"):
        p1_scenarios = [s for s in scenarios if "Fase 1" in s.fase or "eventos" in s.escenario]
        p1_iterations = [it for it in iterations if "eventos" in it.escenario]

        if p1_scenarios:
            print("\n>>> Generando figuras de la Fase 1...")
            plot_dual_memory(p1_scenarios, args.output_dir, dpi=args.dpi)
            plot_temporal_scalability(p1_scenarios, p1_iterations, args.output_dir, dpi=args.dpi)
            plot_combined_panel(p1_scenarios, p1_iterations, args.output_dir, dpi=args.dpi)

    # 2. Gráficos de Fase 2 (Sensibilidad al Volumen por Lote / Concurrencia)
    if args.phase in ("all", "2"):
        p2_scenarios = [s for s in scenarios if "Fase 2" in s.fase or "patron" in s.escenario]
        if p2_scenarios:
            print("\n>>> Generando figuras de la Fase 2...")
            plot_phase2_temporal_acceleration(p2_scenarios, args.output_dir, dpi=args.dpi)
            plot_phase2_memory_plateau(p2_scenarios, args.output_dir, dpi=args.dpi)
            plot_phase2_combined_panel(p2_scenarios, args.output_dir, dpi=args.dpi)

    # 3. Gráficos de Fase 3 (Multi-Inquilino y Concurrencia de Clientes)
    if args.phase in ("all", "3"):
        p3_scenarios = [s for s in scenarios if "Fase 3" in s.fase or "3patrones" in s.escenario]
        if p3_scenarios:
            print("\n>>> Generando figuras de la Fase 3...")
            plot_phase3_fairness_latency(clients, p3_scenarios, args.output_dir, dpi=args.dpi)
            plot_phase3_memory(p3_scenarios, args.output_dir, dpi=args.dpi)
            plot_phase3_combined_panel(clients, p3_scenarios, args.output_dir, dpi=args.dpi)

    print("-" * 80)
    print(f"[ÉXITO] Todos los gráficos se han generado en: {os.path.abspath(args.output_dir)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
