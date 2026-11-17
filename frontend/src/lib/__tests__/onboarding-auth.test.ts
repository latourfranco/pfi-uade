import { describe, it, expect, beforeEach } from "vitest";
import {
  ONBOARDING_AUTH_STORAGE_KEY,
  formatOnboardingAuthSummary,
  getStoredOnboardingAuthSnapshot,
  saveOnboardingAuth,
  validateStorageStateJson,
  type StoredOnboardingAuth,
} from "../onboarding-auth";
import {
  decryptAes256GcmBase64Url,
  encryptAes256GcmBase64Url,
} from "../server/aes-gcm";

describe("aes-gcm & onboarding-auth", () => {
  beforeEach(() => {
    sessionStorage.clear();
  });

  it("encripta y desencripta en formato base64url (nonce 12B + ciphertext + tag 16B)", () => {
    const payload = JSON.stringify({ username: "qa@tienda.com", password: "secret" });
    const token = encryptAes256GcmBase64Url(payload);

    // Base64 URL-safe: sin +, /, =
    expect(token).toMatch(/^[A-Za-z0-9_-]+$/);
    const rawBytes = Buffer.from(token, "base64url");
    expect(rawBytes.length).toBeGreaterThanOrEqual(12 + 16 + payload.length);

    const decrypted = decryptAes256GcmBase64Url(token);
    expect(JSON.parse(decrypted)).toEqual({ username: "qa@tienda.com", password: "secret" });
  });

  it("rechaza claves inválidas o tokens corruptos", () => {
    expect(() => encryptAes256GcmBase64Url("{}", "short")).toThrow(/32 bytes/i);
    expect(() => decryptAes256GcmBase64Url("YWJj")).toThrow(/inválido/i);
  });

  it("valida JSON de sesión pre-autenticada correctamente", () => {
    expect(validateStorageStateJson('{"cookies": [], "origins": []}')).toBe(true);
    expect(validateStorageStateJson("")).toBe(false);
    expect(validateStorageStateJson("[]")).toBe(false);
    expect(validateStorageStateJson("not-json")).toBe(false);
  });

  it("guarda credenciales y storage_state encriptados con AES-256-GCM en sessionStorage", async () => {
    await saveOnboardingAuth({
      mode: "credentials",
      username: "user@tienda.com",
      password: "super-secret-password",
    });

    const raw = getStoredOnboardingAuthSnapshot();
    expect(raw).not.toBeNull();
    expect(raw).not.toContain("super-secret-password");
    const parsed = JSON.parse(raw!) as StoredOnboardingAuth;
    expect(parsed.encrypted).toBe(true);
    expect(JSON.parse(decryptAes256GcmBase64Url(parsed.ciphertext))).toEqual({
      username: "user@tienda.com",
      password: "super-secret-password",
    });
    expect(formatOnboardingAuthSummary(raw)).toBe("Usuario y contraseña (user@tienda.com)");

    await saveOnboardingAuth({
      mode: "storage_state",
      storageStateJson: '{"cookies":[{"name":"sid","value":"abc"}]}',
    });
    const rawStorage = getStoredOnboardingAuthSnapshot();
    expect(rawStorage).not.toContain("abc");
    expect(formatOnboardingAuthSummary(rawStorage)).toBe("Sesión pre-autenticada");

    await saveOnboardingAuth({ mode: "none" });
    expect(sessionStorage.getItem(ONBOARDING_AUTH_STORAGE_KEY)).toBeNull();
    expect(formatOnboardingAuthSummary(null)).toBe("Sin autenticación");
  });

  it("formatea resúmenes inválidos o sin hint", async () => {
    expect(formatOnboardingAuthSummary("invalid-json")).toBe("Sin autenticación");
    expect(formatOnboardingAuthSummary('{"mode":"credentials"}')).toBe(
      "Usuario y contraseña (encriptada)"
    );
    expect(formatOnboardingAuthSummary('{"mode":"none"}')).toBe("Sin autenticación");

    await saveOnboardingAuth({ mode: "credentials" });
    expect(formatOnboardingAuthSummary(getStoredOnboardingAuthSnapshot())).toBe(
      "Usuario y contraseña (encriptada)"
    );
  });
});
