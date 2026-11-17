import { describe, it, expect, vi, beforeEach } from "vitest";

const { mockFrom, mockGetSignedCaptureUrl } = vi.hoisted(() => ({
  mockFrom: vi.fn(),
  mockGetSignedCaptureUrl: vi.fn(),
}));

vi.mock("@/lib/supabase/admin", () => ({
  getSupabaseAdmin: () => ({
    from: mockFrom,
  }),
}));

vi.mock("@/services/gcp/storage.service", () => ({
  getSignedCaptureUrl: mockGetSignedCaptureUrl,
}));

import { FriccionRepository } from "../friccion.repository";

function createDetailQueryMock(result: { data: unknown; error: unknown }) {
  const maybeSingle = vi.fn().mockResolvedValue(result);
  const eq = vi.fn().mockReturnValue({ maybeSingle });
  const select = vi.fn().mockReturnValue({ eq });
  return { select };
}

function createRadarQueryMock(result: { data: unknown; error: unknown }) {
  const order = vi.fn().mockResolvedValue(result);
  const eq = vi.fn().mockReturnValue({ order });
  const select = vi.fn().mockReturnValue({ eq });
  return { select };
}

describe("FriccionRepository", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockGetSignedCaptureUrl.mockResolvedValue("https://signed.example.com/capture.webp");
  });

  describe("getDetailById", () => {
    it("retorna el detalle completo mapeado desde Supabase sin datos hardcoded", async () => {
      const dbRow = {
        id: "pat-101",
        client_id: "client-1",
        nombre: "Modal de Login en Checkout",
        evento_clave: "begin_checkout",
        evento_clave_nombre: "Inicio de checkout",
        tasa_abandono: 32.72,
        llegada_grupo: 0.6728,
        llegada_referencia: 0.9765,
        sesiones: 1156,
        usuarios: 890,
        sesiones_perdidas: 378.75,
        total_sesiones_modelo: 10000,
        secuencia: ["page_view", "begin_checkout"],
        secuencia_nombres: ["Vista de página", "Inicio de checkout"],
        tipo_dispositivo: "mobile",
        navegador: "Safari Mobile",
        sistema_operativo: "iOS",
        ultima_deteccion: "2026-11-10",
        distribucion_dispositivos: [{ label: "mobile", percentage: 75 }],
        distribucion_navegadores: [{ label: "Safari", percentage: 60 }],
        distribucion_sistemas: [{ label: "iOS", percentage: 65 }],
        distribucion_paises: [{ label: "Argentina", percentage: 80 }],
        fricciones_diagnosticos: {
          id: "diag-1",
          friccion_id: "pat-101",
          nombre_corto: "Bloqueo login checkout",
          titulo: "Redirección forzada al login en checkout",
          subtitulo: "Los usuarios móviles pierden su carrito al intentar pagar.",
          severidad: "alta",
          impacto_resumen: "-30.4 pp en avance · 379 sesiones perdidas",
          diagnostico_corto: "Resumen corto",
          diagnostico_parrafos: ["Párrafo 1", "Párrafo 2", "Párrafo 3"],
          evidencias: ["Evidencia A"],
          recomendaciones: ["Permitir guest checkout"],
          audiencia_resumen: "Usuarios móviles recurrentes",
          modelo_llm: "gemini-2.5-pro",
          fecha_ejecucion: "2026-11-11",
        },
        friccion_recorrido_pasos: [
          {
            id: "step-2",
            friccion_id: "pat-101",
            numero_paso: 2,
            nombre_evento: "begin_checkout",
            evento_nombre: "Inicio de checkout",
            ruta_pagina: "/checkout?step=1",
            items: "Hoodie",
            scroll: false,
            en_patron: true,
            friccion_detectada: true,
            notas_contexto: null,
            captura_gcs_url: "gs://pruebas-pfi-evidencias/step2.webp",
            friccion_recorrido_notas: [
              {
                id: "note-2",
                friccion_id: "pat-101",
                paso_id: "step-2",
                numero_paso: 2,
                nota_titulo: "Botón bloqueado",
                nota_descripcion: "Exige login obligatorio.",
                insignias: ["Bloqueo", "Checkout"],
                estado: "error",
                coincidencia_cluster: "crítica",
              },
            ],
          },
          {
            id: "step-1",
            friccion_id: "pat-101",
            numero_paso: 1,
            nombre_evento: "page_view",
            evento_nombre: "Vista de página",
            ruta_pagina: "/catalogo",
            items: null,
            scroll: true,
            en_patron: false,
            friccion_detectada: false,
            notas_contexto: ["Contexto previo al checkout"],
            captura_gcs_url: null,
            friccion_recorrido_notas: [],
          },
        ],
      };

      mockFrom.mockReturnValueOnce(createDetailQueryMock({ data: dbRow, error: null }));

      const detail = await FriccionRepository.getDetailById("pat-101");

      expect(detail).not.toBeNull();
      expect(detail!.id).toBe("pat-101");
      expect(detail!.title).toBe("Redirección forzada al login en checkout");
      expect(detail!.eventoClave).toBe("begin_checkout");
      expect(detail!.eventoClaveNombre).toBe("Inicio de checkout");
      expect(detail!.secuenciaNombres).toEqual(["Vista de página", "Inicio de checkout"]);
      expect(detail!.recommendations).toEqual(["Permitir guest checkout"]);
      expect(detail!.metrics.sessionRate.value).toBe("32,7%");
      expect(detail!.metrics.affectedUsers.value).toBe("890");
      expect(detail!.metrics.totalSessions.value).toBe("1.156");
      expect(detail!.llegadaGrupo).toBeCloseTo(67.28);
      expect(detail!.llegadaReferencia).toBeCloseTo(97.65);
      expect(detail!.caidaPuntosPorcentuales).toBeCloseTo(30.37);
      expect(detail!.porcentajeSitio).toBeCloseTo(11.56);
      expect(detail!.audience.categories).toHaveLength(4);

      // Pasos ordenados por numero_paso ascendente
      expect(detail!.agentJourney.steps.map((s) => s.stepNumber)).toEqual([1, 2]);
      expect(detail!.agentJourney.steps[0].enPatron).toBe(false);
      expect(detail!.agentJourney.steps[0].hasLlmNote).toBe(false);
      expect(detail!.agentJourney.steps[0].resolution).toBe("390 × 844");

      expect(detail!.agentJourney.steps[1].enPatron).toBe(true);
      expect(detail!.agentJourney.steps[1].friccionDetectada).toBe(true);
      expect(detail!.agentJourney.steps[1].hasLlmNote).toBe(true);
      expect(detail!.agentJourney.steps[1].status).toBe("error");
      expect(detail!.agentJourney.steps[1].imageSrc).toBe("https://signed.example.com/capture.webp");
    });

    it("maneja diagnóstico nulo, tablet y campos opcionales vacíos", async () => {
      const dbRow = {
        id: "pat-tablet",
        client_id: "client-1",
        nombre: null,
        evento_clave: null,
        evento_clave_nombre: null,
        tasa_abandono: null,
        llegada_grupo: null,
        llegada_referencia: null,
        sesiones: null,
        usuarios: null,
        sesiones_perdidas: null,
        total_sesiones_modelo: null,
        secuencia: null,
        secuencia_nombres: null,
        tipo_dispositivo: "tablet",
        navegador: null,
        sistema_operativo: null,
        ultima_deteccion: null,
        distribucion_dispositivos: null,
        distribucion_navegadores: null,
        distribucion_sistemas: null,
        distribucion_paises: null,
        fricciones_diagnosticos: null,
        friccion_recorrido_pasos: [
          {
            id: "step-1",
            friccion_id: "pat-tablet",
            numero_paso: 1,
            nombre_evento: null,
            evento_nombre: null,
            ruta_pagina: null,
            items: null,
            scroll: null,
            en_patron: false,
            friccion_detectada: false,
            notas_contexto: null,
            captura_gcs_url: null,
          },
        ],
      };

      mockFrom.mockReturnValueOnce(createDetailQueryMock({ data: dbRow, error: null }));

      const detail = await FriccionRepository.getDetailById("pat-tablet");
      expect(detail).not.toBeNull();
      expect(detail!.metrics.sessionRate.value).toBe("0,0%");
      expect(detail!.metrics.affectedUsers.value).toBe("—");
      expect(detail!.metrics.totalSessions.value).toBe("—");
      expect(detail!.agentJourney.steps[0].resolution).toBe("768 × 1024");
      expect(detail!.audience.categories).toEqual([]);
    });

    it("retorna null cuando la fricción no existe o hay error en Supabase", async () => {
      mockFrom.mockReturnValueOnce(
        createDetailQueryMock({ data: null, error: { message: "DB error" } })
      );
      expect(await FriccionRepository.getDetailById("missing")).toBeNull();

      mockFrom.mockReturnValueOnce(createDetailQueryMock({ data: null, error: null }));
      expect(await FriccionRepository.getDetailById("not-found")).toBeNull();
    });

    it("retorna null si ocurre una excepción inesperada", async () => {
      mockFrom.mockImplementationOnce(() => {
        throw new Error("Connection crash");
      });
      expect(await FriccionRepository.getDetailById("err")).toBeNull();
    });
  });

  describe("getRadarData", () => {
    it("agrupa fricciones por evento_clave usando evento_clave_nombre y métricas reales", async () => {
      const rows = [
        {
          id: "f1",
          nombre: "Fricción 1",
          evento_clave: "begin_checkout",
          evento_clave_nombre: "Inicio de checkout",
          tasa_abandono: 32.7,
          llegada_grupo: 0.67,
          llegada_referencia: 0.97,
          sesiones: 1200,
          usuarios: 900,
          sesiones_perdidas: 400,
          total_sesiones_modelo: 10000,
          secuencia: ["a", "b"],
          secuencia_nombres: ["Paso A", "Paso B"],
          ultima_deteccion: "2026-11-12",
          fricciones_diagnosticos: [
            {
              nombre_corto: "Fricción Checkout",
              titulo: "Título",
              subtitulo: "Sub",
              severidad: "alta",
              impacto_resumen: "-30 pp",
              diagnostico_corto: "Diag corto",
            },
          ],
        },
        {
          id: "f2",
          nombre: "Fricción 2",
          evento_clave: "begin_checkout",
          evento_clave_nombre: "Inicio de checkout",
          tasa_abandono: 15.0,
          llegada_grupo: 0.85,
          llegada_referencia: 0.95,
          sesiones: 800,
          usuarios: 600,
          sesiones_perdidas: 120,
          total_sesiones_modelo: 10000,
          secuencia: null,
          secuencia_nombres: null,
          ultima_deteccion: "2026-11-12",
          fricciones_diagnosticos: {
            nombre_corto: null,
            titulo: null,
            subtitulo: null,
            severidad: "media",
            impacto_resumen: null,
            diagnostico_corto: null,
          },
        },
        {
          id: "f3",
          nombre: null,
          evento_clave: "add_to_cart",
          evento_clave_nombre: "Agregar al carrito",
          tasa_abandono: null,
          llegada_grupo: null,
          llegada_referencia: null,
          sesiones: 500,
          usuarios: 400,
          sesiones_perdidas: 50,
          total_sesiones_modelo: 10000,
          secuencia: null,
          secuencia_nombres: null,
          ultima_deteccion: null,
          fricciones_diagnosticos: null,
        },
      ];

      mockFrom.mockReturnValueOnce(createRadarQueryMock({ data: rows, error: null }));

      const radar = await FriccionRepository.getRadarData("client-1");

      expect(radar.totalAffectedSessions).toBe(2500);
      expect(radar.detectedEvents).toEqual([
        { id: "begin_checkout", name: "Inicio de checkout", count: 2 },
        { id: "add_to_cart", name: "Agregar al carrito", count: 1 },
      ]);
      expect(radar.eventDisplayNames).toEqual({
        begin_checkout: "Inicio de checkout",
        add_to_cart: "Agregar al carrito",
      });
      expect(radar.eventsConfig.begin_checkout.clusters).toHaveLength(2);
      expect(radar.eventsConfig.begin_checkout.clusters[0].users).toBe("900");
      expect(radar.eventsConfig.begin_checkout.clusters[0].sessionsCount).toBe("1.200");
      expect(radar.eventsConfig.begin_checkout.clusters[0].impact).toBe("-30 pp");
      expect(radar.eventsConfig.begin_checkout.clusters[1].impact).toBe("-15.0% Abandono");
      expect(radar.eventsConfig.add_to_cart.clusters[0].tier).toBe("alta");
    });

    it("retorna estructura vacía cuando no hay datos o hay error en Supabase", async () => {
      mockFrom.mockReturnValueOnce(createRadarQueryMock({ data: [], error: null }));
      const empty = await FriccionRepository.getRadarData("client-empty");
      expect(empty.detectedEvents).toEqual([]);
      expect(empty.totalAffectedSessions).toBe(0);

      mockFrom.mockReturnValueOnce(
        createRadarQueryMock({ data: null, error: { message: "Query error" } })
      );
      const onError = await FriccionRepository.getRadarData("client-err");
      expect(onError.detectedEvents).toEqual([]);
      expect(onError.eventsConfig).toEqual({});
    });

    it("retorna estructura vacía si ocurre una excepción inesperada", async () => {
      mockFrom.mockImplementationOnce(() => {
        throw new Error("Crash");
      });
      const res = await FriccionRepository.getRadarData("client-crash");
      expect(res.detectedEvents).toEqual([]);
    });
  });
});
