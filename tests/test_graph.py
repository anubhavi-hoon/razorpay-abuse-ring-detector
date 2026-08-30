import unittest

from abuse_detector.data import Account, Transaction
from abuse_detector.graph import DEFAULT_MAX_ENTITY_ACCOUNTS, detect_rings


def account(account_id, *, device, ip, payment, created_at, ring_label=""):
    return Account(
        account_id=account_id,
        created_at=created_at,
        email_hash=f"email_{account_id}",
        phone_hash=f"phone_{account_id}",
        device_id=device,
        ip_address=ip,
        payment_instrument_id=payment,
        label=int(bool(ring_label)),
        ring_label=ring_label,
    )


def transaction(transaction_id, account_id, promotion=""):
    return Transaction(
        transaction_id=transaction_id,
        account_id=account_id,
        merchant_id="merchant_shared",
        promotion_id=promotion,
        amount="100.00",
        created_at="2026-01-01T01:00:00Z",
        status="succeeded",
    )


class GraphTest(unittest.TestCase):
    def test_shared_entities_link_accounts_and_noisy_entity_is_suppressed(self):
        accounts = [
            account(
                "acct_1",
                device="ring_device",
                ip="198.51.100.1",
                payment="ring_payment",
                created_at="2026-01-01T00:00:00Z",
                ring_label="truth_1",
            ),
            account(
                "acct_2",
                device="ring_device",
                ip="198.51.100.2",
                payment="ring_payment",
                created_at="2026-01-01T00:10:00Z",
                ring_label="truth_1",
            ),
            account("acct_3", device="device_3", ip="common_ip", payment="payment_3", created_at="2026-02-01T00:00:00Z"),
            account("acct_4", device="device_4", ip="common_ip", payment="payment_4", created_at="2026-03-01T00:00:00Z"),
            account("acct_5", device="device_5", ip="common_ip", payment="payment_5", created_at="2026-04-01T00:00:00Z"),
        ]
        transactions = [
            transaction("txn_1", "acct_1", "promo_1"),
            transaction("txn_2", "acct_2", "promo_1"),
            transaction("txn_3", "acct_3"),
            transaction("txn_4", "acct_4"),
            transaction("txn_5", "acct_5"),
        ]
        scores = {
            account.account_id: {
                "ml_score": 0.95 if account.ring_label else 0.05,
                "predicted_label": int(bool(account.ring_label)),
                "reason_codes": "HIGH_PROMOTION_RATIO" if account.ring_label else "",
            }
            for account in accounts
        }
        limits = dict(DEFAULT_MAX_ENTITY_ACCOUNTS)
        limits.update({"ip": 2, "merchant": 2})
        result = detect_rings(accounts, transactions, scores, limits)

        self.assertEqual(len(result["rings"]), 1)
        ring = result["rings"][0]
        members = {row["account_id"] for row in result["members"]}
        self.assertEqual(members, {"acct_1", "acct_2"})
        self.assertTrue(0 <= ring["score"] <= 1)
        self.assertTrue(ring["reason_codes"])
        self.assertIn("device", {edge["relationship_type"] for edge in result["edges"]})
        self.assertNotIn("common_ip", {node["label"] for node in result["nodes"]})
        self.assertEqual(result["evaluation"]["top20_ring_recall"], 1.0)
        self.assertEqual(result["evaluation"]["largest_component"], 2)


if __name__ == "__main__":
    unittest.main()

