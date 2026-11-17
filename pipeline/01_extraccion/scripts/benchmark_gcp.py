#!/usr/bin/env python3
"""
Script de benchmark y pruebas de escalabilidad en Google Cloud Platform (GCP).

Evalúa el comportamiento del pipeline de extracción y normalización en BigQuery
bajo variables independientes:
1. Sensibilidad al Volumen: 10k, 100k, 1M y 5M eventos.
2. Sensibilidad a la Concurrencia: 1, 5, 10 y 20 clientes concurrentes.
3. Estrés Extremo y Capacidad Máxima: 10M y 20M eventos en total.
4. Verificación de Idempotencia.

Permite ejecutar fases individuales con múltiples repeticiones (por defecto 5),
calculando promedio, mediana y percentil 90 (P90) para reducir variabilidad.
"""

import argparse
import asyncio
import os
import random
import statistics
import sys
import time
import tracemalloc
from dataclasses import dataclass, field
from datetime import date
from typing import Any, List, Optional


# Asegurar que el root del proyecto esté en el PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.config import Settings, get_settings  # noqa: E402
from app.models import ClientSourceIntegration  # noqa: E402
from app.services.bigquery_service import BigQueryService  # noqa: E402
from app.services.extraction_pipeline import ExtractionPipeline  # noqa: E402
from app.services.supabase_service import SupabaseService  # noqa: E402

TARGET_DATE_STR = "2026-09-21"
DATE_SUFFIX = "20260921"
BENCHMARK_REGION = "us-central1"


@dataclass
class MetricStats:
    """Métricas estadísticas agregadas (promedio, mediana, P90, min, max)."""
    mean: float
    median: float
    p90: float
    min_val: float
    max_val: float


def compute_stats(values: List[float]) -> MetricStats:
    """Calcula promedio, mediana y percentil 90 a partir de una lista de valores."""
    if not values:
        return MetricStats(0.0, 0.0, 0.0, 0.0, 0.0)
    if len(values) == 1:
        val = round(values[0], 2)
        return MetricStats(val, val, val, val, val)

    m = round(float(statistics.mean(values)), 2)
    med = round(float(statistics.median(values)), 2)

    if len(values) >= 5:
        p90 = round(float(statistics.quantiles(values, n=10, method="inclusive")[8]), 2)
    else:
        sorted_v = sorted(values)
        idx = 0.9 * (len(values) - 1)
        lo = int(idx)
        hi = min(lo + 1, len(values) - 1)
        weight = idx - lo
        p90 = round(float(sorted_v[lo] * (1 - weight) + sorted_v[hi] * weight), 2)

    return MetricStats(
        mean=m,
        median=med,
        p90=p90,
        min_val=round(min(values), 2),
        max_val=round(max(values), 2),
    )


@dataclass
class BenchmarkScenarioResult:
    """Resultado individual de una corrida."""
    fase: str
    nombre_escenario: str
    clientes_concurrentes: int
    eventos_por_cliente: int
    total_eventos_lote: int
    duracion_total_segundos: float
    throughput_eventos_por_seg: float
    bytes_procesados_mb: float
    slot_millis_total: int
    filas_afectadas: int
    ram_pico_mb: float
    exitosos: int
    fallidos: int
    es_idempotente: bool


@dataclass
class AggregatedScenarioResult:
    """Resultado consolidado tras múltiples ejecuciones de un escenario."""
    fase: str
    nombre_escenario: str
    clientes_concurrentes: int
    eventos_por_cliente: int
    total_eventos_lote: int
    num_ejecuciones: int
    duracion_s: MetricStats
    throughput_ev_s: MetricStats
    ram_pico_mb: MetricStats
    bytes_procesados_mb: MetricStats
    filas_afectadas_promedio: float
    exitosos_promedio: float
    fallidos_total: int
    es_idempotente: bool
    individual_runs: List[BenchmarkScenarioResult] = field(default_factory=list)


class GCPBenchmarkRunner:
    """Orquestador de pruebas de rendimiento y escalabilidad sobre GCP BigQuery."""

    def __init__(self, settings: Settings, dry_run: bool = False):
        self.settings = settings
        self.dry_run = dry_run
        self.project_id = settings.PLATFORM_GCP_PROJECT_ID
        self._bq_client: Optional[Any] = None

    @property
    def bq_client(self) -> Any:
        if self._bq_client is None and not self.dry_run:
            from google.cloud import bigquery
            self._bq_client = bigquery.Client(project=self.project_id)
        return self._bq_client

    def setup_synthetic_data(self, target_datasets: Optional[List[str]] = None) -> None:
        """
        Crea las tablas origen sintéticas en BigQuery usando SQL generativo nativo:
        - analytics_bm_10k.events_YYYYMMDD (10.000 filas)
        - analytics_bm_100k.events_YYYYMMDD (100.000 filas)
        - analytics_bm_1m.events_YYYYMMDD (1.000.000 filas)
        - analytics_bm_5m.events_YYYYMMDD (5.000.000 filas)
        """
        all_datasets = {
            "analytics_bm_10k": 10000,
            "analytics_bm_100k": 100000,
            "analytics_bm_1m": 1000000,
            "analytics_bm_5m": 5000000,
        }

        datasets = {k: v for k, v in all_datasets.items() if not target_datasets or k in target_datasets}

        if self.dry_run:
            print(f"[DRY-RUN] Simulación de creación de datasets: {list(datasets.keys())}")
            return

        from google.cloud import bigquery

        print("================================================================================")
        print(" [SETUP] Aprovisionando tablas sintéticas GA4 en BigQuery (Proyecto: %s)" % self.project_id)
        print("================================================================================")

        for dataset_id, row_count in datasets.items():
            print(f"-> Creando dataset '{dataset_id}' en región '{BENCHMARK_REGION}'...")
            ds_ref = bigquery.DatasetReference(self.project_id, dataset_id)
            ds = bigquery.Dataset(ds_ref)
            ds.location = BENCHMARK_REGION
            self.bq_client.create_dataset(ds, exists_ok=True)

            table_id = f"{self.project_id}.{dataset_id}.events_{DATE_SUFFIX}"
            print(f"-> Generando {row_count:,} eventos sintéticos en `{table_id}`...")

            # Para más de 1M de filas, evitamos el límite de GENERATE_ARRAY con un CROSS JOIN batch
            if row_count <= 1000000:
                generator_from_clause = f"FROM UNNEST(GENERATE_ARRAY(1, {row_count})) AS idx"
            else:
                batches = (row_count + 999999) // 1000000
                generator_from_clause = f"""
                FROM (
                  SELECT ((batch - 1) * 1000000 + sub_idx) AS idx
                  FROM UNNEST(GENERATE_ARRAY(1, {batches})) AS batch
                  CROSS JOIN UNNEST(GENERATE_ARRAY(1, 1000000)) AS sub_idx
                  WHERE ((batch - 1) * 1000000 + sub_idx) <= {row_count}
                ) AS idx_gen
                """

            sql = f"""
            CREATE OR REPLACE TABLE `{table_id}`
            CLUSTER BY user_id, event_name
            AS
            SELECT
              '{DATE_SUFFIX}' AS event_date,
              1726915200000000 + (idx * 1000) AS event_timestamp,
              CASE MOD(idx, 4)
                WHEN 0 THEN 'page_view'
                WHEN 1 THEN 'scroll'
                WHEN 2 THEN 'click'
                ELSE 'view_item'
              END AS event_name,
              IF(MOD(idx, 5) = 0, NULL, CONCAT('usr_', CAST(MOD(idx, 20000) AS STRING))) AS user_id,
              CONCAT('pseudo_', CAST(MOD(idx, 40000) AS STRING)) AS user_pseudo_id,
              [
                STRUCT(
                  'page_location' AS key,
                  STRUCT(
                    CONCAT('https://eureka.app/seccion/', CAST(MOD(idx, 50) AS STRING)) AS string_value,
                    CAST(NULL AS INT64) AS int_value,
                    CAST(NULL AS FLOAT64) AS float_value,
                    CAST(NULL AS FLOAT64) AS double_value
                  ) AS value
                ),
                STRUCT(
                  'engagement_time_msec' AS key,
                  STRUCT(
                    CAST(NULL AS STRING) AS string_value,
                    CAST(1000 + MOD(idx, 5000) AS INT64) AS int_value,
                    CAST(NULL AS FLOAT64) AS float_value,
                    CAST(NULL AS FLOAT64) AS double_value
                  ) AS value
                ),
                STRUCT(
                  'percent_scrolled' AS key,
                  STRUCT(
                    CAST(NULL AS STRING) AS string_value,
                    CAST(MOD(idx, 100) AS INT64) AS int_value,
                    CAST(NULL AS FLOAT64) AS float_value,
                    CAST(NULL AS FLOAT64) AS double_value
                  ) AS value
                )
              ] AS event_params,
              STRUCT('Argentina' AS country, 'Buenos Aires' AS city) AS geo,
              STRUCT(
                'mobile' AS category,
                'Android' AS operating_system,
                STRUCT('Chrome' AS browser) AS web_info
              ) AS device,
              ARRAY<STRUCT<item_id STRING, item_name STRING>>[] AS items
            {generator_from_clause};
            """
            job = self.bq_client.query(sql, location=BENCHMARK_REGION)
            job.result()
            print(f"   [OK] Tabla `{table_id}` creada exitosamente en {job.ended - job.started}.")

        print("[SETUP] Aprovisionamiento completado con éxito.\n")

    def reset_destination_table(self) -> None:
        """
        Trunca la tabla de destino dw_analytics_us_central1.eventos_usuario
        para que cada repetición evalúe el costo real de extracción e inserción completa.
        """
        if self.dry_run:
            return

        dw_dataset = f"dw_analytics_{BENCHMARK_REGION.replace('-', '_')}"
        dw_table_id = f"{self.project_id}.{dw_dataset}.eventos_usuario"
        try:
            sql = f"TRUNCATE TABLE `{dw_table_id}`"
            job = self.bq_client.query(sql, location=BENCHMARK_REGION)
            job.result()
        except Exception:
            # Si aún no existe, el pipeline se encargará de crearla vía ensure_target_schema
            pass

    def teardown_benchmark_data(self) -> None:
        """Elimina los datasets de prueba y tablas generadas."""
        if self.dry_run:
            print("[DRY-RUN] Simulación de eliminación de datasets y tablas.")
            return

        datasets_to_drop = [
            "analytics_bm_10k",
            "analytics_bm_100k",
            "analytics_bm_1m",
            "analytics_bm_5m",
            f"dw_analytics_{BENCHMARK_REGION.replace('-', '_')}",
        ]
        print("================================================================================")
        print(" [TEARDOWN] Limpiando datasets de prueba en BigQuery...")
        print("================================================================================")
        for ds in datasets_to_drop:
            try:
                print(f"-> Eliminando dataset '{ds}'...")
                self.bq_client.delete_dataset(ds, delete_contents=True, not_found_ok=True)
                print(f"   [OK] Dataset '{ds}' eliminado.")
            except Exception as e:
                print(f"   [WARN] No se pudo eliminar dataset '{ds}': {e}")
        print("[TEARDOWN] Limpieza finalizada.\n")

    def build_synthetic_clients(self, count: int, scale: str) -> List[ClientSourceIntegration]:
        """Genera una lista de clientes sintéticos apuntando a la escala deseada."""
        clients = []
        for i in range(1, count + 1):
            clients.append(
                ClientSourceIntegration(
                    id=i,
                    cliente_id=f"cli_bm_{scale}_{i:02d}",
                    ga4_property_id=f"bm_{scale}",
                    client_gcp_project_id=self.project_id,
                    gcp_region=BENCHMARK_REGION,
                    activo=True,
                )
            )
        return clients

    async def run_scenario(
        self,
        fase: str,
        nombre: str,
        client_count: int,
        events_per_client: int,
        scale: str,
        is_reexecution: bool = False,
    ) -> BenchmarkScenarioResult:
        """Ejecuta una corrida individual de un escenario y captura métricas."""
        total_events = client_count * events_per_client
        clients = self.build_synthetic_clients(client_count, scale)

        tracemalloc.start()
        start_time = time.perf_counter()

        if self.dry_run:
            # En dry-run simulamos latencias realistas de BigQuery con ligera variación
            jitter = random.uniform(0.92, 1.08)
            base_delay = (0.05 + (events_per_client / 1_000_000) * 0.08) * jitter
            await asyncio.sleep(base_delay)
            duracion = time.perf_counter() - start_time
            current, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()

            filas_afectadas = 0 if is_reexecution else total_events
            bytes_mb = round((events_per_client * 0.0004) * client_count, 2)
            slot_ms = int(duracion * 1000 * min(client_count, 5))

            return BenchmarkScenarioResult(
                fase=fase,
                nombre_escenario=nombre,
                clientes_concurrentes=client_count,
                eventos_por_cliente=events_per_client,
                total_eventos_lote=total_events,
                duracion_total_segundos=round(duracion, 3),
                throughput_eventos_por_seg=round(total_events / max(duracion, 0.001), 1),
                bytes_procesados_mb=bytes_mb,
                slot_millis_total=slot_ms,
                filas_afectadas=filas_afectadas,
                ram_pico_mb=round(peak / (1024 * 1024), 2),
                exitosos=client_count,
                fallidos=0,
                es_idempotente=filas_afectadas == 0 if is_reexecution else True,
            )

        # En ejecución real contra GCP
        self.settings.MAX_CONCURRENT_CLIENTS = max(self.settings.MAX_CONCURRENT_CLIENTS, client_count)
        bq_service = BigQueryService(self.settings, client=self.bq_client)
        # Pre-cargar tabla de destino verificada para evitar DDL concurrentes en lote
        bq_service._verified_tables.add(bq_service.get_table_full_id(BENCHMARK_REGION))

        class BenchmarkMockSupabase(SupabaseService):
            def __init__(self, s: Settings, clients_list: List[ClientSourceIntegration]):
                super().__init__(s)
                self.clients_list = clients_list

            async def get_active_clients(self, cliente_id: Optional[str] = None):
                if cliente_id:
                    return [c for c in self.clients_list if c.cliente_id == cliente_id]
                return self.clients_list

            async def update_sync_success(self, client_db_id: Any, target_date: date):
                pass  # No-op en benchmark

        mock_supabase = BenchmarkMockSupabase(self.settings, clients)
        pipeline = ExtractionPipeline(self.settings, bq_service, mock_supabase)

        response = await pipeline.run_batch(target_date_str=TARGET_DATE_STR)
        duracion = time.perf_counter() - start_time

        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        total_bytes = sum((r.bytes_procesados or 0) for r in response.exitosos)
        total_rows = sum(r.filas_afectadas for r in response.exitosos)
        bytes_mb = round(total_bytes / (1024 * 1024), 2)

        return BenchmarkScenarioResult(
            fase=fase,
            nombre_escenario=nombre,
            clientes_concurrentes=client_count,
            eventos_por_cliente=events_per_client,
            total_eventos_lote=total_events,
            duracion_total_segundos=round(duracion, 3),
            throughput_eventos_por_seg=round(total_events / max(duracion, 0.001), 1),
            bytes_procesados_mb=bytes_mb,
            slot_millis_total=0,
            filas_afectadas=total_rows,
            ram_pico_mb=round(peak / (1024 * 1024), 2),
            exitosos=response.total_exitosos,
            fallidos=response.total_fallidos,
            es_idempotente=(total_rows == 0) if is_reexecution else True,
        )

    async def run_scenario_with_repetitions(
        self,
        fase: str,
        nombre: str,
        client_count: int,
        events_per_client: int,
        scale: str,
        repetitions: int = 5,
        is_reexecution: bool = False,
    ) -> AggregatedScenarioResult:
        """Ejecuta N repeticiones de un escenario y calcula promedio, mediana y P90."""
        total_events = client_count * events_per_client
        print("-" * 80)
        print(
            f" [ESCENARIO] {nombre} | Clientes: {client_count} | "
            f"Eventos/cli: {events_per_client:,} (Total: {total_events:,}) | Repeticiones: {repetitions}"
        )
        print("-" * 80)

        runs: List[BenchmarkScenarioResult] = []

        for rep in range(1, repetitions + 1):
            if not is_reexecution:
                self.reset_destination_table()

            result = await self.run_scenario(
                fase=fase,
                nombre=f"{nombre}_r{rep}",
                client_count=client_count,
                events_per_client=events_per_client,
                scale=scale,
                is_reexecution=is_reexecution,
            )
            runs.append(result)
            print(
                f"   [Corrida {rep}/{repetitions}] Duración: {result.duracion_total_segundos:6.2f}s | "
                f"Throughput: {result.throughput_eventos_por_seg:10,.0f} ev/s | "
                f"RAM Pico: {result.ram_pico_mb:5.2f} MB | Filas: {result.filas_afectadas:,}"
            )

        duraciones = [r.duracion_total_segundos for r in runs]
        throughputs = [r.throughput_eventos_por_seg for r in runs]
        rams = [r.ram_pico_mb for r in runs]
        bytes_list = [r.bytes_procesados_mb for r in runs]
        filas = [r.filas_afectadas for r in runs]

        agg_dur = compute_stats(duraciones)
        agg_tp = compute_stats(throughputs)
        agg_ram = compute_stats(rams)
        agg_bytes = compute_stats(bytes_list)

        print(
            f"   >> RESUMEN {nombre} (N={repetitions}): "
            f"Duración: Prom={agg_dur.mean:.2f}s, Med={agg_dur.median:.2f}s, P90={agg_dur.p90:.2f}s | "
            f"Throughput: Prom={agg_tp.mean:,.0f} ev/s, Med={agg_tp.median:,.0f} ev/s, P90={agg_tp.p90:,.0f} ev/s"
        )

        return AggregatedScenarioResult(
            fase=fase,
            nombre_escenario=nombre,
            clientes_concurrentes=client_count,
            eventos_por_cliente=events_per_client,
            total_eventos_lote=total_events,
            num_ejecuciones=repetitions,
            duracion_s=agg_dur,
            throughput_ev_s=agg_tp,
            ram_pico_mb=agg_ram,
            bytes_procesados_mb=agg_bytes,
            filas_afectadas_promedio=round(statistics.mean(filas), 0),
            exitosos_promedio=round(statistics.mean([r.exitosos for r in runs]), 1),
            fallidos_total=sum(r.fallidos for r in runs),
            es_idempotente=all(r.es_idempotente for r in runs),
            individual_runs=runs,
        )

    async def run_phase_1(self, repetitions: int = 5) -> List[AggregatedScenarioResult]:
        """FASE 1: Sensibilidad al Volumen de Eventos (1 Cliente, 10k, 100k, 1M, 5M)."""
        print("\n================================================================================")
        print(f" FASE 1: Sensibilidad al Volumen de Eventos (1 Cliente, {repetitions} ejecuciones)")
        print("================================================================================")
        scenarios = [
            ("1cli-10k", 10000, "10k"),
            ("1cli-100k", 100000, "100k"),
            ("1cli-1M", 1000000, "1m"),
            ("1cli-5M", 5000000, "5m"),
        ]
        results = []
        for nombre, vol, scale in scenarios:
            res = await self.run_scenario_with_repetitions(
                fase="Fase 1 (Volumen)",
                nombre=nombre,
                client_count=1,
                events_per_client=vol,
                scale=scale,
                repetitions=repetitions,
            )
            results.append(res)
        return results

    async def run_phase_2(self, repetitions: int = 5) -> List[AggregatedScenarioResult]:
        """FASE 2: Sensibilidad a la Concurrencia (Volumen Fijo: 100k por cliente)."""
        print("\n================================================================================")
        print(f" FASE 2: Sensibilidad a la Concurrencia (100k por cliente, {repetitions} ejecuciones)")
        print("================================================================================")
        scenarios = [
            ("1cli-100k", 1, 100000, "100k"),
            ("5cli-100k", 5, 100000, "100k"),
            ("10cli-100k", 10, 100000, "100k"),
            ("20cli-100k", 20, 100000, "100k"),
            ("50cli-100k", 50, 100000, "100k"),
        ]
        results = []
        for nombre, clients, vol, scale in scenarios:
            res = await self.run_scenario_with_repetitions(
                fase="Fase 2 (Concurrencia)",
                nombre=nombre,
                client_count=clients,
                events_per_client=vol,
                scale=scale,
                repetitions=repetitions,
            )
            results.append(res)
        return results

    async def run_phase_3(self, repetitions: int = 5) -> List[AggregatedScenarioResult]:
        """FASE 3: Estrés Extremo y Capacidad Máxima (1M por cliente)."""
        print("\n================================================================================")
        print(f" FASE 3: Estrés Extremo y Capacidad Máxima (1M por cliente, {repetitions} ejecuciones)")
        print("================================================================================")
        scenarios = [
            ("10cli-1M (10M total)", 10, 1000000, "1m"),
            ("20cli-1M (20M total)", 20, 1000000, "1m"),
        ]
        results = []
        for nombre, clients, vol, scale in scenarios:
            res = await self.run_scenario_with_repetitions(
                fase="Fase 3 (Estrés)",
                nombre=nombre,
                client_count=clients,
                events_per_client=vol,
                scale=scale,
                repetitions=repetitions,
            )
            results.append(res)
        return results

    async def run_phase_4(self, repetitions: int = 5) -> List[AggregatedScenarioResult]:
        """FASE 4: Verificación de Idempotencia en Producción."""
        print("\n================================================================================")
        print(f" FASE 4: Verificación de Idempotencia (5 clientes x 100k, {repetitions} ejecuciones)")
        print("================================================================================")
        # Pre-cargar los datos una vez para que la re-ejecución evalúe la deduplicación
        self.reset_destination_table()
        print("-> Precargando 5 clientes x 100k para prueba de idempotencia...")
        await self.run_scenario(
            fase="Fase 4 (Idempotencia)",
            nombre="Carga Inicial",
            client_count=5,
            events_per_client=100000,
            scale="100k",
            is_reexecution=False,
        )

        res = await self.run_scenario_with_repetitions(
            fase="Fase 4 (Idempotencia)",
            nombre="Re-ejecución (Idempotente)",
            client_count=5,
            events_per_client=100000,
            scale="100k",
            repetitions=repetitions,
            is_reexecution=True,
        )
        return [res]


def fmt_int(n: float | int) -> str:
    """Formatea enteros con punto como separador de miles (ej: 10.000)."""
    return f"{int(round(n)):,}".replace(",", ".")


def fmt_float(val: float, decimals: int = 2) -> str:
    """Formatea flotantes con punto para miles y coma para decimales (ej: 4,56)."""
    parts = f"{val:,.{decimals}f}".split(".")
    integer_part = parts[0].replace(",", ".")
    decimal_part = parts[1]
    return f"{integer_part},{decimal_part}"


def format_results_markdown_table(aggregated_results: List[AggregatedScenarioResult]) -> str:
    """Genera tablas en Markdown con números formateados (punto para miles, coma para decimales)."""
    has_multiple_clients = any(agg.clientes_concurrentes > 1 for agg in aggregated_results)

    if has_multiple_clients:
        summary_header = (
            "| Clientes | Eventos/Cli | Total Eventos | "
            "Duración Prom (s) | Duración Mín (s) | Duración Máx (s) | "
            "Throughput Prom (ev/s) | RAM Pico P90 (MB) |"
        )
        summary_sep = (
            "| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |"
        )
    else:
        summary_header = (
            "| Eventos/Cli | Total Eventos | "
            "Duración Prom (s) | Duración Mín (s) | Duración Máx (s) | "
            "Throughput Prom (ev/s) | RAM Pico P90 (MB) |"
        )
        summary_sep = (
            "| :---: | :---: | :---: | :---: | :---: | :---: | :---: |"
        )

    lines = [
        "## Reporte Cuantitativo de Escalabilidad y Rendimiento (BigQuery + Cloud Run)\n",
        "### 1. Resumen Estadístico Consolidado (Promedio, Mínimo y Máximo)\n",
        summary_header,
        summary_sep,
    ]

    for agg in aggregated_results:
        client_col = f"| {agg.clientes_concurrentes} " if has_multiple_clients else "|"
        row = (
            f"{client_col}| {fmt_int(agg.eventos_por_cliente)} | {fmt_int(agg.total_eventos_lote)} | "
            f"{fmt_float(agg.duracion_s.mean, 2)} s | {fmt_float(agg.duracion_s.min_val, 2)} s | "
            f"{fmt_float(agg.duracion_s.max_val, 2)} s | "
            f"{fmt_int(agg.throughput_ev_s.mean)} ev/s | "
            f"{fmt_float(agg.ram_pico_mb.p90, 2)} MB |"
        )
        lines.append(row)

    # Tabla de detalle por ejecución
    lines.append("\n### 2. Detalle de Ejecuciones Individuales\n")
    detail_header = (
        "| Escenario | Ejecución | Duración (s) | Throughput (ev/s) | "
        "RAM Pico (MB) | Datos Leídos (MB) | Filas Afectadas | Estado |"
    )
    detail_sep = "| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |"
    lines.append(detail_header)
    lines.append(detail_sep)

    for agg in aggregated_results:
        for idx, run in enumerate(agg.individual_runs, start=1):
            st = "OK" if run.fallidos == 0 else "Error"
            lines.append(
                f"| {agg.nombre_escenario} | #{idx} | {fmt_float(run.duracion_total_segundos, 2)} s | "
                f"{fmt_int(run.throughput_eventos_por_seg)} ev/s | "
                f"{fmt_float(run.ram_pico_mb, 2)} MB | "
                f"{fmt_float(run.bytes_procesados_mb, 1)} MB | "
                f"{fmt_int(run.filas_afectadas)} | {st} |"
            )

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark de Escalabilidad y Rendimiento en GCP BigQuery")
    parser.add_argument(
        "--action",
        choices=["setup", "run", "teardown", "all"],
        default="run",
        help="Acción a ejecutar: setup (crear datos), run (ejecutar tests), teardown (limpiar), all (todo)",
    )
    parser.add_argument(
        "--phase",
        choices=["1", "2", "3", "4", "all"],
        default="1",
        help="Fase específica a ejecutar: 1 (Volumen 10k-5M), 2 (Concurrencia), 3 (Estrés), 4 (Idempotencia), all",
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=5,
        help="Número de repeticiones por escenario para calcular Promedio, Mediana y P90 (por defecto: 5)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Ejecutar en modo simulación local sin conectarse a GCP ni consumir cuotas",
    )
    parser.add_argument(
        "--output-file",
        default="benchmark_results_gcp.md",
        help="Ruta del archivo Markdown donde guardar los resultados",
    )

    args = parser.parse_args()
    settings = get_settings()
    runner = GCPBenchmarkRunner(settings, dry_run=args.dry_run)

    # Setup de tablas sintéticas
    if args.action in ("setup", "all"):
        runner.setup_synthetic_data()

    # Ejecución de benchmarks
    if args.action in ("run", "all"):
        aggregated_results: List[AggregatedScenarioResult] = []

        async def _run_benchmarks():
            if args.phase in ("1", "all"):
                res1 = await runner.run_phase_1(repetitions=args.runs)
                aggregated_results.extend(res1)

            if args.phase in ("2", "all"):
                res2 = await runner.run_phase_2(repetitions=args.runs)
                aggregated_results.extend(res2)

            if args.phase in ("3", "all"):
                res3 = await runner.run_phase_3(repetitions=args.runs)
                aggregated_results.extend(res3)

            if args.phase in ("4", "all"):
                res4 = await runner.run_phase_4(repetitions=args.runs)
                aggregated_results.extend(res4)

        asyncio.run(_run_benchmarks())

        md_table = format_results_markdown_table(aggregated_results)

        print("\n" + "=" * 80)
        print(" RESULTADOS FINALES DEL BENCHMARK")
        print("=" * 80)
        print(md_table)

        with open(args.output_file, "w", encoding="utf-8") as f:
            f.write(md_table + "\n")
        print(f"\n[OK] Resultados guardados en: {args.output_file}")

    # Limpieza
    if args.action in ("teardown", "all"):
        runner.teardown_benchmark_data()


if __name__ == "__main__":
    main()
