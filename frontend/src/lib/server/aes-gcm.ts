import { createCipheriv, createDecipheriv, randomBytes } from "node:crypto";

const DEFAULT_AES_ENCRYPTION_KEY =
  "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef";

const NONCE_BYTES = 12;
const TAG_BYTES = 16;

function resolveEncryptionKey(hexKey?: string): Buffer {
  const rawHex = (hexKey ?? process.env.AES_ENCRYPTION_KEY ?? DEFAULT_AES_ENCRYPTION_KEY).trim();
  const key = Buffer.from(rawHex, "hex");
  if (key.length !== 32) {
    throw new Error("AES_ENCRYPTION_KEY debe tener 32 bytes (64 caracteres hexadecimales).");
  }
  return key;
}

/**
 * Encrypts a JSON-serialized string using AES-256-GCM and returns a base64url string
 * containing `nonce (12 bytes) + ciphertext + tag (16 bytes)`.
 */
export function encryptAes256GcmBase64Url(jsonPlaintext: string, hexKey?: string): string {
  const key = resolveEncryptionKey(hexKey);
  const nonce = randomBytes(NONCE_BYTES);
  const cipher = createCipheriv("aes-256-gcm", key, nonce);
  const ciphertext = Buffer.concat([cipher.update(jsonPlaintext, "utf8"), cipher.final()]);
  const tag = cipher.getAuthTag();
  return Buffer.concat([nonce, ciphertext, tag]).toString("base64url");
}

/**
 * Decrypts a base64url token formatted as `nonce (12 bytes) + ciphertext + tag (16 bytes)`.
 */
export function decryptAes256GcmBase64Url(token: string, hexKey?: string): string {
  const key = resolveEncryptionKey(hexKey);
  const combined = Buffer.from(token, "base64url");
  if (combined.length < NONCE_BYTES + TAG_BYTES) {
    throw new Error("Token encriptado inválido.");
  }
  const nonce = combined.subarray(0, NONCE_BYTES);
  const tag = combined.subarray(combined.length - TAG_BYTES);
  const ciphertext = combined.subarray(NONCE_BYTES, combined.length - TAG_BYTES);

  const decipher = createDecipheriv("aes-256-gcm", key, nonce);
  decipher.setAuthTag(tag);
  return Buffer.concat([decipher.update(ciphertext), decipher.final()]).toString("utf8");
}
