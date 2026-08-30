/* TypeScript interfaces matching the OpenAPI schema in docs/openapi.json */

export interface SummaryResponse {
  run_id: string;
  account_count: number;
  transaction_count: number;
  scored_account_count: number;
  flagged_account_count: number;
  ring_count: number;
  score_distribution: Record<string, number>;
  review_status_totals: Record<string, number>;
}

export type ReviewStatus = 'new' | 'reviewing' | 'confirmed' | 'dismissed';

export interface RingItem {
  ring_id: string;
  score: number;
  status: ReviewStatus;
  created_at: string;
  member_count: number;
  shared_entity_count: number;
  entity_types: string[];
  promotion_ids: string[];
  reason_codes: string[];
}

export interface RingPage {
  items: RingItem[];
  page: number;
  page_size: number;
  total: number;
}

export interface RingMemberOut {
  account_id: string;
  ml_score: number;
  reason_codes: string[];
}

export interface SharedEntity {
  id: string;
  type: string;
  label: string;
}

export interface GraphNode {
  id: string;
  type: string;
  label: string;
}

export interface GraphEdge {
  source: string;
  target: string;
  type: string;
}

export interface RingDetail {
  ring_id: string;
  score: number;
  status: ReviewStatus;
  created_at: string;
  member_count: number;
  shared_entity_count: number;
  entity_types: string[];
  promotion_ids: string[];
  reason_codes: string[];
  density: number;
  promotion_concentration: number;
  mean_ml_score: number;
  max_ml_score: number;
  temporal_concentration: number;
  members: RingMemberOut[];
  shared_entities: SharedEntity[];
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export type TransactionStatus = 'succeeded' | 'failed' | 'refunded';

export interface TransactionOut {
  transaction_id: string;
  merchant_id: string;
  promotion_id: string | null;
  amount: number;
  created_at: string;
  status: TransactionStatus;
}

export interface AccountDetail {
  account_id: string;
  created_at: string;
  email_hash: string;
  phone_hash: string;
  device_id: string;
  ip_address: string;
  payment_instrument_id: string;
  ml_score: number;
  predicted_label: number;
  reason_codes: string[];
  features: Record<string, number>;
  ring_ids: string[];
  transactions: TransactionOut[];
}

export interface ReviewStatusResponse {
  ring_id: string;
  status: ReviewStatus;
}

export interface ReviewStatusUpdate {
  status: ReviewStatus;
}

export interface RingFilterParams {
  page?: number;
  page_size?: number;
  min_score?: number;
  status?: ReviewStatus | null;
  promotion?: string | null;
  date_from?: string | null;
  date_to?: string | null;
}
