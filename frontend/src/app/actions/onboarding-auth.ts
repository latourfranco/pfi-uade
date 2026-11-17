"use server";

import { encryptAes256GcmBase64Url } from "@/lib/server/aes-gcm";

/**
 * Server Action that encrypts serialized onboarding credentials or session state
 * using AES-256-GCM and AES_ENCRYPTION_KEY.
 */
export async function encryptOnboardingPayloadAction(jsonPlaintext: string): Promise<string> {
  return encryptAes256GcmBase64Url(jsonPlaintext);
}
