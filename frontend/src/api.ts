import type {
  SummaryResponse,
  RingPage,
  RingDetail,
  AccountDetail,
  ReviewStatusResponse,
  ReviewStatus,
  RingFilterParams,
} from './types';

const API_BASE =
  (import.meta.env.VITE_API_BASE_URL as string | undefined) ||
  'http://127.0.0.1:8000/api/v1';

/** Structured API error thrown on non-2xx responses. */
export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

async function handleResponse<T>(res: Response): Promise<T> {
  if (res.ok) {
    return res.json() as Promise<T>;
  }

  let message: string;
  try {
    const body = await res.json();
    if (typeof body.detail === 'string') {
      message = body.detail;
    } else if (Array.isArray(body.detail)) {
      // Validation errors: [{loc, msg, type}, ...]
      message = body.detail
        .map((e: { loc?: unknown[]; msg?: string }) => {
          const loc = Array.isArray(e.loc) ? e.loc.join(' → ') : '';
          return loc ? `${loc}: ${e.msg}` : (e.msg ?? 'Validation error');
        })
        .join('; ');
    } else {
      message = JSON.stringify(body);
    }
  } catch {
    message = `HTTP ${res.status}`;
  }

  if (res.status === 503) {
    throw new ApiError(503, 'Backend unavailable. Is the API server running?');
  }
  if (res.status === 404) {
    throw new ApiError(404, message || 'Not found');
  }

  throw new ApiError(res.status, message);
}

async function get<T>(path: string): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`);
  } catch {
    throw new ApiError(0, 'Network error. Could not reach the API.');
  }
  return handleResponse<T>(res);
}

async function patch<T>(path: string, body: unknown): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
  } catch {
    throw new ApiError(0, 'Network error. Could not reach the API.');
  }
  return handleResponse<T>(res);
}

/* ------------------------------------------------------------------ */
/*  Public API functions                                               */
/* ------------------------------------------------------------------ */

export function fetchSummary(): Promise<SummaryResponse> {
  return get<SummaryResponse>('/summary');
}

export function fetchRings(params: RingFilterParams = {}): Promise<RingPage> {
  const searchParams = new URLSearchParams();
  if (params.page != null) searchParams.set('page', String(params.page));
  if (params.page_size != null)
    searchParams.set('page_size', String(params.page_size));
  if (params.min_score != null && params.min_score > 0)
    searchParams.set('min_score', String(params.min_score));
  if (params.status) searchParams.set('status', params.status);
  if (params.promotion) searchParams.set('promotion', params.promotion);
  if (params.date_from) searchParams.set('date_from', params.date_from);
  if (params.date_to) searchParams.set('date_to', params.date_to);

  const qs = searchParams.toString();
  return get<RingPage>(`/rings${qs ? `?${qs}` : ''}`);
}

export function fetchRingDetail(ringId: string): Promise<RingDetail> {
  return get<RingDetail>(`/rings/${encodeURIComponent(ringId)}`);
}

export function fetchAccountDetail(accountId: string): Promise<AccountDetail> {
  return get<AccountDetail>(`/accounts/${encodeURIComponent(accountId)}`);
}

export function updateRingStatus(
  ringId: string,
  status: ReviewStatus,
): Promise<ReviewStatusResponse> {
  return patch<ReviewStatusResponse>(
    `/rings/${encodeURIComponent(ringId)}/status`,
    { status },
  );
}
