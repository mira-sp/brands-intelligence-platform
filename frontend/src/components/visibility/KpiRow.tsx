'use client';

import { ArrowDownRight, ArrowUpRight, Minus } from 'lucide-react';
import { motion } from 'motion/react';
import { useState } from 'react';
import type { Summary, Trend } from '../../services/visibility';
import { pct } from '../../services/visibility';
import { Sparkline } from './AssistantColumns';

function Kpi({ label, value, foot, children, i }: { label: string; value: string; foot: React.ReactNode; children?: React.ReactNode; i: number }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, delay: i * 0.05, ease: [0.22, 1, 0.36, 1] }}
      className="card flex min-h-[9.5rem] flex-col p-5"
    >
      <div className="label">{label}</div>
      <div className="mt-2 text-[2.1rem] leading-none font-medium tracking-tight tabular">{value}</div>
      <div className="mt-2 text-xs text-ink-3">{foot}</div>
      <div className="mt-auto pt-3">{children}</div>
    </motion.div>
  );
}

function DeltaChip({ now, before }: { now: number | null; before: number | null }) {
  if (now === null || before === null) return null;
  const points = Math.round((now - before) * 100);
  const Icon = points > 0 ? ArrowUpRight : points < 0 ? ArrowDownRight : Minus;
  const tone = points > 0 ? 'text-good' : points < 0 ? 'text-bad' : 'text-ink-2';
  return (
    <span className={`inline-flex items-center gap-0.5 rounded-full bg-wash px-1.5 py-0.5 font-medium ${tone}`}>
      <Icon size={12} strokeWidth={2} aria-hidden />
      {points > 0 ? '+' : ''}
      {points} pts
    </span>
  );
}

const TONES = [
  { key: 'positive', label: 'Positive', color: 'var(--good)' },
  { key: 'neutral', label: 'Neutral', color: 'var(--rule-strong)' },
  { key: 'negative', label: 'Negative', color: 'var(--bad)' },
] as const;

export function KpiRow({ summary, trend, days }: { summary: Summary; trend: Trend | null; days: number }) {
  const [active, setActive] = useState<number | null>(null);
  const tones = TONES.map((t) => ({ ...t, n: summary.sentiment[t.key] ?? 0 }));
  const toneTotal = tones.reduce((a, t) => a + t.n, 0);
  const positive = toneTotal ? tones[0].n / toneTotal : null;
  const weekly = trend?.weeks.map((w) => w.overall) ?? [];
  const hovered = active !== null ? trend?.weeks[active] : undefined;

  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      <Kpi
        i={0}
        label="Mention rate"
        value={pct(hovered ? hovered.overall : summary.mention_rate)}
        foot={
          hovered ? (
            `Week of ${new Date(hovered.week).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })}`
          ) : (
            <span className="inline-flex items-center gap-1.5">
              <DeltaChip now={summary.mention_rate} before={summary.previous_mention_rate} />
              vs. previous {days} days
            </span>
          )
        }
      >
        <Sparkline values={weekly} color="var(--ink)" active={active} onActive={setActive} label="Weekly mention rate" height={36} />
      </Kpi>

      <Kpi i={1} label="Recommended" value={pct(summary.recommendation_rate)} foot="of all answers recommend the brand">
        <Meter value={summary.recommendation_rate ?? 0} />
      </Kpi>

      <Kpi
        i={2}
        label="Average position"
        value={summary.avg_list_rank !== null ? `#${summary.avg_list_rank.toFixed(1)}` : '–'}
        foot="when the brand appears in a list"
      >
        <RankDots rank={summary.avg_list_rank} />
      </Kpi>

      <Kpi i={3} label="Positive tone" value={pct(positive)} foot={`of ${toneTotal} answers that name the brand`}>
        {toneTotal > 0 && (
          <div
            className="flex h-1.5 w-full gap-[2px] overflow-hidden rounded-full"
            role="img"
            aria-label={tones.map((t) => `${t.label} ${t.n}`).join(', ')}
          >
            {tones
              .filter((t) => t.n > 0)
              .map((t) => (
                <div key={t.key} style={{ flexGrow: t.n, background: t.color }} title={`${t.label}: ${t.n}`} />
              ))}
          </div>
        )}
      </Kpi>
    </div>
  );
}

function Meter({ value }: { value: number }) {
  return (
    <div className="h-1.5 w-full overflow-hidden rounded-full bg-wash">
      <motion.div
        initial={{ width: 0 }}
        animate={{ width: `${Math.min(1, value) * 100}%` }}
        transition={{ duration: 0.7, ease: [0.22, 1, 0.36, 1] }}
        className="h-full rounded-full bg-ink"
      />
    </div>
  );
}

/** Five slots for list positions 1-5; the average sits between them. */
function RankDots({ rank }: { rank: number | null }) {
  if (rank === null) return null;
  const pos = Math.min(5, Math.max(1, rank));
  return (
    <div className="relative h-4" aria-hidden>
      <div className="absolute inset-x-0 top-1/2 h-px bg-rule" />
      {[1, 2, 3, 4, 5].map((n) => (
        <span
          key={n}
          className="absolute top-1/2 -translate-x-1/2 -translate-y-1/2 font-mono text-[10px] text-ink-3"
          style={{ left: `${((n - 1) / 4) * 100}%` }}
        >
          <span className="block bg-paper-raised px-1">{n}</span>
        </span>
      ))}
      <motion.span
        initial={{ left: '0%' }}
        animate={{ left: `${((pos - 1) / 4) * 100}%` }}
        transition={{ duration: 0.7, ease: [0.22, 1, 0.36, 1] }}
        className="absolute top-1/2 size-3 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-paper-raised bg-ink"
      />
    </div>
  );
}
