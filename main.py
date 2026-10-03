"""
Main CLI Runner for Greenhouse Job Scraper.
Supports filtering by 1-day freshness, keywords, locations, company lists,
and exporting to PostgreSQL, JSON, and CSV.
"""

import sys
import os
import csv
import json
import asyncio
import argparse
import logging
from datetime import datetime
from typing import List, Dict, Any

from scraper import GreenhouseScraper
from database import DatabaseManager
import config

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("greenhouse_cli")


def export_to_json(jobs: List[Dict[str, Any]], filepath: str):
    """Exports scraped job records to a formatted JSON file."""
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(jobs, f, indent=2, ensure_ascii=False)
    logger.info(f"Successfully saved {len(jobs)} jobs to JSON: {filepath}")


def export_to_csv(jobs: List[Dict[str, Any]], filepath: str):
    """Exports scraped job records to a CSV file matching the schema."""
    if not jobs:
        logger.warning("No jobs to export to CSV.")
        return

    fieldnames = list(jobs[0].keys())
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(jobs)
    logger.info(f"Successfully saved {len(jobs)} jobs to CSV: {filepath}")


def print_progress(stats: Dict[str, Any]):
    """Prints a single-line progress update."""
    processed = stats["companies_processed"]
    total = stats["companies_total"]
    matched = stats["matched_jobs"]
    raw = stats["raw_jobs_found"]
    failed = stats["companies_failed"]
    
    pct = (processed / total * 100) if total > 0 else 0
    sys.stdout.write(
        f"\rProgress: [{processed}/{total}] ({pct:5.1f}%) | Raw Jobs: {raw} | Matched Filter: {matched} | 404/Skipped: {failed}"
    )
    sys.stdout.flush()


async def run_scraper(args):
    """Main async execution function."""
    print("=" * 70)
    print(" " * 18 + "GREENHOUSE JOB BOARD SCRAPER")
    print("=" * 70)

    # Initialize Scraper
    scraper = GreenhouseScraper(
        csv_file=args.file,
        concurrency=args.concurrency,
        days_posted=args.days,
        search_keyword=args.keyword,
        location_filter=args.location,
        job_type_filter=args.type,
        proxy_url=args.proxy or config.WEBSHARE_PROXY_URL,
        proxy_list=args.proxy_list
    )

    print(f"Target CSV File : {args.file}")
    print(f"Days Filter     : {args.days} day(s) (posted/updated within last {args.days*24} hours)" if args.days > 0 else "Days Filter     : None (All active jobs)")
    if args.keyword:
        print(f"Keyword Filter  : Manual Override -> '{args.keyword}'")
    else:
        print(f"Filtering Mode  : Dynamic ApplyUs Profiles ({len(scraper.desired_job_titles)} titles, {len(scraper.dynamic_keywords)} skills with Country Matching)")
    print(f"Location Filter : {args.location or 'Dynamic Client Country Filter'}")
    print(f"Job Type Filter : {args.type or 'None (All types)'}")
    print(f"Proxy Rotation  : {'Webshare Proxy Enabled' if scraper.proxy_manager.is_enabled() else 'Direct Connection (No Proxy)'}")
    print(f"Concurrency     : {args.concurrency} async workers")
    if args.max_jobs:
        print(f"Max Jobs Target : Stop after {args.max_jobs} matched jobs")
    if args.companies:
        print(f"Specific Slugs  : {', '.join(args.companies)}")
    elif args.limit:
        print(f"Company Limit   : First {args.limit} companies from CSV")
    print("-" * 70)

    start_time = datetime.now()
    jobs = await scraper.scrape(
        limit=args.limit,
        specific_slugs=args.companies,
        max_jobs=args.max_jobs,
        progress_callback=print_progress
    )
    duration = (datetime.now() - start_time).total_seconds()
    print("\n" + "-" * 70)
    print(f"Scrape Finished in {duration:.2f} seconds!")
    print(f"Total Companies Processed : {scraper.stats['companies_processed']}")
    print(f"Total Raw Jobs Checked   : {scraper.stats['raw_jobs_found']}")
    print(f"Total Jobs Matched       : {len(jobs)}")
    print("=" * 70)

    # Database Ingestion (NeonDB / PostgreSQL)
    db_url = args.db_url or config.DATABASE_URL
    db = DatabaseManager(db_url=db_url, table_name=args.table)

    if not args.no_db and db.is_configured():
        logger.info(f"Connecting to NeonDB / PostgreSQL ({args.table})...")
        db.init_database()
        if jobs:
            upserted = db.upsert_jobs(jobs)
            logger.info(f"Successfully upserted {upserted} jobs into NeonDB table '{args.table}'.")
    elif not args.no_db:
        logger.info("No DATABASE_URL configured. Skipping database save. (Use --db-url or set in .env)")

    # File Exports
    if args.output:
        export_to_json(jobs, args.output)
    if args.csv:
        export_to_csv(jobs, args.csv)
        
    # If no file output specified, save default json export for convenience
    if not args.output and not args.csv and not (not args.no_db and db.is_configured()):
        default_out = "scraped_jobs.json"
        export_to_json(jobs, default_out)

    if jobs:
        print("\nSample Extracted Job Preview:")
        sample = jobs[0].copy()
        sample["description"] = sample["description"][:120] + "..." if len(sample.get("description", "")) > 120 else sample.get("description")
        print(json.dumps(sample, indent=2))


def main():
    parser = argparse.ArgumentParser(
        description="Greenhouse High-Performance Public Job Board Scraper"
    )
    parser.add_argument(
        "--days", "-d",
        type=int,
        default=config.DEFAULT_DAYS,
        help="Filter jobs posted/updated within X days (default: 1 day = past 24h. Use 0 for all jobs)."
    )
    parser.add_argument(
        "--max-jobs", "-n",
        type=int,
        default=None,
        help="Stop and save after collecting exactly N matching jobs (e.g. --max-jobs 100)."
    )
    parser.add_argument(
        "--keyword", "-k",
        type=str,
        default=None,
        help="Filter jobs matching a search keyword (e.g., 'python', 'software engineer')."
    )
    parser.add_argument(
        "--location", "-l",
        type=str,
        default=None,
        help="Filter by location (e.g., 'United States', 'Remote', 'Ireland')."
    )
    parser.add_argument(
        "--type", "-t",
        type=str,
        default=None,
        help="Filter by employment type (e.g., 'full_time', 'contract', 'internship')."
    )
    parser.add_argument(
        "--companies", "-c",
        nargs="+",
        default=None,
        help="Specific company slugs to scrape (e.g., --companies stripe figma airbnb databricks)."
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit number of companies to scrape from the CSV (useful for testing)."
    )
    parser.add_argument(
        "--file", "-f",
        type=str,
        default=config.DEFAULT_CSV_PATH,
        help="Path to the greenhouse companies CSV file (default: greenhouse.csv)."
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=config.DEFAULT_CONCURRENCY,
        help="Number of concurrent async HTTP connections (default: 40)."
    )
    parser.add_argument(
        "--proxy",
        type=str,
        default=None,
        help="Webshare rotating proxy URL (e.g. http://username-rotate:password@p.webshare.io:80)."
    )
    parser.add_argument(
        "--proxy-list",
        nargs="+",
        default=None,
        help="List of proxy URLs for rotation."
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        default=None,
        help="Save output to JSON file (e.g., -o jobs.json)."
    )
    parser.add_argument(
        "--csv",
        type=str,
        default=None,
        help="Save output to CSV file (e.g., --csv output_jobs.csv)."
    )
    parser.add_argument(
        "--db-url",
        type=str,
        default=None,
        help="NeonDB / PostgreSQL connection URL (e.g. postgresql://user:pass@ep-xyz.neon.tech/neondb?sslmode=require)."
    )
    parser.add_argument(
        "--table",
        type=str,
        default=config.TABLE_NAME,
        help="Target database table name (default: linkedin_jobs)."
    )
    parser.add_argument(
        "--no-db",
        action="store_true",
        help="Skip database insertion even if DATABASE_URL is configured."
    )
    parser.add_argument(
        "--init-db",
        action="store_true",
        help="Initialize NeonDB / PostgreSQL database schema and exit."
    )

    args = parser.parse_args()

    if args.init_db:
        db_url = args.db_url or config.DATABASE_URL
        db = DatabaseManager(db_url=db_url, table_name=args.table)
        if not db.is_configured():
            print("Error: DATABASE_URL is not set. Please provide --db-url or set DATABASE_URL in .env")
            sys.exit(1)
        db.init_database()
        print(f"Database table '{args.table}' and indexes initialized successfully.")
        sys.exit(0)

    try:
        asyncio.run(run_scraper(args))
    except KeyboardInterrupt:
        print("\nScraper interrupted by user.")


if __name__ == "__main__":
    main()
