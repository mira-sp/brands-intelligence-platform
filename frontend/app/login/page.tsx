'use client';

// frontend/app/login/page.tsx
import { Radar } from 'lucide-react';
import { useRouter } from 'next/navigation';
import { useState } from 'react';
import { apiService } from '../../src/services/api';

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await apiService.login(email, password);
      router.replace('/');
    } catch {
      setError('That email and password did not match.');
    } finally {
      setBusy(false);
    }
  };

  const field =
    'mt-1.5 w-full rounded-lg border border-rule bg-paper px-3 py-2 text-sm outline-none transition-colors focus:border-ink-3';

  return (
    <div className="grid min-h-screen place-items-center px-4">
      <div className="w-full max-w-sm">
        <div className="mb-6 flex items-center gap-2 text-[15px] font-medium">
          <span className="grid size-6 place-items-center rounded-md bg-ink text-paper" aria-hidden>
            <Radar size={14} strokeWidth={1.75} />
          </span>
          Visibility
        </div>
        <form onSubmit={submit} className="card space-y-4 p-6">
          <div>
            <h1 className="text-lg font-medium">Sign in</h1>
            <p className="mt-1 text-sm text-ink-3">Use the account your administrator created for you.</p>
          </div>
          <label className="block">
            <span className="label">Email</span>
            <input
              type="email"
              autoComplete="username"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className={field}
            />
          </label>
          <label className="block">
            <span className="label">Password</span>
            <input
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className={field}
            />
          </label>
          {error && (
            <p role="alert" className="rounded-lg bg-wash px-3 py-2 text-sm text-bad">
              {error}
            </p>
          )}
          <button
            type="submit"
            disabled={busy}
            className="w-full rounded-lg bg-ink py-2 text-sm font-medium text-paper transition-opacity hover:opacity-90 disabled:opacity-50"
          >
            {busy ? 'Signing in…' : 'Sign in'}
          </button>
        </form>
      </div>
    </div>
  );
}
