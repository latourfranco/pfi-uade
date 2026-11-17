#!/usr/bin/env python3
"""
Generador de gráficos de alto impacto para la Fase 1 del Benchmark en GCP BigQuery.
"""

import os
import shutil
from typing import Dict, List
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
import numpy as np


def fmt_spanish_thousands(x: float, _pos: int | None = None) -> str:
    """Formatea valores con punto para miles y coma para decimales (ej: 10.000 o 2,5)."""
    if x >= 1:
        return f"{int(round(x)):,}".replace(",", ".")
    return f"{x:g}".replace(".", ",")


def fmt_spanish_decimals(y: float, _pos: int | None = None) -> str:
    """Formatea flotantes con coma como separador decimal (ej: 4,5)."""
    return f"{y:g}".replace(".", ",")


# Configuración de estilo y tipografía limpia
plt.rcParams.update({
    "font.size": 11,
    "axes.labelsize": 12,
    "axes.titlesize": 13,
    "xtick.labelsize": 11,
    "ytick.labelsize": 11,
    "legend.fontsize": 10,
    "figure.titlesize": 14,
    "grid.alpha": 0.4,
    "grid.linestyle": "--",
})

# Datos empíricos medidos en GCP BigQuery (5 ejecuciones por volumen)
VOLUMES = [10_000, 100_000, 1_000_000, 5_000_000]
VOLUME_LABELS = ["10k", "100k", "1M", "5M"]

RUNS_DURATION: Dict[str, List[float]] = {
    "10k": [5.51, 4.65, 4.12, 4.02, 4.49],
    "100k": [4.92, 5.43, 5.53, 5.33, 4.69],
    "1M": [16.79, 16.92, 13.22, 15.76, 13.44],
    "5M": [7.92, 6.42, 7.11, 7.19, 7.47],
}

RUNS_THROUGHPUT: Dict[str, List[float]] = {
    "10k": [1815, 2152, 2428, 2485, 2228],
    "100k": [20324, 18419, 18100, 18768, 21331],
    "1M": [59558, 59105, 75645, 63452, 74380],
    "5M": [631585, 779017, 702935, 695121, 669584],
}

# Estadísticos agregados
TP_MEDIAN = [np.median(RUNS_THROUGHPUT[k]) for k in VOLUME_LABELS]
TP_P90 = [np.percentile(RUNS_THROUGHPUT[k], 90) for k in VOLUME_LABELS]
TP_MIN = [np.min(RUNS_THROUGHPUT[k]) for k in VOLUME_LABELS]
TP_MAX = [np.max(RUNS_THROUGHPUT[k]) for k in VOLUME_LABELS]


def plot_chart_1_throughput(output_path: str) -> None:
    """Gráfico 1: Curva de Throughput vs. Volumen de eventos."""
    fig, ax = plt.subplots(figsize=(8.5, 6), dpi=300)

    # Banda sombreada de dispersión (Min a Max de las 5 ejecuciones)
    ax.fill_between(
        VOLUMES,
        TP_MIN,
        TP_MAX,
        color="#2b5c8f",
        alpha=0.15,
        label="Rango min-max (5 ejecuciones)",
    )

    # Línea de Mediana
    ax.plot(
        VOLUMES,
        TP_MEDIAN,
        color="#1a4472",
        linewidth=2.5,
        marker="o",
        markersize=8,
        label="Mediana (ev/s)",
    )

    # Línea de Percentil 90
    ax.plot(
        VOLUMES,
        TP_P90,
        color="#d9534f",
        linewidth=2.0,
        linestyle="--",
        marker="s",
        markersize=7,
        label="Percentil 90 (P90)",
    )

    # Configuración de escala logarítmica con formato en español (punto para miles)
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.yaxis.set_major_formatter(FuncFormatter(fmt_spanish_thousands))
    ax.set_xticks(VOLUMES)
    ax.set_xticklabels(["10k\n(10.000)", "100k\n(100.000)", "1M\n(1.000.000)", "5M\n(5.000.000)"])

    # Etiquetas de ejes en formato tipo oración y sin "(Escala Logarítmica)"
    ax.set_xlabel("Volumen de eventos por ejecución", fontweight="bold")
    ax.set_ylabel("Throughput de ingesta [eventos / segundo]", fontweight="bold")
    ax.set_title("Curva de Throughput vs Volumen de eventos", fontweight="bold", pad=15)

    # Anotaciones numéricas en cada punto clave
    for vol, tp in zip(VOLUMES, TP_MEDIAN):
        formatted_tp = f"{int(round(tp)):,}".replace(",", ".")
        ax.annotate(
            f"{formatted_tp} ev/s",
            xy=(vol, tp),
            xytext=(0, 14),
            textcoords="offset points",
            ha="center",
            fontweight="semibold",
            fontsize=9.5,
            bbox=dict(boxstyle="round,pad=0.25", fc="#ffffff", ec="#1a4472", lw=0.8, alpha=0.9),
        )

    # Etiqueta de autoescalado sin paréntesis y sin puntero (flecha)
    ax.text(
        2_500_000,
        250_000,
        "Autoescalado masivo de slots",
        ha="center",
        va="center",
        fontsize=9.5,
        fontweight="bold",
        color="#d9534f",
        bbox=dict(boxstyle="round,pad=0.4", fc="#fdf7f7", ec="#d9534f", lw=1),
    )

    ax.grid(True, which="both", linestyle="--", linewidth=0.5, alpha=0.5)
    ax.legend(loc="upper left", frameon=True, facecolor="#ffffff", edgecolor="#cccccc")
    plt.tight_layout()
    plt.savefig(output_path, dpi=300)
    plt.close()
    print(f"[OK] Gráfico 1 guardado en: {output_path}")


def plot_chart_2_boxplot(output_path: str) -> None:
    """Gráfico 2: Diagrama de Cajas mostrando exclusivamente el rango intercuartil (IQR)."""
    fig, ax = plt.subplots(figsize=(8.5, 6), dpi=300)

    data = [RUNS_DURATION[k] for k in VOLUME_LABELS]
    positions = [1, 2, 3, 4]

    # Crear Boxplot con caja (IQR), bigotes y topes (sin línea de mediana)
    bp = ax.boxplot(
        data,
        positions=positions,
        widths=0.45,
        patch_artist=True,
        showbox=True,
        showcaps=True,
        showfliers=False,
        whis=(0, 100),
        boxprops=dict(facecolor="#e8f0fe", color="#1a73e8", linewidth=1.5),
        whiskerprops=dict(color="#1a73e8", linewidth=1.5),
        capprops=dict(color="#1a73e8", linewidth=1.5),
        medianprops=dict(visible=False),
    )

    ax.yaxis.set_major_formatter(FuncFormatter(fmt_spanish_decimals))
    ax.set_xticks(positions)
    ax.set_xticklabels(
        [
            "10k\n(Prom: 4,56 s)",
            "100k\n(Prom: 5,18 s)",
            "1M\n(Prom: 15,23 s)",
            "5M\n(Prom: 7,22 s)",
        ],
        fontweight="semibold",
    )

    # Etiquetas de ejes en formato tipo oración
    ax.set_xlabel("Escala de volumen de eventos", fontweight="bold")
    ax.set_ylabel("Duración total de extracción e inserción [segundos]", fontweight="bold")
    ax.set_title("Distribución de latencia entre ejecuciones", fontweight="bold", pad=15)

    # Línea de referencia del overhead basal fijo (~4,5 s) con texto ubicado hacia la derecha
    ax.axhline(4.5, color="#5f6368", linestyle=":", linewidth=1.2, alpha=0.8)
    ax.text(
        4.4,
        4.75,
        "Overhead basal de inicio en BigQuery (~4,5 s)",
        fontsize=9,
        color="#5f6368",
        style="italic",
        ha="right",
    )

    # Cartel cerca del último boxplot (5M), texto recortado y sin puntero
    ax.text(
        4.0,
        9.2,
        "Aceleración por paralelismo masivo",
        ha="center",
        va="center",
        fontsize=9.5,
        fontweight="semibold",
        color="#1a73e8",
        bbox=dict(boxstyle="round,pad=0.35", fc="#e8f0fe", ec="#1a73e8", lw=1),
    )

    ax.set_xlim(0.5, 4.6)
    ax.set_ylim(2, 20)
    ax.grid(True, axis="y", linestyle="--", linewidth=0.6, alpha=0.6)

    # Leyenda indicando el rango intercuartil
    ax.legend(
        handles=[bp["boxes"][0]],
        labels=["Rango intercuartil (IQR)"],
        loc="upper left",
        frameon=True,
        facecolor="#ffffff",
        edgecolor="#cccccc",
    )

    plt.tight_layout()
    plt.savefig(output_path, dpi=300)
    plt.close()
    print(f"[OK] Gráfico 2 guardado en: {output_path}")


def plot_combined_panel(output_path: str) -> None:
    """Panel combinado con ambos gráficos actualizados."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6.5), dpi=300)

    # --- PANEL IZQUIERDO: Throughput ---
    ax1.fill_between(VOLUMES, TP_MIN, TP_MAX, color="#2b5c8f", alpha=0.15, label="Rango min-max (5 ejecuciones)")
    ax1.plot(VOLUMES, TP_MEDIAN, color="#1a4472", linewidth=2.5, marker="o", markersize=8, label="Mediana (ev/s)")
    ax1.plot(
        VOLUMES,
        TP_P90,
        color="#d9534f",
        linewidth=2.0,
        linestyle="--",
        marker="s",
        markersize=7,
        label="Percentil 90 (P90)",
    )

    ax1.set_xscale("log")
    ax1.set_yscale("log")
    ax1.yaxis.set_major_formatter(FuncFormatter(fmt_spanish_thousands))
    ax1.set_xticks(VOLUMES)
    ax1.set_xticklabels(["10k\n(10.000)", "100k\n(100.000)", "1M\n(1.000.000)", "5M\n(5.000.000)"])
    ax1.set_xlabel("Volumen de eventos por ejecución", fontweight="bold")
    ax1.set_ylabel("Throughput de ingesta [eventos / segundo]", fontweight="bold")
    ax1.set_title("(A) Curva de Throughput vs Volumen de eventos", fontweight="bold")

    for vol, tp in zip(VOLUMES, TP_MEDIAN):
        formatted_tp = f"{int(round(tp)):,}".replace(",", ".")
        ax1.annotate(
            f"{formatted_tp} ev/s",
            xy=(vol, tp),
            xytext=(0, 12),
            textcoords="offset points",
            ha="center",
            fontsize=9,
            fontweight="semibold",
            bbox=dict(boxstyle="round,pad=0.2", fc="#ffffff", ec="#1a4472", lw=0.6, alpha=0.9),
        )

    ax1.text(
        2_500_000,
        250_000,
        "Autoescalado masivo de slots",
        ha="center",
        va="center",
        fontsize=9,
        fontweight="bold",
        color="#d9534f",
        bbox=dict(boxstyle="round,pad=0.3", fc="#fdf7f7", ec="#d9534f", lw=0.8),
    )

    ax1.grid(True, which="both", linestyle="--", linewidth=0.5, alpha=0.5)
    ax1.legend(loc="upper left", frameon=True)

    # --- PANEL DERECHO: Boxplot Latencia ---
    data = [RUNS_DURATION[k] for k in VOLUME_LABELS]
    positions = [1, 2, 3, 4]
    bp = ax2.boxplot(
        data,
        positions=positions,
        widths=0.45,
        patch_artist=True,
        showbox=True,
        showcaps=True,
        showfliers=False,
        whis=(0, 100),
        boxprops=dict(facecolor="#e8f0fe", color="#1a73e8", linewidth=1.5),
        whiskerprops=dict(color="#1a73e8", linewidth=1.5),
        capprops=dict(color="#1a73e8", linewidth=1.5),
        medianprops=dict(visible=False),
    )

    ax2.yaxis.set_major_formatter(FuncFormatter(fmt_spanish_decimals))
    ax2.set_xticks(positions)
    ax2.set_xticklabels(
        [
            "10k\n(Prom: 4,56 s)",
            "100k\n(Prom: 5,18 s)",
            "1M\n(Prom: 15,23 s)",
            "5M\n(Prom: 7,22 s)",
        ]
    )
    ax2.set_xlabel("Escala de volumen de eventos", fontweight="bold")
    ax2.set_ylabel("Duración total [segundos]", fontweight="bold")
    ax2.set_title("(B) Distribución de latencia entre ejecuciones", fontweight="bold")

    # Línea de referencia del overhead basal fijo (~4,5 s) hacia la derecha
    ax2.axhline(4.5, color="#5f6368", linestyle=":", linewidth=1.2, alpha=0.8)
    ax2.text(
        4.4,
        4.75,
        "Overhead basal de inicio en BigQuery (~4,5 s)",
        fontsize=9,
        color="#5f6368",
        style="italic",
        ha="right",
    )

    ax2.text(
        4.0,
        9.2,
        "Aceleración por paralelismo masivo",
        ha="center",
        va="center",
        fontsize=9,
        fontweight="semibold",
        color="#1a73e8",
        bbox=dict(boxstyle="round,pad=0.3", fc="#e8f0fe", ec="#1a73e8", lw=0.8),
    )

    ax2.set_xlim(0.5, 4.6)
    ax2.set_ylim(2, 20)
    ax2.grid(True, axis="y", linestyle="--", linewidth=0.5, alpha=0.6)
    ax2.legend(handles=[bp["boxes"][0]], labels=["Rango intercuartil (IQR)"], loc="upper left", frameon=True)

    fig.suptitle(
        "Evaluación experimental de rendimiento y escalabilidad en GCP BigQuery",
        fontsize=14,
        fontweight="bold",
        y=0.98,
    )
    plt.tight_layout()
    plt.savefig(output_path, dpi=300)
    plt.close()
    print(f"[OK] Panel combinado guardado en: {output_path}")


def main() -> None:
    docs_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "docs"))
    os.makedirs(docs_dir, exist_ok=True)

    chart1_file = os.path.join(docs_dir, "benchmark_fase1_throughput_curva.png")
    chart2_file = os.path.join(docs_dir, "benchmark_fase1_latencia_boxplot.png")
    panel_file = os.path.join(docs_dir, "benchmark_fase1_panel.png")

    plot_chart_1_throughput(chart1_file)
    plot_chart_2_boxplot(chart2_file)
    plot_combined_panel(panel_file)

    # Copiar también a la carpeta de artefactos de Antigravity si existe
    artifact_dir = "/Users/francolatour/.gemini/antigravity-ide/brain/3c3633a7-c8a7-4615-84ed-9118b17b6e5c"
    if os.path.exists(artifact_dir):
        for f in [chart1_file, chart2_file, panel_file]:
            dst = os.path.join(artifact_dir, os.path.basename(f))
            shutil.copy2(f, dst)
            print(f"[OK] Copiado a artefactos: {dst}")


if __name__ == "__main__":
    main()
