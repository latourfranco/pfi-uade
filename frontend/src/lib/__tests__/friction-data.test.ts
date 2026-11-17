import { describe, it, expect } from "vitest";
import {
  normalizeDiagnostico,
  formatPercentFromRatio,
  calculateFunnelDropPp,
  calculateSiteSharePercent,
  buildAudienceCategories,
  mergeStepsWithNotes,
  type FriccionPasoWithNotasRow,
  type FriccionNotaRow,
} from "../friction-data";

describe("friction-data helpers (nuevo modelo Supabase)", () => {
  describe("normalizeDiagnostico", () => {
    it("retorna null cuando recibe null o undefined", () => {
      expect(normalizeDiagnostico(null)).toBeNull();
      expect(normalizeDiagnostico(undefined)).toBeNull();
    });

    it("retorna el primer elemento cuando recibe un array", () => {
      const diag = { id: "d1" };
      expect(normalizeDiagnostico([diag])).toEqual(diag);
      expect(normalizeDiagnostico([])).toBeNull();
    });

    it("retorna el objeto directamente cuando no es array", () => {
      const diag = { id: "d1" };
      expect(normalizeDiagnostico(diag)).toEqual(diag);
    });
  });

  describe("formatPercentFromRatio", () => {
    it("convierte proporciones 0..1 a 0..100", () => {
      expect(formatPercentFromRatio(0.6728)).toBeCloseTo(67.28);
      expect(formatPercentFromRatio("0.9765")).toBeCloseTo(97.65);
    });

    it("retorna null para valores vacíos o no numéricos", () => {
      expect(formatPercentFromRatio(null)).toBeNull();
      expect(formatPercentFromRatio(undefined)).toBeNull();
      expect(formatPercentFromRatio("")).toBeNull();
      expect(formatPercentFromRatio("abc")).toBeNull();
    });
  });

  describe("calculateFunnelDropPp", () => {
    it("calcula la caída en puntos porcentuales entre referencia y grupo", () => {
      expect(calculateFunnelDropPp(0.9765, 0.6728)).toBeCloseTo(30.37);
    });

    it("retorna null si falta alguno de los dos valores", () => {
      expect(calculateFunnelDropPp(null, 0.5)).toBeNull();
      expect(calculateFunnelDropPp(0.9, undefined)).toBeNull();
    });
  });

  describe("calculateSiteSharePercent", () => {
    it("calcula el porcentaje de sesiones sobre el total del modelo", () => {
      expect(calculateSiteSharePercent(500, 2000)).toBeCloseTo(25);
    });

    it("retorna null si sesiones o totalModelo son inválidos o cero", () => {
      expect(calculateSiteSharePercent(null, 2000)).toBeNull();
      expect(calculateSiteSharePercent(500, 0)).toBeNull();
      expect(calculateSiteSharePercent(500, null)).toBeNull();
    });
  });

  describe("buildAudienceCategories", () => {
    it("construye solo las categorías con ítems presentes", () => {
      const categories = buildAudienceCategories({
        distribucion_dispositivos: [{ label: "desktop", percentage: 70 }],
        distribucion_paises: [],
        distribucion_navegadores: null,
        distribucion_sistemas: [{ label: "macOS", percentage: 55 }],
      });

      expect(categories).toEqual([
        { title: "DISPOSITIVO", items: [{ label: "desktop", percentage: 70 }] },
        { title: "SISTEMA", items: [{ label: "macOS", percentage: 55 }] },
      ]);
    });
  });

  describe("mergeStepsWithNotes", () => {
    const paso1: FriccionPasoWithNotasRow = {
      id: "p1",
      friccion_id: "f1",
      numero_paso: 1,
      nombre_evento: "page_view",
      evento_nombre: "Vista de página",
      ruta_pagina: "/home",
      items: null,
      scroll: true,
      en_patron: false,
      friccion_detectada: false,
      notas_contexto: ["Paso previo"],
      captura_gcs_url: null,
    };

    const paso2: FriccionPasoWithNotasRow = {
      id: "p2",
      friccion_id: "f1",
      numero_paso: 2,
      nombre_evento: "begin_checkout",
      evento_nombre: "Inicio de checkout",
      ruta_pagina: "/checkout",
      items: "Hoodie",
      scroll: false,
      en_patron: true,
      friccion_detectada: true,
      notas_contexto: null,
      captura_gcs_url: "gs://pruebas-pfi-evidencias/p2.webp",
      friccion_recorrido_notas: {
        id: "n2",
        friccion_id: "f1",
        paso_id: "p2",
        numero_paso: 2,
        nota_titulo: "Bloqueo en modal",
        nota_descripcion: "No avanza sin login",
        insignias: ["Bloqueo"],
        estado: "error",
        coincidencia_cluster: "crítica",
      },
    };

    const paso3: FriccionPasoWithNotasRow = {
      id: "p3",
      friccion_id: "f1",
      numero_paso: 3,
      nombre_evento: "login",
      evento_nombre: "Inicio de sesión",
      ruta_pagina: "/login",
      items: null,
      scroll: false,
      en_patron: true,
      friccion_detectada: false,
      notas_contexto: null,
      captura_gcs_url: null,
    };

    const notaExternaP3: FriccionNotaRow = {
      id: "n3",
      friccion_id: "f1",
      paso_id: "p3",
      numero_paso: 3,
      nota_titulo: "Redirección a login",
      nota_descripcion: "Pide credenciales",
      insignias: ["Auth"],
      estado: "warning",
      coincidencia_cluster: "alta",
    };

    const notaPorNumero: FriccionNotaRow = {
      id: "n4",
      friccion_id: "f1",
      paso_id: null,
      numero_paso: 4,
      nota_titulo: "Nota por número",
      nota_descripcion: "Fallback por numero_paso",
      insignias: ["Info"],
      estado: "success",
      coincidencia_cluster: "baja",
    };

    const paso4: FriccionPasoWithNotasRow = {
      ...paso1,
      id: "p4",
      numero_paso: 4,
      en_patron: true,
    };

    it("ordena pasos por numero_paso ascendente y vincula notas anidadas, por paso_id o numero_paso", () => {
      const merged = mergeStepsWithNotes([paso4, paso2, paso1, paso3], [notaExternaP3, notaPorNumero]);

      expect(merged.map((m) => m.paso.numero_paso)).toEqual([1, 2, 3, 4]);
      expect(merged[0].nota).toBeNull();
      expect(merged[1].nota?.id).toBe("n2");
      expect(merged[2].nota?.id).toBe("n3");
      expect(merged[3].nota?.id).toBe("n4");
    });
  });
});
