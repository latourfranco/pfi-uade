"use client";

import { useState, useTransition } from "react";
import { Building2, Globe, Users, Briefcase, CheckCircle2, AlertCircle, Loader2, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { ClientePerfil } from "@/repositories/cliente-cuenta.repository";
import type { ClienteIntegracionFuente } from "@/repositories/cliente-integracion.repository";
import { actualizarPerfilInstitucionalAction } from "@/app/actions/cuenta";

interface PerfilInstitucionalCardProps {
  perfil: ClientePerfil | null;
  integracion: ClienteIntegracionFuente | null;
  clienteId?: string;
}

const RUBROS = [
  "E-commerce",
  "Fintech",
  "SaaS / Software",
  "Salud & Bienestar",
  "Banca & Seguros",
  "Educación",
  "Otro",
];

const TAMANOS = [
  "1-10",
  "11-49",
  "50-249",
  "250+",
];

export function PerfilInstitucionalCard({
  perfil,
  integracion,
  clienteId,
}: PerfilInstitucionalCardProps) {
  const [nombre, setNombre] = useState(
    perfil?.nombre_organizacion || "Eureka Fintech S.A."
  );
  const [rubro, setRubro] = useState(perfil?.rubro || "Fintech");
  const [tamanoEquipo, setTamanoEquipo] = useState(
    perfil?.tamano_equipo || "50-249"
  );
  const [dominioUrl, setDominioUrl] = useState(
    perfil?.dominio_url || "https://eureka.io"
  );

  const [feedback, setFeedback] = useState<{
    type: "success" | "error";
    message: string;
  } | null>(null);

  const [isPending, startTransition] = useTransition();

  const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setFeedback(null);

    const formData = new FormData();
    if (clienteId) formData.set("clienteId", clienteId);
    formData.set("nombreOrganizacion", nombre);
    formData.set("rubro", rubro);
    formData.set("tamanoEquipo", tamanoEquipo);
    formData.set("dominioUrl", dominioUrl);

    startTransition(async () => {
      try {
        const res = await actualizarPerfilInstitucionalAction(formData);
        if (res.success) {
          setFeedback({
            type: "success",
            message: "Perfil institucional actualizado correctamente.",
          });
        } else {
          setFeedback({
            type: "error",
            message: res.error || "No se pudo actualizar el perfil.",
          });
        }
      } catch {
        setFeedback({
          type: "error",
          message: "Error de conexión al actualizar el perfil.",
        });
      }
    });
  };

  return (
    <section className="rounded-2xl border border-neutral-200/90 bg-white p-6 sm:p-7 shadow-xs">
      <div className="flex items-center gap-2.5 mb-5">
        <div className="p-2 rounded-xl bg-neutral-100 text-neutral-800 shrink-0">
          <Building2 className="w-5 h-5" />
        </div>
        <div>
          <h2 className="text-lg sm:text-xl font-bold text-neutral-900 tracking-tight">
            Perfil Institucional
          </h2>
          <p className="text-xs text-neutral-500">
            Administrá los datos clave de tu organización y la vinculación con el Data Warehouse.
          </p>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4 text-left">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {/* Nombre Organización */}
          <div className="space-y-1">
            <label
              htmlFor="nombreOrganizacion"
              className="block text-xs font-semibold text-neutral-700"
            >
              Nombre de la institución o empresa
            </label>
            <div className="relative">
              <input
                id="nombreOrganizacion"
                name="nombreOrganizacion"
                type="text"
                value={nombre}
                onChange={(e) => setNombre(e.target.value)}
                required
                className="w-full px-3 py-2 text-sm rounded-lg border border-neutral-300 focus:outline-none focus:ring-2 focus:ring-eureka-primary/30 focus:border-eureka-primary text-neutral-900"
              />
            </div>
          </div>

          {/* Dominio / URL */}
          <div className="space-y-1">
            <label
              htmlFor="dominioUrl"
              className="block text-xs font-semibold text-neutral-700"
            >
              Sitio web o dominio oficial
            </label>
            <div className="relative">
              <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-neutral-400">
                <Globe className="w-4 h-4" />
              </div>
              <input
                id="dominioUrl"
                name="dominioUrl"
                type="text"
                value={dominioUrl}
                onChange={(e) => setDominioUrl(e.target.value)}
                className="w-full pl-9 pr-3 py-2 text-sm rounded-lg border border-neutral-300 focus:outline-none focus:ring-2 focus:ring-eureka-primary/30 focus:border-eureka-primary text-neutral-900"
              />
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {/* Rubro */}
          <div className="space-y-1">
            <label
              htmlFor="rubro"
              className="block text-xs font-semibold text-neutral-700"
            >
              Rubro o industria
            </label>
            <div className="relative">
              <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-neutral-400">
                <Briefcase className="w-4 h-4" />
              </div>
              <select
                id="rubro"
                name="rubro"
                value={rubro}
                onChange={(e) => setRubro(e.target.value)}
                className="w-full pl-9 pr-3 py-2 text-sm rounded-lg border border-neutral-300 focus:outline-none focus:ring-2 focus:ring-eureka-primary/30 focus:border-eureka-primary text-neutral-900 bg-white cursor-pointer"
              >
                {RUBROS.map((r) => (
                  <option key={r} value={r}>
                    {r}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Tamaño de equipo */}
          <div className="space-y-1">
            <label
              htmlFor="tamanoEquipo"
              className="block text-xs font-semibold text-neutral-700"
            >
              Tamaño del equipo (empleados)
            </label>
            <div className="relative">
              <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-neutral-400">
                <Users className="w-4 h-4" />
              </div>
              <select
                id="tamanoEquipo"
                name="tamanoEquipo"
                value={tamanoEquipo}
                onChange={(e) => setTamanoEquipo(e.target.value)}
                className="w-full pl-9 pr-3 py-2 text-sm rounded-lg border border-neutral-300 focus:outline-none focus:ring-2 focus:ring-eureka-primary/30 focus:border-eureka-primary text-neutral-900 bg-white cursor-pointer"
              >
                {TAMANOS.map((t) => (
                  <option key={t} value={t}>
                    {t} personas
                  </option>
                ))}
              </select>
            </div>
          </div>
        </div>

        {/* Estado de la integración de Analítica / Data Warehouse */}
        <div className="rounded-xl border border-neutral-200/90 bg-neutral-50/70 p-4 mt-2">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-bold text-neutral-800 uppercase tracking-wider">
              Fuente de Analítica Conectada
            </span>
            <span
              className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold ${
                integracion?.activo
                  ? "bg-emerald-100 text-emerald-800 border border-emerald-200"
                  : "bg-neutral-200 text-neutral-700"
              }`}
            >
              <span
                className={`w-1.5 h-1.5 rounded-full ${
                  integracion?.activo ? "bg-emerald-500 animate-pulse" : "bg-neutral-400"
                }`}
              />
              {integracion?.activo ? "Activa y sincronizada" : "Sin conexión activa"}
            </span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 text-xs text-neutral-600">
            <div>
              <span className="text-neutral-400 block">Propiedad GA4:</span>
              <span className="font-mono font-medium text-neutral-800">
                {integracion?.ga4_property_id || "No vinculada"}
              </span>
            </div>
            <div>
              <span className="text-neutral-400 block">Proyecto GCP BigQuery:</span>
              <span className="font-mono font-medium text-neutral-800 truncate block">
                {integracion?.client_gcp_project_id || "dw-client-default"}
              </span>
            </div>
            <div>
              <span className="text-neutral-400 block">Región de Almacenamiento:</span>
              <span className="font-mono font-medium text-neutral-800">
                {integracion?.gcp_region || "us-central1"}
              </span>
            </div>
          </div>
        </div>

        {feedback && (
          <div
            role="alert"
            className={`p-3 rounded-lg text-xs font-medium flex items-center gap-2 ${
              feedback.type === "success"
                ? "bg-emerald-50 text-emerald-800 border border-emerald-200"
                : "bg-red-50 text-red-800 border border-red-200"
            }`}
          >
            {feedback.type === "success" ? (
              <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
            ) : (
              <AlertCircle className="w-4 h-4 text-red-600 shrink-0" />
            )}
            <span>{feedback.message}</span>
          </div>
        )}

        <div className="flex justify-end pt-2">
          <Button
            type="submit"
            disabled={isPending}
            className="bg-eureka-primary hover:bg-eureka-primary/90 text-white font-medium px-5 py-2 rounded-xl text-sm cursor-pointer shadow-xs"
          >
            {isPending ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin mr-1.5" />
                Guardando...
              </>
            ) : (
              <>
                <Sparkles className="w-3.5 h-3.5 mr-1" />
                Guardar cambios
              </>
            )}
          </Button>
        </div>
      </form>
    </section>
  );
}
