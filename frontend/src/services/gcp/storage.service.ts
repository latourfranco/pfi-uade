import { Storage } from "@google-cloud/storage";

// Cache en memoria para URLs firmadas (evita firmas repetidas en el mismo proceso de servidor)
const signedUrlCache = new Map<string, { url: string; expiresAt: number }>();

function getStorageClient(): Storage | null {
  try {
    if (process.env.GCP_SERVICE_ACCOUNT_KEY) {
      const raw = process.env.GCP_SERVICE_ACCOUNT_KEY.trim();
      const credentials = JSON.parse(raw);
      return new Storage({
        projectId: credentials.project_id,
        credentials: {
          client_email: credentials.client_email,
          private_key: credentials.private_key?.replace(/\\n/g, "\n"),
        },
      });
    }

    if (process.env.GOOGLE_APPLICATION_CREDENTIALS) {
      return new Storage({
        keyFilename: process.env.GOOGLE_APPLICATION_CREDENTIALS,
      });
    }

    return new Storage();
  } catch (error) {
    console.error("[StorageService] Error al inicializar cliente de GCS:", error);
    return null;
  }
}

let storageInstance: Storage | null = null;
function getStorage(): Storage | null {
  if (!storageInstance) {
    storageInstance = getStorageClient();
  }
  return storageInstance;
}

/**
 * Parsea un URI de GCS con formato gs://bucket/nombre-archivo
 */
export function parseGcsUri(gcsUri: string): { bucket: string; fileName: string } | null {
  if (!gcsUri || !gcsUri.startsWith("gs://")) {
    return null;
  }
  const cleanPath = gcsUri.replace(/^gs:\/\//, "");
  const firstSlashIndex = cleanPath.indexOf("/");
  if (firstSlashIndex === -1) {
    return null;
  }
  return {
    bucket: cleanPath.slice(0, firstSlashIndex),
    fileName: cleanPath.slice(firstSlashIndex + 1),
  };
}

/**
 * Resuelve de forma inteligente el archivo real en GCS.
 * Si el archivo exacto no existe (por ejemplo debido a variaciones mínimas de timestamp),
 * busca el archivo más reciente que coincida con el hash y el número de paso.
 */
async function resolveExistingFileName(
  storage: Storage,
  bucketName: string,
  fileName: string
): Promise<string> {
  const bucket = storage.bucket(bucketName);
  try {
    const file = bucket.file(fileName);
    const [exists] = await file.exists();
    if (exists) {
      return fileName;
    }

    // Buscar por prefijo {hash}_1_step_{numeroPaso}_
    const prefixMatch = fileName.match(/^([a-f0-9]{32,64}_1_step_\d+_)/);
    if (prefixMatch) {
      const prefix = prefixMatch[1];
      const [files] = await bucket.getFiles({ prefix, maxResults: 10 });
      if (files.length > 0) {
        const sorted = files.map((f) => f.name).sort();
        const best = sorted[sorted.length - 1];
        console.log(`[StorageService] Captura remapeada a archivo existente en GCS: '${fileName}' -> '${best}'`);
        return best;
      }
    }
  } catch (err) {
    console.warn(`[StorageService] Error al verificar existencia en GCS de ${fileName}:`, err);
  }

  return fileName;
}

/**
 * Genera una Signed URL v4 con expiración temporal para un archivo privado en GCS.
 * Si falla o no hay credenciales, devuelve `undefined` para que la UI muestre el placeholder.
 */
export async function getSignedCaptureUrl(
  gcsUri: string | null | undefined,
  expiresInMinutes = 60
): Promise<string | undefined> {
  if (!gcsUri) return undefined;

  // Si ya es una URL HTTP(S) o ruta local, devolverla directamente
  if (gcsUri.startsWith("http://") || gcsUri.startsWith("https://") || gcsUri.startsWith("/")) {
    return gcsUri;
  }

  const parsed = parseGcsUri(gcsUri);
  if (!parsed) {
    console.warn(`[StorageService] Formato GCS inválido: ${gcsUri}`);
    return undefined;
  }

  // Verificar cache en memoria (con 5 minutos de margen antes de expirar)
  const cached = signedUrlCache.get(gcsUri);
  const now = Date.now();
  if (cached && cached.expiresAt > now + 5 * 60 * 1000) {
    return cached.url;
  }

  const storage = getStorage();
  if (!storage) {
    console.warn("[StorageService] Cliente de Storage no disponible.");
    return undefined;
  }

  try {
    const actualFileName = await resolveExistingFileName(storage, parsed.bucket, parsed.fileName);
    const expiresAt = now + expiresInMinutes * 60 * 1000;

    const [signedUrl] = await storage
      .bucket(parsed.bucket)
      .file(actualFileName)
      .getSignedUrl({
        version: "v4",
        action: "read",
        expires: expiresAt,
      });

    signedUrlCache.set(gcsUri, { url: signedUrl, expiresAt });
    return signedUrl;
  } catch (error) {
    console.error(`[StorageService] Error al generar Signed URL para ${gcsUri}:`, error);
    return undefined;
  }
}
