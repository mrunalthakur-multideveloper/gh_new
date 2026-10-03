"""
Greenhouse Job Data Extraction & Enrichment Parser.
Parses raw Greenhouse API / HTML payloads into clean, normalized data structures
matching the database schema.
"""

import re
import html
from typing import Dict, Any, Optional, Tuple, List
from datetime import datetime, timezone
from bs4 import BeautifulSoup
from dateutil import parser as date_parser


# List of US states (names & 2-letter codes)
US_STATES = {
    'AL': 'Alabama', 'AK': 'Alaska', 'AZ': 'Arizona', 'AR': 'Arkansas', 'CA': 'California',
    'CO': 'Colorado', 'CT': 'Connecticut', 'DE': 'Delaware', 'FL': 'Florida', 'GA': 'Georgia',
    'HI': 'Hawaii', 'ID': 'Idaho', 'IL': 'Illinois', 'IN': 'Indiana', 'IA': 'Iowa',
    'KS': 'Kansas', 'KY': 'Kentucky', 'LA': 'Louisiana', 'ME': 'Maine', 'MD': 'Maryland',
    'MA': 'Massachusetts', 'MI': 'Michigan', 'MN': 'Minnesota', 'MS': 'Mississippi', 'MO': 'Missouri',
    'MT': 'Montana', 'NE': 'Nebraska', 'NV': 'Nevada', 'NH': 'New Hampshire', 'NJ': 'New Jersey',
    'NM': 'New Mexico', 'NY': 'New York', 'NC': 'North Carolina', 'ND': 'North Dakota', 'OH': 'Ohio',
    'OK': 'Oklahoma', 'OR': 'Oregon', 'PA': 'Pennsylvania', 'RI': 'Rhode Island', 'SC': 'South Carolina',
    'SD': 'South Dakota', 'TN': 'Tennessee', 'TX': 'Texas', 'UT': 'Utah', 'VT': 'Vermont',
    'VA': 'Virginia', 'WA': 'Washington', 'WV': 'West Virginia', 'WI': 'Wisconsin', 'WY': 'Wyoming',
    'DC': 'District of Columbia'
}
US_STATE_NAMES_REV = {v.lower(): k for k, v in US_STATES.items()}

KNOWN_COUNTRIES = {
    "united states", "usa", "us", "united kingdom", "uk", "great britain", "canada", "germany", 
    "france", "india", "australia", "ireland", "japan", "brazil", "mexico", "singapore", 
    "netherlands", "spain", "poland", "switzerland", "sweden", "israel", "italy", "new zealand", 
    "portugal", "colombia", "argentina", "chile", "south africa", "philippines", "vietnam"
}

KNOWN_US_CITIES = {
    "san francisco", "new york", "new york city", "seattle", "austin", "chicago", "los angeles",
    "boston", "denver", "atlanta", "dallas", "houston", "miami", "san diego", "san jose",
    "portland", "philadelphia", "phoenix", "washington", "mountain view", "palo alto", "sunnyvale",
    "oakland", "redmond", "bellevue", "raleigh", "durham", "charlotte", "salt lake city", "nashville"
}

# Comprehensive tech skills dictionary
TECH_SKILLS = [
    "Python", "JavaScript", "TypeScript", "Go", "Golang", "Java", "C++", "C#", "Ruby", "Rust", 
    "Scala", "Kotlin", "Swift", "PHP", "Dart", "Solidity", "SQL", "R", "Bash", "Shell",
    "React", "React Native", "Next.js", "Vue.js", "Angular", "Node.js", "Express", "Django", 
    "FastAPI", "Flask", "Spring Boot", "Ruby on Rails", "ASP.NET", ".NET", "GraphQL", "REST API",
    "PostgreSQL", "MySQL", "MongoDB", "Redis", "Cassandra", "DynamoDB", "Snowflake", "BigQuery", 
    "Elasticsearch", "Kafka", "RabbitMQ", "Redshift", "ClickHouse", "Databricks", "Supabase", "Prisma",
    "AWS", "Amazon Web Services", "GCP", "Google Cloud", "Azure", "Docker", "Kubernetes", 
    "Terraform", "Ansible", "CI/CD", "Jenkins", "GitHub Actions", "GitLab", "Linux", "Serverless",
    "Machine Learning", "Deep Learning", "NLP", "LLM", "Generative AI", "PyTorch", "TensorFlow", 
    "Scikit-learn", "Pandas", "NumPy", "OpenCV", "Hugging Face", "LangChain", "LlamaIndex",
    "Spark", "Apache Spark", "Airflow", "dbt", "Hadoop", "Flink",
    "Microservices", "System Design", "Agile", "Scrum", "DevOps", "Cybersecurity", "Zero Trust"
]

SKILL_PATTERNS = [
    (re.compile(rf"\b{re.escape(skill)}\b", re.IGNORECASE), skill) for skill in TECH_SKILLS
]


def clean_html_content(raw_html: str) -> str:
    """Decodes HTML entities and extracts clean structured readable text."""
    if not raw_html:
        return ""
    unescaped = html.unescape(raw_html)
    soup = BeautifulSoup(unescaped, "html.parser")
    
    # Remove script and style elements
    for s in soup(["script", "style", "noscript"]):
        s.decompose()
        
    text = soup.get_text(separator="\n")
    # Clean excessive whitespace
    lines = [line.strip() for line in text.splitlines()]
    clean_text = "\n".join([line for line in lines if line])
    return clean_text


def parse_location(location_name: Optional[str], text_content: str = "") -> Tuple[Optional[str], Optional[str], Optional[str], str, bool]:
    """
    Parses location string into (city, state, country, location_display, is_remote).
    """
    if not location_name:
        location_name = ""
        
    display = location_name.strip()
    city = None
    state = None
    country = None
    
    # Determine remote
    is_remote = False
    lower_loc = location_name.lower()
    if any(k in lower_loc for k in ["remote", "virtual", "telecommute", "anywhere", "work from home", "wfh"]):
        is_remote = True
    elif text_content:
        lower_desc = text_content[:1500].lower()
        if "100% remote" in lower_desc or "fully remote" in lower_desc or "remote eligible" in lower_desc or "work from anywhere" in lower_desc:
            is_remote = True

    # Split location segments: e.g., "San Francisco, CA, United States" or "Austin, TX" or "Seattle, San Francisco, New York City"
    parts = [p.strip() for p in re.split(r"[,/|;]+", display) if p.strip()]
    
    if len(parts) == 1:
        single = parts[0]
        single_lower = single.lower()
        if single.upper() in US_STATES:
            state = single.upper()
            country = "United States"
        elif single_lower in US_STATE_NAMES_REV:
            state = US_STATE_NAMES_REV[single_lower]
            country = "United States"
        elif single_lower in ["us", "usa", "united states"]:
            country = "United States"
        elif single_lower in KNOWN_COUNTRIES:
            country = single.title()
        elif single_lower in KNOWN_US_CITIES:
            city = single
            country = "United States"
        elif not is_remote:
            city = single
            
    elif len(parts) == 2:
        part0, part1 = parts[0], parts[1]
        part0_lower = part0.lower()
        part1_up = part1.upper()
        part1_lower = part1.lower()
        
        city = part0
        if part1_up in US_STATES:
            state = part1_up
            country = "United States"
        elif part1_lower in US_STATE_NAMES_REV:
            state = US_STATE_NAMES_REV[part1_lower]
            country = "United States"
        elif part1_lower in ["us", "usa", "united states"]:
            country = "United States"
        elif part1_lower in KNOWN_COUNTRIES:
            country = part1.title()
        elif part0_lower in KNOWN_US_CITIES and part1_lower in KNOWN_US_CITIES:
            city = f"{part0}, {part1}"
            country = "United States"
        else:
            state = part1

    elif len(parts) >= 3:
        last_part = parts[-1]
        last_lower = last_part.lower()
        mid_part = parts[-2]
        mid_up = mid_part.upper()
        mid_lower = mid_part.lower()
        
        if last_lower in ["us", "usa", "united states"] or last_lower in KNOWN_COUNTRIES:
            country = "United States" if last_lower in ["us", "usa", "united states"] else last_part.title()
            if mid_up in US_STATES:
                state = mid_up
            elif mid_lower in US_STATE_NAMES_REV:
                state = US_STATE_NAMES_REV[mid_lower]
            else:
                state = mid_part
            city = ", ".join(parts[:-2])
        elif all(p.lower() in KNOWN_US_CITIES for p in parts):
            city = ", ".join(parts)
            country = "United States"
        else:
            city = parts[0]
            if mid_up in US_STATES:
                state = mid_up
            country = last_part
        
    return city, state, country, display or "Not Specified", is_remote


def parse_compensation(text: str) -> Tuple[Optional[float], Optional[float], str, str, Optional[str]]:
    """
    Extracts salary/compensation details from description text.
    Returns: (compensation_min, compensation_max, compensation_currency, compensation_interval, salary_text)
    """
    currency = "USD"
    interval = "yearly"
    comp_min = None
    comp_max = None
    salary_text = None

    if not text:
        return None, None, currency, interval, None

    # Salary patterns
    patterns = [
        # $120,000 - $180,000 / year or per year or / yr
        r"([$€£CA$USD\s]{1,5})\s*(\d{2,3}(?:,\d{3})+|\d{2,3}k)\s*(?:-|to|–)\s*([$€£CA$USD\s]{0,5})\s*(\d{2,3}(?:,\d{3})+|\d{2,3}k)\s*(?:(?:USD|CAD|EUR|GBP)?\s*(?:/\s*|\s+per\s+)?(year|yr|annum|annual|hr|hour|month|mo))?",
        # $65.00 - $85.00 / hour
        r"([$€£CA$USD\s]{1,5})\s*(\d{2,3}(?:\.\d{2})?)\s*(?:-|to|–)\s*([$€£CA$USD\s]{0,5})\s*(\d{2,3}(?:\.\d{2})?)\s*(?:/\s*|\s+per\s+)?(hour|hr)",
        # Base Salary: $150,000
        r"(?:base\s+salary|salary\s+range|compensation|pay\s+range)[:\s]+([$€£CA$USD\s]{1,5})\s*(\d{2,3}(?:,\d{3})+|\d{2,3}k)\s*(?:-|to|–)?\s*([$€£CA$USD\s]{0,5})?\s*(\d{2,3}(?:,\d{3})+|\d{2,3}k)?",
    ]

    for pat in patterns:
        match = re.search(pat, text, re.IGNORECASE)
        if match:
            salary_text = match.group(0).strip()
            
            # Detect currency
            if "€" in salary_text or "EUR" in salary_text:
                currency = "EUR"
            elif "£" in salary_text or "GBP" in salary_text:
                currency = "GBP"
            elif "CA$" in salary_text or "CAD" in salary_text:
                currency = "CAD"
            else:
                currency = "USD"
                
            # Detect interval
            lower_snip = salary_text.lower()
            if any(h in lower_snip for h in ["/hr", "hour", "/hour", "hourly"]):
                interval = "hourly"
            elif any(m in lower_snip for m in ["/mo", "month", "/month", "monthly"]):
                interval = "monthly"
            else:
                interval = "yearly"

            # Parse numbers
            nums = re.findall(r"\b\d{1,3}(?:,\d{3})+(?:\.\d+)?|\b\d{2,3}k|\b\d{2,3}(?:\.\d{2})?\b", salary_text)
            parsed_nums = []
            for n in nums:
                n_clean = n.replace(",", "").lower()
                if "k" in n_clean:
                    val = float(n_clean.replace("k", "")) * 1000
                else:
                    try:
                        val = float(n_clean)
                    except ValueError:
                        continue
                if val >= 10:  # Skip trivial numbers
                    parsed_nums.append(val)

            if len(parsed_nums) >= 2:
                comp_min = min(parsed_nums[0], parsed_nums[1])
                comp_max = max(parsed_nums[0], parsed_nums[1])
            elif len(parsed_nums) == 1:
                comp_min = parsed_nums[0]
                comp_max = parsed_nums[0]

            break

    return comp_min, comp_max, currency, interval, salary_text


def parse_experience(text: str) -> Tuple[Optional[int], Optional[int], Optional[str]]:
    """
    Extracts experience requirements.
    Returns: (experience_min, experience_max, experience_text)
    """
    if not text:
        return None, None, None

    exp_min = None
    exp_max = None
    exp_text = None

    patterns = [
        # 5+ years of experience, 3-5 years of experience, 5 to 7 years
        r"(\d{1,2})\+?\s*(?:-|to|–)\s*(\d{1,2})\+?\s*years?(?:\s+of)?\s*(?:[a-zA-Z\s,]{0,30})?\s*experience",
        r"(\d{1,2})\+\s*years?(?:\s+of)?\s*(?:[a-zA-Z\s,]{0,30})?\s*experience",
        r"(?:at\s+least|minimum\s+of)\s*(\d{1,2})\s*years?(?:\s+of)?\s*(?:[a-zA-Z\s,]{0,30})?\s*experience",
        r"(\d{1,2})\s*years?(?:\s+of)?\s*(?:industry|software|professional|relevant)?\s*experience",
    ]

    for pat in patterns:
        match = re.search(pat, text, re.IGNORECASE)
        if match:
            exp_text = match.group(0).strip()
            groups = match.groups()
            try:
                if len(groups) >= 2 and groups[1] is not None:
                    exp_min = int(groups[0])
                    exp_max = int(groups[1])
                elif len(groups) >= 1 and groups[0] is not None:
                    exp_min = int(groups[0])
                    exp_max = None
            except ValueError:
                pass
            break

    return exp_min, exp_max, exp_text


# Cache for dynamically compiled skill patterns
_DYNAMIC_SKILL_CACHE: Dict[str, Tuple[re.Pattern, str]] = {}

def get_compiled_patterns(skill_list: Optional[List[str]] = None) -> List[Tuple[re.Pattern, str]]:
    """Returns compiled regex patterns for given skill list or defaults to TECH_SKILLS."""
    if not skill_list:
        return SKILL_PATTERNS
    
    patterns = []
    for skill in skill_list:
        skill_clean = skill.strip()
        if not skill_clean:
            continue
        if skill_clean not in _DYNAMIC_SKILL_CACHE:
            try:
                # Use word boundary or delimiter matching safely
                esc = re.escape(skill_clean)
                pattern = re.compile(r"(?:^|[\s,;./()\[\]{}|\-–—])(" + esc + r")(?:$|[\s,;./()\[\]{}|\-–—])", re.IGNORECASE)
                _DYNAMIC_SKILL_CACHE[skill_clean] = (pattern, skill_clean)
            except Exception:
                continue
        patterns.append(_DYNAMIC_SKILL_CACHE[skill_clean])
    return patterns


def extract_skills(text: str, custom_keywords: Optional[List[str]] = None) -> Optional[str]:
    """Matches known tech skills and tools in the job text using dynamic keywords or default skills."""
    if not text:
        return None
    
    patterns = get_compiled_patterns(custom_keywords)
    found = []
    for pattern, skill in patterns:
        if pattern.search(text):
            found.append(skill)
            
    if not found:
        return None
        
    return ", ".join(dict.fromkeys(found))


def parse_h1b_sponsorship(text: str) -> Optional[str]:
    """Detects visa sponsorship / H-1B statements."""
    if not text:
        return None
        
    lower = text.lower()
    if any(p in lower for p in ["not able to sponsor", "no visa sponsorship", "will not sponsor", "cannot sponsor", "without sponsorship", "does not sponsor"]):
        return "Not Sponsored"
    elif any(p in lower for p in ["visa sponsorship available", "sponsorship is available", "we sponsor visas", "h-1b transfer", "h1b sponsorship", "willing to sponsor"]):
        return "Available"
    elif any(p in lower for p in ["us citizen or green card", "u.s. citizen or permanent resident", "security clearance required", "must be a us citizen"]):
        return "US Citizen / Green Card Required"
    elif "authorized to work in" in lower:
        return "Work Authorization Required"
    return None


def extract_emails(text: str) -> Optional[str]:
    """Extracts email addresses from text."""
    if not text:
        return None
    matches = re.findall(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", text)
    valid = [m for m in matches if not m.endswith((".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"))]
    if valid:
        return ", ".join(dict.fromkeys(valid))
    return None


def determine_job_level(title: str, text: str = "") -> str:
    """Classifies job level from title and text."""
    t_lower = title.lower()
    
    if any(k in t_lower for k in ["intern", "internship", "co-op"]):
        return "Internship"
    if any(k in t_lower for k in ["vp", "vice president", "head of", "director", "chief", "c-level", "cto", "cio", "cso"]):
        return "Executive / Director"
    if any(k in t_lower for k in ["principal", "distinguished", "fellow"]):
        return "Principal"
    if any(k in t_lower for k in ["staff"]):
        return "Staff"
    if any(k in t_lower for k in ["lead", "lead engineer", "team lead", "tech lead"]):
        return "Lead"
    if any(k in t_lower for k in ["senior", "sr.", "sr "]):
        return "Senior"
    if any(k in t_lower for k in ["entry", "junior", "jr.", "jr ", "graduate", "associate"]):
        return "Entry Level"
    if any(k in t_lower for k in ["manager", "engineering manager", "em"]):
        return "Management"
        
    return "Mid-Senior Level"


def determine_job_type(title: str, text: str = "") -> str:
    """Classifies employment type."""
    combined = f"{title} {text[:1000]}".lower()
    if "intern" in title.lower():
        return "Internship"
    if any(k in combined for k in ["part-time", "part time"]):
        return "Part-time"
    if any(k in combined for k in ["contract", "contractor", "freelance", "temp", "temporary"]):
        return "Contract"
    return "Full-time"


def parse_greenhouse_job(
    raw_job: Dict[str, Any], 
    company_name: str, 
    company_slug: str, 
    company_url: Optional[str] = None,
    search_keyword: Optional[str] = None,
    keywords_list: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Takes a raw Greenhouse API job object and transforms it into the complete schema structure.
    """
    job_id_raw = raw_job.get("id")
    job_id = f"gh_{job_id_raw}" if job_id_raw else f"gh_{company_slug}_{raw_job.get('title', 'job')}"
    title = raw_job.get("title", "").strip()
    
    # URL handling
    canonical_job_url = raw_job.get("absolute_url") or f"https://boards.greenhouse.io/{company_slug}/jobs/{job_id_raw}"
    apply_url = f"{canonical_job_url}#app" if "#" not in canonical_job_url else canonical_job_url
    
    # Description parsing
    raw_content = raw_job.get("content", "")
    clean_desc = clean_html_content(raw_content)
    
    # Location
    raw_location = raw_job.get("location", {})
    loc_name = raw_location.get("name") if isinstance(raw_location, dict) else str(raw_location or "")
    city, state, country, loc_display, is_remote = parse_location(loc_name, clean_desc)
    
    # Date posted
    pub_date_str = raw_job.get("first_published") or raw_job.get("updated_at")
    date_posted = None
    if pub_date_str:
        try:
            dt = date_parser.parse(pub_date_str)
            date_posted = dt.date().isoformat()
        except Exception:
            date_posted = datetime.now(timezone.utc).date().isoformat()
    else:
        date_posted = datetime.now(timezone.utc).date().isoformat()
        
    # Department / Function
    departments = raw_job.get("departments", [])
    dept_names = [d.get("name") for d in departments if isinstance(d, dict) and d.get("name")]
    job_function = ", ".join(dept_names) if dept_names else None
    
    # Compensation
    comp_min, comp_max, currency, interval, salary_text = parse_compensation(clean_desc)
    
    # Experience
    exp_min, exp_max, exp_text = parse_experience(clean_desc)
    
    # Skills (using dynamically fetched keywords)
    skills = extract_skills(f"{title}\n{clean_desc}", custom_keywords=keywords_list)
    
    # Sponsorship
    sponsorship = parse_h1b_sponsorship(clean_desc)
    
    # Emails
    emails = extract_emails(clean_desc)
    
    # Job Level & Type
    job_level = determine_job_level(title, clean_desc)
    job_type = determine_job_type(title, clean_desc)
    
    # Company Logo & Industry
    company_url_final = company_url or f"https://job-boards.greenhouse.io/{company_slug}"
    company_logo = f"https://logo.clearbit.com/{company_slug}.com"
    company_industry = "Technology / Software"
    
    return {
        "job_id": job_id,
        "title": title,
        "company_name": company_name or raw_job.get("company_name") or company_slug.title(),
        "company_url": company_url_final,
        "company_logo": company_logo,
        "location_city": city,
        "location_state": state,
        "location_country": country,
        "location_display": loc_display,
        "description": clean_desc,
        "date_posted": date_posted,
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "job_url": canonical_job_url,
        "apply_url": apply_url,
        "job_type": job_type,
        "job_level": job_level,
        "company_industry": company_industry,
        "job_function": job_function,
        "is_remote": is_remote,
        "is_easy_apply": True,
        "compensation_min": comp_min,
        "compensation_max": comp_max,
        "compensation_currency": currency,
        "compensation_interval": interval,
        "emails": emails,
        "search_keyword": search_keyword,
        "experience": exp_text,
        "salary_text": salary_text,
        "skills": skills,
        "sponsorship_h1b": sponsorship,
        "source": "greenhouse2",
        "experience_max": exp_max,
        "experience_min": exp_min,
    }
