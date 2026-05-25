"""Konfiguracja. Limity budżetu, klucze, ścieżki."""
import os
DAILY_BUDGET_USD = float(os.getenv("DAILY_BUDGET_USD", "5.0"))
MONTHLY_BUDGET_USD = float(os.getenv("MONTHLY_BUDGET_USD", "60.0"))
DEFAULT_LANG = "pl"
