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

/** Plain-language explanations for reason codes. */
export const REASON_CODE_SENTENCES: Record<string, string> = {
  HIGH_MEAN_ML_SCORE: 'These accounts have a high average risk score.',
  MULTIPLE_SHARED_ENTITIES: 'These accounts share multiple identifiers or relationships.',
  DENSE_ACCOUNT_LINKS: 'These accounts form a dense relationship network.',
  CONCENTRATED_PROMOTIONS: 'These accounts concentrated their activity on the same promotions.',
  CLUSTERED_ACCOUNT_CREATION: 'These accounts were created within a short time window.',
  SHARED_PAYMENT_INSTRUMENT: 'These accounts reused the same payment method.',
  SHARED_DEVICE: 'These accounts reused the same device.',
  RAPID_PROMO_CLAIMS: 'These accounts claimed promotions repeatedly within a short period.',
  HIGH_PROMOTION_RATIO: 'A high share of their transactions used promotions.',
  HIGH_FAILURE_RATIO: 'A high share of their transactions failed.',
  HIGH_REFUND_RATIO: 'A high share of their transactions were refunded.',
  EARLY_PROMOTION_USE: 'Promotions were used soon after account creation.',
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

/** Returns a sentence explanation, with a readable fallback for unknown codes. */
export function getReasonSentence(code: string): string {
  return REASON_CODE_SENTENCES[code] ?? `${getReasonLabel(code)}.`;
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

/** Return the user-facing risk band for a 0–1 score. */
export function getRiskLevel(score: number): string {
  if (score >= SCORE_BUCKETS.high.min) return 'High risk';
  if (score >= SCORE_BUCKETS.medium.min) return 'Medium risk';
  return 'Low risk';
}

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

/* ================================================================== */
/*  Behavioral Feature Explorer Metadata                               */
/* ================================================================== */

export type FeatureCategory =
  | 'lifecycle'
  | 'activity'
  | 'promotions'
  | 'outcomes'
  | 'shared_identity';

export interface FeatureMeta {
  key: string;
  label: string;
  description: string;
  category: FeatureCategory;
  isRatio?: boolean;
  isSharedIdentity?: boolean;
}

export const FEATURE_CATEGORIES: { key: 'all' | FeatureCategory; label: string }[] = [
  { key: 'all', label: 'All' },
  { key: 'lifecycle', label: 'Lifecycle' },
  { key: 'activity', label: 'Activity' },
  { key: 'promotions', label: 'Promotions' },
  { key: 'outcomes', label: 'Outcomes' },
  { key: 'shared_identity', label: 'Shared identity' },
];

export const BEHAVIORAL_FEATURES: Record<string, FeatureMeta> = {
  // Account lifecycle
  account_age_days: {
    key: 'account_age_days',
    label: 'Account age',
    description: 'Days between account creation and the analysis cutoff.',
    category: 'lifecycle',
  },
  time_to_first_promotion_hours: {
    key: 'time_to_first_promotion_hours',
    label: 'Time to first promotion',
    description: 'Hours between signup and the first observed promotion claim.',
    category: 'lifecycle',
  },

  // Transaction activity
  transaction_count: {
    key: 'transaction_count',
    label: 'Transactions',
    description: 'Number of transactions observed before the analysis cutoff.',
    category: 'activity',
  },
  total_amount: {
    key: 'total_amount',
    label: 'Total transaction amount',
    description: 'Combined value of all observed transactions.',
    category: 'activity',
  },
  mean_amount: {
    key: 'mean_amount',
    label: 'Average transaction amount',
    description: 'Average value of an observed transaction.',
    category: 'activity',
  },
  distinct_merchant_count: {
    key: 'distinct_merchant_count',
    label: 'Distinct merchants',
    description: 'Number of different merchants used by this account.',
    category: 'activity',
  },

  // Promotion behavior
  promotion_claim_count: {
    key: 'promotion_claim_count',
    label: 'Promotion claims',
    description: 'Number of observed transactions that used a promotion.',
    category: 'promotions',
  },
  promotion_claim_ratio: {
    key: 'promotion_claim_ratio',
    label: 'Promotion-use ratio',
    description: 'Share of observed transactions that used a promotion.',
    category: 'promotions',
    isRatio: true,
  },
  distinct_promotion_count: {
    key: 'distinct_promotion_count',
    label: 'Distinct promotions',
    description: 'Number of different promotions used by this account.',
    category: 'promotions',
  },
  max_promotion_claims_1h: {
    key: 'max_promotion_claims_1h',
    label: 'Peak promotion claims per hour',
    description: 'Highest number of promotion claims observed in any rolling one-hour window.',
    category: 'promotions',
  },

  // Outcomes and velocity
  failure_ratio: {
    key: 'failure_ratio',
    label: 'Failed transaction ratio',
    description: 'Share of observed transactions that failed.',
    category: 'outcomes',
    isRatio: true,
  },
  refund_ratio: {
    key: 'refund_ratio',
    label: 'Refunded transaction ratio',
    description: 'Share of observed transactions that were refunded.',
    category: 'outcomes',
    isRatio: true,
  },
  max_transactions_1h: {
    key: 'max_transactions_1h',
    label: 'Peak transactions per hour',
    description: 'Highest number of transactions observed in any rolling one-hour window.',
    category: 'outcomes',
  },

  // Shared identity signals
  shared_device_accounts: {
    key: 'shared_device_accounts',
    label: 'Accounts sharing this device',
    description: 'Other visible accounts using the same device.',
    category: 'shared_identity',
    isSharedIdentity: true,
  },
  shared_ip_accounts: {
    key: 'shared_ip_accounts',
    label: 'Accounts sharing this IP',
    description: 'Other visible accounts using the same IP address.',
    category: 'shared_identity',
    isSharedIdentity: true,
  },
  shared_payment_instrument_accounts: {
    key: 'shared_payment_instrument_accounts',
    label: 'Accounts sharing this payment method',
    description: 'Other visible accounts using the same payment instrument.',
    category: 'shared_identity',
    isSharedIdentity: true,
  },
  shared_email_accounts: {
    key: 'shared_email_accounts',
    label: 'Accounts sharing this email identifier',
    description: 'Other visible accounts using the same email identifier.',
    category: 'shared_identity',
    isSharedIdentity: true,
  },
  shared_phone_accounts: {
    key: 'shared_phone_accounts',
    label: 'Accounts sharing this phone identifier',
    description: 'Other visible accounts using the same phone identifier.',
    category: 'shared_identity',
    isSharedIdentity: true,
  },
};

/**
 * Returns metadata for a feature key, with safe fallback for unknown keys.
 */
export function getFeatureMeta(key: string): FeatureMeta {
  if (key in BEHAVIORAL_FEATURES) {
    return BEHAVIORAL_FEATURES[key];
  }
  const label = key
    .toLowerCase()
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase());
  return {
    key,
    label,
    description: `Observed value for ${label.toLowerCase()}.`,
    category: 'activity',
    isRatio: key.toLowerCase().includes('ratio'),
    isSharedIdentity: key.toLowerCase().includes('shared_'),
  };
}

/**
 * Formats a feature value with units and precision appropriate to its measurement.
 */
export function formatFeatureValue(key: string, value: number): string {
  // Missing promotion representation
  if (key === 'time_to_first_promotion_hours') {
    if (value === -1) {
      return 'No promotion observed';
    }
    return `${value.toFixed(2)} hours`;
  }

  // Account age in days
  if (key === 'account_age_days') {
    return `${value.toFixed(2)} days`;
  }

  // Ratios (0.0 - 1.0 -> 0.00% - 100.00%)
  if (key.toLowerCase().includes('ratio')) {
    return `${(value * 100).toFixed(2)}%`;
  }

  // Amounts (2 decimal places, no currency symbol)
  if (key === 'total_amount' || key === 'mean_amount') {
    return value.toFixed(2);
  }

  // Integer counts
  if (
    key.includes('count') ||
    key.includes('accounts') ||
    key.includes('_1h') ||
    Number.isInteger(value)
  ) {
    return Math.round(value).toLocaleString();
  }

  // Fallback
  return value.toFixed(2);
}
