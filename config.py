"""
Configuration and Environment Settings.
"""

import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "")
TABLE_NAME = os.getenv("TABLE_NAME", "links")
DEFAULT_CSV_PATH = os.getenv("GREENHOUSE_CSV_PATH", "greenhouse.csv")
DEFAULT_CONCURRENCY = int(os.getenv("CONCURRENCY", "40"))
DEFAULT_DAYS = int(os.getenv("DEFAULT_DAYS", "1"))

# ApplyUs Dynamic Microservice Settings
INTERNAL_SERVICE_API_KEY = os.getenv("INTERNAL_SERVICE_API_KEY", "applyus_secret_microservice_key_2026")
APPLYUS_API_URL = os.getenv("APPLYUS_API_URL", "https://api.applyus.org/api/clients/active-domains")

# Webshare Proxy Settings
WEBSHARE_PROXY_URL = os.getenv("WEBSHARE_PROXY_URL", "")
WEBSHARE_PROXIES = os.getenv("WEBSHARE_PROXIES", "")

