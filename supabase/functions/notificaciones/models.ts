export interface WorkflowNotificacionesPayload {
  fecha_ejecucion: string;
  ids_clientes: string[];
}

export type EstadoCuenta = "activo" | "baja_solicitada" | "purgado";

export interface ClientePerfil {
  cliente_id: string;
  nombre_organizacion: string;
  estado_cuenta: EstadoCuenta | string;
}

export interface Destinatario {
  cliente_id: string;
  email: string;
  nombre: string;
}

export interface DiagnosticoFriccion {
  id: string;
  friccion_id: string;
  client_id: string;
  nombre_corto: string | null;
  titulo: string | null;
  severidad: "alta" | "media" | "baja" | string | null;
  impacto_resumen: string | null;
  fecha_ejecucion: string | null;
  created_at: string | null;
  updated_at: string | null;
  sesiones_perdidas: number | null;
  tasa_abandono: number | null;
}

export interface NotificacionEnviadaRegistro {
  cliente_id: string;
  friccion_id: string;
  diagnostico_id: string;
  diagnostico_updated_at: string;
  fecha_ejecucion: string;
  resend_email_id: string | null;
  destinatarios: string[];
  estado: "enviado" | "fallido";
}

export interface DetalleClienteResultado {
  cliente_id: string;
  estado: "notificado" | "omitido" | "fallido";
  motivo: string;
  diagnosticos_notificados: number;
  destinatarios: number;
  resend_id?: string;
  error?: string;
}

export interface RespuestaNotificaciones {
  estado: "COMPLETADO" | "COMPLETADO_CON_ERRORES";
  fecha_ejecucion: string;
  clientes_procesados: number;
  clientes_notificados: number;
  clientes_omitidos: number;
  clientes_fallidos: number;
  detalle: DetalleClienteResultado[];
}
