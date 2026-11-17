"use client";

import { useState, useTransition } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { AlertTriangle, Loader2, ShieldAlert } from "lucide-react";
import { solicitarBajaDefinitivaCuentaAction } from "@/app/actions/cuenta";

interface ModalConfirmacionBajaProps {
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
  clienteId?: string;
}

const CONFIRMATION_KEYWORD = "ELIMINAR MI CUENTA";

export function ModalConfirmacionBaja({
  isOpen,
  onOpenChange,
  clienteId,
}: ModalConfirmacionBajaProps) {
  const [confirmText, setConfirmText] = useState("");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();

  const isConfirmed = confirmText.trim() === CONFIRMATION_KEYWORD;

  const handleClose = (open: boolean) => {
    if (isPending) return;
    if (!open) {
      setConfirmText("");
      setErrorMessage(null);
    }
    onOpenChange(open);
  };

  const handleConfirmarBaja = () => {
    if (!isConfirmed || isPending) return;

    setErrorMessage(null);
    startTransition(async () => {
      try {
        const result = await solicitarBajaDefinitivaCuentaAction({
          clienteId,
          confirmacion: confirmText.trim(),
          motivo: "Baja voluntaria definitiva y supresión de datos",
        });

        if (result.success && result.redirectUrl) {
          window.location.href = result.redirectUrl;
        } else {
          setErrorMessage(
            result.error ||
            "Ocurrió un fallo al procesar la baja de la cuenta. Intente nuevamente."
          );
        }
      } catch (err: unknown) {
        setErrorMessage(
          err instanceof Error
            ? err.message
            : "Error de conexión al tramitar la baja definitiva."
        );
      }
    });
  };

  return (
    <Dialog open={isOpen} onOpenChange={handleClose}>
      <DialogContent className="sm:max-w-md border-red-200">
        <DialogHeader>
          <div className="flex items-center gap-2.5 text-red-600 mb-1">
            <div className="p-2 rounded-xl bg-red-100 text-red-600 shrink-0">
              <AlertTriangle className="w-5 h-5" />
            </div>
            <DialogTitle className="text-xl font-bold text-neutral-900">
              Confirmar baja definitiva
            </DialogTitle>
          </div>
          <DialogDescription className="text-sm text-neutral-600 text-left">
            Esta acción es irreversible y ejecutará el ejercicio del derecho de
            supresión de datos sobre toda la telemetría e infraestructura del cliente.
          </DialogDescription>
        </DialogHeader>

        {/* Resumen de efectos irreversibles */}
        <div className="rounded-xl border border-red-200/80 bg-red-50/70 p-3.5 text-xs text-red-950 space-y-2">
          <div className="flex items-start gap-2 font-medium">
            <ShieldAlert className="w-4 h-4 text-red-600 shrink-0 mt-0.5" />
            <span>Al confirmar la solicitud se procederá con:</span>
          </div>
          <ul className="list-disc pl-6 space-y-1 text-neutral-700">
            <li>
              <strong>Revocación de tokens de Google:</strong> Corte de acceso OAuth2 a las propiedades de GA4 y proyectos de GCP.
            </li>
            <li>
              <strong>Invalidación de sesiones:</strong> Destrucción de cookies de sesión activa.
            </li>
            <li>
              <strong>Purga asíncrona:</strong> Eliminación de fuentes en base transaccional y destrucción del dataset en BigQuery Data Warehouse.
            </li>
          </ul>
        </div>

        {/* Formulario de confirmación deliberada */}
        <div className="space-y-2 pt-1 text-left">
          <label
            htmlFor="confirm-delete-input"
            className="block text-xs font-semibold text-neutral-700"
          >
            Para proceder, escribí con exactitud{" "}
            <span className="font-mono text-red-600 bg-red-50 px-1.5 py-0.5 rounded border border-red-200">
              {CONFIRMATION_KEYWORD}
            </span>
          </label>
          <input
            id="confirm-delete-input"
            type="text"
            value={confirmText}
            onChange={(e) => setConfirmText(e.target.value)}
            disabled={isPending}
            placeholder={CONFIRMATION_KEYWORD}
            className="w-full px-3 py-2 text-sm rounded-lg border border-neutral-300 focus:outline-none focus:ring-2 focus:ring-red-500/30 focus:border-red-500 disabled:opacity-50"
            autoComplete="off"
          />
        </div>

        {errorMessage && (
          <div
            role="alert"
            className="p-2.5 rounded-lg bg-red-100 text-red-700 text-xs font-medium border border-red-200"
          >
            {errorMessage}
          </div>
        )}

        <DialogFooter className="mt-2 flex items-center justify-end gap-2">
          <Button
            type="button"
            variant="outline"
            onClick={() => handleClose(false)}
            disabled={isPending}
            className="cursor-pointer"
          >
            Cancelar
          </Button>
          <Button
            type="button"
            variant="destructive"
            onClick={handleConfirmarBaja}
            disabled={!isConfirmed || isPending}
            className="bg-red-600 hover:bg-red-700 text-white font-medium cursor-pointer disabled:cursor-not-allowed disabled:opacity-40"
          >
            {isPending ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin mr-1.5" />
                Revocando y purgando...
              </>
            ) : (
              "Confirmar baja definitiva"
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
