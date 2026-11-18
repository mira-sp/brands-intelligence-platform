'use client';

// frontend/app/page.tsx - AI visibility briefing
import { useRouter } from 'next/navigation';
import { useCallback, useEffect, useState } from 'react';
import { AssistantColumns } from '../src/components/visibility/AssistantColumns';
import { AnswerDrawer, type DrawerTarget } from '../src/components/visibility/AnswerDrawer';
import { InsightBanner } from '../src/components/visibility/InsightBanner';
import { KpiRow } from '../src/components/visibility/KpiRow';
import { Masthead } from '../src/components/visibility/Masthead';
import { QuestionMatrix } from '../src/components/visibility/QuestionMatrix';
import { ShareOfVoice } from '../src/components/visibility/ShareOfVoice';
import { Sources } from '../src/components/visibility/Sources';
import { TrendChart } from '../src/components/visibility/TrendChart';
import { apiService } from '../src/services/api';
import {
  UnauthorizedError,
  visibilityApi,
  type BrandRef,
  type Matrix,
  type Summary,
  type Trend,
  type VisibilityConfig,
} from '../src/services/visibility';

const BRAND_KEY = 'briefing-brand';

interface Data {
  summary: Summary;
  trend: Trend;
  matrix: Matrix;
  config: VisibilityConfig;
}

export default function BriefingPage() {
  const router = useRouter();
  const [brands, setBrands] = useState<BrandRef[] | null>(null);
  const [brandId, setBrandId] = useState<string | null>(null);
  const [days, setDays] = useState(30);
  const [data, setData] = useState<Data | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [drawer, setDrawer] = useState<DrawerTarget | null>(null);

  const handleError = useCallback(
    (e: unknown) => {
      if (e instanceof UnauthorizedError) router.replace('/login');
      else setError(e instanceof Error ? e.message : 'Something went wrong');
    },
    [router],
  );

  // Who am I + which brands exist
  useEffect(() => {
    visibilityApi
      .me()
      .then(() => visibilityApi.brands())
      .then((list) => {
        setBrands(list);
        let stored: string | null = null;
        try {
          stored = window.localStorage.getItem(BRAND_KEY);
        } catch {
          /* ignore */
        }
        setBrandId(list.find((b) => b.id === stored)?.id ?? list[0]?.id ?? null);
      })
      .catch(handleError);
  }, [handleError]);

  // Everything for the selected brand + period
  useEffect(() => {
    if (!brandId) return;
    let cancelled = false;
    setError(null);
    Promise.all([
      visibilityApi.summary(brandId, days),
      visibilityApi.trend(brandId, Math.max(days, 90)),
      visibilityApi.matrix(brandId, days),
      visibilityApi.config(brandId),
    ])
      .then(([summary, trend, matrix, config]) => !cancelled && setData({ summary, trend, matrix, config }))
      .catch((e) => !cancelled && handleError(e));
    return () => {
      cancelled = true;
    };
  }, [brandId, days, handleError]);

  const selectBrand = (id: string) => {
    setData(null);
    setBrandId(id);
    try {
      window.localStorage.setItem(BRAND_KEY, id);
    } catch {
      /* ignore */
    }
  };

  const brand = brands?.find((b) => b.id === brandId);
  const closeDrawer = useCallback(() => setDrawer(null), []);

  return (
    <div className="mx-auto max-w-[1180px] px-4 pb-24 sm:px-8">
      <Masthead
        brands={brands ?? []}
        brandId={brandId}
        onBrand={selectBrand}
        days={days}
        onDays={setDays}
        onSignOut={() => {
          apiService.logout();
          router.replace('/login');
        }}
      />

      {error && (
        <p role="alert" className="mt-8 border-l-2 border-bad pl-3 text-sm text-ink-2">
          {error}
        </p>
      )}

      {brands && !brands.length && (
        <p className="mt-16 text-lg text-ink-2">No brands yet. Create one and add some questions to track.</p>
      )}

      {!data && !error && brands?.length !== 0 && <LoadingState />}

      {data && brand && (
        <main className="space-y-4">
          <div className="flex flex-wrap items-end justify-between gap-2 pt-8 pb-2">
            <div>
              <h1 className="text-2xl font-medium tracking-tight">{brand.name}</h1>
              <p className="mt-1 text-sm text-ink-3">
                Last {days} days · {data.summary.runs.toLocaleString('en')} answers from{' '}
                {Object.keys(data.summary.by_provider).length} assistants
              </p>
            </div>
          </div>
          <InsightBanner summary={data.summary} matrix={data.matrix} brandName={brand.name} days={days} />
          <KpiRow summary={data.summary} trend={data.trend} days={days} />
          <AssistantColumns summary={data.summary} trend={data.trend} />
          <div className="grid gap-4 lg:grid-cols-[1.4fr_1fr]">
            <TrendChart trend={data.trend} />
            <ShareOfVoice summary={data.summary} brandName={brand.name} />
          </div>
          <QuestionMatrix
            matrix={data.matrix}
            onOpen={(promptId, question, provider) => setDrawer({ promptId, question, provider })}
          />
          <Sources summary={data.summary} />
          <footer className="pt-4 flex flex-wrap justify-between gap-2 text-xs text-ink-3">
            <span>
              Mentions are detected by name matching; tone, rank and claims by an AI judge. Every number links back to
              the stored answers.
            </span>
            <a href="/sentiment" className="underline decoration-rule-strong underline-offset-[3px] hover:text-ink">
              Legacy sentiment view
            </a>
          </footer>
        </main>
      )}

      {brandId && data && (
        <AnswerDrawer
          target={drawer}
          brandId={brandId}
          brandNames={[brand?.name ?? '', ...data.config.aliases]}
          competitors={data.config.competitors}
          onClose={closeDrawer}
        />
      )}
    </div>
  );
}

function LoadingState() {
  return (
    <div className="animate-pulse py-10" aria-label="Loading">
      <div className="h-3 w-32 rounded bg-wash" />
      <div className="mt-6 h-12 w-3/4 rounded bg-wash" />
      <div className="mt-3 h-12 w-1/2 rounded bg-wash" />
      <div className="mt-14 grid grid-cols-2 gap-6 lg:grid-cols-4">
        {[0, 1, 2, 3].map((i) => (
          <div key={i} className="h-28 rounded bg-wash" />
        ))}
      </div>
    </div>
  );
}
