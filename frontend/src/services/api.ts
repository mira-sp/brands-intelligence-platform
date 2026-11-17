// frontend/src/services/api.ts

export interface Brand {
  id: string;
  name: string;
  industry: string;
  website?: string;
  is_active: boolean;
}

export interface Mention {
  id: string;
  brand_id: string;
  content: string;
  platform: string;
  sentiment_score: number;
  sentiment_label: 'positive' | 'negative' | 'neutral';
  crisis_probability: number;
  published_at: string;
  likes_count: number;
  shares_count: number;
  comments_count: number;
}

export interface SentimentAnalysis {
  sentiment_score: number;
  sentiment_label: string;
  confidence: number;
  crisis_probability: number;
  urgency_score: number;
  crisis_indicators: number;
  model_info: Record<string, unknown>;
}

export interface CrisisAlert {
  id: string;
  brand_id: string;
  content: string;
  platform: string;
  sentiment_score: number;
  sentiment_label: string;
  crisis_probability: number;
  published_at: string;
  urgency_level: 'HIGH' | 'MEDIUM' | 'LOW';
}

export interface AnalyticsOverview {
  total_mentions: number;
  average_sentiment: number;
  sentiment_breakdown: {
    positive: number;
    negative: number;
    neutral: number;
  };
  high_crisis_alerts: number;
  urgent_mentions: number;
  sentiment_distribution: {
    positive_percentage: number;
    negative_percentage: number;
    neutral_percentage: number;
  };
  crisis_metrics: {
    crisis_percentage: number;
    urgent_percentage: number;
  };
}

const TOKEN_KEY = 'bip_access_token';

class ApiService {
  private baseURL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';
  // Short-lived JWT (30 min). Kept in sessionStorage so it is cleared when the tab closes.
  private token: string | null = null;

  private getToken(): string | null {
    if (this.token) return this.token;
    try {
      this.token = typeof window !== 'undefined' ? window.sessionStorage.getItem(TOKEN_KEY) : null;
    } catch {
      this.token = null;
    }
    return this.token;
  }

  private request(path: string, init: RequestInit = {}): Promise<Response> {
    const headers = new Headers(init.headers);
    const token = this.getToken();
    if (token) headers.set('Authorization', `Bearer ${token}`);
    return fetch(`${this.baseURL}${path}`, { ...init, headers }).then((response) => {
      if (response.status === 401) this.logout();
      return response;
    });
  }

  async login(email: string, password: string): Promise<void> {
    const body = new URLSearchParams({ username: email, password });
    const response = await fetch(`${this.baseURL}/auth/token`, { method: 'POST', body });
    if (!response.ok) throw new Error('Login failed');
    const data: { access_token: string } = await response.json();
    this.token = data.access_token;
    try {
      window.sessionStorage.setItem(TOKEN_KEY, data.access_token);
    } catch {
      /* storage unavailable - token stays in memory only */
    }
  }

  logout(): void {
    this.token = null;
    try {
      window.sessionStorage.removeItem(TOKEN_KEY);
    } catch {
      /* ignore */
    }
  }

  isAuthenticated(): boolean {
    return this.getToken() !== null;
  }

  async getBrands(): Promise<Brand[]> {
    const response = await this.request(`/api/brands`);
    if (!response.ok) throw new Error('Failed to fetch brands');
    return response.json();
  }

  async getMentions(params?: { limit?: number; brand_id?: string }): Promise<Mention[]> {
    const query = new URLSearchParams();
    if (params?.limit) query.append('limit', params.limit.toString());
    if (params?.brand_id) query.append('brand_id', params.brand_id);
    
    const response = await this.request(`/api/mentions?${query}`);
    if (!response.ok) throw new Error('Failed to fetch mentions');
    return response.json();
  }

  async getSampleData(): Promise<{ brands: Brand[]; mentions: Mention[] }> {
    const response = await this.request(`/api/demo/sample-data`);
    if (!response.ok) throw new Error('Failed to fetch sample data');
    return response.json();
  }

  async analyzeSentiment(text: string): Promise<SentimentAnalysis> {
    const response = await this.request(`/api/ml/analyze-sentiment`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text })
    });
    if (!response.ok) throw new Error('Failed to analyze sentiment');
    return response.json();
  }

  async getCrisisAlerts(threshold: number = 0.7): Promise<{ crisis_alerts: CrisisAlert[]; total_alerts: number }> {
    const response = await this.request(`/api/mentions/crisis-alerts?threshold=${encodeURIComponent(threshold)}`);
    if (!response.ok) throw new Error('Failed to fetch crisis alerts');
    return response.json();
  }

  async getAnalyticsOverview(): Promise<AnalyticsOverview> {
    const response = await this.request(`/api/analytics/sentiment-overview`);
    if (!response.ok) throw new Error('Failed to fetch analytics');
    return response.json();
  }

  async reanalyzeMention(mentionId: string): Promise<Record<string, unknown>> {
    const response = await this.request(`/api/mentions/${encodeURIComponent(mentionId)}/reanalyze`, {
      method: 'POST'
    });
    if (!response.ok) throw new Error('Failed to reanalyze mention');
    return response.json();
  }

  async getModelInfo(): Promise<Record<string, unknown>> {
    const response = await this.request(`/api/ml/model-info`);
    if (!response.ok) throw new Error('Failed to fetch model info');
    return response.json();
  }
}

export const apiService = new ApiService();