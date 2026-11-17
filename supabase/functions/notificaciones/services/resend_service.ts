export interface EnviarEmailParams {
  from: string;
  to: string[];
  subject: string;
  html: string;
}

export class ResendApiError extends Error {
  readonly status: number;
  readonly esTransitorio: boolean;
  readonly esGlobal: boolean;

  constructor(status: number, detalle: string) {
    super(`Fallo en Resend API (${status}): ${detalle}`);
    this.name = "ResendApiError";
    this.status = status;
    this.esTransitorio = status === 429 || status >= 500;
    this.esGlobal = status === 401 || status === 403 || status === 429 || status >= 500;
  }
}

export async function enviarEmailTransaccional(
  apiKey: string,
  params: EnviarEmailParams,
  fetchFn: typeof fetch = fetch,
): Promise<{ id: string }> {
  const response = await fetchFn("https://api.resend.com/emails", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${apiKey}`,
    },
    body: JSON.stringify(params),
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new ResendApiError(response.status, errorText);
  }

  return await response.json();
}
