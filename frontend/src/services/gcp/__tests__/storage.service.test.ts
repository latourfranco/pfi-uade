import { describe, it, expect, vi, beforeEach } from "vitest";

const { mockGetSignedUrl, mockExists, mockGetFiles } = vi.hoisted(() => ({
  mockGetSignedUrl: vi.fn(),
  mockExists: vi.fn(),
  mockGetFiles: vi.fn(),
}));

vi.mock("@google-cloud/storage", () => {
  return {
    Storage: class MockStorage {
      bucket() {
        return {
          file: () => ({
            exists: mockExists,
            getSignedUrl: mockGetSignedUrl,
          }),
          getFiles: mockGetFiles,
        };
      }
    },
  };
});

import { parseGcsUri, getSignedCaptureUrl } from "../storage.service";

describe("storage.service", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("parseGcsUri", () => {
    it("parsea correctamente un URI gs:// válido", () => {
      expect(parseGcsUri("gs://pruebas-pfi-evidencias/folder/step_1.webp")).toEqual({
        bucket: "pruebas-pfi-evidencias",
        fileName: "folder/step_1.webp",
      });
    });

    it("retorna null si el URI no empieza con gs:// o no tiene slash", () => {
      expect(parseGcsUri("")).toBeNull();
      expect(parseGcsUri("https://example.com/img.png")).toBeNull();
      expect(parseGcsUri("gs://solo-bucket")).toBeNull();
    });
  });

  describe("getSignedCaptureUrl", () => {
    it("retorna undefined si gcsUri es nulo o vacío", async () => {
      expect(await getSignedCaptureUrl(null)).toBeUndefined();
      expect(await getSignedCaptureUrl(undefined)).toBeUndefined();
      expect(await getSignedCaptureUrl("")).toBeUndefined();
    });

    it("retorna directamente URLs HTTP(S) o rutas locales", async () => {
      expect(await getSignedCaptureUrl("https://cdn.example.com/a.webp")).toBe(
        "https://cdn.example.com/a.webp"
      );
      expect(await getSignedCaptureUrl("http://localhost:3000/a.png")).toBe(
        "http://localhost:3000/a.png"
      );
      expect(await getSignedCaptureUrl("/captures/local.png")).toBe("/captures/local.png");
    });

    it("retorna undefined cuando el formato gs:// es inválido", async () => {
      expect(await getSignedCaptureUrl("gs://bucket-sin-archivo")).toBeUndefined();
    });

    it("genera Signed URL v4 y usa cache en memoria en llamadas repetidas", async () => {
      mockExists.mockResolvedValueOnce([true]);
      mockGetSignedUrl.mockResolvedValueOnce(["https://storage.googleapis.com/signed-v4-url"]);

      const uri = "gs://pruebas-pfi-evidencias/abc123_1_step_1_1000.webp";
      const first = await getSignedCaptureUrl(uri);
      const second = await getSignedCaptureUrl(uri);

      expect(first).toBe("https://storage.googleapis.com/signed-v4-url");
      expect(second).toBe("https://storage.googleapis.com/signed-v4-url");
      expect(mockGetSignedUrl).toHaveBeenCalledTimes(1);
    });

    it("remapea por prefijo cuando el archivo exacto no existe en GCS", async () => {
      const hash = "a".repeat(32);
      const originalUri = `gs://pruebas-pfi-evidencias/${hash}_1_step_2_old.webp`;
      const resolvedName = `${hash}_1_step_2_new.webp`;

      mockExists.mockResolvedValueOnce([false]);
      mockGetFiles.mockResolvedValueOnce([[{ name: resolvedName }]]);
      mockGetSignedUrl.mockResolvedValueOnce(["https://storage.googleapis.com/remapped-url"]);

      const url = await getSignedCaptureUrl(originalUri);
      expect(url).toBe("https://storage.googleapis.com/remapped-url");
      expect(mockGetFiles).toHaveBeenCalledWith({
        prefix: `${hash}_1_step_2_`,
        maxResults: 10,
      });
    });

    it("retorna undefined si ocurre un error al firmar la URL", async () => {
      mockExists.mockRejectedValueOnce(new Error("GCS unreachable"));
      mockGetSignedUrl.mockRejectedValueOnce(new Error("Sign failed"));

      const url = await getSignedCaptureUrl("gs://pruebas-pfi-evidencias/fail_step.webp");
      expect(url).toBeUndefined();
    });
  });
});
