import type { FrictionDetail } from "@/lib/friction-data";

export function createMockFrictionDetail(overrides: Partial<FrictionDetail> = {}): FrictionDetail {
  return {
    id: "pat-101",
    indexBadge: 1,
    title: "Modal de Login en Checkout",
    subtitle: "El flujo obliga a iniciar sesión antes de completar la compra.",
    eventoClave: "begin_checkout",
    eventoClaveNombre: "Inicio de checkout",
    severidad: "alta",
    impactoResumen: "-30.4 pp en avance · 379 sesiones perdidas",
    secuencia: ["page_view", "begin_checkout"],
    secuenciaNombres: ["Vista de página", "Inicio de checkout"],
    tipoDispositivo: "desktop",
    metrics: {
      sessionRate: { value: "32,7%", label: "tasa de abandono" },
      affectedUsers: { value: "890", label: "usuarios afectados" },
      totalSessions: { value: "1.156", label: "sesiones analizadas" },
    },
    diagnosis: {
      paragraphs: [
        "Manifestación en UI: el modal bloquea el botón continuar.",
        "Causa raíz: validación de sesión en el backend.",
      ],
    },
    evidence: ["Caída de 30.4 pp frente a la referencia."],
    recommendations: ["Habilitar checkout como invitado."],
    agentJourney: {
      steps: [
        {
          id: "step-1",
          stepNumber: 1,
          title: "Catálogo principal",
          actionSubtitle: "Vista de página",
          captureName: "captura · catalogo",
          resolution: "1440 × 900",
          caption: "Catálogo principal · catalogo",
          noteTitle: "Paso de contexto",
          noteDescription: "Navegación previa al checkout.",
          badges: [],
          screenTime: "",
          clusterMatch: "",
          url: "https://shop.example.com/catalogo",
          eventoNombre: "Vista de página",
          enPatron: false,
          friccionDetectada: false,
          notasContexto: ["Contexto previo"],
          hasLlmNote: false,
        },
        {
          id: "step-2",
          stepNumber: 2,
          title: "Inicio de checkout",
          actionSubtitle: "Inicio de checkout",
          captureName: "captura · checkout",
          resolution: "1440 × 900",
          caption: "Inicio de checkout · checkout",
          noteTitle: "Bloqueo en modal de login",
          noteDescription: "Al presionar Continuar redirige al formulario de acceso.",
          badges: ["Bloqueo", "Checkout"],
          screenTime: "",
          clusterMatch: "crítica",
          status: "error",
          url: "https://shop.example.com/checkout",
          eventoNombre: "Inicio de checkout",
          items: "Hoodie Clásico",
          scroll: false,
          enPatron: true,
          friccionDetectada: true,
          notasContexto: [],
          hasLlmNote: true,
        },
      ],
    },
    audience: {
      summary: "Usuarios recurrentes en desktop y mobile.",
      categories: [
        {
          title: "DISPOSITIVO",
          items: [
            { label: "Desktop", percentage: 70 },
            { label: "Mobile", percentage: 30 },
          ],
        },
        {
          title: "UBICACIÓN",
          items: [{ label: "Argentina", percentage: 85 }],
        },
      ],
    },
    ...overrides,
  };
}
