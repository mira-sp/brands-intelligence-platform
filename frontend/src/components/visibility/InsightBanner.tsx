'use client';

import { motion } from 'motion/react';
import type { Matrix, Summary } from '../../services/visibility';
import { pct, providerLabel } from '../../services/visibility';

interface Insight {
  label: string;
  text: React.ReactNode;
}

/** Turns the numbers into a few plain-language takeaways. */
function buildInsights(summary: Summary, matrix: Matrix | null, brandName: string, days: number): Insight[] {
  const out: Insight[] = [];

  if (summary.mention_rate !== null && summary.previous_mention_rate !== null) {
    const pts = Math.round((summary.mention_rate - summary.previous_mention_rate) * 100);
    out.push({
      label: 'Trend',
      text:
        pts === 0 ? (
          <>Visibility is flat compared with the previous {days} days.</>
        ) : (
          <>
            Named {pts > 0 ? 'more' : 'less'} often: <b>{pts > 0 ? '+' : ''}
            {pts} pts</b> compared with the previous {days} days.
          </>
        ),
    });
  }

  const providers = Object.entries(summary.by_provider)
    .filter(([, s]) => s.mention_rate !== null)
    .sort((a, b) => (b[1].mention_rate ?? 0) - (a[1].mention_rate ?? 0));
  if (providers.length >= 2) {
    const [best, worst] = [providers[0], providers[providers.length - 1]];
    out.push({
      label: 'Assistants',
      text: (
        <>
          <b>{providerLabel(best[0])}</b> names you most ({pct(best[1].mention_rate)}),{' '}
          <b>{providerLabel(worst[0])}</b> least ({pct(worst[1].mention_rate)}).
        </>
      ),
    });
  }

  if (matrix?.rows.length) {
    const scored = matrix.rows
      .map((r) => {
        const cells = Object.values(r.cells).filter((c) => c && c.mention_rate !== null);
        const runs = cells.reduce((a, c) => a + (c?.runs ?? 0), 0);
        const hits = cells.reduce((a, c) => a + (c?.mention_rate ?? 0) * (c?.runs ?? 0), 0);
        return { text: r.text, rate: runs ? hits / runs : null };
      })
      .filter((r): r is { text: string; rate: number } => r.rate !== null)
      .sort((a, b) => a.rate - b.rate);
    if (scored.length) {
      out.push({
        label: 'Biggest gap',
        text: (
          <>
            “{scored[0].text}” names you in only <b>{pct(scored[0].rate)}</b> of answers.
          </>
        ),
      });
    }
  }

  const sov = Object.entries(summary.share_of_voice)
    .filter(([, v]) => v !== null)
    .sort((a, b) => (b[1] ?? 0) - (a[1] ?? 0));
  const leader = sov[0];
  if (leader && leader[0] !== brandName) {
    out.push({
      label: 'Competition',
      text: (
        <>
          <b>{leader[0]}</b> leads share of voice with {pct(leader[1])}; you have{' '}
          {pct(summary.share_of_voice[brandName] ?? 0)}.
        </>
      ),
    });
  }
  return out;
}

export function InsightBanner({
  summary,
  matrix,
  brandName,
  days,
}: {
  summary: Summary;
  matrix: Matrix | null;
  brandName: string;
  days: number;
}) {
  const insights = buildInsights(summary, matrix, brandName, days);
  if (!insights.length) return null;
  return (
    <motion.section
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
      aria-label="Key takeaways"
      className="relative overflow-hidden rounded-[14px] bg-banner p-6 text-banner-ink"
    >
      {/* faint concentric rings as a quiet backdrop */}
      <svg aria-hidden className="pointer-events-none absolute -top-24 -right-16 size-80 opacity-[0.12]" viewBox="0 0 200 200">
        {[30, 50, 70, 90].map((r) => (
          <circle key={r} cx="100" cy="100" r={r} fill="none" stroke="currentColor" strokeWidth="0.8" />
        ))}
      </svg>
      <div className="relative">
        <h2 className="text-[15px] font-medium">Key takeaways</h2>
        <div className="mt-4 grid gap-x-8 gap-y-4 sm:grid-cols-2 lg:grid-cols-4">
          {insights.map((i) => (
            <div key={i.label} className="border-l border-banner-ink/20 pl-4">
              <div className="text-xs font-medium text-banner-ink-2">{i.label}</div>
              <p className="mt-1 text-sm leading-snug [&_b]:font-medium [&_b]:text-white">{i.text}</p>
            </div>
          ))}
        </div>
      </div>
    </motion.section>
  );
}
