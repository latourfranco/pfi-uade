import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";

const { mockGetDetailById, mockNotFound } = vi.hoisted(() => ({
  mockGetDetailById: vi.fn(),
  mockNotFound: vi.fn(() => {
    throw new Error("NEXT_NOT_FOUND");
  }),
}));

vi.mock("@/repositories/friccion.repository", () => ({
  FriccionRepository: {
    getDetailById: mockGetDetailById,
  },
}));

vi.mock("next/navigation", () => ({
  notFound: mockNotFound,
  useSearchParams: () => new URLSearchParams(),
}));

vi.mock("@/components/dashboard/friction-detail/friction-detail-view", () => ({
  FrictionDetailView: ({ data, eventId }: { data: { id: string }; eventId?: string }) => (
    <div data-testid="friction-detail-view">
      {data.id}:{eventId ?? "none"}
    </div>
  ),
}));

import FrictionDetailPage from "../page";

describe("FrictionDetailPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renderiza FrictionDetailView cuando la fricción existe", async () => {
    mockGetDetailById.mockResolvedValueOnce({ id: "pat-1" });

    const jsx = await FrictionDetailPage({
      params: Promise.resolve({ id: "pat-1" }),
      searchParams: Promise.resolve({ event: "begin_checkout" }),
    });
    render(jsx);

    expect(mockGetDetailById).toHaveBeenCalledWith("pat-1");
    expect(await screen.findByTestId("friction-detail-view")).toHaveTextContent(
      "pat-1:begin_checkout"
    );
  });

  it("renderiza correctamente sin searchParams", async () => {
    mockGetDetailById.mockResolvedValueOnce({ id: "pat-2" });

    const jsx = await FrictionDetailPage({
      params: Promise.resolve({ id: "pat-2" }),
    });
    render(jsx);

    expect(await screen.findByTestId("friction-detail-view")).toHaveTextContent("pat-2:none");
  });

  it("invoca notFound() cuando getDetailById retorna null", async () => {
    mockGetDetailById.mockResolvedValueOnce(null);

    await expect(
      FrictionDetailPage({
        params: Promise.resolve({ id: "missing-id" }),
      })
    ).rejects.toThrow("NEXT_NOT_FOUND");

    expect(mockNotFound).toHaveBeenCalledTimes(1);
  });
});
