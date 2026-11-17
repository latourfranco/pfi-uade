import type { FrictionDetail } from "@/lib/friction-data";

const integerFormatter = new Intl.NumberFormat("es-AR");

/**
 * Escapes special HTML characters to prevent malformed markup or XSS.
 */
function escapeHtml(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

/**
 * Formats the conversion impact summary for the exported report.
 */
function formatExportConversionImpact(data: FrictionDetail): string | null {
  if (
    data.caidaPuntosPorcentuales !== null &&
    data.caidaPuntosPorcentuales !== undefined &&
    !Number.isNaN(data.caidaPuntosPorcentuales)
  ) {
    const ppFormatted = Math.abs(data.caidaPuntosPorcentuales).toFixed(1).replace(".", ",");
    const parts = [`-${ppFormatted} pp de conversión`];
    if (
      data.sesionesPerdidas !== null &&
      data.sesionesPerdidas !== undefined &&
      !Number.isNaN(data.sesionesPerdidas)
    ) {
      parts.push(`${integerFormatter.format(Math.round(data.sesionesPerdidas))} sesiones perdidas`);
    }
    return parts.join(" · ");
  }

  return data.impactoResumen ?? null;
}

/**
 * Builds a sanitized HTML filename from the friction title.
 */
export function buildFrictionExportFilename(title: string): string {
  const slug = title
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 60);

  return `hallazgos-${slug || "friccion"}.html`;
}

/**
 * Converts a Blob into a Base64 data URL.
 */
function blobToDataUrl(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onloadend = () => {
      if (typeof reader.result === "string") {
        resolve(reader.result);
      } else {
        reject(new Error("Could not convert blob to data URL"));
      }
    };
    reader.onerror = () => reject(reader.error ?? new Error("FileReader error"));
    reader.readAsDataURL(blob);
  });
}

/**
 * Fetches an image URL and encodes it as a Base64 data URL, falling back to the original URL.
 */
export async function resolveImageAsDataUrl(url: string): Promise<string> {
  try {
    const response = await fetch(url);
    if (!response.ok) {
      return url;
    }
    const blob = await response.blob();
    return await blobToDataUrl(blob);
  } catch {
    return url;
  }
}

/**
 * Builds a self-contained, readable HTML report summarizing all findings for a friction pattern.
 */
export function buildFrictionFindingsHtml(
  data: FrictionDetail,
  resolvedImages: Record<string, string> = {}
): string {
  const conversionImpact = formatExportConversionImpact(data);
  const paragraphs = data.diagnosis?.paragraphs ?? [];
  const evidence = data.evidence ?? [];
  const recommendations = data.recommendations ?? [];
  const steps = data.agentJourney?.steps ?? [];
  const populatedCategories = (data.audience?.categories ?? [])
    .map((cat) => ({
      title: cat.title,
      items: cat.items
        .filter((item) => item.percentage > 0)
        .sort((a, b) => b.percentage - a.percentage)
        .slice(0, 5),
    }))
    .filter((cat) => cat.items.length > 0);

  const diagnosisHtml =
    paragraphs.length > 0
      ? `<section class="card">
      <h2>Diagnóstico del agente</h2>
      ${paragraphs.map((p) => `<p>${escapeHtml(p)}</p>`).join("\n      ")}
    </section>`
      : "";

  const evidenceHtml =
    evidence.length > 0
      ? `<section class="card">
      <h2>Evidencia</h2>
      <ul>
        ${evidence.map((item) => `<li>${escapeHtml(item)}</li>`).join("\n        ")}
      </ul>
    </section>`
      : "";

  const recommendationsHtml =
    recommendations.length > 0
      ? `<section class="card">
      <h2>Recomendaciones</h2>
      <ol>
        ${recommendations.map((rec) => `<li>${escapeHtml(rec)}</li>`).join("\n        ")}
      </ol>
    </section>`
      : "";

  const journeyHtml =
    steps.length > 0
      ? `<section class="card">
      <h2>Recorrido del agente</h2>
      <ol class="steps">
        ${steps
          .map((step, index) => {
            const badge = step.friccionDetectada
              ? `<span class="badge badge-danger">Mayor fricción</span>`
              : step.enPatron
                ? `<span class="badge badge-pattern">En patrón</span>`
                : "";
            const urlLine = step.url
              ? `<div class="meta"><strong>URL:</strong> ${escapeHtml(step.url)}</div>`
              : "";
            const noteParts = [step.noteTitle, step.noteDescription].filter(Boolean);
            const noteLine =
              noteParts.length > 0
                ? `<div class="note">${escapeHtml(noteParts.join(" — "))}</div>`
                : "";
            const imgSrc = step.imageSrc
              ? resolvedImages[step.imageSrc] ?? step.imageSrc
              : null;
            const imgLine = imgSrc
              ? `<div class="screenshot"><img src="${escapeHtml(imgSrc)}" alt="Captura paso ${index + 1}: ${escapeHtml(step.title)}" loading="lazy" /></div>`
              : "";
            return `<li>
          <div class="step-title"><strong>${escapeHtml(step.title)}</strong> ${badge}</div>
          ${urlLine}
          ${noteLine}
          ${imgLine}
        </li>`;
          })
          .join("\n        ")}
      </ol>
    </section>`
      : "";

  const audienceHtml =
    populatedCategories.length > 0
      ? `<section class="card">
      <h2>Quiénes son</h2>
      <div class="audience-grid">
        ${populatedCategories
          .map(
            (cat) => `<div class="audience-card">
          <h3>${escapeHtml(cat.title)}</h3>
          <ul>
            ${cat.items
              .map((item) => `<li><span>${escapeHtml(item.label)}</span><strong>${item.percentage}%</strong></li>`)
              .join("\n            ")}
          </ul>
        </div>`
          )
          .join("\n        ")}
      </div>
    </section>`
      : "";

  return `<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Hallazgos — ${escapeHtml(data.title)}</title>
  <style>
    :root { color-scheme: light; }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      padding: 32px 20px;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background: #faf9f5;
      color: #171717;
      line-height: 1.6;
    }
    .container { max-width: 880px; margin: 0 auto; display: flex; flex-direction: column; gap: 20px; }
    .header { background: #ffffff; border: 1px solid #e5e5e5; border-radius: 16px; padding: 24px 28px; }
    h1 { margin: 0 0 8px; font-size: 26px; line-height: 1.25; }
    .subtitle { margin: 0; color: #525252; font-size: 15px; }
    .impact-pill {
      display: inline-block;
      margin-top: 14px;
      padding: 6px 12px;
      border-radius: 10px;
      background: #fef2f2;
      border: 1px solid #fecaca;
      color: #b91c1c;
      font-size: 13px;
      font-weight: 600;
    }
    .kpis {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 12px;
      margin-top: 18px;
    }
    .kpi { background: #fafaf9; border: 1px solid #e7e5e4; border-radius: 12px; padding: 12px 14px; }
    .kpi-value { font-size: 22px; font-weight: 700; color: #4f46e5; }
    .kpi-label { font-size: 12px; color: #525252; margin-top: 2px; }
    .card { background: #ffffff; border: 1px solid #e5e5e5; border-radius: 16px; padding: 22px 26px; }
    h2 { margin: 0 0 12px; font-size: 15px; text-transform: uppercase; letter-spacing: 0.06em; color: #4f46e5; }
    h3 { margin: 0 0 8px; font-size: 14px; color: #262626; }
    p { margin: 0 0 10px; color: #262626; }
    p:last-child { margin-bottom: 0; }
    ul, ol { margin: 0; padding-left: 20px; }
    li { margin-bottom: 8px; color: #262626; }
    li:last-child { margin-bottom: 0; }
    .steps li { margin-bottom: 18px; }
    .step-title { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; }
    .badge {
      display: inline-block;
      padding: 2px 8px;
      border-radius: 999px;
      font-size: 11px;
      font-weight: 600;
    }
    .badge-danger { background: #dc2626; color: #ffffff; }
    .badge-pattern { background: #fef2f2; color: #dc2626; border: 1px solid #fca5a5; }
    .meta { font-size: 13px; color: #525252; margin-top: 4px; word-break: break-all; }
    .note { font-size: 14px; color: #404040; margin-top: 6px; background: #fafaf9; padding: 8px 10px; border-radius: 8px; }
    .screenshot {
      margin-top: 10px;
      border: 1px solid #e5e5e5;
      border-radius: 10px;
      overflow: hidden;
      background: #fafaf9;
      padding: 8px;
    }
    .screenshot img {
      display: block;
      max-width: 100%;
      max-height: 460px;
      width: auto;
      height: auto;
      margin: 0 auto;
      border-radius: 6px;
    }
    .audience-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 14px; }
    .audience-card { background: #fafaf9; border: 1px solid #e7e5e4; border-radius: 12px; padding: 12px 14px; }
    .audience-card ul { list-style: none; padding: 0; }
    .audience-card li { display: flex; justify-content: space-between; gap: 8px; font-size: 13px; margin-bottom: 6px; }
    @media print {
      body { background: #ffffff; padding: 0; }
      .card, .header, .screenshot { break-inside: avoid; }
    }
  </style>
</head>
<body>
  <main class="container">
    <header class="header">
      <h1>${escapeHtml(data.title)}</h1>
      ${data.subtitle ? `<p class="subtitle">${escapeHtml(data.subtitle)}</p>` : ""}
      ${conversionImpact ? `<div class="impact-pill">${escapeHtml(conversionImpact)}</div>` : ""}
      <div class="kpis">
        <div class="kpi">
          <div class="kpi-value">${escapeHtml(data.metrics.sessionRate.value)}</div>
          <div class="kpi-label">${escapeHtml(data.metrics.sessionRate.label)}</div>
        </div>
        <div class="kpi">
          <div class="kpi-value">${escapeHtml(data.metrics.affectedUsers.value)}</div>
          <div class="kpi-label">${escapeHtml(data.metrics.affectedUsers.label)}</div>
        </div>
        <div class="kpi">
          <div class="kpi-value">${escapeHtml(data.metrics.totalSessions.value)}</div>
          <div class="kpi-label">${escapeHtml(data.metrics.totalSessions.label)}</div>
        </div>
      </div>
    </header>
    ${diagnosisHtml}
    ${evidenceHtml}
    ${recommendationsHtml}
    ${journeyHtml}
    ${audienceHtml}
  </main>
</body>
</html>
`;
}

/**
 * Triggers a client-side HTML download of the friction findings, embedding screenshots as Base64.
 */
export async function downloadFrictionFindings(data: FrictionDetail): Promise<void> {
  const uniqueUrls = Array.from(
    new Set(
      (data.agentJourney?.steps ?? [])
        .map((step) => step.imageSrc)
        .filter((src): src is string => Boolean(src))
    )
  );

  const entries = await Promise.all(
    uniqueUrls.map(async (url) => [url, await resolveImageAsDataUrl(url)] as const)
  );
  const resolvedImages = Object.fromEntries(entries);

  const html = buildFrictionFindingsHtml(data, resolvedImages);
  const blob = new Blob([html], { type: "text/html;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = buildFrictionExportFilename(data.title);
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
  URL.revokeObjectURL(url);
}
