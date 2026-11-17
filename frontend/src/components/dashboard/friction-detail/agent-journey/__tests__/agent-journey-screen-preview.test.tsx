import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, act } from '@testing-library/react';
import { AgentJourneyScreenPreview } from '../agent-journey-screen-preview';
import type { AgentJourneyStep } from '@/lib/friction-data';
import { createMockFrictionDetail } from '../../__tests__/test-fixtures';

describe('AgentJourneyScreenPreview Component', () => {
  const baseSteps = createMockFrictionDetail().agentJourney.steps;
  const steps: AgentJourneyStep[] = [
    { ...baseSteps[0], imageSrc: 'https://cdn.example.com/step-1.webp' },
    { ...baseSteps[1], imageSrc: 'https://cdn.example.com/step-2.webp' },
    { ...baseSteps[1], stepNumber: 3, title: 'Paso 3', imageSrc: 'https://cdn.example.com/step-3.webp' },
  ];

  it('renderiza la barra de URL del navegador y la captura correspondiente', async () => {
    await act(async () => {
      render(
        <AgentJourneyScreenPreview
          steps={steps}
          selectedStepIndex={0}
        />
      );
    });

    expect(screen.getByText(steps[0].url!)).toBeInTheDocument();
  });

  it('permite abrir y cerrar el modo pantalla completa mediante botón y tecla Escape', async () => {
    await act(async () => {
      render(
        <AgentJourneyScreenPreview
          steps={steps}
          selectedStepIndex={0}
        />
      );
    });

    // Abrir pantalla completa mediante el botón de zoom
    const zoomButton = screen.getByRole('button', { name: /ver captura en pantalla completa/i });
    await act(async () => {
      fireEvent.click(zoomButton);
    });

    // En pantalla completa se renderiza el botón de cerrar
    const closeButton = screen.getByRole('button', { name: /cerrar pantalla completa/i });
    expect(closeButton).toBeInTheDocument();
    expect(document.body.style.overflow).toBe('hidden');

    // Cerrar con Escape
    await act(async () => {
      window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));
    });

    expect(screen.queryByRole('button', { name: /cerrar pantalla completa/i })).not.toBeInTheDocument();
    expect(document.body.style.overflow).toBe('unset');
  });

  it('avanza al siguiente paso al hacer scroll con la rueda hacia abajo', async () => {
    const handleSelectStep = vi.fn();

    let container: HTMLElement;
    await act(async () => {
      const res = render(
        <AgentJourneyScreenPreview
          steps={steps}
          selectedStepIndex={1}
          onSelectStep={handleSelectStep}
        />
      );
      container = res.container;
      await Promise.resolve();
    });

    await act(async () => {
      await Promise.resolve();
    });

    const frameEl = container!.querySelector('.cursor-ns-resize')!;

    await act(async () => {
      fireEvent.wheel(frameEl, { deltaY: 100 });
    });
    expect(handleSelectStep).toHaveBeenCalledWith(2);
  });

  it('retrocede al paso anterior al hacer scroll con la rueda hacia arriba', async () => {
    const handleSelectStep = vi.fn();

    let container: HTMLElement;
    await act(async () => {
      const res = render(
        <AgentJourneyScreenPreview
          steps={steps}
          selectedStepIndex={1}
          onSelectStep={handleSelectStep}
        />
      );
      container = res.container;
      await Promise.resolve();
    });

    await act(async () => {
      await Promise.resolve();
    });

    const frameEl = container!.querySelector('.cursor-ns-resize')!;

    await act(async () => {
      fireEvent.wheel(frameEl, { deltaY: -100 });
    });
    expect(handleSelectStep).toHaveBeenCalledWith(0);
  });

  it('avanza al siguiente paso mediante gesto touch swipe hacia arriba', async () => {
    const handleSelectStep = vi.fn();

    let container: HTMLElement;
    await act(async () => {
      const res = render(
        <AgentJourneyScreenPreview
          steps={steps}
          selectedStepIndex={1}
          onSelectStep={handleSelectStep}
        />
      );
      container = res.container;
      await Promise.resolve();
    });

    await act(async () => {
      await Promise.resolve();
    });

    const frameEl = container!.querySelector('.cursor-ns-resize')!;

    await act(async () => {
      fireEvent.touchStart(frameEl, { touches: [{ clientY: 200 }] });
      fireEvent.touchMove(frameEl, { touches: [{ clientY: 100 }] });
    });
    expect(handleSelectStep).toHaveBeenCalledWith(2);
  });

  it('retrocede al paso anterior mediante gesto touch swipe hacia abajo', async () => {
    const handleSelectStep = vi.fn();

    let container: HTMLElement;
    await act(async () => {
      const res = render(
        <AgentJourneyScreenPreview
          steps={steps}
          selectedStepIndex={1}
          onSelectStep={handleSelectStep}
        />
      );
      container = res.container;
      await Promise.resolve();
    });

    await act(async () => {
      await Promise.resolve();
    });

    const frameEl = container!.querySelector('.cursor-ns-resize')!;

    await act(async () => {
      fireEvent.touchStart(frameEl, { touches: [{ clientY: 100 }] });
      fireEvent.touchMove(frameEl, { touches: [{ clientY: 200 }] });
    });
    expect(handleSelectStep).toHaveBeenCalledWith(0);
  });

  it('maneja eventos onLoad y onError en la imagen de captura', async () => {
    let container: HTMLElement;
    await act(async () => {
      const res = render(
        <AgentJourneyScreenPreview
          steps={steps}
          selectedStepIndex={0}
        />
      );
      container = res.container;
    });

    const img = container!.querySelector('img')!;
    await act(async () => {
      fireEvent.load(img);
    });
    expect(img.className).toContain('opacity-100');

    await act(async () => {
      fireEvent.error(img);
    });
    // Al haber error de imagen, se muestra el nombre de captura de respaldo
    expect(screen.getAllByText(steps[0].captureName).length).toBeGreaterThan(0);
  });

  it('renderiza captura con fallback de bounding box cuando el paso no tiene imagen', async () => {
    const stepsWithoutImage: AgentJourneyStep[] = [
      {
        ...steps[0],
        imageSrc: undefined,
        captureName: 'pantalla_fallback_sin_imagen',
      },
    ];

    await act(async () => {
      render(
        <AgentJourneyScreenPreview
          steps={stepsWithoutImage}
          selectedStepIndex={0}
        />
      );
    });

    expect(screen.getByText('pantalla_fallback_sin_imagen')).toBeInTheDocument();
  });

  it('no avanza ni retrocede cuando ya está en los límites (primer o último paso)', async () => {
    const handleSelectStep = vi.fn();

    let container: HTMLElement;
    // Prueba en el último paso
    await act(async () => {
      const res = render(
        <AgentJourneyScreenPreview
          steps={steps}
          selectedStepIndex={steps.length - 1}
          onSelectStep={handleSelectStep}
        />
      );
      container = res.container;
      await Promise.resolve();
    });

    await act(async () => {
      await Promise.resolve();
    });

    const frameEl = container!.querySelector('.cursor-ns-resize')!;

    // Intentar avanzar con rueda en el último paso -> no debe llamar a onSelectStep
    await act(async () => {
      fireEvent.wheel(frameEl, { deltaY: 100 });
    });
    expect(handleSelectStep).not.toHaveBeenCalled();

    // Intentar avanzar con touch en el último paso -> no debe llamar
    await act(async () => {
      fireEvent.touchStart(frameEl, { touches: [{ clientY: 200 }] });
      fireEvent.touchMove(frameEl, { touches: [{ clientY: 100 }] });
    });
    expect(handleSelectStep).not.toHaveBeenCalled();

    // Movimiento táctil menor al umbral (TOUCH_THRESHOLD = 55)
    await act(async () => {
      fireEvent.touchStart(frameEl, { touches: [{ clientY: 100 }] });
      fireEvent.touchMove(frameEl, { touches: [{ clientY: 90 }] });
    });
    expect(handleSelectStep).not.toHaveBeenCalled();
  });

  it('soporta apertura de pantalla completa y cierre por clic en el backdrop con paso sin imagen y sin url', async () => {
    const stepsWithoutImage: AgentJourneyStep[] = [
      {
        ...steps[0],
        url: '',
        caption: '',
        imageSrc: undefined,
        captureName: 'pantalla_modal_sin_imagen',
      },
    ];

    let container: HTMLElement;
    await act(async () => {
      const res = render(
        <AgentJourneyScreenPreview
          steps={stepsWithoutImage}
          selectedStepIndex={0}
        />
      );
      container = res.container;
    });

    // Abrir pantalla completa
    const zoomBtn = screen.getByRole('button', { name: /ver captura en pantalla completa/i });
    await act(async () => {
      fireEvent.click(zoomBtn);
    });

    expect(screen.getAllByText('pantalla_modal_sin_imagen').length).toBeGreaterThan(0);

    // Clic en el backdrop para cerrar
    const backdrop = container!.ownerDocument.querySelector('.fixed.inset-0')!;
    await act(async () => {
      fireEvent.click(backdrop);
    });

    expect(screen.queryByRole('button', { name: /cerrar pantalla completa/i })).not.toBeInTheDocument();
  });

  it('cubre ramas adicionales: tecla distinta a Escape en modal, scroll y touch en modal o cooldown, scroll en paso 0 y caption explícito', async () => {
    const handleSelectStep = vi.fn();
    const stepsWithCaption: AgentJourneyStep[] = [
      {
        ...steps[0],
        caption: 'Mi descripción de captura personalizada',
      },
      steps[1],
    ];

    let container: HTMLElement;
    await act(async () => {
      const res = render(
        <AgentJourneyScreenPreview
          steps={stepsWithCaption}
          selectedStepIndex={0}
          onSelectStep={handleSelectStep}
        />
      );
      container = res.container;
      await Promise.resolve();
    });

    await act(async () => {
      await Promise.resolve();
    });

    const frameEl = container!.querySelector('.cursor-ns-resize')!;

    // 1. Scroll hacia arriba cuando ya está en paso 0
    await act(async () => {
      fireEvent.wheel(frameEl, { deltaY: -100 });
    });
    expect(handleSelectStep).not.toHaveBeenCalled();

    // 2. Eventos rápidos de rueda sucesivos (para cubrir resetTimer y cooldown)
    await act(async () => {
      fireEvent.wheel(frameEl, { deltaY: 60 });
      fireEvent.wheel(frameEl, { deltaY: 60 });
    });

    // 3. touchMove cuando touchStartY es null
    await act(async () => {
      fireEvent.touchMove(frameEl, { touches: [{ clientY: 100 }] });
    });

    // 4. Abrir modal y probar tecla distinta a Escape y eventos durante modal abierto
    const zoomBtn = screen.getByRole('button', { name: /ver captura en pantalla completa/i });
    await act(async () => {
      fireEvent.click(zoomBtn);
    });

    // Presionar tecla Enter (no debe cerrar)
    await act(async () => {
      window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter' }));
    });
    expect(screen.getByRole('button', { name: /cerrar pantalla completa/i })).toBeInTheDocument();

    // Rueda del mouse mientras el modal está abierto (debe ignorarse)
    await act(async () => {
      fireEvent.wheel(frameEl, { deltaY: 100 });
    });

    // TouchMove mientras el modal está abierto (debe ignorarse)
    await act(async () => {
      fireEvent.touchMove(frameEl, { touches: [{ clientY: 100 }] });
    });

    // Cerrar modal
    await act(async () => {
      window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));
    });
  });

  it('maneja selectedStepIndex fuera de rango recurriendo al paso 0 por defecto', async () => {
    await act(async () => {
      render(
        <AgentJourneyScreenPreview
          steps={steps}
          selectedStepIndex={999}
        />
      );
    });

    expect(screen.getByText(steps[0].url!)).toBeInTheDocument();
  });
});
