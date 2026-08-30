import type { ReviewStatus } from './types';

/**
 * Human-readable labels for reason codes.
 * Unknown codes fall back to title-cased text via getReasonLabel().
 */
export const REASON_CODE_LABELS: Record<string, string> = {
  HIGH_MEAN_ML_SCORE: 'High average account risk',
  MULTIPLE_SHARED_ENTITIES: 'Multiple shared entities',
  DENSE_ACCOUNT_LINKS: 'Dense account relationships',
  CONCENTRATED_PROMOTIONS: 'Concentrated promotion use',
  CLUSTERED_ACCOUNT_CREATION: 'Closely timed account creation',
  SHARED_PAYMENT_INSTRUMENT: 'Shared payment instrument',
  SHARED_DEVICE: 'Shared device',
  RAPID_PROMO_CLAIMS: 'Rapid promotion claims',
  HIGH_PROMOTION_RATIO: 'High promotion-use ratio',
  HIGH_FAILURE_RATIO: 'High payment-failure ratio',
  HIGH_REFUND_RATIO: 'High refund ratio',
  EARLY_PROMOTION_USE: 'Promotion used soon after signup',
};

/** Returns the human label for a reason code, falling back to title case. */
export function getReasonLabel(code: string): string {
  if (code in REASON_CODE_LABELS) {
    return REASON_CODE_LABELS[code];
  }
  // Title-case fallback: "SOME_UNKNOWN_CODE" → "Some Unknown Code"
  return code
    .toLowerCase()
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

/**
 * Allowed review-status transitions.
 * Key = current status, value = list of allowed next statuses.
 */
export const REVIEW_TRANSITIONS: Record<ReviewStatus, ReviewStatus[]> = {
  new: ['reviewing'],
  reviewing: ['new', 'confirmed', 'dismissed'],
  confirmed: ['reviewing'],
  dismissed: ['reviewing'],
};

/** Button labels for status transitions. */
export const TRANSITION_LABELS: Record<ReviewStatus, string> = {
  new: 'Return to New',
  reviewing: 'Start Reviewing',
  confirmed: 'Confirm',
  dismissed: 'Dismiss',
};

/** Reopening statuses share a label. */
export function getTransitionLabel(
  currentStatus: ReviewStatus,
  targetStatus: ReviewStatus,
): string {
  if (
    (currentStatus === 'confirmed' || currentStatus === 'dismissed') &&
    targetStatus === 'reviewing'
  ) {
    return 'Reopen';
  }
  if (currentStatus === 'new' && targetStatus === 'reviewing') {
    return 'Start Reviewing';
  }
  return TRANSITION_LABELS[targetStatus];
}

/** Score bucket thresholds matching the backend's summary buckets. */
export const SCORE_BUCKETS = {
  low: { max: 0.5, label: 'Low' },
  medium: { min: 0.5, max: 0.8, label: 'Medium' },
  high: { min: 0.8, label: 'High' },
} as const;

/** Format a 0–1 score as a percentage string. */
export function formatScore(score: number): string {
  return `${(score * 100).toFixed(2)}%`;
}

/** Format an ISO date string for display. */
export function formatDate(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleDateString('en-GB', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  });
}

/** Format an ISO datetime string for display. */
export function formatDateTime(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleString('en-GB', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}
