import { encryptOnboardingPayloadAction } from "@/app/actions/onboarding-auth";

export type OnboardingAuthMode = "none" | "credentials" | "storage_state";

export interface StoredOnboardingAuth {
  mode: OnboardingAuthMode;
  encrypted: boolean;
  ciphertext: string;
  usernameHint?: string;
}

export const ONBOARDING_AUTH_STORAGE_KEY = "eureka_onboarding_auth";

/**
 * Validates that a string is a non-empty JSON object representing a pre-authenticated session.
 */
export function validateStorageStateJson(raw: string): boolean {
  const trimmed = raw.trim();
  if (!trimmed) return false;
  try {
    const parsed: unknown = JSON.parse(trimmed);
    return typeof parsed === "object" && parsed !== null && !Array.isArray(parsed);
  } catch {
    return false;
  }
}

/**
 * Saves onboarding authentication configuration encrypted in sessionStorage.
 */
export async function saveOnboardingAuth(params: {
  mode: OnboardingAuthMode;
  username?: string;
  password?: string;
  storageStateJson?: string;
}): Promise<void> {
  if (typeof window === "undefined") return;

  if (params.mode === "none") {
    sessionStorage.removeItem(ONBOARDING_AUTH_STORAGE_KEY);
    return;
  }

  const secretPayload =
    params.mode === "credentials"
      ? JSON.stringify({ username: params.username ?? "", password: params.password ?? "" })
      : JSON.stringify(JSON.parse((params.storageStateJson ?? "{}").trim()));

  const ciphertext = await encryptOnboardingPayloadAction(secretPayload);
  const record: StoredOnboardingAuth = {
    mode: params.mode,
    encrypted: true,
    ciphertext,
    usernameHint: params.mode === "credentials" ? params.username?.trim() : undefined,
  };

  sessionStorage.setItem(ONBOARDING_AUTH_STORAGE_KEY, JSON.stringify(record));
}

/**
 * Reads the stored onboarding auth state from sessionStorage.
 */
export function getStoredOnboardingAuthSnapshot(): string | null {
  if (typeof window === "undefined") return null;
  return sessionStorage.getItem(ONBOARDING_AUTH_STORAGE_KEY);
}

/**
 * Formats a human-readable summary label from a serialized StoredOnboardingAuth string.
 */
export function formatOnboardingAuthSummary(raw: string | null): string {
  if (!raw) return "Sin autenticación";
  try {
    const parsed = JSON.parse(raw) as Partial<StoredOnboardingAuth>;
    if (parsed.mode === "credentials") {
      return parsed.usernameHint
        ? `Usuario y contraseña (${parsed.usernameHint})`
        : "Usuario y contraseña (encriptada)";
    }
    if (parsed.mode === "storage_state") {
      return "Sesión pre-autenticada";
    }
    return "Sin autenticación";
  } catch {
    return "Sin autenticación";
  }
}
