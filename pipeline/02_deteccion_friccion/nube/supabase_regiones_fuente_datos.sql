-- Supabase (Postgres): región de un cliente -> tabla de eventos en BigQuery. Creada el 2026-11-14.
-- Una fila por región; agregar una región = cargar una fila, sin redeploy. La lee ingesta/clientes.py con
-- el rol de solo lectura del módulo (modulo_friccion).

create table public.regiones_fuente_datos (
  gcp_region        text primary key,
  bq_project_id     text not null,
  bq_dataset        text not null,
  bq_tabla_eventos  text not null default 'eventos_usuario',
  bq_ubicacion      text not null,
  activo            boolean not null default true,
  created_at        timestamptz not null default now(),
  updated_at        timestamptz not null default now()
);
comment on table public.regiones_fuente_datos is
  'Región de un cliente -> tabla de eventos en BigQuery. Una fila por región; agregar una región = cargar una fila.';
comment on column public.regiones_fuente_datos.bq_ubicacion is
  'Ubicación del dataset (US, us-central1...): los jobs de BigQuery deben correr ahí.';

alter table public.regiones_fuente_datos enable row level security;
revoke all on public.regiones_fuente_datos from anon, authenticated;
grant select (gcp_region, bq_project_id, bq_dataset, bq_tabla_eventos, bq_ubicacion, activo)
  on public.regiones_fuente_datos to modulo_friccion;
create policy modulo_friccion_lectura on public.regiones_fuente_datos
  for select to modulo_friccion using (true);

insert into public.regiones_fuente_datos (gcp_region, bq_project_id, bq_dataset, bq_ubicacion) values
  ('US',          'pruebas-pfi', 'dw_analytics_us',          'US'),
  ('us-central1', 'pruebas-pfi', 'dw_analytics_us_central1', 'us-central1');
