import { Suspense } from "react";
import type { Metadata } from "next";
import { obtenerInformacionCuenta } from "@/app/actions/cuenta";
import { CuentaView } from "@/components/cuenta/cuenta-view";

export const metadata: Metadata = {
  title: "eureka | Configuración de Cuenta y Supresión de Datos",
  description:
    "Administración del perfil institucional y ejercicio del derecho de supresión de datos.",
};

export default async function CuentaPage() {
  const { perfil, integracion } = await obtenerInformacionCuenta();

  return (
    <Suspense fallback={<div className="min-h-screen bg-[#FAF9F5] p-10" />}>
      <CuentaView perfil={perfil} integracion={integracion} />
    </Suspense>
  );
}
