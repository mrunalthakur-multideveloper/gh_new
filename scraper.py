"""
Asynchronous Greenhouse Job Board Scraper.
Fetches public Greenhouse job listings for 6,000+ companies with filtering by date,
keyword, location, and employment type.
"""

import os
import csv
import json
import asyncio
import logging
from typing import List, Dict, Any, Optional, Set, Tuple
from datetime import datetime, timezone, timedelta
from dateutil import parser as date_parser
import aiohttp

from parser import parse_greenhouse_job
from active_domains import ActiveDomainsClient
from proxy_manager import ProxyManager

logger = logging.getLogger("greenhouse_scraper")


class GreenhouseScraper:
    def __init__(
        self,
        csv_file: str = "greenhouse.csv",
        concurrency: int = 30,
        timeout_seconds: int = 15,
        days_posted: Optional[int] = 1,
        search_keyword: Optional[str] = None,
        location_filter: Optional[str] = None,
        job_type_filter: Optional[str] = None,
        use_active_domains: bool = True,
        proxy_url: Optional[str] = None,
        proxy_list: Optional[List[str]] = None
    ):
        self.csv_file = csv_file
        self.concurrency = concurrency
        self.timeout_seconds = timeout_seconds
        self.days_posted = days_posted
        self.search_keyword = search_keyword.strip() if search_keyword else None
        self.location_filter = location_filter.strip().lower() if location_filter else None
        self.job_type_filter = job_type_filter.strip().lower() if job_type_filter else None
        self.use_active_domains = use_active_domains

        # Proxy Manager
        self.proxy_manager = ProxyManager(proxy_url=proxy_url, proxy_list=proxy_list)

        # Dynamic Active Domains Client
        self.active_domains_client = ActiveDomainsClient() if use_active_domains else None
        self.desired_job_titles: List[str] = []
        self.dynamic_keywords: List[str] = []

        if self.use_active_domains and not self.search_keyword:
            try:
                self.desired_job_titles, self.dynamic_keywords = self.active_domains_client.get_titles_and_keywords()
                logger.info(f"Loaded {len(self.desired_job_titles)} desired job titles and {len(self.dynamic_keywords)} keywords from ApplyUs API.")
            except Exception as e:
                logger.warning(f"Could not load active domains: {e}")

        # Statistics
        self.stats = {
            "companies_total": 0,
            "companies_processed": 0,
            "companies_failed": 0,
            "raw_jobs_found": 0,
            "matched_jobs": 0
        }

    def load_companies(self, limit: Optional[int] = None, specific_slugs: Optional[List[str]] = None) -> List[Dict[str, str]]:
        """Loads company records from CSV or filters by specific slugs."""
        companies = []
        
        if specific_slugs:
            for s in specific_slugs:
                slug_clean = s.strip().lower().replace("https://job-boards.greenhouse.io/", "").replace("https://boards.greenhouse.io/", "").strip("/")
                companies.append({
                    "name": slug_clean.title(),
                    "slug": slug_clean,
                    "url": f"https://job-boards.greenhouse.io/{slug_clean}"
                })
            return companies

        if not os.path.exists(self.csv_file):
            raise FileNotFoundError(f"CSV file '{self.csv_file}' not found.")

        with open(self.csv_file, mode="r", encoding="utf-8", errors="ignore") as f:
            reader = csv.DictReader(f)
            seen_slugs: Set[str] = set()
            for row in reader:
                slug = row.get("slug", "").strip()
                if not slug or slug in seen_slugs:
                    continue
                seen_slugs.add(slug)
                companies.append({
                    "name": row.get("name", slug).strip(),
                    "slug": slug,
                    "url": row.get("url", f"https://job-boards.greenhouse.io/{slug}").strip()
                })
                if limit and len(companies) >= limit:
                    break

        self.stats["companies_total"] = len(companies)
        return companies

    def is_job_matching_filters(self, raw_job: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """
        Checks whether raw job matches date, keyword/desired_job_titles, location, and type filters.
        Returns: (is_match, matched_keyword_or_title)
        """
        # 1. Date Filter (e.g. within 1 day)
        if self.days_posted is not None and self.days_posted > 0:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=self.days_posted)
            
            pub_date_str = raw_job.get("first_published") or raw_job.get("updated_at")
            if pub_date_str:
                try:
                    job_dt = date_parser.parse(pub_date_str)
                    if job_dt.tzinfo is None:
                        job_dt = job_dt.replace(tzinfo=timezone.utc)
                    if job_dt < cutoff_date:
                        return False, None
                except Exception:
                    pass

        title = (raw_job.get("title") or "").strip()
        title_lower = title.lower()
        content = (raw_job.get("content") or "").lower()
        location_raw = raw_job.get("location")
        loc_str = location_raw.get("name", "") if isinstance(location_raw, dict) else str(location_raw or "")
        loc_lower = loc_str.lower()

        matched_tag = self.search_keyword

        # 2. Desired Job Titles & Location Matching via Active Domains
        if self.search_keyword:
            kw_lower = self.search_keyword.lower()
            if kw_lower not in title_lower and kw_lower not in content:
                return False, None
            matched_tag = self.search_keyword
        elif self.use_active_domains and self.active_domains_client:
            # Client profile matching on BOTH desired_job_titles AND location/country
            matched, matched_title, client_profile = self.active_domains_client.match_job_with_clients(
                job_title=title,
                job_location_str=loc_str,
                job_desc=content
            )
            if not matched:
                return False, None
            matched_tag = matched_title or (client_profile.get("domain") if client_profile else None)
        elif self.desired_job_titles:
            # Fallback title match
            matched = any(t.lower() in title_lower for t in self.desired_job_titles)
            if not matched:
                return False, None

        # 3. Manual Location Filter override (if explicitly provided via CLI)
        if self.location_filter:
            loc_query = self.location_filter
            if loc_query == "remote":
                if not any(k in loc_lower or k in content[:1000] for k in ["remote", "work from home", "anywhere", "wfh"]):
                    return False, None
            elif loc_query in ["us", "usa", "united states"]:
                if not any(k in loc_lower for k in ["united states", "usa", "us", ", ca", ", ny", ", tx", ", wa", ", ma", ", il", "san francisco", "new york", "seattle", "austin"]):
                    return False, None
            else:
                if loc_query not in loc_lower:
                    return False, None

        # 4. Job Type Filter (e.g. "full_time" / "contract" / "internship")
        if self.job_type_filter:
            t_filter = self.job_type_filter.replace("_", " ").replace("-", " ")
            if "intern" in t_filter:
                if "intern" not in title_lower:
                    return False, None
            elif "contract" in t_filter:
                if "contract" not in title_lower and "contract" not in content[:500]:
                    return False, None

        return True, matched_tag

    async def fetch_company_jobs(
        self,
        session: aiohttp.ClientSession,
        semaphore: asyncio.Semaphore,
        company: Dict[str, str]
    ) -> List[Dict[str, Any]]:
        """Fetches and parses jobs for a single company with proxy support."""
        slug = company["slug"]
        name = company["name"]
        company_url = company.get("url")
        api_url = f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true"
        proxy = self.proxy_manager.get_proxy()

        async with semaphore:
            try:
                async with session.get(
                    api_url,
                    proxy=proxy,
                    timeout=aiohttp.ClientTimeout(total=self.timeout_seconds)
                ) as response:
                    if response.status == 200:
                        data = await response.json(content_type=None)
                        raw_jobs = data.get("jobs", [])
                        self.stats["raw_jobs_found"] += len(raw_jobs)
                        
                        matched = []
                        for raw_job in raw_jobs:
                            is_match, matched_tag = self.is_job_matching_filters(raw_job)
                            if is_match:
                                parsed = parse_greenhouse_job(
                                    raw_job=raw_job,
                                    company_name=name,
                                    company_slug=slug,
                                    company_url=company_url,
                                    search_keyword=matched_tag,
                                    keywords_list=self.dynamic_keywords if self.dynamic_keywords else None
                                )
                                matched.append(parsed)

                        self.stats["companies_processed"] += 1
                        self.stats["matched_jobs"] += len(matched)
                        return matched

                    elif response.status == 404:
                        self.stats["companies_processed"] += 1
                        return []
                    else:
                        self.stats["companies_failed"] += 1
                        return []
            except Exception as e:
                self.stats["companies_failed"] += 1
                logger.debug(f"Error fetching {slug}: {e}")
                return []

    async def scrape(
        self,
        limit: Optional[int] = None,
        specific_slugs: Optional[List[str]] = None,
        max_jobs: Optional[int] = None,
        progress_callback = None
    ) -> List[Dict[str, Any]]:
        """
        Executes the async scraping workflow over the target company list.
        """
        companies = self.load_companies(limit=limit, specific_slugs=specific_slugs)
        self.stats["companies_total"] = len(companies)
        
        logger.info(f"Starting scrape for {len(companies)} companies (Concurrency: {self.concurrency}, Days Posted: {self.days_posted})...")

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*"
        }
        
        semaphore = asyncio.Semaphore(self.concurrency)
        all_jobs: List[Dict[str, Any]] = []

        connector = aiohttp.TCPConnector(limit=self.concurrency + 20, ssl=False)
        async with aiohttp.ClientSession(headers=headers, connector=connector) as session:
            tasks = [
                asyncio.create_task(self.fetch_company_jobs(session, semaphore, comp))
                for comp in companies
            ]
            
            for task in asyncio.as_completed(tasks):
                jobs = await task
                if jobs:
                    all_jobs.extend(jobs)
                if progress_callback:
                    progress_callback(self.stats)
                    
                if max_jobs and len(all_jobs) >= max_jobs:
                    all_jobs = all_jobs[:max_jobs]
                    # Cancel remaining tasks
                    for t in tasks:
                        if not t.done():
                            t.cancel()
                    break

        return all_jobs[:max_jobs] if max_jobs else all_jobs
