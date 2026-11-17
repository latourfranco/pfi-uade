-- Resultados del módulo de detección de fricción (BigQuery, proyecto pruebas-pfi).
-- Un solo conjunto de datos para todas las regiones: los eventos se leen de la región del cliente
-- (dw_analytics_<region>) y los resultados se centralizan acá.
-- Acordado con el usuario el 2026-11-14: solo lo que usa el motor, sin estructuras anidadas. Única lista:
-- patrones.secuencia, un array ordenado de pasos (pedido del usuario, 2026-11-15).

CREATE SCHEMA IF NOT EXISTS `pruebas-pfi.friccion_resultados`
OPTIONS (location = 'US',
         description = 'Resultados del módulo de detección de fricción: patrones y su sesión representativa');

-- Una fila por patrón. La detección diaria hace MERGE por id_patron: si existe se actualizan sus cifras,
-- id_modelo y ultima_deteccion; si no, se inserta. El orden de prioridad es sesiones_perdidas (impacto: cuánta
-- gente no llegó por el patrón). Decidido con el usuario el 2026-11-15: el orden por diferencia con margen ponía
-- arriba caídas grandes en grupos de 50 personas y dejaba abajo patrones que pierden cientos de sesiones.
CREATE TABLE IF NOT EXISTS `pruebas-pfi.friccion_resultados.patrones` (
  id_patron           STRING  NOT NULL OPTIONS (description = 'Hash de id_cliente + objetivo + secuencia. Clave del MERGE y de Supabase (fricciones)'),
  id_cliente          STRING  NOT NULL,
  objetivo            STRING  NOT NULL OPTIONS (description = 'Escalón del embudo que le faltaba a esa gente (ej. add_to_cart)'),
  secuencia           ARRAY<STRING>     OPTIONS (description = 'Pasos del patrón en orden (cada uno "evento página", en el vocabulario de páginas del modelo). El último es el paso de la fricción (sin columna aparte: sería redundante, 2026-11-15)'),
  sesiones            INT64   NOT NULL,
  usuarios            INT64   NOT NULL,
  llegada_grupo       FLOAT64 NOT NULL OPTIONS (description = 'Proporción del grupo que llega al objetivo'),
  llegada_referencia  FLOAT64 NOT NULL OPTIONS (description = 'Proporción del resto que pasó por el mismo contexto que llega al objetivo'),
  sesiones_perdidas   FLOAT64 NOT NULL OPTIONS (description = 'Impacto: sesiones × (llegada_referencia − llegada_grupo). Criterio de orden'),
  id_modelo           STRING  NOT NULL OPTIONS (description = 'Entrenamiento con el que se detectó por última vez'),
  primera_deteccion   DATE    NOT NULL,
  ultima_deteccion    DATE    NOT NULL
)
CLUSTER BY id_cliente, id_patron
OPTIONS (description = 'Patrones de fricción detectados, uno por fila');

-- Una fila por evento de la sesión representativa de cada patrón. Se escribe solo cuando el patrón aparece
-- por primera vez y no se reemplaza (el módulo de exploración la reproduce una sola vez).
-- Los pasos son los que ve el motor: sin eventos descartados por el preprocesamiento y con el scroll plegado.
-- Sin timestamp a propósito: el orden lo da `orden`. La hora de inicio de la sesión queda en id_sesion.
CREATE TABLE IF NOT EXISTS `pruebas-pfi.friccion_resultados.sesion_representativa` (
  id_patron           STRING    NOT NULL,
  id_sesion           STRING    NOT NULL OPTIONS (description = '<id_usuario>_<id_sesion>: id_sesion es el ga_session_id de GA4 (o el inicio en segundos si se calculó con el corte de 30 min); estable entre corridas'),
  orden               INT64     NOT NULL OPTIONS (description = 'Número de paso; clave = id_patron + orden'),
  nombre_evento       STRING    NOT NULL,
  ruta                STRING    NOT NULL OPTIONS (description = 'URL real (incluye el término de búsqueda)'),
  items               STRING             OPTIONS (description = 'Producto a abrir o agregar al carrito'),
  scroll              BOOL      NOT NULL OPTIONS (description = 'Llegó al fondo de la página (scroll de GA4 plegado en el paso, §3.6)'),
  en_patron           BOOL      NOT NULL,
  es_paso_friccion    BOOL      NOT NULL,
  tipo_dispositivo    STRING,
  navegador           STRING,
  sistema_operativo   STRING
)
CLUSTER BY id_patron
OPTIONS (description = 'Sesión representativa de cada patrón, un evento por fila, para reproducirla con Playwright');

-- Una fila por entrenamiento (2026-11-15). La corrida diaria carga el modelo más reciente del cliente
-- (mayor `entrenado`); patrones.id_modelo apunta acá. Reentrenar cuando la AUC del día cae debajo de
-- auc_ic95_inf (PLAN §14). El modelo en sí (red, vocabulario, reglas de rutas, eventos clave) está en `artefacto`.
CREATE TABLE IF NOT EXISTS `pruebas-pfi.friccion_resultados.modelos` (
  id_modelo      STRING    NOT NULL OPTIONS (description = '<id_cliente>_<fecha y hora del entrenamiento UTC, AAAAMMDDTHHMMSS>'),
  id_cliente     STRING    NOT NULL,
  entrenado      TIMESTAMP NOT NULL,
  datos_desde    TIMESTAMP NOT NULL OPTIONS (description = 'Inicio de la primera sesión de la ventana de entrenamiento'),
  datos_hasta    TIMESTAMP NOT NULL OPTIONS (description = 'Inicio de la última sesión de la ventana'),
  sesiones       INT64     NOT NULL,
  objetivo       STRING    NOT NULL OPTIONS (description = 'Evento de conversión elegido por el LLM'),
  eventos_clave  ARRAY<STRING>      OPTIONS (description = 'Hitos elegidos por el LLM, objetivo incluido; el orden lo aprende el motor'),
  auc            FLOAT64   NOT NULL OPTIONS (description = 'AUC de predecir la llegada al objetivo en la validación del entrenamiento'),
  auc_ic95_inf   FLOAT64   NOT NULL OPTIONS (description = 'Límite inferior del IC95 de la AUC: debajo de esto se reentrena'),
  artefacto      STRING    NOT NULL OPTIONS (description = 'Ruta del modelo guardado: carpeta local o gs://'),
  nombres_hitos  ARRAY<STRING>      OPTIONS (description = 'Nombre legible de cada hito para el negocio, elegido por el LLM, en el mismo orden que eventos_clave. Vacío si los eventos clave se pasaron a mano')   -- agregada el 2026-11-17 (ALTER TABLE ADD COLUMN: queda al final)
)
CLUSTER BY id_cliente
OPTIONS (description = 'Registro de modelos entrenados, uno por fila');
