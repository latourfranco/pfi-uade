import React from "npm:react@18.3.1";
import {
  Body,
  Button,
  Container,
  Head,
  Heading,
  Html,
  Img,
  Preview,
  Section,
  Text,
} from "npm:@react-email/components@0.0.22";
import { EUREKA_LOGO_BASE64 } from "./logo.ts";

export interface DiagnosticoEmailProps {
  nombreCliente?: string;
  totalFricciones?: number;
  friccionPrincipal?: string;
  impactoResumen?: string;
  severidad?: string;
  enlaceDashboard?: string;
  logoUrl?: string;
}

export const DiagnosticoEmail = ({
  totalFricciones = 1,
  enlaceDashboard = "https://eureka.app/dashboard",
  logoUrl = EUREKA_LOGO_BASE64,
}: DiagnosticoEmailProps) => {
  const fontStack =
    "'Space Grotesk', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif";

  return (
    <Html lang="es">
      <Head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link
          rel="preconnect"
          href="https://fonts.gstatic.com"
          crossOrigin="anonymous"
        />
        <link
          href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&display=swap"
          rel="stylesheet"
        />
      </Head>
      <Preview>Nuevo ciclo de análisis de UX completado en Eureka</Preview>
      <Body
        style={{
          backgroundColor: "#f4f4f0", // Beige cálido del manual de marca
          fontFamily: fontStack,
          margin: 0,
          padding: "36px 16px",
        }}
      >
        <Container
          style={{
            backgroundColor: "#ffffff",
            maxWidth: "600px",
            margin: "0 auto",
            borderRadius: "12px",
            border: "1px solid #e2e8f0",
            overflow: "hidden",
            boxShadow: "0 4px 12px rgba(10, 10, 10, 0.04)",
          }}
        >
          {/* Borde superior en el color índigo principal de la marca */}
          <div
            style={{
              height: "4px",
              backgroundColor: "#5256E8", // Color índigo principal de Eureka
              width: "100%",
            }}
          />

          <div style={{ padding: "32px 32px 28px 32px" }}>
            {/* Encabezado con Logotipo Oficial de Eureka */}
            <table
              width="100%"
              border={0}
              cellPadding={0}
              cellSpacing={0}
              role="presentation"
              style={{ marginBottom: "28px" }}
            >
              <tbody>
                <tr>
                  <td align="left" style={{ verticalAlign: "middle" }}>
                    <Img
                      src={logoUrl}
                      width="152"
                      height="34"
                      alt="eureka"
                      style={{
                        display: "block",
                        maxWidth: "152px",
                        height: "auto",
                        border: "0",
                        outline: "none",
                        textDecoration: "none",
                      }}
                    />
                  </td>
                </tr>
              </tbody>
            </table>

            {/* Título principal */}
            <Heading
              style={{
                fontSize: "22px",
                fontWeight: 700,
                color: "#0a0a0a", // Gris oscuro casi negro del manual
                margin: "0 0 16px 0",
                letterSpacing: "-0.02em",
                lineHeight: "1.3",
              }}
            >
              Nuevo reporte de fricción disponible
            </Heading>

            {/* Saludo y contexto */}
            <Text
              style={{
                fontSize: "15px",
                color: "#525252", // Gris de apoyo del manual
                lineHeight: "1.6",
                margin: "0 0 24px 0",
              }}
            >
              ¡Hola! <br />
              Concluyó exitosamente el procesamiento del lote diario de eventos de navegación de tu
              plataforma web.
            </Text>

            {/* Banner con cantidad de patrones de fricción detectados */}
            <Section
              style={{
                backgroundColor: "#eef2ff", // Tono claro del índigo
                border: "1px solid #c7d2fe", // Borde sutil índigo
                borderLeft: "4px solid #5256E8", // Borde destacado en índigo principal
                padding: "18px 20px",
                borderRadius: "8px",
                margin: "24px 0",
              }}
            >
              <Text
                style={{
                  margin: "0",
                  fontSize: "15px",
                  fontWeight: "bold",
                  color: "#1e1b4b", // Índigo oscuro para legibilidad
                  lineHeight: "1.5",
                }}
              >
                Nuevos patrones de fricción detectados:{" "}
                <span
                  style={{
                    backgroundColor: "#ffffff",
                    padding: "2px 10px",
                    borderRadius: "6px",
                    border: "1px solid #c7d2fe",
                    color: "#5256E8",
                    fontSize: "16px",
                    fontWeight: 700,
                    marginLeft: "4px",
                  }}
                >
                  {totalFricciones}
                </span>
              </Text>
            </Section>

            {/* Botón de Acción alineado a la derecha */}
            <table
              width="100%"
              border={0}
              cellPadding={0}
              cellSpacing={0}
              role="presentation"
              style={{ marginTop: "28px", marginBottom: "12px" }}
            >
              <tbody>
                <tr>
                  <td align="right">
                    <Button
                      href={enlaceDashboard}
                      style={{
                        backgroundColor: "#5256E8", // Índigo: color de acción para botones y enlaces
                        color: "#ffffff",
                        padding: "13px 26px",
                        borderRadius: "8px",
                        textDecoration: "none",
                        fontSize: "15px",
                        fontWeight: 600,
                        display: "inline-block",
                        letterSpacing: "-0.01em",
                        boxShadow: "0 2px 6px rgba(82, 86, 232, 0.35)",
                      }}
                    >
                      Explorar resultados
                    </Button>
                  </td>
                </tr>
              </tbody>
            </table>

            {/* Pie de página de la tarjeta */}
            <div
              style={{
                marginTop: "36px",
                borderTop: "1px solid #efefe8", // Beige/gris claro delimitador
                paddingTop: "20px",
              }}
            >
              <Text
                style={{
                  fontSize: "12px",
                  color: "#828282", // Gris neutro del manual
                  margin: "0",
                  lineHeight: "1.5",
                }}
              >
                Eureka · Detección autónoma de fricción en aplicaciones web
              </Text>
            </div>
          </div>
        </Container>
      </Body>
    </Html>
  );
};
