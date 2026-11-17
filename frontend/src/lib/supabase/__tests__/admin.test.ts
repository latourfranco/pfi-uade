import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { getSupabaseAdmin } from '../admin';
import * as supabaseModule from '@supabase/supabase-js';

vi.mock('@supabase/supabase-js', () => ({
  createClient: vi.fn(),
}));

describe('getSupabaseAdmin', () => {
  const originalEnv = process.env;

  beforeEach(() => {
    vi.resetModules();
    process.env = { ...originalEnv };
  });

  afterEach(() => {
    process.env = originalEnv;
    vi.clearAllMocks();
  });

  it('lanza un error si NEXT_PUBLIC_SUPABASE_URL no está definida', () => {
    delete process.env.NEXT_PUBLIC_SUPABASE_URL;
    process.env.SUPABASE_SERVICE_ROLE_KEY = 'test-key';

    expect(() => getSupabaseAdmin()).toThrowError(
      'Configuración de Supabase incompleta: NEXT_PUBLIC_SUPABASE_URL o SUPABASE_SERVICE_ROLE_KEY no están definidas.'
    );
  });

  it('lanza un error si SUPABASE_SERVICE_ROLE_KEY no está definida', () => {
    process.env.NEXT_PUBLIC_SUPABASE_URL = 'https://xyz.supabase.co';
    delete process.env.SUPABASE_SERVICE_ROLE_KEY;

    expect(() => getSupabaseAdmin()).toThrowError(
      'Configuración de Supabase incompleta: NEXT_PUBLIC_SUPABASE_URL o SUPABASE_SERVICE_ROLE_KEY no están definidas.'
    );
  });

  it('lanza un error si ambas variables de entorno faltan', () => {
    delete process.env.NEXT_PUBLIC_SUPABASE_URL;
    delete process.env.SUPABASE_SERVICE_ROLE_KEY;

    expect(() => getSupabaseAdmin()).toThrowError(
      'Configuración de Supabase incompleta: NEXT_PUBLIC_SUPABASE_URL o SUPABASE_SERVICE_ROLE_KEY no están definidas.'
    );
  });

  it('crea e inicializa el cliente con persistSession y autoRefreshToken en false', () => {
    process.env.NEXT_PUBLIC_SUPABASE_URL = 'https://xyz.supabase.co';
    process.env.SUPABASE_SERVICE_ROLE_KEY = 'service-role-secret';

    const mockClient = { from: vi.fn() };
    vi.mocked(supabaseModule.createClient).mockReturnValue(
      mockClient as unknown as ReturnType<typeof supabaseModule.createClient>
    );

    const client = getSupabaseAdmin();

    expect(supabaseModule.createClient).toHaveBeenCalledWith(
      'https://xyz.supabase.co',
      'service-role-secret',
      {
        auth: {
          persistSession: false,
          autoRefreshToken: false,
        },
      }
    );
    expect(client).toBe(mockClient);
  });
});
