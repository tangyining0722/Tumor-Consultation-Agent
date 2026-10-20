import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

@dataclass(frozen=True)
class Settings:
    deepseek_key: str = os.getenv("DEEPSEEK_API_KEY", "")
    deepseek_base: str = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    deepseek_model: str = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
    doubao_key: str = os.getenv("DOUBAO_API_KEY", "")
    doubao_base: str = os.getenv("DOUBAO_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3")
    doubao_model: str = os.getenv("DOUBAO_MODEL", "YOUR_ARK_ENDPOINT_ID")
    ncbi_email: str = os.getenv("NCBI_EMAIL", "")
    db_path: str = os.getenv("MEDICOUNCIL_DB", "medicouncil.db")

settings = Settings()
