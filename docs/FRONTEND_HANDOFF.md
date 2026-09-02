# Frontend handoff

This document and [`openapi.json`](openapi.json) are the complete contract for the Antigravity frontend. The backend owns all detection, scoring, filtering, pagination, and review-transition rules; the frontend only presents API responses.

## Connection

- Local API base URL: `http://127.0.0.1:8000/api/v1`
- OpenAPI file: `docs/openapi.json`
- Interactive local docs: `http://127.0.0.1:8000/docs`
- Start the API with `ALLOWED_ORIGINS=http://localhost:3000 uvicorn abuse_detector.api:app --reload`.
- Replace `http://localhost:3000` with the frontend's exact origin. Multiple origins are comma-separated; wildcards are not enabled.
- Keep the API base URL configurable in the frontend. Do not append `/api/v1` in individual request functions.

The API serves the most recently loaded detection run. A `503` means the database is unavailable or no run has been loaded.

## Screens and calls

| Screen/action | API call | Presentation rule |
|---|---|---|
| Dashboard | `GET /summary` | Show totals, score buckets, and review-status totals. |
| Ranked rings | `GET /rings` | Render `items` in returned order; the server ranks by score. |
| Ring filters | `GET /rings` with query parameters | Send filters to the API; do not reimplement them client-side. |
| Ring detail | `GET /rings/{ring_id}` | Use `nodes` and `edges` directly for the relationship graph; present resilience separately from risk. |
| Account detail | `GET /accounts/{account_id}` | Open from a ring member and show features, reasons, and transactions. |
| Review status | `PATCH /rings/{ring_id}/status` | Send `{"status":"reviewing"}` and replace local status from the response. |

All screens need loading, empty, and error states. The graph needs a readable list fallback for accessibility and narrow screens.

## Ring list filters and pagination

| Parameter | Meaning |
|---|---|
| `page` | Integer starting at `1`; default `1`. |
| `page_size` | Integer `1`–`100`; default `20`. |
| `min_score` | Inclusive number from `0` to `1`. |
| `status` | Exact value: `new`, `reviewing`, `confirmed`, or `dismissed`. |
| `promotion` | Exact promotion ID. |
| `date_from`, `date_to` | Inclusive `YYYY-MM-DD` bounds on the earliest member signup date. |

Use the response's `page`, `page_size`, and `total` values for navigation. Changing a filter resets `page` to `1`. An empty result is a successful response with `items: []` and `total: 0`.

## Review workflow

| Current status | Allowed next status |
|---|---|
| `new` | `reviewing` |
| `reviewing` | `new`, `confirmed`, `dismissed` |
| `confirmed` | `reviewing` |
| `dismissed` | `reviewing` |

Submitting the existing status is also valid. A disallowed transition returns `409`; display the returned `detail` and keep the previous status.

## Reason-code labels

| Code | Display label |
|---|---|
| `HIGH_MEAN_ML_SCORE` | High average account risk |
| `MULTIPLE_SHARED_ENTITIES` | Multiple shared entities |
| `DENSE_ACCOUNT_LINKS` | Dense account relationships |
| `CONCENTRATED_PROMOTIONS` | Concentrated promotion use |
| `CLUSTERED_ACCOUNT_CREATION` | Closely timed account creation |
| `SHARED_PAYMENT_INSTRUMENT` | Shared payment instrument |
| `SHARED_DEVICE` | Shared device |
| `RAPID_PROMO_CLAIMS` | Rapid promotion claims |
| `HIGH_PROMOTION_RATIO` | High promotion-use ratio |
| `HIGH_FAILURE_RATIO` | High payment-failure ratio |
| `HIGH_REFUND_RATIO` | High refund ratio |
| `EARLY_PROMOTION_USE` | Promotion used soon after signup |

Unknown future codes should fall back to title-cased text instead of breaking the page. Scores are `0`–`1`; present them consistently as percentages without changing the underlying value.

## Representative successful payloads

`GET /summary`

```json
{
  "run_id": "default",
  "account_count": 2000,
  "transaction_count": 10000,
  "scored_account_count": 2000,
  "flagged_account_count": 75,
  "ring_count": 208,
  "score_distribution": {"low": 193, "medium": 0, "high": 15},
  "review_status_totals": {"new": 208, "reviewing": 0, "confirmed": 0, "dismissed": 0}
}
```

`GET /rings?page=1&page_size=1`

```json
{
  "items": [{
    "ring_id": "ring_ed21b140010d",
    "score": 0.99908648,
    "status": "new",
    "created_at": "2026-01-15T00:39:00Z",
    "member_count": 5,
    "shared_entity_count": 3,
    "entity_types": ["device", "ip", "payment_instrument"],
    "promotion_ids": ["promo_01"],
    "reason_codes": ["HIGH_MEAN_ML_SCORE", "MULTIPLE_SHARED_ENTITIES", "SHARED_DEVICE"]
  }],
  "page": 1,
  "page_size": 1,
  "total": 208
}
```

`GET /rings/ring_ed21b140010d`

```json
{
  "ring_id": "ring_ed21b140010d",
  "score": 0.99908648,
  "status": "new",
  "created_at": "2026-01-15T00:39:00Z",
  "member_count": 5,
  "shared_entity_count": 3,
  "entity_types": ["device", "ip", "payment_instrument"],
  "promotion_ids": ["promo_01"],
  "reason_codes": ["HIGH_MEAN_ML_SCORE", "MULTIPLE_SHARED_ENTITIES", "SHARED_DEVICE"],
  "density": 1.0,
  "promotion_concentration": 1.0,
  "mean_ml_score": 0.99954458,
  "max_ml_score": 0.9997344,
  "temporal_concentration": 0.995238,
  "detection_resilience": "moderate",
  "min_entity_removals": 3,
  "critical_entity_types": ["device", "ip", "payment_instrument"],
  "members": [{"account_id": "acct_000036", "ml_score": 0.9997344, "reason_codes": ["SHARED_PAYMENT_INSTRUMENT", "SHARED_DEVICE", "HIGH_PROMOTION_RATIO"]}],
  "shared_entities": [{"id": "device:device_ring_008", "type": "device", "label": "device_ring_008"}],
  "nodes": [
    {"id": "acct_000036", "type": "account", "label": "acct_000036"},
    {"id": "device:device_ring_008", "type": "device", "label": "device_ring_008"}
  ],
  "edges": [{"source": "acct_000036", "target": "device:device_ring_008", "type": "device"}]
}
```

`GET /accounts/acct_000036`

```json
{
  "account_id": "acct_000036",
  "created_at": "2026-01-15T01:27:00Z",
  "email_hash": "email_7ba1c47461a5749513c1",
  "phone_hash": "phone_49ed58a6101b64404da9",
  "device_id": "device_ring_008",
  "ip_address": "198.51.100.8",
  "payment_instrument_id": "payment_ring_008",
  "ml_score": 0.9997344,
  "predicted_label": 1,
  "reason_codes": ["SHARED_PAYMENT_INSTRUMENT", "SHARED_DEVICE", "HIGH_PROMOTION_RATIO"],
  "features": {"transaction_count": 4.0, "promotion_claim_ratio": 1.0, "refund_ratio": 0.25},
  "ring_ids": ["ring_ed21b140010d"],
  "transactions": [{
    "transaction_id": "txn_00000036",
    "merchant_id": "merchant_001",
    "promotion_id": "promo_01",
    "amount": 105.0,
    "created_at": "2026-01-15T05:36:00Z",
    "status": "succeeded"
  }]
}
```

`PATCH /rings/ring_ed21b140010d/status` with `{"status":"reviewing"}`

```json
{"ring_id":"ring_ed21b140010d","status":"reviewing"}
```

## Representative errors

Missing ring (`404`):

```json
{"detail":"Ring not found"}
```

Disallowed review transition (`409`):

```json
{"detail":"Cannot move ring from 'new' to 'confirmed'"}
```

Invalid filter relationship (`422`):

```json
{"detail":"date_from must not be after date_to"}
```

Schema validation errors also return `422`, with `detail` as an array of objects containing `loc`, `msg`, and `type`. Treat `detail` as either a string or an array when displaying API errors.

## Antigravity boundary

Build only the dashboard, ranked-ring list, ring detail/graph, account detail/transactions, filters, pagination, and review controls. Do not add authentication, data upload, model training, risk calculations, mock APIs, backend routes, or frontend-only filtering. Those are either backend responsibilities or outside this MVP.
