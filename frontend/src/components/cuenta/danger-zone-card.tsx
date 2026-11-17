"use client";

import { useState } from "react";
import { AlertTriangle, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ModalConfirmacionBaja } from "./modal-confirmacion-baja";

interface DangerZoneCardProps {
  clienteId?: string;
}

export function DangerZoneCard({ clienteId }: DangerZoneCardProps) {
  const [isModalOpen, setIsModalOpen] = useState(false);

  return (
    <section
      data-testid="danger-zone-section"
      className="rounded-2xl border border-red-300/80 bg-red-50/40 p-6 sm:p-7 shadow-xs relative overflow-hidden transition-all duration-200"
    >
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-5">
        <div className="space-y-1.5 max-w-xl">
          <div className="inline-flex items-center gap-2 text-red-600 font-bold text-sm tracking-wide uppercase">
            <AlertTriangle className="w-4 h-4 text-red-600" />
            <span>Zona de peligro</span>
          </div>
          <h3 className="text-lg sm:text-xl font-bold text-neutral-900 tracking-tight">
            Baja definitiva de la cuenta
          </h3>
          <p className="text-xs sm:text-sm text-neutral-600 leading-relaxed">
            Tramita la supresión total e irreversible de tu cuenta institucional.
            Se revocarán los accesos OAuth concedidos a Google, se invalidarán
            todas las cookies de sesión y se ordenará la purga de datos tanto
            en la base transaccional como en el Data Warehouse (BigQuery).
          </p>
        </div>

        <Button
          type="button"
          onClick={() => setIsModalOpen(true)}
          className="bg-red-600 hover:bg-red-700 text-white font-medium px-4 py-2 text-sm rounded-xl shrink-0 cursor-pointer shadow-sm hover:shadow-md transition-all inline-flex items-center gap-2"
        >
          <Trash2 className="w-4 h-4" />
          <span>Tramitar baja definitiva</span>
        </Button>
      </div>

      <ModalConfirmacionBaja
        isOpen={isModalOpen}
        onOpenChange={setIsModalOpen}
        clienteId={clienteId}
      />
    </section>
  );
}
