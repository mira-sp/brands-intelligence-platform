'use client';

import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import type { Trend } from '../../services/visibility';
import { pct } from '../../services/visibility';
import { SectionTitle } from './AssistantColumns';

const fmtWeek = (iso: string) => new Date(iso).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' });

interface TipProps {
  active?: boolean;
  payload?: { value: number; payload: { week: string } }[];
}

function Tip({ active, payload }: TipProps) {
  if (!active || !payload?.length) return null;
  const { value, payload: row } = payload[0];
  return (
    <div className="rounded-lg border border-rule bg-paper-raised px-3 py-2 shadow-[0_8px_24px_-12px_rgba(0,0,0,0.25)]">
      <div className="label">Week of {fmtWeek(row.week)}</div>
      <div className="mt-1 text-lg font-medium leading-none tabular">{pct(value)}</div>
    </div>
  );
}

export function TrendChart({ trend }: { trend: Trend | null }) {
  const data = (trend?.weeks ?? []).filter((w) => w.overall !== null).map((w) => ({ week: w.week, overall: w.overall }));
  const last = data[data.length - 1];

  return (
    <section className="card p-6">
      <SectionTitle title="Mention rate over time" note="All assistants combined, per week" />
      {data.length < 2 ? (
        <p className="text-sm text-ink-3">Not enough weeks of data yet.</p>
      ) : (
        <>
          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={data} margin={{ top: 8, right: 44, bottom: 0, left: -12 }}>
                <defs>
                  <linearGradient id="inkWash" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="var(--ink)" stopOpacity={0.12} />
                    <stop offset="100%" stopColor="var(--ink)" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid vertical={false} stroke="var(--rule)" />
                <XAxis
                  dataKey="week"
                  tickFormatter={fmtWeek}
                  tick={{ fill: 'var(--ink-3)', fontSize: 11, fontFamily: 'var(--font-mono)' }}
                  axisLine={{ stroke: 'var(--rule-strong)' }}
                  tickLine={false}
                  minTickGap={28}
                  dy={6}
                />
                <YAxis
                  domain={[0, 1]}
                  ticks={[0, 0.25, 0.5, 0.75, 1]}
                  tickFormatter={(v: number) => `${v * 100}%`}
                  tick={{ fill: 'var(--ink-3)', fontSize: 11, fontFamily: 'var(--font-mono)' }}
                  axisLine={false}
                  tickLine={false}
                />
                <Tooltip content={<Tip />} cursor={{ stroke: 'var(--rule-strong)', strokeWidth: 1 }} />
                <Area
                  type="monotone"
                  dataKey="overall"
                  stroke="var(--ink)"
                  strokeWidth={2}
                  fill="url(#inkWash)"
                  dot={false}
                  activeDot={{ r: 5, fill: 'var(--ink)', stroke: 'var(--paper-raised)', strokeWidth: 2 }}
                  isAnimationActive={false}
                  animationDuration={900}
                  label={(props: { index?: number; x?: number | string; y?: number | string }) =>
                    props.index === data.length - 1 ? (
                      <text
                        key="end"
                        x={Number(props.x) + 10}
                        y={Number(props.y) + 4}
                        fill="var(--ink)"
                        fontSize={12}
                        fontFamily="var(--font-mono)"
                      >
                        {pct(last.overall)}
                      </text>
                    ) : (
                      <g key={props.index} />
                    )
                  }
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
          {/* Same data as a table for screen readers */}
          <table className="sr-only">
            <caption>Weekly mention rate, all assistants</caption>
            <thead>
              <tr>
                <th>Week</th>
                <th>Mention rate</th>
              </tr>
            </thead>
            <tbody>
              {data.map((d) => (
                <tr key={d.week}>
                  <td>{d.week}</td>
                  <td>{pct(d.overall)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </section>
  );
}
