'use client';

import type { Matrix, MatrixCell } from '../../services/visibility';
import { pct, providerColor, providerLabel } from '../../services/visibility';
import { SectionTitle } from './AssistantColumns';

function Cell({
  cell,
  provider,
  question,
  onOpen,
}: {
  cell: MatrixCell | null;
  provider: string;
  question: string;
  onOpen: () => void;
}) {
  if (!cell || cell.mention_rate === null) {
    return <div className="flex h-10 items-center justify-center rounded-md bg-wash text-xs text-ink-3">–</div>;
  }
  const rate = cell.mention_rate;
  // Sequential single-hue scale: tint of the accent, light -> dark with the mention rate
  const strength = Math.round(6 + rate * 84);
  const onDark = strength >= 52;
  const last = cell.last_mentioned
    ? cell.last_list_rank
      ? `#${cell.last_list_rank}`
      : 'named'
    : 'absent';
  return (
    <button
      onClick={onOpen}
      className="group relative flex h-10 w-full items-center justify-between rounded-md px-2.5 ring-ink-3 transition-shadow hover:ring-1"
      style={{
        background: `color-mix(in oklab, var(--accent) ${strength}%, var(--paper-raised))`,
        color: onDark ? 'var(--accent-ink)' : 'var(--ink)',
      }}
      aria-label={`${providerLabel(provider)}: mentioned in ${pct(cell.mention_rate)} of ${cell.runs} answers to "${question}". Last answer: ${last}. Open answers.`}
    >
      <span className="text-sm font-medium tabular">{pct(rate)}</span>
      <span className="font-mono text-[10px] tabular opacity-70">{cell.last_mentioned ? last : '–'}</span>
      <span
        role="tooltip"
        className="pointer-events-none absolute bottom-full z-10 mb-1 hidden w-max max-w-[14rem] rounded-md border border-rule-strong bg-paper-raised px-2.5 py-1.5 text-left text-xs text-ink-2 shadow-[0_8px_24px_-12px_rgba(0,0,0,0.3)] group-hover:block group-focus-visible:block"
      >
        <span className="font-medium text-ink">{pct(cell.mention_rate)}</span> of {cell.runs} answers
        <br />
        last answer: {last}
      </span>
    </button>
  );
}

export function QuestionMatrix({
  matrix,
  onOpen,
}: {
  matrix: Matrix | null;
  onOpen: (promptId: string, question: string, provider: string) => void;
}) {
  if (!matrix || !matrix.rows.length) return null;
  const providers = matrix.providers;
  const cols = `minmax(0,1fr) repeat(${providers.length}, minmax(4.5rem, 6.5rem)) 3.5rem`;

  const rowRate = (cells: Record<string, MatrixCell | null>) => {
    const vals = Object.values(cells).filter((c): c is MatrixCell => !!c && c.mention_rate !== null);
    const runs = vals.reduce((a, c) => a + c.runs, 0);
    return runs ? vals.reduce((a, c) => a + (c.mention_rate ?? 0) * c.runs, 0) / runs : null;
  };

  return (
    <section className="card p-6">
      <SectionTitle
        
        title="Questions customers ask"
        note="How often each assistant names the brand · small number: list position in the latest answer"
      />
      <div className="-mx-4 overflow-x-auto px-4">
        <div role="table" className="min-w-[36rem]">
          <div role="row" className="grid items-end gap-x-2 border-b border-rule-strong pb-2" style={{ gridTemplateColumns: cols }}>
            <span role="columnheader" className="label">
              Question
            </span>
            {providers.map((p) => (
              <span role="columnheader" key={p} className="flex flex-col items-center gap-1.5 text-xs text-ink-2">
                <span className="inline-block h-[3px] w-4 rounded-full" style={{ background: providerColor(p) }} aria-hidden />
                {providerLabel(p)}
              </span>
            ))}
            <span role="columnheader" className="label text-right">
              All
            </span>
          </div>
          {matrix.rows.map((row) => {
            const all = rowRate(row.cells);
            return (
              <div
                role="row"
                key={row.prompt_id}
                className="grid items-center gap-x-1.5 border-b border-rule py-1.5 last:border-b-0"
                style={{ gridTemplateColumns: cols }}
              >
                <span role="cell" className="pr-4 text-sm leading-snug">
                  {row.text}
                </span>
                {providers.map((p) => (
                  <div role="cell" key={p}>
                    <Cell cell={row.cells[p]} provider={p} question={row.text} onOpen={() => onOpen(row.prompt_id, row.text, p)} />
                  </div>
                ))}
                <span role="cell" className="text-right font-mono text-xs tabular text-ink">
                  {pct(all)}
                </span>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
