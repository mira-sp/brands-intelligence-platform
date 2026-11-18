'use client';

import { useState } from 'react';
import type { Summary, Trend } from '../../services/visibility';
import { pct, providerColor, providerLabel } from '../../services/visibility';

const W = 220;
const PAD = 5;

export function Sparkline({
  values,
  color,
  active,
  onActive,
  label,
  height = 48,
}: {
  values: (number | null)[];
  color: string;
  active: number | null;
  onActive: (i: number | null) => void;
  label: string;
  height?: number;
}) {
  const H = height;
  const n = values.length;
  const x = (i: number) => PAD + (n <= 1 ? 0 : (i * (W - 2 * PAD)) / (n - 1));
  const y = (v: number) => PAD + (1 - v) * (H - 2 * PAD);

  // Path with gaps where a week has no data
  let d = '';
  values.forEach((v, i) => {
    if (v === null) return;
    d += `${i > 0 && values[i - 1] !== null ? 'L' : 'M'}${x(i).toFixed(1)},${y(v).toFixed(1)}`;
  });
  const lastIdx = values.map((v, i) => (v === null ? -1 : i)).reduce((a, b) => Math.max(a, b), -1);
  const shown = active ?? lastIdx;

  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      style={{ height: H }}
      className="w-full overflow-visible"
      role="img"
      aria-label={label}
      onMouseMove={(e) => {
        const rect = e.currentTarget.getBoundingClientRect();
        const rel = ((e.clientX - rect.left) / rect.width) * W;
        const i = Math.round(((rel - PAD) / (W - 2 * PAD)) * (n - 1));
        onActive(Math.max(0, Math.min(n - 1, i)));
      }}
      onMouseLeave={() => onActive(null)}
    >
      <line x1={0} x2={W} y1={y(0.5)} y2={y(0.5)} stroke="var(--rule)" strokeWidth={1} strokeDasharray="2 3" />
      <path d={d} fill="none" stroke={color} strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />
      {active !== null && <line x1={x(active)} x2={x(active)} y1={0} y2={H} stroke="var(--rule-strong)" strokeWidth={1} />}
      {shown >= 0 && values[shown] !== null && (
        <circle cx={x(shown)} cy={y(values[shown] as number)} r={4} fill={color} stroke="var(--paper-raised)" strokeWidth={2} />
      )}
      <rect x={0} y={0} width={W} height={H} fill="transparent" />
    </svg>
  );
}

function Column({ provider, summary, trend }: { provider: string; summary: Summary; trend: Trend | null }) {
  const [active, setActive] = useState<number | null>(null);
  const values = trend?.weeks.map((w) => w.by_provider[provider] ?? null) ?? [];
  const stats = summary.by_provider[provider];
  const hovered = active !== null ? trend?.weeks[active] : undefined;
  const value = hovered ? hovered.by_provider[provider] : stats?.mention_rate;
  const caption = hovered
    ? `Week of ${new Date(hovered.week).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })}`
    : `${stats?.mentioned ?? 0} of ${stats?.runs ?? 0} answers`;

  return (
    <div className="rounded-[10px] border border-rule p-4">
      <div className="flex items-center gap-2">
        <span className="inline-block size-2 rounded-full" style={{ background: providerColor(provider) }} aria-hidden />
        <span className="text-sm text-ink-2">{providerLabel(provider)}</span>
      </div>
      <div className="mt-2 text-2xl font-medium tracking-tight tabular">{pct(value)}</div>
      <div className="mt-0.5 h-4 text-xs text-ink-3">{caption}</div>
      <div className="mt-3">
        <Sparkline
          values={values}
          color={providerColor(provider)}
          active={active}
          onActive={setActive}
          label={`${providerLabel(provider)} weekly mention rate`}
        />
      </div>
    </div>
  );
}

export function AssistantColumns({ summary, trend }: { summary: Summary; trend: Trend | null }) {
  const providers = Object.keys(summary.by_provider).sort();
  if (!providers.length) return null;
  return (
    <section className="card p-6">
      <SectionTitle title="By assistant" note="Share of answers that name the brand · weekly, last 90 days" />
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {providers.map((p) => (
          <Column key={p} provider={p} summary={summary} trend={trend} />
        ))}
      </div>
    </section>
  );
}

export function SectionTitle({ title, note }: { title: string; note?: string }) {
  return (
    <div className="mb-5">
      <h2 className="text-[15px] font-medium">{title}</h2>
      {note && <p className="mt-0.5 text-xs text-ink-3">{note}</p>}
    </div>
  );
}
