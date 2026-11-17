import { act } from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import LoginPage from "../page";
import * as authActions from "@/app/actions/auth";
import * as navigation from "next/navigation";

vi.mock("@/app/actions/auth", () => ({
  signInWithGoogleAction: vi.fn(),
}));

describe("LoginPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(navigation, "useSearchParams").mockReturnValue(
      new URLSearchParams("next=/dashboard/cuenta") as unknown as ReturnType<
        typeof navigation.useSearchParams
      >
    );
  });

  it("inicia autenticación con Google al hacer clic en Continuar con Google", async () => {
    vi.mocked(authActions.signInWithGoogleAction).mockResolvedValue({
      success: true,
    });

    await act(async () => {
      render(<LoginPage />);
    });

    await act(async () => {
      fireEvent.click(
        screen.getByRole("button", { name: /Continuar con Google/i })
      );
    });

    expect(authActions.signInWithGoogleAction).toHaveBeenCalledWith(
      "/dashboard/cuenta"
    );
  });

  it("muestra error si llega ?error=google_auth_failed o falla la acción", async () => {
    vi.spyOn(navigation, "useSearchParams").mockReturnValue(
      new URLSearchParams("error=google_auth_failed") as unknown as ReturnType<
        typeof navigation.useSearchParams
      >
    );

    await act(async () => {
      render(<LoginPage />);
    });

    expect(screen.getByRole("alert")).toHaveTextContent(
      "No pudimos completar el inicio de sesión con Google."
    );

    vi.mocked(authActions.signInWithGoogleAction).mockResolvedValue({
      success: false,
      error: "Fallo OAuth",
    });

    await act(async () => {
      fireEvent.click(
        screen.getByRole("button", { name: /Continuar con Google/i })
      );
    });

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent("Fallo OAuth");
    });
  });
});
