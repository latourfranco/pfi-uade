import { assertStringIncludes } from "@std/assert";
import { renderAsync } from "npm:@react-email/components@0.0.22";
import React from "npm:react@18.3.1";
import { DiagnosticoEmail } from "../templates/DiagnosticoEmail.tsx";

Deno.test("DiagnosticoEmail - renderiza correctamente con props personalizadas", async () => {
  const html = await renderAsync(
    React.createElement(DiagnosticoEmail, {
      nombreCliente: "Acme Corp",
      totalFricciones: 5,
      friccionPrincipal: "Rage clicks en botón de pago",
      impactoResumen: "Pérdida crítica de conversión",
      severidad: "crítica",
      enlaceDashboard: "https://eureka.app/dashboard/acme",
    }),
  );

  assertStringIncludes(html, "¡Hola!");
  assertStringIncludes(html, "Nuevos patrones de fricción detectados:");
  assertStringIncludes(html, "5");
  assertStringIncludes(html, "https://eureka.app/dashboard/acme");
  assertStringIncludes(html, "Nuevo reporte de fricción disponible");
  assertStringIncludes(html, "Explorar resultados");
  assertStringIncludes(
    html,
    "Eureka · Detección autónoma de fricción en aplicaciones web",
  );
});

Deno.test("DiagnosticoEmail - renderiza correctamente con valores por defecto", async () => {
  const html = await renderAsync(React.createElement(DiagnosticoEmail, {}));

  assertStringIncludes(html, "¡Hola!");
  assertStringIncludes(html, "Nuevos patrones de fricción detectados:");
  assertStringIncludes(html, "1");
  assertStringIncludes(html, "Explorar resultados");
  assertStringIncludes(html, "https://eureka.app/dashboard");
});
