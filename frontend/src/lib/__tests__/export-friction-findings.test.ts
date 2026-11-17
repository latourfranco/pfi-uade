import { describe, it, expect, vi, afterEach } from "vitest";
import {
  buildFrictionExportFilename,
  buildFrictionFindingsHtml,
  downloadFrictionFindings,
  resolveImageAsDataUrl,
} from "../export-friction-findings";
import { createMockFrictionDetail } from "@/components/dashboard/friction-detail/__tests__/test-fixtures";

describe("export-friction-findings", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("genera nombres de archivo .html sanitizados y con fallback", () => {
    expect(buildFrictionExportFilename("Bloqueo de envío — Checkout")).toBe(
      "hallazgos-bloqueo-de-envio-checkout.html"
    );
    expect(buildFrictionExportFilename("   ---   ")).toBe("hallazgos-friccion.html");
  });

  it("genera el reporte HTML completo con todas las secciones y escapando caracteres", () => {
    const detail = createMockFrictionDetail({
      title: "Bloqueo <script>alert(1)</script> & Checkout",
      caidaPuntosPorcentuales: 12.5,
      sesionesPerdidas: 420,
      agentJourney: {
        steps: [
          {
            id: "1",
            stepNumber: 1,
            title: "Inicio",
            actionSubtitle: "Navegación",
            captureName: "step-1.png",
            resolution: "1440x900",
            caption: "",
            noteTitle: "Paso normal",
            noteDescription: "Sin bloqueos",
            badges: [],
            screenTime: "4s",
            clusterMatch: "baja",
            url: "https://tienda.test/cart",
            enPatron: false,
            friccionDetectada: false,
          },
          {
            id: "2",
            stepNumber: 2,
            title: "Paso en patrón",
            actionSubtitle: "Click",
            captureName: "step-2.png",
            resolution: "1440x900",
            caption: "",
            noteTitle: "En patrón",
            noteDescription: "Comportamiento repetido",
            badges: [],
            screenTime: "8s",
            clusterMatch: "alta",
            url: "https://tienda.test/shipping",
            enPatron: true,
            friccionDetectada: false,
          },
          {
            id: "3",
            stepNumber: 3,
            title: "Mayor fricción",
            actionSubtitle: "Bloqueo",
            captureName: "step-3.png",
            resolution: "1440x900",
            caption: "",
            noteTitle: "Bloqueo total",
            noteDescription: "El usuario abandona",
            badges: [],
            screenTime: "15s",
            clusterMatch: "crítica",
            url: "https://tienda.test/login",
            imageSrc: "https://cdn.example.com/step-3.webp",
            enPatron: true,
            friccionDetectada: true,
          },
        ],
      },
      audience: {
        summary: "",
        categories: [
          {
            title: "Dispositivo",
            items: [
              { label: "Mobile", percentage: 70 },
              { label: "Desktop", percentage: 30 },
              { label: "Zero", percentage: 0 },
            ],
          },
        ],
      },
    });

    const html = buildFrictionFindingsHtml(detail, {
      "https://cdn.example.com/step-3.webp": "data:image/webp;base64,MOCKDATA",
    });
    expect(html).toContain("<!DOCTYPE html>");
    expect(html).toContain("Bloqueo &lt;script&gt;alert(1)&lt;/script&gt; &amp; Checkout");
    expect(html).not.toContain("<script>alert(1)</script>");
    expect(html).toContain('src="data:image/webp;base64,MOCKDATA"');
    expect(html).toContain('alt="Captura paso 3: Mayor fricción"');

    const htmlFallbackImg = buildFrictionFindingsHtml(detail);
    expect(htmlFallbackImg).toContain('src="https://cdn.example.com/step-3.webp"');
    expect(html).toContain("-12,5 pp de conversión · 420 sesiones perdidas");
    expect(html).toContain("<h2>Diagnóstico del agente</h2>");
    expect(html).toContain("<h2>Evidencia</h2>");
    expect(html).toContain("<h2>Recomendaciones</h2>");
    expect(html).toContain("<h2>Recorrido del agente</h2>");
    expect(html).toContain("badge-pattern\">En patrón</span>");
    expect(html).toContain("badge-danger\">Mayor fricción</span>");
    expect(html).toContain("<h2>Quiénes son</h2>");
    expect(html).toContain("<h3>Dispositivo</h3>");
    expect(html).toContain("<span>Mobile</span><strong>70%</strong>");
    expect(html).not.toContain("Zero");
  });

  it("omite secciones vacías y usa impactoResumen como fallback", () => {
    const detail = createMockFrictionDetail({
      subtitle: "",
      caidaPuntosPorcentuales: null,
      sesionesPerdidas: null,
      impactoResumen: "Caída estimada 8%",
      diagnosis: { paragraphs: [] },
      evidence: [],
      recommendations: [],
      agentJourney: { steps: [] },
      audience: { summary: "", categories: [] },
    });

    const html = buildFrictionFindingsHtml(detail);
    expect(html).toContain('<div class="impact-pill">Caída estimada 8%</div>');
    expect(html).not.toContain('<p class="subtitle">');
    expect(html).not.toContain("<h2>Diagnóstico del agente</h2>");
    expect(html).not.toContain("<h2>Evidencia</h2>");
    expect(html).not.toContain("<h2>Recomendaciones</h2>");
    expect(html).not.toContain("<h2>Recorrido del agente</h2>");
    expect(html).not.toContain("<h2>Quiénes son</h2>");
  });

  it("cubre variantes sin sesionesPerdidas, sin impactoResumen y pasos sin url ni notas", () => {
    const detailOnlyPp = createMockFrictionDetail({
      caidaPuntosPorcentuales: 5,
      sesionesPerdidas: null,
      impactoResumen: null,
      agentJourney: {
        steps: [
          {
            id: "1",
            stepNumber: 1,
            title: "Paso mínimo",
            actionSubtitle: "Click",
            captureName: "step-1.png",
            resolution: "1440x900",
            caption: "",
            noteTitle: "",
            noteDescription: "",
            badges: [],
            screenTime: "2s",
            clusterMatch: "baja",
            url: "",
            enPatron: false,
            friccionDetectada: false,
          },
        ],
      },
      audience: {
        summary: "",
        categories: [
          {
            title: "Vacía",
            items: [{ label: "None", percentage: 0 }],
          },
          {
            title: "Navegador",
            items: [
              { label: "Safari", percentage: 20 },
              { label: "Chrome", percentage: 80 },
            ],
          },
        ],
      },
    });

    const htmlOnlyPp = buildFrictionFindingsHtml(detailOnlyPp);
    expect(htmlOnlyPp).toContain('<div class="impact-pill">-5,0 pp de conversión</div>');
    expect(htmlOnlyPp).not.toContain("sesiones perdidas");
    expect(htmlOnlyPp).toContain("<strong>Paso mínimo</strong>");
    expect(htmlOnlyPp).not.toContain("<strong>URL:</strong>");
    expect(htmlOnlyPp).not.toContain('<div class="note">');
    expect(htmlOnlyPp).not.toContain("<h3>Vacía</h3>");
    expect(htmlOnlyPp).toContain("<span>Chrome</span><strong>80%</strong>");

    const detailNoImpact = createMockFrictionDetail({
      caidaPuntosPorcentuales: null,
      sesionesPerdidas: null,
      impactoResumen: null,
    });
    expect(buildFrictionFindingsHtml(detailNoImpact)).not.toContain('<div class="impact-pill">');
  });

  it("convierte imágenes a Base64 y hace fallback a la URL si falla", async () => {
    const okBlob = new Blob(["fake-image"], { type: "image/png" });
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce({
        ok: true,
        blob: async () => okBlob,
      } as Response)
      .mockResolvedValueOnce({ ok: false } as Response)
      .mockRejectedValueOnce(new Error("CORS error"));

    const dataUrl = await resolveImageAsDataUrl("https://cdn.example.com/ok.png");
    expect(dataUrl).toMatch(/^data:image\/png;base64,/);

    const fallbackHttp = await resolveImageAsDataUrl("https://cdn.example.com/404.png");
    expect(fallbackHttp).toBe("https://cdn.example.com/404.png");

    const fallbackErr = await resolveImageAsDataUrl("https://cdn.example.com/cors.png");
    expect(fallbackErr).toBe("https://cdn.example.com/cors.png");
    expect(fetchMock).toHaveBeenCalledTimes(3);
  });

  it("descarga el archivo HTML mediante Blob y anchor embebiendo capturas", async () => {
    const detail = createMockFrictionDetail({
      agentJourney: {
        steps: [
          {
            id: "1",
            stepNumber: 1,
            title: "Con captura",
            actionSubtitle: "Click",
            captureName: "c.webp",
            resolution: "1440x900",
            caption: "",
            noteTitle: "",
            noteDescription: "",
            badges: [],
            screenTime: "2s",
            clusterMatch: "baja",
            imageSrc: "https://cdn.example.com/step.webp",
          },
        ],
      },
    });
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce({
      ok: false,
    } as Response);
    const createObjectURLSpy = vi.spyOn(URL, "createObjectURL").mockReturnValue("blob:mock-url");
    const revokeObjectURLSpy = vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => {});
    const clickSpy = vi
      .spyOn(HTMLAnchorElement.prototype, "click")
      .mockImplementation(() => {});

    await downloadFrictionFindings(detail);

    expect(createObjectURLSpy).toHaveBeenCalledTimes(1);
    expect(clickSpy).toHaveBeenCalledTimes(1);
    expect(revokeObjectURLSpy).toHaveBeenCalledWith("blob:mock-url");
  });
});
