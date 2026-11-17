#!/usr/bin/env python3
"""
Generador de gráfico de alto impacto para la Fase 2 del Benchmark en GCP BigQuery.
Muestra la evolución del tiempo de ejecución en función de la cantidad de clientes
y las tandas del semáforo de concurrencia (1, 5, 10, 20 y 50 clientes).

Reglas de diseño aplicadas:
- Mayúscula solo en la primera letra de las etiquetas de ejes.
- Sin punteros / flechas.
- Sin badge o cartel adicional de conclusiones técnicas (omitido punto 4 a pedido del usuario).
- Separadores estándar en español: punto para miles y coma para decimales.
- Ajuste lineal (R^2) y anotaciones de tandas en cada punto.
"""

import os
import shutil
from typing import Dict, List
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
import numpy as np


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
    "legend.fontsize": 10.5,
    "figure.titlesize": 14,
    "grid.alpha": 0.4,
    "grid.linestyle": "--",
})

# Datos empíricos medidos en GCP BigQuery (Fase 2: 100k eventos por cliente, N=5)
CLIENTS = [1, 5, 10, 20, 50]
CLIENT_LABELS = ["1", "5", "10", "20", "50"]

RUNS_DURATION: Dict[int, List[float]] = {
    1: [3.98, 3.31, 3.55, 3.22, 2.96],
    5: [10.55, 8.20, 10.43, 7.38, 8.10],
    10: [21.01, 18.64, 12.27, 11.99, 14.86],
    20: [31.05, 30.23, 32.10, 30.13, 31.20],
    50: [78.32, 71.20, 73.53, 57.36, 68.75],
}

# Estadísticos agregados (Duración promedio por nivel de clientes)
MEANS = [float(np.mean(RUNS_DURATION[c])) for c in CLIENTS]


def plot_phase2_linear_scalability(output_path: str) -> None:
    """Genera el gráfico de escalabilidad lineal de la Fase 2."""
    fig, ax = plt.subplots(figsize=(9, 6), dpi=300)

    # 1. Regresión lineal (Ajuste por mínimos cuadrados)
    x_arr = np.array(CLIENTS, dtype=float)
    y_arr = np.array(MEANS, dtype=float)
    slope, intercept = np.polyfit(x_arr, y_arr, 1)

    # Cálculo del coeficiente de determinación R^2
    y_pred = slope * x_arr + intercept
    ss_res = float(np.sum((y_arr - y_pred) ** 2))
    ss_tot = float(np.sum((y_arr - np.mean(y_arr)) ** 2))
    r_squared = 1 - (ss_res / ss_tot)
    r2_str = f"{r_squared:.3f}".replace(".", ",")

    x_line = np.linspace(0, 52, 100)
    y_line = slope * x_line + intercept

    # Línea de ajuste lineal
    ax.plot(
        x_line,
        y_line,
        color="#d9534f",
        linestyle="--",
        linewidth=1.8,
        label=f"Ajuste lineal ($R^2 = {r2_str}$)",
        zorder=2,
    )

    # 2. Puntos empíricos de duración promedio
    ax.plot(
        CLIENTS,
        MEANS,
        color="#1a73e8",
        linewidth=2.0,
        marker="o",
        markersize=8,
        markerfacecolor="#ffffff",
        markeredgewidth=2.2,
        markeredgecolor="#1a73e8",
        label="Duración promedio",
        zorder=4,
    )

    # 3. Anotaciones de valor numérico sobre cada punto (sin tandas ni punteros)
    point_labels = [
        "3,40 s",
        "8,93 s",
        "15,75 s",
        "30,94 s",
        "69,83 s",
    ]

    offsets = [
        (0, 14),   # 1 cli
        (0, 14),   # 5 cli
        (0, 14),   # 10 cli
        (0, 14),   # 20 cli
        (-14, 14),  # 50 cli
    ]

    for c, m, text, (off_x, off_y) in zip(CLIENTS, MEANS, point_labels, offsets):
        ax.annotate(
            text,
            xy=(c, m),
            xytext=(off_x, off_y),
            textcoords="offset points",
            ha="center",
            fontsize=9.5,
            fontweight="semibold",
            color="#202124",
            bbox=dict(
                boxstyle="round,pad=0.25",
                fc="#ffffff",
                ec="#1a73e8",
                lw=0.8,
                alpha=0.95,
            ),
            zorder=5,
        )

    # Configuración de ejes limpia (sin tandas)
    ax.set_xticks(CLIENTS)
    ax.set_xticklabels(["1", "5", "10", "20", "50"], fontweight="semibold")

    ax.yaxis.set_major_formatter(FuncFormatter(fmt_spanish_decimals))
    ax.set_xlim(-1, 54)
    ax.set_ylim(0, 85)

    # Etiquetas de ejes en formato tipo oración
    ax.set_xlabel("Cantidad de clientes concurrentes", fontweight="bold")
    ax.set_ylabel("Duración total de extracción e inserción [segundos]", fontweight="bold")
    ax.set_title("Evolución del tiempo de ejecución según la cantidad de clientes", fontweight="bold", pad=15)

    ax.grid(True, linestyle="--", linewidth=0.6, alpha=0.5)
    ax.legend(loc="upper left", frameon=True, facecolor="#ffffff", edgecolor="#cccccc")

    plt.tight_layout()
    plt.savefig(output_path, dpi=300)
    plt.close()
    print(f"[OK] Gráfico guardado en: {output_path}")


def main() -> None:
    docs_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "docs"))
    os.makedirs(docs_dir, exist_ok=True)

    chart_file = os.path.join(docs_dir, "benchmark_fase2_escalabilidad_lineal.png")
    plot_phase2_linear_scalability(chart_file)

    artifact_dir = "/Users/francolatour/.gemini/antigravity-ide/brain/3c3633a7-c8a7-4615-84ed-9118b17b6e5c"
    if os.path.exists(artifact_dir):
        dst = os.path.join(artifact_dir, os.path.basename(chart_file))
        shutil.copy2(chart_file, dst)
        print(f"[OK] Copiado a artefactos: {dst}")


if __name__ == "__main__":
    main()
