import React, { act } from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import * as navigation from "next/navigation";

const { mockInitiateGoogleOAuth } = vi.hoisted(() => ({
  mockInitiateGoogleOAuth: vi.fn(),
}));

vi.mock("@/app/actions/google-auth", () => ({
  initiateGoogleOAuth: mockInitiateGoogleOAuth,
}));

import FuenteOnboardingPage from "../page";

describe("FuenteOnboardingPage (src/app/onboarding/fuente/page.tsx)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockInitiateGoogleOAuth.mockResolvedValue(undefined);
  });

  it("renderiza el estado inicial de conexión con Google, términos desmarcados y botón deshabilitado", async () => {
    vi.spyOn(navigation, "useSearchParams").mockReturnValue(
      new URLSearchParams() as unknown as ReturnType<typeof navigation.useSearchParams>
    );

    await act(async () => {
      render(<FuenteOnboardingPage />);
    });

    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(
      "Conexión con Google Analytics"
    );
    const connectBtn = screen.getByRole("button", { name: /conectar con google/i });
    expect(connectBtn).toBeDisabled();

    // Abrir modal de términos
    const termsTrigger = screen.getByRole("button", { name: /términos de la conexión/i });
    await act(async () => {
      fireEvent.click(termsTrigger);
    });

    expect(
      screen.getByText("Transparencia total sobre cómo cuidamos tus datos y tu cuenta.")
    ).toBeInTheDocument();

    // Cerrar modal
    const closeBtn = screen.getByRole("button", { name: /entendido/i });
    await act(async () => {
      fireEvent.click(closeBtn);
    });

    // Marcar checkbox de términos
    const checkbox = screen.getByRole("checkbox", { name: /acepto los/i });
    await act(async () => {
      fireEvent.click(checkbox);
    });

    expect(connectBtn).toBeEnabled();
  });

  it("inicia el flujo OAuth real con Google al hacer click cuando los términos están aceptados", async () => {
    vi.spyOn(navigation, "useSearchParams").mockReturnValue(
      new URLSearchParams() as unknown as ReturnType<typeof navigation.useSearchParams>
    );

    await act(async () => {
      render(<FuenteOnboardingPage />);
    });

    const checkbox = screen.getByRole("checkbox", { name: /acepto los/i });
    await act(async () => {
      fireEvent.click(checkbox);
    });

    const connectBtn = screen.getByRole("button", { name: /conectar con google/i });
    await act(async () => {
      fireEvent.click(connectBtn);
    });

    expect(mockInitiateGoogleOAuth).toHaveBeenCalledTimes(1);
  });

  it("muestra error y restablece el botón si initiateGoogleOAuth falla", async () => {
    mockInitiateGoogleOAuth.mockRejectedValueOnce(new Error("OAuth config missing"));
    vi.spyOn(navigation, "useSearchParams").mockReturnValue(
      new URLSearchParams() as unknown as ReturnType<typeof navigation.useSearchParams>
    );

    await act(async () => {
      render(<FuenteOnboardingPage />);
    });

    await act(async () => {
      fireEvent.click(screen.getByRole("checkbox", { name: /acepto los/i }));
    });

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /conectar con google/i }));
    });

    expect(screen.getByText("Ocurrió un error en la sincronización")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /conectar con google/i })).toBeEnabled();
  });

  it("renderiza banner de error específico cuando errorParam es conocido", async () => {
    vi.spyOn(navigation, "useSearchParams").mockReturnValue(
      new URLSearchParams("error=permisos_insuficientes") as unknown as ReturnType<
        typeof navigation.useSearchParams
      >
    );

    await act(async () => {
      render(<FuenteOnboardingPage />);
    });

    expect(screen.getByText("Permisos insuficientes en Google")).toBeInTheDocument();
  });

  it("renderiza banner de error fallback cuando errorParam es desconocido", async () => {
    vi.spyOn(navigation, "useSearchParams").mockReturnValue(
      new URLSearchParams("error=error_no_mapeado") as unknown as ReturnType<
        typeof navigation.useSearchParams
      >
    );

    await act(async () => {
      render(<FuenteOnboardingPage />);
    });

    expect(screen.getByText("Ocurrió un error en la sincronización")).toBeInTheDocument();
  });

  it("renderiza estado de conexión exitosa cuando status=success con enlace directo al resumen", async () => {
    vi.spyOn(navigation, "useSearchParams").mockReturnValue(
      new URLSearchParams(
        "status=success&propertyName=MiTienda&propertyId=123&region=us-east1&projectId=proj-1&rubro=Fintech&tamano=50-249"
      ) as unknown as ReturnType<typeof navigation.useSearchParams>
    );

    await act(async () => {
      render(<FuenteOnboardingPage />);
    });

    expect(screen.getByText("Conexión establecida con éxito")).toBeInTheDocument();
    expect(screen.getByText("MiTienda")).toBeInTheDocument();

    const link = screen.getByRole("link", { name: /avanzar/i });
    expect(link).toHaveAttribute("href", expect.stringContaining("propertyName=MiTienda"));
  });
});
