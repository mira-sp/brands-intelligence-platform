'use client';

import { ArrowUpRight, X } from 'lucide-react';
import { AnimatePresence, motion } from 'motion/react';
import { Fragment, useEffect, useMemo, useState } from 'react';
import type { Run } from '../../services/visibility';
import { hostname, providerColor, providerLabel, safeHref, visibilityApi } from '../../services/visibility';

export interface DrawerTarget {
  promptId: string;
  question: string;
  provider: string;
}

const escapeRe = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

/** Renders answer text: strips markdown bold, highlights the brand, underlines competitors. */
function AnswerText({ text, brandNames, competitors }: { text: string; brandNames: string[]; competitors: string[] }) {
  const names = [...brandNames, ...competitors].filter(Boolean).sort((a, b) => b.length - a.length);
  const clean = text.replace(/\*\*(.+?)\*\*/g, '$1');
  if (!names.length) return <p className="whitespace-pre-line">{clean}</p>;
  const re = new RegExp(`(?<![\\w])(${names.map(escapeRe).join('|')})(?![\\w])`, 'gi');
  const brandSet = new Set(brandNames.map((n) => n.toLowerCase()));
  return (
    <p className="whitespace-pre-line">
      {clean.split(re).map((part, i) => {
        if (i % 2 === 0) return <Fragment key={i}>{part}</Fragment>;
        return brandSet.has(part.toLowerCase()) ? (
          <mark key={i} className="rounded-[2px] bg-highlight px-0.5 text-ink">
            {part}
          </mark>
        ) : (
          <span key={i} className="underline decoration-rule-strong decoration-1 underline-offset-[3px]">
            {part}
          </span>
        );
      })}
    </p>
  );
}

const fmtDate = (iso: string) =>
  new Date(iso).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });

const SENTIMENT_LABEL: Record<string, string> = {
  positive: 'Positive',
  neutral: 'Neutral',
  negative: 'Negative',
  not_mentioned: 'Not mentioned',
};

export function AnswerDrawer({
  target,
  brandId,
  brandNames,
  competitors,
  onClose,
}: {
  target: DrawerTarget | null;
  brandId: string;
  brandNames: string[];
  competitors: string[];
  onClose: () => void;
}) {
  const [runs, setRuns] = useState<Run[] | null>(null);
  const [selected, setSelected] = useState(0);

  useEffect(() => {
    if (!target) return;
    let cancelled = false;
    setRuns(null);
    setSelected(0);
    visibilityApi
      .runs(brandId, target.promptId, target.provider, 16)
      .then((r) => !cancelled && setRuns(r))
      .catch(() => !cancelled && setRuns([]));
    return () => {
      cancelled = true;
    };
  }, [target, brandId]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose();
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  const run = runs?.[selected];
  const history = useMemo(() => (runs ? [...runs].reverse() : []), [runs]); // oldest -> newest

  return (
    <AnimatePresence>
      {target && (
        <>
          <motion.div
            key="scrim"
            className="fixed inset-0 z-40 bg-black/20 backdrop-blur-[1px]"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
          />
          <motion.aside
            key="panel"
            role="dialog"
            aria-modal="true"
            aria-label={`Answers from ${providerLabel(target.provider)}`}
            className="fixed inset-y-0 right-0 z-50 flex w-full max-w-[36rem] flex-col border-l border-rule-strong bg-paper-raised shadow-[-24px_0_48px_-32px_rgba(0,0,0,0.35)]"
            initial={{ x: '100%' }}
            animate={{ x: 0 }}
            exit={{ x: '100%' }}
            transition={{ type: 'spring', stiffness: 380, damping: 40 }}
          >
            <div className="flex items-start justify-between gap-4 border-b border-rule px-6 pt-5 pb-4">
              <div>
                <div className="flex items-center gap-2">
                  <span className="inline-block h-[3px] w-4 rounded-full" style={{ background: providerColor(target.provider) }} />
                  <span className="label">{providerLabel(target.provider)} · answer history</span>
                </div>
                <h3 className="mt-2 text-xl font-medium leading-snug tracking-tight">{target.question}</h3>
              </div>
              <button onClick={onClose} aria-label="Close" className="mt-1 text-ink-3 transition-colors hover:text-ink">
                <X size={18} strokeWidth={1.5} />
              </button>
            </div>

            {/* History strip: one mark per answer, filled = brand named */}
            {history.length > 0 && (
              <div className="border-b border-rule px-6 py-3">
                <div className="flex items-center gap-[3px]" role="listbox" aria-label="Answers, oldest to newest">
                  {history.map((r) => {
                    const idx = runs!.indexOf(r);
                    const isSel = idx === selected;
                    return (
                      <button
                        key={r.id}
                        role="option"
                        aria-selected={isSel}
                        title={`${fmtDate(r.created_at)}: ${r.brand_mentioned ? (r.list_rank ? `#${r.list_rank}` : 'named') : 'not named'}`}
                        onClick={() => setSelected(idx)}
                        className={`h-6 w-3 rounded-[2px] border transition-transform hover:-translate-y-0.5 ${
                          r.brand_mentioned ? 'border-ink bg-ink' : 'border-rule-strong bg-transparent'
                        } ${isSel ? 'outline-2 outline-offset-2 outline-ink' : ''}`}
                      />
                    );
                  })}
                </div>
                <div className="mt-2 flex justify-between font-mono text-[10px] text-ink-3">
                  <span>{fmtDate(history[0].created_at)}</span>
                  <span>{fmtDate(history[history.length - 1].created_at)}</span>
                </div>
              </div>
            )}

            <div className="flex-1 overflow-y-auto px-6 py-5">
              {!runs && <p className="text-sm text-ink-3">Loading answers…</p>}
              {runs && !runs.length && <p className="text-sm text-ink-3">No answers stored yet.</p>}
              {run && (
                <motion.div key={run.id} initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.25 }}>
                  <dl className="grid grid-cols-3 gap-4 border-b border-rule pb-4">
                    <div>
                      <dt className="label">Named</dt>
                      <dd className="mt-1 text-sm">{run.brand_mentioned ? (run.list_rank ? `Yes, #${run.list_rank}` : 'Yes') : 'No'}</dd>
                    </div>
                    <div>
                      <dt className="label">Tone</dt>
                      <dd className="mt-1 text-sm">{SENTIMENT_LABEL[run.sentiment ?? ''] ?? '–'}</dd>
                    </div>
                    <div>
                      <dt className="label">Recommended</dt>
                      <dd className="mt-1 text-sm">{run.recommended ? 'Yes' : 'No'}</dd>
                    </div>
                  </dl>

                  {run.summary && <p className="mt-4 rounded-lg bg-wash px-3 py-2.5 text-sm leading-snug text-ink-2">{run.summary}</p>}

                  <div className="mt-5">
                    <div className="label mb-2">
                      Answer · {fmtDate(run.created_at)} · <span className="normal-case">{run.model}</span>
                    </div>
                    <div className="text-[15px] leading-relaxed text-ink">
                      {run.answer_text ? (
                        <AnswerText text={run.answer_text} brandNames={brandNames} competitors={competitors} />
                      ) : (
                        <p className="text-ink-3">{run.error ?? 'No answer text.'}</p>
                      )}
                    </div>
                  </div>

                  {run.claims.length > 0 && (
                    <div className="mt-6">
                      <div className="label mb-2">Claims about the brand · check these are true</div>
                      <ul className="space-y-1.5">
                        {run.claims.map((c) => (
                          <li key={c} className="flex gap-2 text-sm text-ink-2">
                            <span className="text-ink-3" aria-hidden>
                              —
                            </span>
                            {c}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {run.sources.length > 0 && (
                    <div className="mt-6 pb-4">
                      <div className="label mb-2">Cited sources</div>
                      <ul className="space-y-1">
                        {run.sources.map((s) => {
                          const href = safeHref(s.url);
                          return (
                            <li key={s.url}>
                              {href ? (
                                <a
                                  href={href}
                                  target="_blank"
                                  rel="noopener noreferrer nofollow"
                                  className="inline-flex items-center gap-1 text-sm text-ink-2 underline decoration-rule-strong underline-offset-[3px] hover:text-ink"
                                >
                                  {hostname(s.url)}
                                  <ArrowUpRight size={12} strokeWidth={1.5} />
                                </a>
                              ) : (
                                <span className="text-sm text-ink-3">{s.url}</span>
                              )}
                            </li>
                          );
                        })}
                      </ul>
                    </div>
                  )}
                </motion.div>
              )}
            </div>
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  );
}
