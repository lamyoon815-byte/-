/**
 * Accessibility tokens for low-vision users.
 * `HighContrast` is a fixed black/white/yellow palette that ignores the system light/dark mode.
 */

import { Colors } from '@/constants/theme';

export type Palette = {
  background: string;
  surface: string;
  text: string;
  textSecondary: string;
  accent: string;
  accentText: string;
  border: string;
  danger: string;
};

export const HighContrast: Palette = {
  background: '#000000',
  surface: '#000000',
  text: '#FFFFFF',
  textSecondary: '#FFFFFF',
  accent: '#FFD60A',
  accentText: '#000000',
  border: '#FFFFFF',
  danger: '#FF8A80',
};

export function getPalette(scheme: 'light' | 'dark', highContrast: boolean): Palette {
  if (highContrast) return HighContrast;
  const c = Colors[scheme];
  return {
    background: c.background,
    surface: c.backgroundElement,
    text: c.text,
    textSecondary: c.textSecondary,
    accent: scheme === 'dark' ? '#4DA3FF' : '#0A58CA',
    accentText: scheme === 'dark' ? '#000000' : '#FFFFFF',
    border: c.backgroundSelected,
    danger: scheme === 'dark' ? '#FF8A80' : '#B3261E',
  };
}

/** Minimum touch target (pt). Apple HIG 44, Material 48 — we go larger for low vision. */
export const MinTouchTarget = 56;

export const FontSize = {
  body: 20,
  label: 18,
  heading: 26,
  button: 22,
} as const;
