from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    redis_url: str
    data_dir: str = "./data"
    
    local_test_file: str = "epoch_lob_local_test.csv"
    eval_file: str = "epoch_server_hidden.parquet"

    eval_checkpoint_interval: int = 50
    initial_cash: float = 100_000.0
    inventory_penalty_gamma: float = 0.01
    
    volatility_window: int = 1200

    eval_deadline: str = "2099-12-31T23:59:59"
    secret_key: str

settings = Settings()