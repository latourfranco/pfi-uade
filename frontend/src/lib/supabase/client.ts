import { createBrowserClient } from "@supabase/ssr";

/**
 * Cliente de Supabase para componentes de navegador (Client Components).
 */
export function createSupabaseBrowserClient() {
  const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

  if (!supabaseUrl || !supabaseAnonKey) {
    throw new Error(
      "Configuración de Supabase incompleta: NEXT_PUBLIC_SUPABASE_URL o NEXT_PUBLIC_SUPABASE_ANON_KEY no están definidas."
    );
  }

  return createBrowserClient(supabaseUrl, supabaseAnonKey);
}
