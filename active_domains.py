"""
Active Domains & Client Profiles Client.
Fetches dynamic desired_job_titles and keywords from https://api.applyus.org/api/clients/active-domains
"""

import os
import logging
from typing import List, Dict, Any, Set, Tuple, Optional
import requests
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger("active_domains")

DEFAULT_API_URL = os.getenv("APPLYUS_API_URL", "https://api.applyus.org/api/clients/active-domains")
DEFAULT_API_KEY = os.getenv("INTERNAL_SERVICE_API_KEY", "applyus_secret_microservice_key_2026")


class ActiveDomainsClient:
    def __init__(self, api_url: str = DEFAULT_API_URL, api_key: str = DEFAULT_API_KEY):
        self.api_url = api_url
        self.api_key = api_key
        self._cached_data: List[Dict[str, Any]] = []
        self._cached_titles: List[str] = []
        self._cached_keywords: List[str] = []

    def fetch_active_domains(self) -> List[Dict[str, Any]]:
        """Fetches active domains and client configurations from the API."""
        if self._cached_data:
            return self._cached_data

        headers = {
            "x-api-key": self.api_key,
            "User-Agent": "GreenhouseScraper/2.0",
            "Accept": "application/json"
        }

        try:
            resp = requests.get(self.api_url, headers=headers, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("success") and isinstance(data.get("data"), list):
                    self._cached_data = data["data"]
                    logger.info(f"Successfully fetched {len(self._cached_data)} active client profiles from ApplyUs API.")
                    return self._cached_data
            logger.warning(f"Failed to fetch active domains (Status {resp.status_code}): {resp.text}")
        except Exception as e:
            logger.error(f"Error connecting to Active Domains API: {e}")

        return []

    def get_desired_job_titles(self) -> List[str]:
        """Returns a deduplicated list of all desired job titles across active clients."""
        if self._cached_titles:
            return self._cached_titles

        data = self.fetch_active_domains()
        titles_set: Set[str] = set()
        for item in data:
            for t in item.get("desired_job_titles", []):
                t_clean = t.strip()
                if t_clean:
                    titles_set.add(t_clean)

        self._cached_titles = sorted(list(titles_set))
        return self._cached_titles

    def get_keywords(self) -> List[str]:
        """Returns a deduplicated list of all technical keywords across active clients."""
        if self._cached_keywords:
            return self._cached_keywords

        data = self.fetch_active_domains()
        keywords_set: Set[str] = set()
        for item in data:
            for k in item.get("keywords", []):
                k_clean = k.strip()
                if k_clean:
                    keywords_set.add(k_clean)

        self._cached_keywords = sorted(list(keywords_set))
        return self._cached_keywords

    def get_titles_and_keywords(self) -> Tuple[List[str], List[str]]:
        """Returns (desired_job_titles, keywords)."""
        return self.get_desired_job_titles(), self.get_keywords()

    def match_job_with_clients(
        self,
        job_title: str,
        job_location_str: str,
        job_desc: str = ""
    ) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
        """
        Matches a job against active clients based on BOTH desired_job_titles AND location/country.
        Returns: (is_matched, matched_title_or_keyword, matched_client_profile)
        """
        data = self.fetch_active_domains()
        if not data:
            return False, None, None

        title_lower = (job_title or "").lower().strip()
        loc_lower = (job_location_str or "").lower().strip()
        desc_lower = (job_desc or "").lower()

        # Common tech title indicators
        is_tech_role = any(r in title_lower for r in [
            "engineer", "developer", "architect", "data", "full stack", "fullstack",
            "frontend", "front-end", "backend", "back-end", "software", "programmer",
            "dba", "database", "python", "react", "node", "web", "platform", "cloud",
            "infrastructure", "devops", "sre", "machine learning", "ai", "scientist"
        ])

        for client in data:
            target_country = (client.get("country") or "").lower().strip()
            desired_titles = client.get("desired_job_titles", [])
            client_keywords = client.get("keywords", [])
            domain_name = client.get("domain", "")

            # 1. Check Title Match (Direct or Partial)
            title_matched = False
            matched_tag = None
            for t in desired_titles:
                t_clean = t.lower().strip()
                words = [w for w in t_clean.split() if len(w) > 2 and w not in ["the", "and", "for", "with", "developer", "engineer"]]
                if t_clean in title_lower:
                    title_matched = True
                    matched_tag = t
                    break
                elif len(words) >= 1 and all(w in title_lower for w in words):
                    title_matched = True
                    matched_tag = t
                    break

            # 2. Check Description Keyword Match (Like Greenhouse Portal Search)
            # If the role is a software/tech role and mentions the domain's core technologies
            if not title_matched and is_tech_role:
                domain_lower = domain_name.lower()
                if "python" in domain_lower and any(k in desc_lower for k in ["python", "django", "fastapi", "flask", "sqlalchemy"]):
                    title_matched = True
                    matched_tag = "Python Developer"
                elif "frontend" in domain_lower and any(k in desc_lower for k in ["react", "typescript", "javascript", "next.js", "vue", "angular"]):
                    title_matched = True
                    matched_tag = "Frontend Developer"
                elif "full stack" in domain_lower and any(k in desc_lower for k in ["full stack", "fullstack", "react", "node", "typescript", "django", "spring boot"]):
                    title_matched = True
                    matched_tag = "Full Stack Developer"
                elif "database" in domain_lower or "dba" in domain_lower:
                    if any(k in desc_lower for k in ["dba", "database administrator", "postgresql dba", "mysql dba", "oracle dba", "sql server dba"]):
                        title_matched = True
                        matched_tag = "Database Administrator"

            if not title_matched:
                continue

            # 3. Check Location / Country Match
            loc_matched = False

            if not target_country or target_country in ["global", "worldwide", "any"]:
                loc_matched = True

            elif target_country in ["united states", "usa", "us"]:
                us_keywords = [
                    "united states", "usa", "us", ", ca", ", ny", ", tx", ", wa", ", ma", ", il",
                    ", fl", ", nc", ", ga", ", co", ", va", ", pa", ", nj", "san francisco",
                    "new york", "seattle", "austin", "chicago", "boston", "los angeles",
                    "remote, usa", "remote - us", "remote (us", "remote - usa", "remote, us"
                ]
                if any(k in loc_lower for k in us_keywords):
                    loc_matched = True
                elif "remote" in loc_lower or "remote" in desc_lower[:1000]:
                    if not any(ex in loc_lower for ex in ["emea", "apac", "latam", "europe", "uk only", "canada only"]):
                        loc_matched = True

            elif target_country in ["ireland", "ie"]:
                ie_keywords = ["ireland", "dublin", "cork", "galway", "limerick", ", ie", "remote, ireland", "remote - ireland"]
                if any(k in loc_lower for k in ie_keywords):
                    loc_matched = True
                elif "remote" in loc_lower and any(r in loc_lower for r in ["europe", "emea", "eu"]):
                    loc_matched = True

            elif target_country in ["united kingdom", "uk"]:
                uk_keywords = ["united kingdom", "uk", "great britain", "england", "london", "manchester", "birmingham", "scotland", "edinburgh"]
                if any(k in loc_lower for k in uk_keywords):
                    loc_matched = True
                elif "remote" in loc_lower and any(r in loc_lower for r in ["europe", "emea", "uk"]):
                    loc_matched = True

            elif target_country in ["canada", "ca"]:
                ca_keywords = ["canada", "toronto", "vancouver", "montreal", "ottawa", "ontario", ", on", ", bc", ", qc"]
                if any(k in loc_lower for k in ca_keywords):
                    loc_matched = True

            else:
                if target_country in loc_lower or target_country in desc_lower[:1000]:
                    loc_matched = True

            if loc_matched:
                return True, matched_tag, client

        return False, None, None

