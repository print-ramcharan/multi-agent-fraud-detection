"""
Synthetic Transaction Data Generator for Fraud Detection

Generates realistic synthetic transaction data with ~3% fraud rate.
Features model real-world fraud patterns: higher amounts, newer accounts,
unusual hours, rapid successive transactions, etc.
"""

import os
import numpy as np
import pandas as pd

# Reproducibility
SEED = 42
np.random.seed(SEED)

# Configuration
N_TRANSACTIONS = 55_000
FRAUD_RATE = 0.03


def generate_legitimate(n: int) -> pd.DataFrame:
    """Generate legitimate transaction features."""
    return pd.DataFrame({
        # Log-normal amount centered around $150
        "amount": np.random.lognormal(mean=np.log(150), sigma=0.8, size=n).clip(1, 10_000),

        # Bimodal hours: peaks at 10-14 (lunch) and 18-20 (evening)
        "hour_of_day": np.concatenate([
            np.random.normal(12, 2, size=n // 2).clip(0, 23),
            np.random.normal(19, 1.5, size=n - n // 2).clip(0, 23),
        ]).astype(int),

        # Higher on weekdays (0=Mon, 6=Sun)
        "day_of_week": np.random.choice(
            range(7), size=n, p=[0.17, 0.17, 0.17, 0.17, 0.15, 0.09, 0.08]
        ),

        # 60% online
        "is_online": np.random.binomial(1, 0.60, size=n),

        # Low merchant risk
        "merchant_risk": np.random.beta(2, 8, size=n),

        # Low country risk
        "country_risk": np.random.beta(2, 10, size=n),

        # Established accounts, avg ~700 days
        "customer_age_days": np.random.gamma(shape=7, scale=100, size=n).clip(1, 5000).astype(int),

        # ~2 transactions in last 24h
        "transaction_count_24h": np.random.poisson(2, size=n).clip(0, 30),

        # Amount z-score close to 0
        "amount_zscore": np.random.normal(0, 1, size=n).clip(-4, 4),

        # Short distance from home
        "distance_from_home": np.abs(np.random.normal(15, 20, size=n)).clip(0, 500),

        # Older devices, avg ~200 days
        "device_age_days": np.random.gamma(shape=4, scale=50, size=n).clip(1, 2000).astype(int),

        # 10% new device
        "is_new_device": np.random.binomial(1, 0.10, size=n),

        # ~1.5 distinct merchants in 24h
        "distinct_merchants_24h": np.random.poisson(1.5, size=n).clip(0, 15),

        # ~12 hours since last transaction
        "time_since_last_txn_hours": np.abs(np.random.exponential(12, size=n)).clip(0.01, 168),
    })


def generate_fraud(n: int) -> pd.DataFrame:
    """Generate fraudulent transaction features."""
    return pd.DataFrame({
        # Higher amounts, centered around $800
        "amount": np.random.lognormal(mean=np.log(800), sigma=1.0, size=n).clip(5, 50_000),

        # Flat distribution across all hours (fraudsters don't sleep)
        "hour_of_day": np.random.randint(0, 24, size=n),

        # Skew towards weekends
        "day_of_week": np.random.choice(
            range(7), size=n, p=[0.10, 0.10, 0.10, 0.10, 0.12, 0.24, 0.24]
        ),

        # 85% online
        "is_online": np.random.binomial(1, 0.85, size=n),

        # High merchant risk
        "merchant_risk": np.random.beta(6, 3, size=n),

        # High country risk
        "country_risk": np.random.beta(5, 3, size=n),

        # Newer accounts, avg ~90 days
        "customer_age_days": np.random.gamma(shape=2, scale=45, size=n).clip(1, 1000).astype(int),

        # ~8 transactions in last 24h (rapid-fire)
        "transaction_count_24h": np.random.poisson(8, size=n).clip(1, 50),

        # Large deviation from normal spending
        "amount_zscore": np.random.normal(3, 1.5, size=n).clip(0, 10),

        # Large, variable distance from home
        "distance_from_home": np.abs(np.random.normal(500, 400, size=n)).clip(10, 15_000),

        # Very new devices, avg ~15 days
        "device_age_days": np.random.gamma(shape=2, scale=7.5, size=n).clip(1, 200).astype(int),

        # 60% new device
        "is_new_device": np.random.binomial(1, 0.60, size=n),

        # ~5 distinct merchants in 24h
        "distinct_merchants_24h": np.random.poisson(5, size=n).clip(1, 25),

        # Very short time since last transaction (~0.5 hours)
        "time_since_last_txn_hours": np.abs(np.random.exponential(0.5, size=n)).clip(0.001, 10),
    })


def generate_dataset(
    n_transactions: int = N_TRANSACTIONS,
    fraud_rate: float = FRAUD_RATE,
) -> pd.DataFrame:
    """Generate the full synthetic dataset with labels."""
    n_fraud = int(n_transactions * fraud_rate)
    n_legit = n_transactions - n_fraud

    legit_df = generate_legitimate(n_legit)
    legit_df["is_fraud"] = 0

    fraud_df = generate_fraud(n_fraud)
    fraud_df["is_fraud"] = 1

    df = pd.concat([legit_df, fraud_df], ignore_index=True)
    df = df.sample(frac=1, random_state=SEED).reset_index(drop=True)

    # Round continuous features for readability
    df["amount"] = df["amount"].round(2)
    df["amount_zscore"] = df["amount_zscore"].round(3)
    df["distance_from_home"] = df["distance_from_home"].round(1)
    df["time_since_last_txn_hours"] = df["time_since_last_txn_hours"].round(3)
    df["merchant_risk"] = df["merchant_risk"].round(4)
    df["country_risk"] = df["country_risk"].round(4)

    return df


def print_stats(df: pd.DataFrame) -> None:
    """Print class distribution and feature statistics."""
    total = len(df)
    n_fraud = df["is_fraud"].sum()
    n_legit = total - n_fraud

    print("=" * 60)
    print("SYNTHETIC TRANSACTION DATA — CLASS DISTRIBUTION")
    print("=" * 60)
    print(f"  Total transactions : {total:,}")
    print(f"  Legitimate         : {n_legit:,} ({n_legit / total * 100:.2f}%)")
    print(f"  Fraudulent         : {n_fraud:,} ({n_fraud / total * 100:.2f}%)")
    print("=" * 60)

    print("\nFeature Statistics (Legitimate vs. Fraud):")
    print("-" * 60)
    features = [c for c in df.columns if c != "is_fraud"]
    for feat in features:
        legit_mean = df.loc[df["is_fraud"] == 0, feat].mean()
        fraud_mean = df.loc[df["is_fraud"] == 1, feat].mean()
        print(f"  {feat:<28s}  legit={legit_mean:>10.2f}  fraud={fraud_mean:>10.2f}")
    print()


if __name__ == "__main__":
    print("Generating synthetic transaction data …")
    dataset = generate_dataset()

    output_dir = os.path.dirname(os.path.abspath(__file__))
    output_path = os.path.join(output_dir, "training_data.csv")

    dataset.to_csv(output_path, index=False)
    print(f"Saved {len(dataset):,} transactions to {output_path}")

    print_stats(dataset)
