'use client';

import type { Summary } from '../../services/visibility';
import { hostname, urlPath } from '../../services/visibility';
import { SectionTitle } from './AssistantColumns';

export function Sources({ summary }: { summary: Summary }) {
  const rows = summary.top_sources;
  if (!rows.length) return null;
  const max = Math.max(...rows.map((r) => r.count));
  return (
    <section className="card p-6">
      <SectionTitle title="Where the answers come from" note="Pages the assistants cited most - improve your presence here" />
      <ol className="grid gap-x-10 sm:grid-cols-2">
        {rows.map((r, i) => {
          return (
            <li key={r.url} className="grid grid-cols-[1.75rem_1fr_auto] items-baseline gap-2 border-b border-rule py-2.5">
              <span className="font-mono text-xs tabular text-ink-3">{String(i + 1).padStart(2, '0')}</span>
              <span className="min-w-0">
                <span className="block truncate text-sm">{hostname(r.url)}</span>
                <span className="block truncate font-mono text-[11px] text-ink-3">{urlPath(r.url)}</span>
                <span className="mt-1.5 block h-[3px] rounded-r-full bg-rule-strong" style={{ width: `${(r.count / max) * 100}%` }} />
              </span>
              <span className="font-mono text-xs tabular text-ink-2">{r.count}×</span>
            </li>
          );
        })}
      </ol>
    </section>
  );
}
