'use client';

import { Moon, Radar, Sun } from 'lucide-react';
import { useEffect, useState } from 'react';
import type { BrandRef } from '../../services/visibility';

const PERIODS = [7, 30, 90] as const;

function useTheme() {
  const [theme, setTheme] = useState<'light' | 'dark' | null>(null);
  useEffect(() => {
    let stored: string | null = null;
    try {
      stored = window.localStorage.getItem('briefing-theme');
    } catch {
      /* storage unavailable */
    }
    const initial =
      stored === 'light' || stored === 'dark'
        ? stored
        : window.matchMedia('(prefers-color-scheme: dark)').matches
          ? 'dark'
          : 'light';
    document.documentElement.dataset.theme = initial;
    setTheme(initial);
  }, []);
  const toggle = () => {
    const next = theme === 'dark' ? 'light' : 'dark';
    document.documentElement.dataset.theme = next;
    try {
      window.localStorage.setItem('briefing-theme', next);
    } catch {
      /* ignore */
    }
    setTheme(next);
  };
  return { theme, toggle };
}

export function Masthead({
  brands,
  brandId,
  onBrand,
  days,
  onDays,
  onSignOut,
}: {
  brands: BrandRef[];
  brandId: string | null;
  onBrand: (id: string) => void;
  days: number;
  onDays: (d: number) => void;
  onSignOut: () => void;
}) {
  const { theme, toggle } = useTheme();
  const today = new Intl.DateTimeFormat('en-GB', { day: 'numeric', month: 'long', year: 'numeric' }).format(new Date());

  return (
    <header className="border-b border-rule">
      <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-3 py-3">
        <div className="flex items-center gap-3">
          <span className="inline-flex items-center gap-2 text-[15px] font-medium"><span className="grid size-6 place-items-center rounded-md bg-ink text-[11px] text-paper" aria-hidden><Radar size={14} strokeWidth={1.75} /></span>Visibility</span>
          <span className="label hidden sm:inline">{today}</span>
        </div>

        <div className="flex flex-wrap items-center gap-x-5 gap-y-2">
          <label className="flex items-center gap-2">
            <span className="label">Brand</span>
            <select
              value={brandId ?? ''}
              onChange={(e) => onBrand(e.target.value)}
              className="cursor-pointer border-b border-rule-strong bg-transparent pr-1 text-sm outline-none hover:border-ink"
            >
              {brands.map((b) => (
                <option key={b.id} value={b.id}>
                  {b.name}
                </option>
              ))}
            </select>
          </label>

          <div role="radiogroup" aria-label="Period" className="flex items-center">
            {PERIODS.map((p) => (
              <button
                key={p}
                role="radio"
                aria-checked={days === p}
                onClick={() => onDays(p)}
                className={`px-2 py-1 font-mono text-xs transition-colors ${
                  days === p ? 'text-ink underline decoration-1 underline-offset-[6px]' : 'text-ink-3 hover:text-ink'
                }`}
              >
                {p}d
              </button>
            ))}
          </div>

          <button
            onClick={toggle}
            aria-label={theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'}
            className="text-ink-3 transition-colors hover:text-ink"
          >
            {theme === 'dark' ? <Sun size={15} strokeWidth={1.5} /> : <Moon size={15} strokeWidth={1.5} />}
          </button>
          <button onClick={onSignOut} className="label transition-colors hover:text-ink">
            Sign out
          </button>
        </div>
      </div>
    </header>
  );
}
