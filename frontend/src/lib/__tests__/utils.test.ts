import { describe, it, expect } from 'vitest';
import { cn } from '../utils';

describe('cn utility', () => {
  it('combina nombres de clases simples correctamente', () => {
    expect(cn('class-a', 'class-b')).toBe('class-a class-b');
  });

  it('soporta valores condicionales y filtra falsy values', () => {
    const isTrue = true;
    const isFalse = false;
    expect(cn('base', isTrue && 'active', isFalse && 'hidden', null, undefined)).toBe('base active');
  });

  it('resuelve colisiones de clases Tailwind CSS', () => {
    expect(cn('p-4', 'p-2')).toBe('p-2');
    expect(cn('text-red-500', 'text-blue-500')).toBe('text-blue-500');
  });

  it('maneja arrays y objetos de clases', () => {
    expect(cn(['btn', 'btn-primary'], { 'opacity-50': true, 'hidden': false })).toBe(
      'btn btn-primary opacity-50'
    );
  });
});
