"""Supabase: cliente -> región -> dónde están sus eventos en BigQuery.

Lee dos tablas con el usuario de solo lectura del módulo (modulo_friccion):
- clientes_integracion_fuente: región (gcp_region) y si el cliente está activo.
- regiones_fuente_datos: por región, proyecto / dataset / tabla de eventos y ubicación del dataset.
"""
import re
from dataclasses import dataclass

import psycopg2

# Los nombres de proyecto, dataset y tabla van dentro del SQL de BigQuery (no se pueden pasar como
# parámetro), así que se validan contra el formato que admite BigQuery antes de usarlos.
_PROYECTO = re.compile(r"^[a-z][a-z0-9-]{4,28}[a-z0-9]$")
_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,1023}$")


class ClienteNoDisponible(Exception):
    """El cliente no existe, está inactivo o su región no tiene una fuente de eventos configurada."""


@dataclass(frozen=True)
class FuenteEventos:
    cliente_id: str
    gcp_region: str
    bq_project_id: str
    bq_dataset: str
    bq_tabla_eventos: str
    bq_ubicacion: str   # los jobs de BigQuery tienen que correr en la ubicación del dataset

    @property
    def tabla(self) -> str:
        return f"`{self.bq_project_id}.{self.bq_dataset}.{self.bq_tabla_eventos}`"


_SQL = """
select c.cliente_id::text, c.activo, c.gcp_region,
       r.bq_project_id, r.bq_dataset, r.bq_tabla_eventos, r.bq_ubicacion, r.activo
from public.clientes_integracion_fuente c
left join public.regiones_fuente_datos r on r.gcp_region = c.gcp_region
where c.cliente_id::text = %s
"""


def buscar_fuente(cliente_id: str, supabase_db_url: str) -> FuenteEventos:
    """Fuente de eventos de un cliente. Falla con ClienteNoDisponible si no se lo puede procesar."""
    con = psycopg2.connect(supabase_db_url, connect_timeout=15,
                           options="-c default_transaction_read_only=on -c statement_timeout=15000")
    try:
        with con.cursor() as cur:
            cur.execute(_SQL, (cliente_id,))
            fila = cur.fetchone()
    finally:
        con.close()
    if fila is None:
        raise ClienteNoDisponible(f"Cliente {cliente_id} no existe en clientes_integracion_fuente")
    cid, activo, region, proyecto, dataset, tabla, ubicacion, region_activa = fila
    if not activo:
        raise ClienteNoDisponible(f"Cliente {cid} está inactivo")
    if proyecto is None:
        raise ClienteNoDisponible(f"La región {region!r} del cliente {cid} no tiene fuente en regiones_fuente_datos")
    if not region_activa:
        raise ClienteNoDisponible(f"La región {region!r} del cliente {cid} está inactiva")
    if not (_PROYECTO.match(proyecto) and _IDENT.match(dataset) and _IDENT.match(tabla)):
        raise ClienteNoDisponible(f"Fuente mal configurada para la región {region!r}: {proyecto}.{dataset}.{tabla}")
    return FuenteEventos(cid, region, proyecto, dataset, tabla, ubicacion)
