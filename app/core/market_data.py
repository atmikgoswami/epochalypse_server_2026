import os
import pandas as pd
from app.core.config import settings

class MarketDataStore:
    def __init__(self):
        self._local: pd.DataFrame | None = None
        self._eval: pd.DataFrame | None = None

    def load(self):
        local_path = os.path.join(settings.data_dir, settings.local_test_file)
        eval_path  = os.path.join(settings.data_dir, settings.eval_file)

        self._local = self._load_and_validate(pd.read_csv(local_path))
        self._eval  = self._load_and_validate(pd.read_parquet(eval_path))

    def _load_and_validate(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.reset_index(drop=True)

        required = {"b_p_1", "a_p_1", "trade_flow", "volatility"}
        missing = required - set(df.columns)
        if missing:
            raise ValueError(
                f"Data file is missing required columns: {missing}. "
                f"Re-run prepare_dataset.py to regenerate the files."
            )

        if df["volatility"].isna().any():
            raise ValueError("volatility column contains NaN — re-run prepare_dataset.py.")

        return df

    def local_len(self) -> int:
        return len(self._local)

    def eval_len(self) -> int:
        return len(self._eval)

    def local_tick(self, index: int) -> dict:
        return self._row(self._local, index)

    def eval_tick(self, index: int) -> dict:
        return self._row(self._eval, index)

    def _row(self, df: pd.DataFrame, index: int) -> dict:
        row = df.iloc[index]
        return {
            "tick":       index,
            "b_p":        [float(row[f"b_p_{i}"]) for i in range(1, 11)],
            "b_v":        [float(row[f"b_v_{i}"]) for i in range(1, 11)],
            "a_p":        [float(row[f"a_p_{i}"]) for i in range(1, 11)],
            "a_v":        [float(row[f"a_v_{i}"]) for i in range(1, 11)],
            "trade_flow": float(row.get("trade_flow", 0.0)),
            "volatility": float(row["volatility"]),
        }


market_data = MarketDataStore()