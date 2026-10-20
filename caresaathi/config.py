"""Configuration settings for CareSaathi AI."""
import os
from pathlib import Path

# Base directories
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

# Database
DB_PATH = str(DATA_DIR / "caresaathi.db")

# Emergency contact numbers (PRD Section 8: In India, 112 is the national emergency number)
NATIONAL_EMERGENCY_NUMBER = "112"
AMBULANCE_NUMBER = "102"

# Agent configurations
AGENT_NAME = "caresaathi_agent"
AGENT_SEED = os.getenv("CARESAATHI_AGENT_SEED", "caresaathi_fetchathon_seed_2026_demo")
AGENT_PORT = int(os.getenv("CARESAATHI_AGENT_PORT", "8008"))
AGENT_ENDPOINT = f"http://127.0.0.1:{AGENT_PORT}/submit"

# Web UI configurations
WEB_PORT = int(os.getenv("CARESAATHI_WEB_PORT", "8080"))
WEB_HOST = os.getenv("CARESAATHI_WEB_HOST", "127.0.0.1")

# Standard clinical disclaimers
CLINICAL_DISCLAIMER = (
    "DISCLAIMER: CareSaathi AI is an administrative and routine tracking assistant "
    "operating strictly on doctor-approved care plans. It is NOT a diagnostic tool, "
    "does not prescribe or alter medications, and cannot replace emergency medical services. "
    "In case of severe acute distress, call 112 immediately."
)
