'use client';

import { motion } from 'motion/react';
import type { Summary } from '../../services/visibility';
import { pct } from '../../services/visibility';
import { SectionTitle } from './AssistantColumns';

export function ShareOfVoice({ summary, brandName }: { summary: Summary; brandName: string }) {
  const rows = Object.entries(summary.share_of_voice)
    .filter(([, v]) => v !== null)
    .sort((a, b) => (b[1] ?? 0) - (a[1] ?? 0)) as [string, number][];
  const max = Math.max(...rows.map(([, v]) => v), 0.0001);
  if (!rows.length) return null;

  return (
    <section className="card p-6">
      <SectionTitle title="Share of voice" note="Mentions of each company across all answers" />
      <ol className="space-y-4">
        {rows.map(([name, value], i) => {
          const isBrand = name === brandName;
          return (
            <li key={name} className="grid grid-cols-[7.5rem_1fr_3rem] items-center gap-3 sm:grid-cols-[9rem_1fr_3rem]">
              <span className={`truncate text-sm ${isBrand ? 'font-medium text-ink' : 'text-ink-2'}`} title={name}>
                {name}
              </span>
              <div className="h-2.5">
                <motion.div
                  initial={{ width: 0 }}
                  animate={{ width: `${(value / max) * 100}%` }}
                  transition={{ duration: 0.7, delay: 0.05 * i, ease: [0.22, 1, 0.36, 1] }}
                  className="h-full rounded-r-[4px]"
                  style={{ background: isBrand ? 'var(--ink)' : 'var(--rule-strong)' }}
                  title={`${name}: ${pct(value, 1)}`}
                />
              </div>
              <span className={`text-right font-mono text-xs tabular ${isBrand ? 'text-ink' : 'text-ink-3'}`}>
                {pct(value)}
              </span>
            </li>
          );
        })}
      </ol>
    </section>
  );
}
