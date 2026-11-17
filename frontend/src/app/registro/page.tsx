"use client";

import { useState } from "react";
import Link from "next/link";
import { AlertCircle, Loader2 } from "lucide-react";
import { EurekaLogo } from "@/components/brand/eureka-logo";
import { signInWithGoogleAction } from "@/app/actions/auth";

function GoogleIcon() {
  return (
    <svg className="w-4 h-4 shrink-0" viewBox="0 0 24 24" aria-hidden="true">
      <path
        fill="#4285F4"
        d="M23.745 12.27c0-.79-.07-1.54-.19-2.27H12v4.51h6.6c-.29 1.52-1.14 2.82-2.4 3.68v3.05h3.88c2.27-2.09 3.665-5.17 3.665-8.97z"
      />
      <path
        fill="#34A853"
        d="M12 24c3.3 0 6.08-1.09 8.1-2.96l-3.88-3.05c-1.09.73-2.48 1.16-4.22 1.16-3.24 0-5.99-2.19-6.97-5.13H1.04v3.14C3.05 21.14 7.21 24 12 24z"
      />
      <path
        fill="#FBBC05"
        d="M5.03 14.02A7.18 7.18 0 0 1 4.65 12c0-.7.13-1.38.38-2.02V6.84H1.04A11.97 11.97 0 0 0 0 12c0 1.93.46 3.76 1.04 5.16l3.99-3.14z"
      />
      <path
        fill="#EA4335"
        d="M12 4.85c1.8 0 3.41.62 4.68 1.83l3.51-3.51C18.07 1.19 15.3 0 12 0 7.21 0 3.05 2.86 1.04 6.84l3.99 3.14c.98-2.94 3.73-5.13 6.97-5.13z"
      />
    </svg>
  );
}

export default function RegistroPage() {
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleGoogleRegister = async () => {
    setError(null);
    setIsSubmitting(true);

    const result = await signInWithGoogleAction("/onboarding/rubro");
    if (result && !result.success) {
      setError(result.error || "No pudimos crear tu cuenta con Google.");
      setIsSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen w-full bg-[#FAF9F5] flex flex-col justify-between p-6 sm:p-10 md:p-14 selection:bg-eureka-primary/20 selection:text-[#4F46E5]">
      <header className="w-full max-w-5xl mx-auto flex items-center justify-between">
        <Link href="/" className="cursor-pointer">
          <EurekaLogo size="md" />
        </Link>
        <Link
          href="/login"
          className="text-xs sm:text-sm font-medium text-neutral-600 hover:text-eureka-primary transition-colors"
        >
          ¿Ya tenés cuenta? Iniciar sesión
        </Link>
      </header>

      <main className="w-full max-w-md mx-auto my-10">
        <div className="rounded-2xl border border-neutral-200/90 bg-white p-7 sm:p-9 shadow-sm">
          <div className="mb-6">
            <h1 className="text-2xl sm:text-3xl font-bold text-eureka-dark tracking-tight">
              Crear cuenta
            </h1>
            <p className="text-sm text-neutral-500 mt-1.5">
              Registrate con Google y completá el onboarding para activar tu radar.
            </p>
          </div>

          {error && (
            <div
              role="alert"
              className="mb-5 flex items-start gap-2.5 rounded-xl border border-red-200 bg-red-50/80 px-3.5 py-3 text-xs sm:text-sm text-red-700"
            >
              <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
              <span>{error}</span>
            </div>
          )}

          <button
            type="button"
            onClick={handleGoogleRegister}
            disabled={isSubmitting}
            className="w-full inline-flex items-center justify-center gap-3 rounded-xl border border-neutral-200 bg-white hover:bg-neutral-50 disabled:opacity-60 text-neutral-800 font-medium text-sm py-3.5 px-5 shadow-xs transition-all cursor-pointer"
          >
            {isSubmitting ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin text-eureka-primary" />
                <span>Conectando con Google...</span>
              </>
            ) : (
              <>
                <GoogleIcon />
                <span>Registrarse con Google</span>
              </>
            )}
          </button>

          <p className="mt-6 text-center text-xs sm:text-sm text-neutral-500">
            ¿Ya tenés una cuenta?{" "}
            <Link
              href="/login"
              className="font-semibold text-eureka-primary hover:underline"
            >
              Iniciar sesión
            </Link>
          </p>
        </div>
      </main>

      <footer className="w-full max-w-5xl mx-auto text-center text-xs text-neutral-400">
        eureka — Radar autónomo de fricciones digitales
      </footer>
    </div>
  );
}
