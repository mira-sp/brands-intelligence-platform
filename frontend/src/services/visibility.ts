// frontend/src/services/visibility.ts
import { apiService } from './api';

export type Sentiment = 'positive' | 'neutral' | 'negative' | 'not_mentioned';

export interface BrandRef {
  id: string;
  name: string;
  industry: string | null;
}

export interface ProviderStats {
  runs: number;
  mentioned: number;
  mention_rate: number | null;
}

export interface Summary {
  brand_id: string;
  period_days: number;
  runs: number;
  mention_rate: number | null;
  previous_mention_rate: number | null;
  recommendation_rate: number | null;
  avg_list_rank: number | null;
  sentiment: Partial<Record<Sentiment, number>>;
  avg_sentiment_score: number | null;
  by_provider: Record<string, ProviderStats>;
  share_of_voice: Record<string, number | null>;
  top_sources: { url: string; count: number }[];
}

export interface TrendWeek {
  week: string;
  overall: number | null;
  by_provider: Record<string, number | null>;
}

export interface Trend {
  providers: string[];
  weeks: TrendWeek[];
}

export interface MatrixCell {
  runs: number;
  mention_rate: number | null;
  last_run_id: string;
  last_mentioned: boolean;
  last_list_rank: number | null;
  last_sentiment: Sentiment | null;
}

export interface Matrix {
  providers: string[];
  rows: { prompt_id: string; text: string; cells: Record<string, MatrixCell | null> }[];
}

export interface Run {
  id: string;
  prompt_id: string;
  provider: string;
  model: string;
  created_at: string;
  brand_mentioned: boolean;
  mention_order: number | null;
  list_rank: number | null;
  recommended: boolean | null;
  sentiment: Sentiment | null;
  sentiment_score: number | null;
  competitors_mentioned: string[];
  claims: string[];
  summary: string | null;
  sources: { url: string; title: string }[];
  answer_text: string | null;
  error: string | null;
}

export interface VisibilityConfig {
  brand_id: string;
  aliases: string[];
  competitors: string[];
}

async function get<T>(path: string): Promise<T> {
  const response = await apiService.request(path);
  if (response.status === 401) throw new UnauthorizedError();
  if (!response.ok) throw new Error(`Request failed (${response.status})`);
  return response.json();
}

export class UnauthorizedError extends Error {
  constructor() {
    super('Not signed in');
  }
}

const enc = encodeURIComponent;

export const visibilityApi = {
  me: () => get<{ id: string; email: string; role: string }>('/auth/me'),
  brands: () => get<BrandRef[]>('/api/brands'),
  config: (brandId: string) => get<VisibilityConfig>(`/visibility/brands/${enc(brandId)}/config`),
  summary: (brandId: string, days: number) => get<Summary>(`/visibility/brands/${enc(brandId)}/summary?days=${days}`),
  trend: (brandId: string, days: number) => get<Trend>(`/visibility/brands/${enc(brandId)}/trend?days=${days}`),
  matrix: (brandId: string, days: number) => get<Matrix>(`/visibility/brands/${enc(brandId)}/matrix?days=${days}`),
  runs: (brandId: string, promptId: string, provider: string, limit = 12) =>
    get<Run[]>(
      `/visibility/brands/${enc(brandId)}/runs?prompt_id=${enc(promptId)}&provider=${enc(provider)}&limit=${limit}`,
    ),
};

/* ---- Presentation helpers shared by the components ---- */

export const PROVIDER_LABEL: Record<string, string> = {
  chatgpt: 'ChatGPT',
  claude: 'Claude',
  gemini: 'Gemini',
  perplexity: 'Perplexity',
};

/** Fixed colour per assistant (never by rank) - CSS variables defined in globals.css */
export const providerColor = (p: string) =>
  ['chatgpt', 'claude', 'gemini', 'perplexity'].includes(p) ? `var(--s-${p})` : 'var(--ink-3)';

export const providerLabel = (p: string) => PROVIDER_LABEL[p] ?? p;

export const pct = (v: number | null | undefined, digits = 0) =>
  v === null || v === undefined ? '–' : `${(v * 100).toFixed(digits)}%`;

export const hostname = (url: string) => {
  try {
    return new URL(url).hostname.replace(/^www\./, '');
  } catch {
    return url;
  }
};

export const urlPath = (url: string) => {
  try {
    return new URL(url).pathname;
  } catch {
    return '';
  }
};

/** Source URLs come from AI output (untrusted): only ever link to http(s). */
export const safeHref = (url: string): string | undefined => {
  try {
    const u = new URL(url);
    return u.protocol === 'https:' || u.protocol === 'http:' ? u.href : undefined;
  } catch {
    return undefined;
  }
};
