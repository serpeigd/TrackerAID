"""Configuración centralizada leída de variables de entorno.

Todo el proyecto lee la config de aquí en vez de llamar a os.environ
disperso por el código, para que quede un único sitio que documente
qué variables existen y sus valores por defecto (ver .env.example).
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    bdns_base_url: str = os.getenv(
        "BDNS_BASE_URL", "https://www.infosubvenciones.es/bdnstrans/api"
    )
    bdns_vpd: str = os.getenv("BDNS_VPD", "GE")
    database_url: str = os.getenv("DATABASE_URL", "")
    llm_monthly_budget_eur: float = float(os.getenv("LLM_MONTHLY_BUDGET_EUR", "5"))
    supabase_url: str = os.getenv("SUPABASE_URL", "")
    supabase_service_role_key: str = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    ollama_url: str = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
    ollama_model: str = os.getenv("OLLAMA_MODEL", "llama3.1:8b")


settings = Settings()
