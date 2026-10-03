# Greenhouse Job Scraper (NeonDB & Google Colab Edition)

A high-performance, asynchronous job scraper for **Greenhouse job boards** (`job-boards.greenhouse.io` and `boards.greenhouse.io`). It processes over **6,000+ companies** from `greenhouse.csv`, filters by **Active Client Profiles** (Desired Job Titles + Candidate Locations) posted in the **last 24 hours**, routes requests through **Webshare Rotating Proxies**, and writes directly into **NeonDB (Serverless PostgreSQL)**.

---

## 🚀 Key Features

- 📍 **Location-Aware Scraping**: Matches jobs strictly against the active client's target location (e.g. *United States*, *Ireland*, *United Kingdom*, *Canada*, *Remote*).
- 🎯 **Dynamic ApplyUs Profiles**: Automatically syncs target job titles and skills from `https://api.applyus.org/api/clients/active-domains`.
- 🌐 **Webshare Proxy Rotation**: Built-in proxy manager rotating requests through Webshare endpoints (`p.webshare.io:80`) to eliminate rate limits.
- 🐘 **NeonDB PostgreSQL Storage**: Full DDL schema (`schema.sql`) and batch upserts (`ON CONFLICT (job_id) DO UPDATE ...`) with SSL (`sslmode=require`) compatibility.
- ☁️ **Google Colab Ready**: Includes [`greenhouse_scraper_colab.ipynb`](file:///c:/Users/nithi/OneDrive/Desktop/greenhouse/greenhouse_scraper_colab.ipynb) and [`colab_runner.py`](file:///c:/Users/nithi/OneDrive/Desktop/greenhouse/colab_runner.py) for running with 1 click in the cloud.
- ⚡ **Ultra Fast**: Scans 6,000+ companies and 170,000+ jobs in under 60 seconds!

---

## 📦 Project Structure

```
greenhouse/
├── greenhouse.csv                    # 6,000+ Greenhouse companies directory
├── greenhouse_scraper_colab.ipynb   # Ready-to-run Google Colab Notebook
├── colab_runner.py                  # Colab runner script
├── active_domains.py                # ApplyUs client profiles & location matcher
├── proxy_manager.py                 # Webshare proxy rotation manager
├── database.py                      # NeonDB / PostgreSQL connection & upsert manager
├── parser.py                        # Data enrichment & normalization engine
├── scraper.py                       # Async high-concurrency Greenhouse crawler
├── main.py                          # CLI runner
├── schema.sql                       # PostgreSQL schema DDL
├── config.py                        # Configuration settings
└── .env                             # Environment variables
```

---

## 🔧 Environment Configuration (`.env`)

```ini
# 1. NeonDB PostgreSQL Connection (Serverless PostgreSQL)
DATABASE_URL=postgresql://neondb_owner:YOUR_NEON_PASSWORD@ep-xyz-pooler.us-east-2.aws.neon.tech/neondb?sslmode=require

# 2. Target Database Table Name
TABLE_NAME=linkedin_jobs

# 3. ApplyUs Active Domains API Credentials
INTERNAL_SERVICE_API_KEY=applyus_secret_microservice_key_2026
APPLYUS_API_URL=https://api.applyus.org/api/clients/active-domains

# 4. Webshare Proxy Rotation (Optional)
# Format: http://username-rotate:password@p.webshare.io:80
WEBSHARE_PROXY_URL=

# 5. Scraper Defaults
DEFAULT_DAYS=1
CONCURRENCY=50
GREENHOUSE_CSV_PATH=greenhouse.csv
```

---

## 💻 Running Locally

### 1. Scrape jobs posted in past 24h & save to NeonDB:
```bash
python main.py --days 1
```

### 2. Run with Webshare Rotating Proxy:
```bash
python main.py --proxy "http://username-rotate:password@p.webshare.io:80" --days 1
```

### 3. Initialize NeonDB table schema:
```bash
python main.py --init-db
```

### 4. Test scrape 100 jobs to CSV:
```bash
python main.py --days 1 --max-jobs 100 --csv test_100_jobs.csv
```

---

## ☁️ Running in Google Colab

### Method 1: Using the Colab Notebook (`greenhouse_scraper_colab.ipynb`)
1. Open [Google Colab](https://colab.research.google.com/).
2. Click **Upload** and upload [`greenhouse_scraper_colab.ipynb`](file:///c:/Users/nithi/OneDrive/Desktop/greenhouse/greenhouse_scraper_colab.ipynb).
3. Upload the project folder or `greenhouse.csv`.
4. In **Cell 2**, set your `DATABASE_URL` (NeonDB) and `WEBSHARE_PROXY_URL`.
5. Run all cells!

### Method 2: Running via Terminal / Colab Shell
```bash
!git clone <YOUR_REPO> # or upload the files
!pip install -q aiohttp beautifulsoup4 psycopg2-binary python-dateutil python-dotenv requests
!python colab_runner.py
```
