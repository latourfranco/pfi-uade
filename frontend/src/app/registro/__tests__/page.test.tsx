import { act } from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import RegistroPage from "../page";
import * as authActions from "@/app/actions/auth";

vi.mock("@/app/actions/auth", () => ({
  signInWithGoogleAction: vi.fn(),
}));

describe("RegistroPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("inicia registro con Google hacia /onboarding/rubro", async () => {
    vi.mocked(authActions.signInWithGoogleAction).mockResolvedValue({
      success: true,
    });

    await act(async () => {
      render(<RegistroPage />);
    });

    await act(async () => {
      fireEvent.click(
        screen.getByRole("button", { name: /Registrarse con Google/i })
      );
    });

    expect(authActions.signInWithGoogleAction).toHaveBeenCalledWith(
      "/onboarding/rubro"
    );
  });

  it("muestra error cuando falla el registro con Google", async () => {
    vi.mocked(authActions.signInWithGoogleAction).mockResolvedValue({
      success: false,
      error: "Error OAuth Google",
    });

    await act(async () => {
      render(<RegistroPage />);
    });

    await act(async () => {
      fireEvent.click(
        screen.getByRole("button", { name: /Registrarse con Google/i })
      );
    });

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent("Error OAuth Google");
    });
  });
});
