"""
PDF Resume Parser
-----------------
Extracts canonical fields from PDF resumes.

Key design decisions:
- Uses pdfplumber + pypdf (dual decoders) to handle custom fonts
- Detects section boundaries to avoid treating projects as experience
- Only extracts COMPANY internships/jobs as Experience (not side-projects)
- Location extracted from header/profile section
- Years of experience computed from actual employment date ranges only
"""
import re
import uuid
from datetime import datetime
from typing import Iterator, List, Optional, Tuple, Dict
import pdfplumber
from parsers.base import BaseParser
from domain.models import RawRecord, Location, Experience, Education
from normalizers.email import normalize_email
from normalizers.phone import normalize_phone
from normalizers.text import normalize_text
from core.logger import logger

# ---------------------------------------------------------------------------
# Compiled Regexes
# ---------------------------------------------------------------------------
EMAIL_REGEX = re.compile(
    r"(?<![\w.])([a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,6})(?![\w.@])"
)
PHONE_REGEX = re.compile(r"(\+?(?:\d[\s\-]?){9,14}\d)")

# Matches date ranges: "May 2024 - Jul 2024", "2020 – Present", "Jan 2022 - current"
DATE_RANGE_RE = re.compile(
    r"((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{4}|\d{4})"
    r"\s*[-–—]\s*"
    r"((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{4}"
    r"|\d{4}|Present|present|current|Current)",
    re.I,
)

MONTH_MAP = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}

# ---------------------------------------------------------------------------
# Skill dictionary (canonical names only — no project names)
# ---------------------------------------------------------------------------
COMMON_SKILLS = {
    # Languages
    "python", "java", "c++", "c#", "c", "ruby", "golang", "go", "swift", "kotlin",
    "javascript", "typescript", "php", "scala", "rust", "r", "matlab",
    # Frontend
    "react", "angular", "vue", "html", "css", "jquery", "next.js", "nextjs",
    # Backend
    "django", "flask", "fastapi", "spring", "node.js", "nodejs", "express",
    # Cloud / DevOps
    "aws", "gcp", "azure", "docker", "kubernetes", "terraform", "ci/cd", "jenkins",
    # Databases
    "sql", "mysql", "postgresql", "mongodb", "redis", "sqlite", "nosql",
    # ML / Data
    "machine learning", "deep learning", "data science", "nlp", "computer vision",
    "tensorflow", "pytorch", "keras", "scikit-learn", "pandas", "numpy", "opencv",
    # Tools
    "git", "linux", "bash", "rest api", "graphql", "microservices", "agile", "jira",
    # CS fundamentals
    "data structures", "algorithms", "oop",
}

# ---------------------------------------------------------------------------
# Section classification
# ---------------------------------------------------------------------------
# Sections that contain real employment history
WORK_SECTIONS = {"experience", "work experience", "internship", "internships", "employment"}

# Sections that should NOT contribute to experience (projects, edu, etc.)
NON_WORK_SECTIONS = {
    "projects", "project", "academic projects", "personal projects",
    "education", "academic", "skills", "technical skills",
    "certifications", "achievements", "publications", "references",
    "awards", "summary", "objective", "contact", "profile", "languages",
    "interests", "volunteer",
}

ALL_SECTION_HEADERS = WORK_SECTIONS | NON_WORK_SECTIONS

# Job-title keywords — line before date must contain at least one of these
# to be considered real employment
JOB_TITLE_KEYWORDS = {
    "intern", "internship", "engineer", "analyst", "developer", "scientist",
    "manager", "lead", "architect", "consultant", "associate", "officer",
    "executive", "trainee", "assistant", "specialist", "researcher",
}

# Company indicators: real companies usually contain these
COMPANY_INDICATORS = {
    "ltd", "limited", "pvt", "private", "inc", "corp", "corporation",
    "technologies", "tech", "solutions", "services", "systems",
    "steel", "tata", "infosys", "wipro", "cognizant", "accenture",
    "product", "consulting", "group", "industries", "enterprises",
}

# Phrases that indicate a project (not a company)
PROJECT_INDICATORS = {
    "software", "app", "application", "system", "platform", "website",
    "dashboard", "bot", "tool", "library", "api", "(sih", "sih 2025",
    "hackathon", "competition", "project",
}

# Indian states and cities for location extraction
INDIAN_LOCATIONS = [
    ("gunupur", "odisha"), ("joda", "odisha"), ("bhubaneswar", "odisha"),
    ("rourkela", "odisha"), ("cuttack", "odisha"),
    ("mumbai", "maharashtra"), ("pune", "maharashtra"), ("nagpur", "maharashtra"),
    ("bangalore", "karnataka"), ("bengaluru", "karnataka"),
    ("hyderabad", "telangana"), ("chennai", "tamil Nadu"),
    ("kolkata", "west bengal"), ("delhi", "delhi"), ("new delhi", "delhi"),
    ("lucknow", "uttar pradesh"), ("noida", "uttar pradesh"),
    ("gurugram", "haryana"), ("gurgaon", "haryana"),
    ("ahmedabad", "gujarat"), ("surat", "gujarat"),
    ("jaipur", "rajasthan"), ("kochi", "kerala"),
    ("indore", "madhya pradesh"), ("bhopal", "madhya pradesh"),
]

# Key-Value patterns for structured resumes
NOTE_PATTERNS = {
    "full_name": r"^(?:name|candidate)\s*:\s*(.+)$",
    "email":     r"^e[\-]?mail\s*:\s*(.+)$",
    "phone":     r"^(?:phone|mobile|contact)\s*:\s*(.+)$",
    "headline":  r"^(?:headline|title|position|objective)\s*:\s*(.+)$",
    "skills":    r"^skills?\s*:\s*(.+)$",
    "city":      r"^city\s*:\s*(.+)$",
    "region":    r"^(?:region|state|province)\s*:\s*(.+)$",
    "country":   r"^country\s*:\s*(.+)$",
    "linkedin":  r"^linkedin\s*:\s*(.+)$",
    "github":    r"^github\s*:\s*(.+)$",
}

STOP_WORDS = NON_WORK_SECTIONS | {"get in touch", "get in touch!"}


# ---------------------------------------------------------------------------
# Parser class
# ---------------------------------------------------------------------------
class PdfParser(BaseParser):
    def __init__(self):
        super().__init__(source_name="resume_pdf")

    # -----------------------------------------------------------------------
    # Step 1: Extract raw text
    # -----------------------------------------------------------------------
    def _extract_text(self, file_path: str) -> str:
        text = ""
        # 1. Try pypdf first (incredibly fast)
        try:
            import pypdf
            with open(file_path, "rb") as f:
                reader = pypdf.PdfReader(f)
                for page in reader.pages:
                    extracted = page.extract_text()
                    if extracted:
                        text += extracted + "\n"
        except Exception as e:
            logger.warning(f"pypdf failed: {e}")

        # 2. If pypdf failed or extracted very little text, fallback to pdfplumber
        if len(text.strip()) < 50:
            text = "" # Reset
            try:
                import pdfplumber
                with pdfplumber.open(file_path) as pdf:
                    for page in pdf.pages:
                        extracted = page.extract_text()
                        if extracted:
                            text += extracted + "\n"
            except Exception as e:
                logger.error(f"pdfplumber failed: {e}")

        logger.info(f"Raw extracted text (first 1000 chars):\n{text[:1000]!r}")
        return text

    # -----------------------------------------------------------------------
    # Step 2: Section-aware line tagging
    # -----------------------------------------------------------------------
    def _tag_sections(self, text: str) -> List[Tuple[str, str]]:
        """
        Return list of (section_name, line) for every non-empty line.
        section_name is one of: 'header', 'work', 'education', 'skills',
        'projects', 'other'
        """
        lines = [l.strip() for l in text.split("\n")]
        tagged = []
        current_section = "header"

        for line in lines:
            if not line:
                continue
            lo = line.lower().strip()

            # Check if this line IS a section header
            if lo in WORK_SECTIONS:
                current_section = "work"
                continue
            elif lo in {"education", "academic"}:
                current_section = "education"
                continue
            elif lo in {"skills", "technical skills", "key skills"}:
                current_section = "skills"
                continue
            elif lo in {"projects", "project", "academic projects", "personal projects"}:
                current_section = "projects"
                continue
            elif lo in NON_WORK_SECTIONS - {"education", "academic", "skills",
                                             "technical skills", "projects", "project",
                                             "academic projects", "personal projects"}:
                current_section = "other"
                continue

            tagged.append((current_section, line))

        return tagged

    # -----------------------------------------------------------------------
    # Step 3: Email, Phone
    # -----------------------------------------------------------------------
    def _extract_email(self, text: str) -> Optional[str]:
        matches = EMAIL_REGEX.findall(text)
        for m in matches:
            norm = normalize_email(m)
            if norm:
                return norm
        return None

    def _extract_phone(self, text: str) -> Optional[str]:
        matches = PHONE_REGEX.findall(text)
        for m in matches:
            digits = re.sub(r"[^\d+]", "", m)
            if 10 <= len(digits) <= 15:
                norm = normalize_phone(m)
                if norm:
                    return norm
        return None

    # -----------------------------------------------------------------------
    # Step 4: Name (from header section only)
    # -----------------------------------------------------------------------
    def _extract_name(self, tagged_lines: List[Tuple[str, str]]) -> Tuple[Optional[str], Optional[str]]:
        header_lines = [l for sec, l in tagged_lines if sec == "header"]
        for line in header_lines[:15]:
            lo = line.lower().strip()
            # Skip pure contact info lines
            if "@" in line or "http" in lo:
                continue
                
            # If line has a phone number (e.g. "Name +91 720..."), remove it so we can check the name
            clean_line = re.sub(r"\+?\d[\d\-\s\(\)]{7,}\d", "", line).strip()
            
            # If the line STILL contains digits (like a year), it's probably not a name line
            if re.search(r"\d", clean_line):
                continue
                
            if len(clean_line) > 60:
                continue
            words = clean_line.split()
            # Skip if any word is a section/stop keyword
            if any(w.lower() in STOP_WORDS for w in words):
                continue
            # Reject trailing periods UNLESS it's an initial (like A.)
            if any(w.endswith(".") and len(w) > 2 for w in words):
                continue
            # A name: 1-5 words, all alpha (including hyphens/periods)
            if 1 <= len(words) <= 5 and all(re.match(r"^[A-Za-z.\-']+$", w) for w in words):
                # Also ensure at least one word doesn't look like a generic lowercased word
                first = normalize_text(words[0].title())
                last = normalize_text(" ".join(w.title() for w in words[1:])) if len(words) > 1 else None
                return first, last
        return None, None

    # -----------------------------------------------------------------------
    # Step 5: Headline (line right after name in header)
    # -----------------------------------------------------------------------
    def _extract_headline(self, tagged_lines: List[Tuple[str, str]], full_name: str) -> Optional[str]:
        header_lines = [l for sec, l in tagged_lines if sec == "header"]
        name_lo = (full_name or "").lower()
        for i, line in enumerate(header_lines):
            if name_lo and name_lo in line.lower() and i + 1 < len(header_lines):
                nxt = header_lines[i + 1]
                if (len(nxt) <= 60
                        and "@" not in nxt
                        and not re.search(r"\d{4,}", nxt)
                        and nxt.lower() not in STOP_WORDS
                        and not nxt.isupper()):
                    return nxt
        return None

    def _extract_location(self, text: str, tagged_lines: List[Tuple[str, str]]) -> Optional[Location]:
        """
        Extract location. Priority:
        1. Explicit KV label: 'Location: ...' or 'Address: ...'
        2. Scan lines near phone/email in the raw text (the profile/header area)
           looking for a standalone 'City, State' pattern — catches 'Sindurpank, Odisha' etc.
        3. College city/state from the education section
        4. Known Indian city/state scan
        """
        # 1. Explicit label
        kv_match = re.search(r"(?:location|address)\s*:\s*([^\n]+)", text, re.I)
        if kv_match:
            parts = [p.strip() for p in kv_match.group(1).split(",")]
            if len(parts) >= 2:
                return Location(city=parts[0], region=parts[1], country="IN")

        # 2. Scan first 15 lines (header/about me) for "City, State" patterns
        #    This is robust even if the PDF extraction merges it with other text
        all_lines = text.split("\n")
        known_states = {"odisha", "maharashtra", "karnataka", "delhi", "telangana", 
                        "tamil nadu", "gujarat", "west bengal", "punjab", "haryana", 
                        "kerala", "rajasthan", "uttar pradesh", "madhya pradesh"}
                        
        for line in all_lines[:15]:
            # Skip if it's obviously a GitHub or LinkedIn URL line
            if "http" in line.lower() or "github.com" in line.lower():
                continue
            
            # Find a pattern: CapitalizedWord, CapitalizedWord
            # E.g., "Sindurpank, Odisha"
            for m in re.finditer(r"\b([A-Z][a-z]{2,20}),\s*([A-Z][a-z]{3,20})\b", line):
                city = m.group(1).strip()
                state = m.group(2).strip()
                
                # Check if the state is a known Indian state to be super safe
                if state.lower() in known_states:
                    return Location(city=city, region=state, country="IN")
                
                # Or if neither word is a stop word and they aren't verbs
                if (city.lower() not in STOP_WORDS and state.lower() not in STOP_WORDS
                        and len(city) > 2 and len(state) > 3
                        and state.lower() not in {"deployed", "developed", "created"}):
                    return Location(city=city, region=state, country="IN")

        # 3. College location from education section
        edu_lines = [l for sec, l in tagged_lines if sec == "education"]
        for line in edu_lines:
            m = re.search(
                r"(?:college|university|institute|giet|gandhi|iit|nit)[^,\n]*,"
                r"\s*([A-Za-z]{2,15}),\s*([A-Za-z]{2,15})\b",
                line, re.I
            )
            if m:
                city = m.group(1).strip()
                state = m.group(2).strip()
                # sanity: state shouldn't be a verb/adjective like 'Deployed'
                if (len(city) > 2 and len(state) > 2
                        and city[0].isupper() and state[0].isupper()):
                    return Location(city=city, region=state, country="IN")

        # 4. Known Indian city/state pair scan
        text_lower = text.lower()
        for city, state in INDIAN_LOCATIONS:
            if city in text_lower:
                return Location(city=city.title(), region=state.title(), country="IN")

        return None


    # -----------------------------------------------------------------------
    # Step 7: Date helpers
    # -----------------------------------------------------------------------
    def _parse_date(self, date_str: str) -> Optional[Tuple[int, int]]:
        """Parse 'May 2024' or '2024' → (month, year). None for Present/current."""
        s = date_str.strip().lower()
        if s in ("present", "current", "now"):
            return None
        m = re.match(r"([a-z]+)\.?\s+(\d{4})", s)
        if m:
            return MONTH_MAP.get(m.group(1)[:3], 1), int(m.group(2))
        m = re.match(r"(\d{4})", s)
        if m:
            return 1, int(m.group(1))
        return None

    def _months_between(self, start: Tuple[int, int], end: Optional[Tuple[int, int]]) -> float:
        if end is None:
            now = datetime.now()
            end = (now.month, now.year)
        return max(0, (end[1] - start[1]) * 12 + (end[0] - start[0]))

    # -----------------------------------------------------------------------
    # Step 8: Experience — WORK sections only, company-validated
    # -----------------------------------------------------------------------
    def _is_real_company(self, company_line: str) -> bool:
        """Return True if the line looks like a real company, not a project."""
        lo = company_line.lower()
        # If it contains project indicators it's likely a project
        for pi in PROJECT_INDICATORS:
            if pi in lo:
                return False
        # If it contains company indicators → yes
        for ci in COMPANY_INDICATORS:
            if ci in lo:
                return True
        # If it looks like "Company City, State" → yes
        if re.match(r"^[A-Za-z\s&,\.\-]{5,60}$", company_line.strip()):
            return True
        return False

    def _has_job_title(self, title_str: str) -> bool:
        """Return True if the extracted title string contains a job-title keyword."""
        lo = title_str.lower()
        return any(kw in lo for kw in JOB_TITLE_KEYWORDS)

    def _extract_experience(
        self, tagged_lines: List[Tuple[str, str]]
    ) -> Tuple[List[Experience], Optional[float]]:
        """
        Extract only REAL company experience from WORK sections.
        Strategy:
          - Only look at lines tagged as 'work'
          - Find lines containing a date range
          - Title = words before the date on that line
          - Company = next non-empty line (validated as real company)
          - Reject if title has no job-title keyword OR company looks like a project
        """
        # Rebuild ordered lines with section tags for context
        all_tagged = tagged_lines
        experiences: List[Experience] = []
        total_months = 0.0
        seen_companies: set = set()

        # Only work-tagged lines for scanning
        work_line_indices = [i for i, (sec, _) in enumerate(all_tagged) if sec == "work"]

        for idx in work_line_indices:
            sec, line = all_tagged[idx]
            date_match = DATE_RANGE_RE.search(line)
            if not date_match:
                continue

            start_str = date_match.group(1)
            end_str = date_match.group(2)
            start_t = self._parse_date(start_str)
            end_t = self._parse_date(end_str)
            if not start_t:
                continue

            months = self._months_between(start_t, end_t)
            if months < 0 or months > 600:
                continue

            # Title: text before the date on the same line
            title_raw = line[:date_match.start()].strip()
            title_raw = re.sub(r"[\-–,]+\s*$", "", title_raw).strip()

            # Skip if title doesn't look like a job title
            if not title_raw or not self._has_job_title(title_raw):
                continue

            # Company: look on the NEXT work-tagged line(s)
            company = ""
            loc_city = None
            loc_region = None
            for j in range(idx + 1, min(idx + 5, len(all_tagged))):
                next_sec, next_line = all_tagged[j]
                if not next_line.strip():
                    continue
                if DATE_RANGE_RE.search(next_line):
                    break  # another job entry
                if next_line.strip().lower() in ALL_SECTION_HEADERS:
                    break
                # Validate it's a company
                if self._is_real_company(next_line):
                    # Try to parse "Company City, State"
                    loc_m = re.match(
                        r"^(.+?)\s+([A-Za-z][a-z]+(?:\s[A-Za-z][a-z]+)?)"
                        r",\s*([A-Za-z][a-z]+(?:\s[A-Za-z][a-z]+)?)$",
                        next_line.strip()
                    )
                    if loc_m:
                        company = loc_m.group(1).strip()
                        loc_city = loc_m.group(2).strip()
                        loc_region = loc_m.group(3).strip()
                    else:
                        company = next_line.strip()
                    break

            if not company:
                continue

            # Deduplicate by company key
            company_key = re.sub(r"\s+", " ", company.lower()[:30])
            if company_key in seen_companies:
                continue
            seen_companies.add(company_key)

            start_fmt = f"{start_t[1]}-{start_t[0]:02d}"
            end_fmt = f"{end_t[1]}-{end_t[0]:02d}" if end_t else "Present"

            experiences.append(Experience(
                company=company,
                title=title_raw,
                start=start_fmt,
                end=end_fmt,
            ))
            total_months += months

        years = round(total_months / 12, 1) if total_months > 0 else None
        return experiences, years

    # -----------------------------------------------------------------------
    # Step 9: Education
    # -----------------------------------------------------------------------
    def _extract_education(self, text: str, tagged_lines: List[Tuple[str, str]]) -> List[Education]:
        """
        Extract education entries from the education-tagged section.
        Institution must come from a clean, short line that contains a college/university keyword.
        """
        edu_lines = [l for sec, l in tagged_lines if sec == "education"]
        if not edu_lines:
            # Fallback: extract from full text but only look between EDUCATION and next section
            edu_match = re.search(
                r"(?:education|academic)\s*\n(.*?)\n(?:experience|internship|skills|projects|certifications)",
                text, re.I | re.S
            )
            edu_lines = edu_match.group(1).splitlines() if edu_match else []

        DEGREE_KEYWORDS = [
            r"b\.?tech", r"b\.?e\.?", r"m\.?tech", r"mca", r"bca",
            r"bachelor", r"master", r"phd", r"b\.?sc", r"m\.?sc",
            r"graduation",
        ]
        degree_pattern = re.compile("|".join(DEGREE_KEYWORDS), re.I)

        education: List[Education] = []
        seen_inst: set = set()

        for i, line in enumerate(edu_lines):
            if not degree_pattern.search(line):
                continue

            degree = None
            field = None
            end_year = None

            # Degree parsing
            course_m = re.search(
                r"(b\.?tech|b\.?e\.?|m\.?tech|bachelor|master|phd|mca|bca|b\.?sc|m\.?sc)",
                line, re.I
            )
            if course_m:
                degree = course_m.group(1).upper().replace(".", "").replace(" ", "")

            # Field: content inside parentheses
            field_m = re.search(r"\(([^)]{5,80})\)", line)
            if field_m:
                field = field_m.group(1).strip()

            # End year: search the ENTIRE education block for any 4-digit year >= 2020
            # (prefer the latest year found, which is graduation year)
            year_candidates = []
            for edu_line in edu_lines:
                for ym in re.finditer(r"\b(20[2-9]\d|19\d{2})\b", edu_line):
                    year_candidates.append(int(ym.group(1)))
            if year_candidates:
                # Most recent year in edu section = likely graduation year
                end_year = max(year_candidates)

            # Institution: look for a SHORT line (< 80 chars) with college/university keyword
            # Don't grab lines that contain bullet points, REST APIs, etc.
            institution = None
            for j in range(max(0, i - 2), min(i + 6, len(edu_lines))):
                candidate = edu_lines[j].strip()
                # Must contain an institution keyword
                if not re.search(r"\b(college|university|institute|iit|nit|iiit|giet|vit|bits|nit)\b", candidate, re.I):
                    continue
                # Must be a clean line — not a bullet, not too long, no REST API / project text
                if len(candidate) > 100:
                    continue
                if re.search(r"(api|rest|deployed|integrated|scalable|database|server|github)", candidate, re.I):
                    continue
                # Extract just the institution name (everything before any comma-separated city)
                # e.g. "Gandhi Institute for Engineering and Technology, Gunupur, Odisha"
                # → keep only the institution part
                inst_parts = candidate.split(",")
                raw_inst = inst_parts[0].strip()
                # Remove prefix labels like "College :"
                raw_inst = re.sub(r"^(?:college|university|institute)\s*:?\s*", "", raw_inst, flags=re.I).strip()
                if len(raw_inst) > 5:
                    institution = raw_inst
                    break

            if not institution:
                continue

            inst_key = institution.lower()[:25]
            if inst_key in seen_inst:
                continue
            seen_inst.add(inst_key)

            education.append(Education(
                institution=institution,
                degree=degree or "Graduation",
                field=field,
                end_year=end_year,
            ))

        return education

    # -----------------------------------------------------------------------
    # Step 10: Skills — dictionary-based, no project names
    # -----------------------------------------------------------------------
    def _extract_skills(self, text: str) -> List[str]:
        text_lower = text.lower()
        seen: set = set()
        found: List[str] = []
        for skill in sorted(COMMON_SKILLS):
            pattern = r"\b" + re.escape(skill) + r"\b"
            if re.search(pattern, text_lower):
                key = skill.lower()
                if key not in seen:
                    seen.add(key)
                    found.append(normalize_text(skill.title()))
        return found

    # -----------------------------------------------------------------------
    # Step 11: Links
    # -----------------------------------------------------------------------
    def _extract_urls(self, text: str) -> dict:
        links = {}
        linkedin = re.search(r"https?://(?:www\.)?linkedin\.com/in/[^\s,;\"'<>]+", text, re.I)
        if linkedin:
            links["linkedin"] = linkedin.group(0).rstrip(".)")
        github = re.search(r"https?://(?:www\.)?github\.com/[^\s,;\"'<>]+", text, re.I)
        if github:
            links["github"] = github.group(0).rstrip(".)")
        return links

    # -----------------------------------------------------------------------
    # Step 12: Structured KV patterns
    # -----------------------------------------------------------------------
    def _apply_note_patterns(self, text: str) -> dict:
        values = {}
        for field, pattern in NOTE_PATTERNS.items():
            match = re.search(pattern, text, re.I | re.M)
            if match:
                values[field] = match.group(1).strip()
        return values

    # -----------------------------------------------------------------------
    # Main parse entry point
    # -----------------------------------------------------------------------
    def parse(self, file_path: str) -> Iterator[RawRecord]:
        logger.info(f"Parsing PDF: {file_path}")
        text = self._extract_text(file_path)

        # Tag every line with its section
        tagged_lines = self._tag_sections(text)

        # Structured KV (for notes / structured resume formats)
        kv = self._apply_note_patterns(text)

        # --- Name ---
        first_name, last_name = None, None
        if kv.get("full_name"):
            parts = kv["full_name"].split()
            first_name = normalize_text(parts[0].title()) if parts else None
            last_name = normalize_text(" ".join(w.title() for w in parts[1:])) if len(parts) > 1 else None
        else:
            first_name, last_name = self._extract_name(tagged_lines)

        full_name = f"{first_name or ''} {last_name or ''}".strip()

        # --- Email ---
        email = self._extract_email(text)

        # --- Phone ---
        phone = self._extract_phone(text)

        # --- Headline ---
        headline = kv.get("headline") or self._extract_headline(tagged_lines, full_name)

        # --- Skills (dictionary-based, deduplicated) ---
        if kv.get("skills"):
            raw_skills = re.split(r"[,|•·\t]+", kv["skills"])
            skills = list(dict.fromkeys(s.strip().title() for s in raw_skills if s.strip()))
        else:
            skills = self._extract_skills(text)

        # --- Experience (company internships/jobs ONLY, deduplicated) ---
        experiences, years_experience = self._extract_experience(tagged_lines)

        # --- Education ---
        education = self._extract_education(text, tagged_lines)

        # --- Location (header/profile section first) ---
        location = self._extract_location(text, tagged_lines)
        if not location and (kv.get("city") or kv.get("region")):
            location = Location(
                city=kv.get("city"),
                region=kv.get("region"),
                country=kv.get("country", "IN"),
            )

        # --- Links ---
        links = self._extract_urls(text)
        if kv.get("linkedin"):
            links["linkedin"] = kv["linkedin"]
        if kv.get("github"):
            links["github"] = kv["github"]

        logger.info(
            f"PDF parsed → name='{full_name}', email={email}, phone={phone}, "
            f"headline='{headline}', location={location}, "
            f"experience={[(e.company, e.start, e.end) for e in experiences]}, "
            f"years_exp={years_experience}, "
            f"education={[e.institution[:25] for e in education]}, "
            f"skills_count={len(skills)}"
        )

        yield RawRecord(
            source_system=self.source_name,
            original_id=str(uuid.uuid4()),
            first_name=first_name,
            last_name=last_name,
            email=email,
            phone=phone,
            headline=headline,
            years_experience=years_experience,
            location=location,
            skills=skills,
            experience=experiences,
            education=education,
            links=links,
            raw_data={
                "extracted_text_preview": text[:500] + "..." if len(text) > 500 else text
            },
        )
