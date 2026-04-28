"""SheerID async verification engine for all supported services."""
from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import random
import re
import time
from io import BytesIO
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple

import httpx
from PIL import Image, ImageDraw, ImageFont

log = logging.getLogger(__name__)

SHEERID_API = "https://services.sheerid.com/rest/v2"
SHEERID_BASE = "https://services.sheerid.com"

MIN_DELAY_MS = 300
MAX_DELAY_MS = 800


# ---------------------------------------------------------------------------
# Proxy rotation — supports multiple proxies (PROXY_URL or PROXY_LIST)
# Format: ip:port:user:pass (one per line) or http://user:pass@ip:port
# ---------------------------------------------------------------------------

def _load_proxy_list() -> List[str]:
    """Load proxies from PROXY_LIST (multi-line) or PROXY_URL (single)."""
    proxies: List[str] = []

    # PROXY_LIST: multi-line list of proxies (ip:port:user:pass format)
    proxy_list_raw = os.environ.get("PROXY_LIST", "").strip()
    if proxy_list_raw:
        for line in proxy_list_raw.splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split(":")
            if len(parts) == 4:
                ip, port, user, pwd = parts
                proxies.append(f"http://{user}:{pwd}@{ip}:{port}")
            elif line.startswith(("http://", "https://", "socks5://")):
                proxies.append(line)

    # PROXY_URL: single proxy (backward compatible)
    single = os.environ.get("PROXY_URL", "").strip()
    if single and single not in proxies:
        proxies.append(single)

    return proxies


_PROXY_POOL: List[str] = []
_PROXY_INDEX = 0


def _get_next_proxy() -> Optional[str]:
    """Get next proxy from pool using round-robin rotation."""
    global _PROXY_POOL, _PROXY_INDEX
    if not _PROXY_POOL:
        _PROXY_POOL = _load_proxy_list()
    if not _PROXY_POOL:
        return None
    proxy = _PROXY_POOL[_PROXY_INDEX % len(_PROXY_POOL)]
    _PROXY_INDEX += 1
    return proxy


def _get_random_proxy() -> Optional[str]:
    """Get a random proxy from pool."""
    global _PROXY_POOL
    if not _PROXY_POOL:
        _PROXY_POOL = _load_proxy_list()
    if not _PROXY_POOL:
        return None
    return random.choice(_PROXY_POOL)


# ---------------------------------------------------------------------------
# Name data
# ---------------------------------------------------------------------------
FIRST_NAMES = [
    "James", "John", "Robert", "Michael", "William", "David", "Richard",
    "Joseph", "Thomas", "Christopher", "Charles", "Daniel", "Matthew",
    "Anthony", "Mark", "Donald", "Steven", "Andrew", "Paul", "Joshua",
    "Kenneth", "Kevin", "Brian", "George", "Timothy", "Ronald", "Edward",
    "Jason", "Jeffrey", "Ryan", "Jacob", "Nicholas", "Eric", "Jonathan",
    "Mary", "Patricia", "Jennifer", "Linda", "Elizabeth", "Barbara",
    "Susan", "Jessica", "Sarah", "Karen", "Lisa", "Nancy", "Betty",
    "Margaret", "Sandra", "Ashley", "Kimberly", "Emily", "Donna",
    "Michelle", "Dorothy", "Carol", "Amanda", "Melissa", "Deborah",
    "Stephanie", "Rebecca", "Sharon", "Laura", "Emma", "Olivia", "Ava",
    "Isabella", "Sophia", "Mia", "Charlotte", "Amelia",
]

LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller",
    "Davis", "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez",
    "Wilson", "Anderson", "Thomas", "Taylor", "Moore", "Jackson", "Martin",
    "Lee", "Perez", "Thompson", "White", "Harris", "Sanchez", "Clark",
    "Ramirez", "Lewis", "Robinson", "Walker", "Young", "Allen", "King",
    "Wright", "Scott", "Torres", "Nguyen", "Hill", "Flores", "Green",
    "Adams", "Nelson", "Baker", "Hall", "Rivera", "Campbell", "Mitchell",
    "Carter", "Roberts", "Turner", "Phillips", "Evans", "Parker", "Edwards",
]

# ---------------------------------------------------------------------------
# University / school catalogues
# ---------------------------------------------------------------------------
STUDENT_UNIVERSITIES: List[Dict[str, Any]] = [
    {"id": 2565, "name": "Pennsylvania State University-Main Campus", "domain": "psu.edu", "weight": 100},
    {"id": 3499, "name": "University of California, Los Angeles", "domain": "ucla.edu", "weight": 98},
    {"id": 3491, "name": "University of California, Berkeley", "domain": "berkeley.edu", "weight": 97},
    {"id": 1953, "name": "Massachusetts Institute of Technology", "domain": "mit.edu", "weight": 95},
    {"id": 3113, "name": "Stanford University", "domain": "stanford.edu", "weight": 95},
    {"id": 2285, "name": "New York University", "domain": "nyu.edu", "weight": 96},
    {"id": 1426, "name": "Harvard University", "domain": "harvard.edu", "weight": 92},
    {"id": 698, "name": "Columbia University", "domain": "columbia.edu", "weight": 92},
    {"id": 3568, "name": "University of Michigan", "domain": "umich.edu", "weight": 95},
    {"id": 3686, "name": "University of Texas at Austin", "domain": "utexas.edu", "weight": 94},
    {"id": 378, "name": "Arizona State University", "domain": "asu.edu", "weight": 93},
    {"id": 3521, "name": "University of Florida", "domain": "ufl.edu", "weight": 91},
    {"id": 1217, "name": "Georgia Institute of Technology", "domain": "gatech.edu", "weight": 90},
    {"id": 602, "name": "Carnegie Mellon University", "domain": "cmu.edu", "weight": 89},
    {"id": 2506, "name": "Ohio State University", "domain": "osu.edu", "weight": 88},
    {"id": 328355, "name": "University of Toronto", "domain": "utoronto.ca", "weight": 88},
    {"id": 328315, "name": "University of British Columbia", "domain": "ubc.ca", "weight": 86},
    {"id": 273409, "name": "University of Oxford", "domain": "ox.ac.uk", "weight": 88},
    {"id": 273378, "name": "University of Cambridge", "domain": "cam.ac.uk", "weight": 88},
    {"id": 273294, "name": "Imperial College London", "domain": "imperial.ac.uk", "weight": 85},
    {"id": 10011178, "name": "Technical University of Munich", "domain": "tum.de", "weight": 85},
    {"id": 345301, "name": "The University of Melbourne", "domain": "unimelb.edu.au", "weight": 85},
    {"id": 354085, "name": "The University of Tokyo", "domain": "u-tokyo.ac.jp", "weight": 83},
    {"id": 356355, "name": "National University of Singapore", "domain": "nus.edu.sg", "weight": 85},
    {"id": 588731, "name": "Hanoi University of Science and Technology", "domain": "hust.edu.vn", "weight": 90},
    {"id": 588772, "name": "FPT University", "domain": "fpt.edu.vn", "weight": 88},
]

# Google One program uses different organization IDs than other programs
GOOGLE_ONE_UNIVERSITIES: List[Dict[str, Any]] = [
    # =========== USA - HIGH PRIORITY (real SheerID IDs) ===========
    {"id": 2565, "name": "Pennsylvania State University-Main Campus", "domain": "psu.edu", "weight": 100},
    {"id": 3499, "name": "University of California, Los Angeles", "domain": "ucla.edu", "weight": 98},
    {"id": 3491, "name": "University of California, Berkeley", "domain": "berkeley.edu", "weight": 97},
    {"id": 1953, "name": "Massachusetts Institute of Technology", "domain": "mit.edu", "weight": 95},
    {"id": 3113, "name": "Stanford University", "domain": "stanford.edu", "weight": 95},
    {"id": 2285, "name": "New York University", "domain": "nyu.edu", "weight": 96},
    {"id": 1426, "name": "Harvard University", "domain": "harvard.edu", "weight": 92},
    {"id": 590759, "name": "Yale University", "domain": "yale.edu", "weight": 90},
    {"id": 2626, "name": "Princeton University", "domain": "princeton.edu", "weight": 90},
    {"id": 698, "name": "Columbia University", "domain": "columbia.edu", "weight": 92},
    {"id": 3508, "name": "University of Chicago", "domain": "uchicago.edu", "weight": 88},
    {"id": 943, "name": "Duke University", "domain": "duke.edu", "weight": 88},
    {"id": 751, "name": "Cornell University", "domain": "cornell.edu", "weight": 90},
    {"id": 2420, "name": "Northwestern University", "domain": "northwestern.edu", "weight": 88},
    {"id": 3568, "name": "University of Michigan", "domain": "umich.edu", "weight": 95},
    {"id": 3686, "name": "University of Texas at Austin", "domain": "utexas.edu", "weight": 94},
    {"id": 1217, "name": "Georgia Institute of Technology", "domain": "gatech.edu", "weight": 93},
    {"id": 602, "name": "Carnegie Mellon University", "domain": "cmu.edu", "weight": 92},
    {"id": 3477, "name": "University of California, San Diego", "domain": "ucsd.edu", "weight": 93},
    {"id": 3600, "name": "University of North Carolina at Chapel Hill", "domain": "unc.edu", "weight": 90},
    {"id": 3645, "name": "University of Southern California", "domain": "usc.edu", "weight": 91},
    {"id": 3629, "name": "University of Pennsylvania", "domain": "upenn.edu", "weight": 90},
    {"id": 1603, "name": "Indiana University Bloomington", "domain": "iu.edu", "weight": 88},
    {"id": 2506, "name": "Ohio State University", "domain": "osu.edu", "weight": 90},
    {"id": 2700, "name": "Purdue University", "domain": "purdue.edu", "weight": 89},
    {"id": 3761, "name": "University of Washington", "domain": "uw.edu", "weight": 90},
    {"id": 3770, "name": "University of Wisconsin-Madison", "domain": "wisc.edu", "weight": 88},
    {"id": 3562, "name": "University of Maryland", "domain": "umd.edu", "weight": 87},
    {"id": 519, "name": "Boston University", "domain": "bu.edu", "weight": 86},
    {"id": 378, "name": "Arizona State University", "domain": "asu.edu", "weight": 92},
    {"id": 3521, "name": "University of Florida", "domain": "ufl.edu", "weight": 90},
    {"id": 3535, "name": "University of Illinois at Urbana-Champaign", "domain": "illinois.edu", "weight": 91},
    {"id": 3557, "name": "University of Minnesota Twin Cities", "domain": "umn.edu", "weight": 88},
    {"id": 3483, "name": "University of California, Davis", "domain": "ucdavis.edu", "weight": 89},
    {"id": 3487, "name": "University of California, Irvine", "domain": "uci.edu", "weight": 88},
    {"id": 3502, "name": "University of California, Santa Barbara", "domain": "ucsb.edu", "weight": 87},
    {"id": 2874, "name": "Santa Monica College", "domain": "smc.edu", "weight": 85},
    {"id": 2350, "name": "Northern Virginia Community College", "domain": "nvcc.edu", "weight": 84},
    # =========== OTHER COUNTRIES (lower priority) ===========
    {"id": 328355, "name": "University of Toronto", "domain": "utoronto.ca", "weight": 40},
    {"id": 328315, "name": "University of British Columbia", "domain": "ubc.ca", "weight": 38},
    {"id": 273409, "name": "University of Oxford", "domain": "ox.ac.uk", "weight": 35},
    {"id": 273378, "name": "University of Cambridge", "domain": "cam.ac.uk", "weight": 35},
    {"id": 345301, "name": "The University of Melbourne", "domain": "unimelb.edu.au", "weight": 30},
    {"id": 345303, "name": "The University of Sydney", "domain": "sydney.edu.au", "weight": 28},
]

TEACHER_UNIVERSITIES: List[Dict[str, Any]] = [
    {"id": 2565, "name": "Pennsylvania State University-Main Campus", "domain": "psu.edu", "weight": 100},
    {"id": 3499, "name": "University of California, Los Angeles", "domain": "ucla.edu", "weight": 98},
    {"id": 3491, "name": "University of California, Berkeley", "domain": "berkeley.edu", "weight": 97},
    {"id": 1953, "name": "Massachusetts Institute of Technology", "domain": "mit.edu", "weight": 95},
    {"id": 3113, "name": "Stanford University", "domain": "stanford.edu", "weight": 95},
    {"id": 2285, "name": "New York University", "domain": "nyu.edu", "weight": 94},
    {"id": 1426, "name": "Harvard University", "domain": "harvard.edu", "weight": 92},
    {"id": 698, "name": "Columbia University", "domain": "columbia.edu", "weight": 92},
    {"id": 3568, "name": "University of Michigan", "domain": "umich.edu", "weight": 93},
    {"id": 3686, "name": "University of Texas at Austin", "domain": "utexas.edu", "weight": 92},
    {"id": 1217, "name": "Georgia Institute of Technology", "domain": "gatech.edu", "weight": 91},
    {"id": 602, "name": "Carnegie Mellon University", "domain": "cmu.edu", "weight": 90},
    {"id": 328355, "name": "University of Toronto", "domain": "utoronto.ca", "weight": 85},
    {"id": 273409, "name": "University of Oxford", "domain": "ox.ac.uk", "weight": 85},
    {"id": 273378, "name": "University of Cambridge", "domain": "cam.ac.uk", "weight": 85},
]

K12_SCHOOLS: List[Dict[str, Any]] = [
    {"id": 155694, "name": "Stuyvesant High School", "weight": 100},
    {"id": 156251, "name": "Bronx High School Of Science", "weight": 98},
    {"id": 157582, "name": "Brooklyn Technical High School", "weight": 95},
    {"id": 3704245, "name": "Thomas Jefferson High School For Science And Technology", "weight": 100},
    {"id": 3521141, "name": "Walter Payton College Preparatory High School", "weight": 95},
    {"id": 3521074, "name": "Whitney M Young Magnet High School", "weight": 92},
    {"id": 3539252, "name": "Gretchen Whitney High School", "weight": 95},
    {"id": 262338, "name": "Lowell High School (San Francisco)", "weight": 90},
    {"id": 3536914, "name": "BASIS Scottsdale", "weight": 90},
    {"id": 202063, "name": "Signature School Inc", "weight": 95},
    {"id": 183857, "name": "School For Advanced Studies Homestead", "weight": 92},
    {"id": 3506727, "name": "Loveless Academic Magnet Program High School (LAMP)", "weight": 90},
    {"id": 174195, "name": "North Carolina School of Science and Mathematics", "weight": 90},
]

# Program IDs per service
PROGRAM_IDS: Dict[str, str] = {
    "spotify": "67c8c14f5f17a83b745e3f82",
    "youtube": "67c8c14f5f17a83b745e3f82",
    "google_one": "67c8c14f5f17a83b745e3f82",
    "boltnew": "68cc6a2e64f55220de204448",
    "k12": "68d47554aa292d20b9bec8f7",
    "veterans": "690415d58971e73ca187d8c9",
    "perplexity": "",
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _weighted_choice(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    weights = [i["weight"] for i in items]
    total = sum(weights)
    r = random.uniform(0, total)
    cumulative = 0.0
    for item in items:
        cumulative += item["weight"]
        if r <= cumulative:
            return item
    return items[0]


def _generate_fingerprint() -> str:
    """Generate realistic browser fingerprint to avoid fraud detection."""
    resolutions = ["1920x1080", "1366x768", "1536x864", "1440x900", "1280x720", "2560x1440"]
    timezones = [-8, -7, -6, -5, -4, 0, 1, 2, 3, 5.5, 8, 9, 10]
    languages = ["en-US", "en-GB", "en-CA", "en-AU", "es-ES", "fr-FR", "de-DE", "pt-BR"]
    platforms = ["Win32", "MacIntel", "Linux x86_64"]
    vendors = ["Google Inc.", "Apple Computer, Inc.", ""]
    components = [
        str(int(time.time() * 1000)),
        str(random.random()),
        random.choice(resolutions),
        str(random.choice(timezones)),
        random.choice(languages),
        random.choice(platforms),
        random.choice(vendors),
        str(random.randint(1, 16)),   # hardware concurrency
        str(random.randint(2, 32)),   # device memory GB
        str(random.randint(0, 1)),    # touch support
    ]
    return hashlib.md5("|".join(components).encode()).hexdigest()


def _generate_name() -> Tuple[str, str]:
    return random.choice(FIRST_NAMES), random.choice(LAST_NAMES)


def _generate_email(first: str, last: str, domain: str) -> str:
    patterns = [
        f"{first[0].lower()}{last.lower()}{random.randint(100, 999)}",
        f"{first.lower()}.{last.lower()}{random.randint(10, 99)}",
        f"{last.lower()}{first[0].lower()}{random.randint(100, 999)}",
    ]
    return f"{random.choice(patterns)}@{domain}"


def _generate_student_dob() -> str:
    year = random.randint(2000, 2006)
    month = random.randint(1, 12)
    day = random.randint(1, 28)
    return f"{year}-{month:02d}-{day:02d}"


def _generate_teacher_dob() -> str:
    year = random.randint(1970, 2000)
    month = random.randint(1, 12)
    day = random.randint(1, 28)
    return f"{year}-{month:02d}-{day:02d}"


def _parse_verification_id(url: str) -> Optional[str]:
    m = re.search(r"verificationId=([a-f0-9]+)", url, re.IGNORECASE)
    return m.group(1) if m else None


def _parse_program_id(url: str) -> Optional[str]:
    m = re.search(r"/verify/([a-f0-9]+)", url, re.IGNORECASE)
    return m.group(1) if m else None


# ---------------------------------------------------------------------------
# Document generators
# ---------------------------------------------------------------------------

def _generate_student_id_image(first: str, last: str, school: str) -> bytes:
    w, h = 650, 400
    img = Image.new("RGB", (w, h), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    try:
        font_lg = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 22)
        font_md = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 16)
        font_sm = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 12)
    except Exception:
        font_lg = font_md = font_sm = ImageFont.load_default()

    draw.rectangle([(0, 0), (w, 60)], fill=(0, 51, 102))
    draw.text((w // 2, 30), "STUDENT IDENTIFICATION CARD", fill=(255, 255, 255), font=font_lg, anchor="mm")
    draw.text((w // 2, 90), school[:50], fill=(0, 51, 102), font=font_md, anchor="mm")

    draw.rectangle([(30, 120), (150, 280)], outline=(180, 180, 180), width=2)
    draw.text((90, 200), "PHOTO", fill=(180, 180, 180), font=font_md, anchor="mm")

    student_id = f"STU{random.randint(100000, 999999)}"
    y = 130
    for line in [
        f"Name: {first} {last}",
        f"ID: {student_id}",
        "Status: Full-time Student",
        "Major: Computer Science",
        f"Valid: {time.strftime('%Y')}-{int(time.strftime('%Y')) + 1}",
    ]:
        draw.text((175, y), line, fill=(51, 51, 51), font=font_md)
        y += 28

    draw.rectangle([(0, h - 40), (w, h)], fill=(0, 51, 102))
    draw.text((w // 2, h - 20), "Property of University", fill=(255, 255, 255), font=font_sm, anchor="mm")

    for i in range(20):
        x = 480 + i * 7
        draw.rectangle([(x, 280), (x + 3, 280 + random.randint(30, 50))], fill=(0, 0, 0))

    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _generate_transcript_image(first: str, last: str, school: str, dob: str) -> bytes:
    """Generate academic transcript image (higher success rate than ID card)."""
    w, h = 850, 1100
    img = Image.new("RGB", (w, h), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    try:
        font_header = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 28)
        font_title = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 20)
        font_text = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)
        font_bold = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 14)
    except Exception:
        font_header = font_title = font_text = font_bold = ImageFont.load_default()

    draw.text((w // 2, 50), school.upper(), fill=(0, 0, 0), font=font_header, anchor="mm")
    draw.text((w // 2, 90), "OFFICIAL ACADEMIC TRANSCRIPT", fill=(50, 50, 50), font=font_title, anchor="mm")
    draw.line([(50, 110), (w - 50, 110)], fill=(0, 0, 0), width=2)

    y = 150
    draw.text((50, y), f"Student Name: {first} {last}", fill=(0, 0, 0), font=font_bold)
    draw.text((w - 300, y), f"Student ID: {random.randint(10000000, 99999999)}", fill=(0, 0, 0), font=font_text)
    y += 30
    draw.text((50, y), f"Date of Birth: {dob}", fill=(0, 0, 0), font=font_text)
    draw.text((w - 300, y), f"Date Issued: {time.strftime('%Y-%m-%d')}", fill=(0, 0, 0), font=font_text)
    y += 40

    draw.rectangle([(50, y), (w - 50, y + 40)], fill=(240, 240, 240))
    semester = random.choice(["SPRING", "FALL"])
    draw.text((w // 2, y + 20), f"CURRENT STATUS: ENROLLED ({semester} {time.strftime('%Y')})", fill=(0, 100, 0), font=font_bold, anchor="mm")
    y += 70

    courses = [
        ("CS 101", "Intro to Computer Science", "4.0", random.choice(["A", "A-", "B+"])),
        ("MATH 201", "Calculus I", "3.0", random.choice(["A-", "B+", "A"])),
        ("ENG 102", "Academic Writing", "3.0", random.choice(["B+", "A-", "B"])),
        ("PHYS 150", "Physics for Engineers", "4.0", random.choice(["A", "A-", "B+"])),
        ("HIST 110", "World History", "3.0", random.choice(["A", "B+", "A-"])),
    ]

    draw.text((50, y), "Course Code", font=font_bold, fill=(0, 0, 0))
    draw.text((200, y), "Course Title", font=font_bold, fill=(0, 0, 0))
    draw.text((600, y), "Credits", font=font_bold, fill=(0, 0, 0))
    draw.text((700, y), "Grade", font=font_bold, fill=(0, 0, 0))
    y += 20
    draw.line([(50, y), (w - 50, y)], fill=(0, 0, 0), width=1)
    y += 20

    for code, title, cred, grade in courses:
        draw.text((50, y), code, font=font_text, fill=(0, 0, 0))
        draw.text((200, y), title, font=font_text, fill=(0, 0, 0))
        draw.text((600, y), cred, font=font_text, fill=(0, 0, 0))
        draw.text((700, y), grade, font=font_text, fill=(0, 0, 0))
        y += 30

    y += 20
    draw.line([(50, y), (w - 50, y)], fill=(0, 0, 0), width=1)
    y += 30

    gpa = round(random.uniform(3.5, 3.95), 2)
    draw.text((50, y), f"Cumulative GPA: {gpa}", font=font_bold, fill=(0, 0, 0))
    draw.text((w - 300, y), "Academic Standing: Good", font=font_bold, fill=(0, 0, 0))

    draw.text((w // 2, h - 50), "This document is electronically generated and valid without signature.",
              fill=(100, 100, 100), font=font_text, anchor="mm")

    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _generate_teacher_cert_image(first: str, last: str, school: str) -> bytes:
    w, h = 800, 500
    img = Image.new("RGB", (w, h), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    try:
        title_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 28)
        text_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 20)
        small_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)
    except Exception:
        title_font = text_font = small_font = ImageFont.load_default()

    draw.rectangle([(20, 20), (w - 20, h - 20)], outline=(0, 51, 102), width=3)
    draw.text((w // 2, 60), "FACULTY EMPLOYMENT VERIFICATION", fill=(0, 51, 102), font=title_font, anchor="mm")
    draw.line([(50, 100), (w - 50, 100)], fill=(0, 51, 102), width=2)
    draw.text((w // 2, 140), school, fill=(51, 51, 51), font=text_font, anchor="mm")

    y = 200
    for line in [
        f"Employee Name: {first} {last}",
        "Position: Faculty Member",
        "Department: Education",
        "Employment Status: Active",
        f"Issue Date: {time.strftime('%B %d, %Y')}",
    ]:
        draw.text((100, y), line, fill=(51, 51, 51), font=text_font)
        y += 40

    draw.text(
        (w // 2, h - 60),
        "This document verifies current employment status.",
        fill=(128, 128, 128),
        font=small_font,
        anchor="mm",
    )
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _generate_k12_badge(first: str, last: str, school: str) -> bytes:
    w, h = 500, 350
    img = Image.new("RGB", (w, h), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    try:
        title_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 20)
        text_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)
        small_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 10)
    except Exception:
        title_font = text_font = small_font = ImageFont.load_default()

    draw.rectangle([(0, 0), (w, 50)], fill=(34, 139, 34))
    draw.text((w // 2, 25), "STAFF IDENTIFICATION", fill=(255, 255, 255), font=title_font, anchor="mm")
    draw.text((w // 2, 75), school[:45], fill=(34, 139, 34), font=text_font, anchor="mm")

    draw.rectangle([(25, 100), (125, 220)], outline=(200, 200, 200), width=2)
    draw.text((75, 160), "PHOTO", fill=(200, 200, 200), font=text_font, anchor="mm")

    y = 110
    for line in [
        f"Name: {first} {last}",
        "Role: Teacher",
        "Department: Education",
        f"ID: TCH{random.randint(10000, 99999)}",
        f"Valid: {time.strftime('%Y')}-{int(time.strftime('%Y')) + 1}",
    ]:
        draw.text((140, y), line, fill=(51, 51, 51), font=text_font)
        y += 24

    draw.rectangle([(0, h - 30), (w, h)], fill=(34, 139, 34))
    draw.text((w // 2, h - 15), "Authorized Personnel Only", fill=(255, 255, 255), font=small_font, anchor="mm")
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Async HTTP helpers
# ---------------------------------------------------------------------------

async def _api_request(
    client: httpx.AsyncClient,
    method: str,
    endpoint: str,
    body: Optional[Dict] = None,
) -> Tuple[Dict, int]:
    await asyncio.sleep(random.randint(MIN_DELAY_MS, MAX_DELAY_MS) / 1000)
    try:
        resp = await client.request(
            method,
            f"{SHEERID_API}{endpoint}",
            json=body,
            headers={"Content-Type": "application/json"},
        )
        data = resp.json() if resp.text else {}
        if resp.status_code >= 400:
            log.warning("SheerID %s %s -> %d: %s", method, endpoint, resp.status_code, data)
        return data, resp.status_code
    except Exception as exc:
        raise RuntimeError(f"SheerID request failed: {exc}") from exc


async def _upload_s3(client: httpx.AsyncClient, url: str, data: bytes) -> bool:
    try:
        resp = await client.put(url, content=data, headers={"Content-Type": "image/png"}, timeout=60)
        return 200 <= resp.status_code < 300
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Link validation
# ---------------------------------------------------------------------------

async def _check_link(client: httpx.AsyncClient, vid: str) -> Optional[str]:
    """Check if verification link is valid. Returns error message or None."""
    data, status = await _api_request(client, "GET", f"/verification/{vid}")
    if status == 404:
        return "الرابط منتهي أو غير موجود. أنشئ رابط تحقق جديد."
    if status != 200:
        return f"فشل فحص الرابط: HTTP {status}"
    step = data.get("currentStep", "")
    if step == "success":
        return "هذا الرابط تم التحقق منه مسبقاً."
    if step == "pending":
        return "هذا الرابط قيد المراجعة بالفعل."
    return None


# ---------------------------------------------------------------------------
# Public verification functions — one per service type
# ---------------------------------------------------------------------------

async def verify_student(url: str, service_key: str) -> Dict[str, Any]:
    """Student verification flow (Spotify, YouTube, Google One, Perplexity)."""
    vid = _parse_verification_id(url)
    if not vid:
        return {"success": False, "error": "رابط غير صالح — لم يتم العثور على verificationId"}

    program_id = PROGRAM_IDS.get(service_key) or _parse_program_id(url) or ""
    first, last = _generate_name()
    uni = _weighted_choice(STUDENT_UNIVERSITIES)
    email = _generate_email(first, last, uni["domain"])
    dob = _generate_student_dob()
    fingerprint = _generate_fingerprint()

    log.info("Student verify: %s %s @ %s (vid=%s…)", first, last, uni["name"], vid[:12])

    _api_proxy = _get_random_proxy()
    log.info("Using proxy for student verify: %s", _api_proxy[:30] + "..." if _api_proxy else "none")
    async with httpx.AsyncClient(timeout=30, proxy=_api_proxy) as client:
        err = await _check_link(client, vid)
        if err:
            return {"success": False, "error": err}

        # Generate document: transcript 70%, student ID 30%
        if random.random() < 0.7:
            doc = _generate_transcript_image(first, last, uni["name"], dob)
        else:
            doc = _generate_student_id_image(first, last, uni["name"])

        body = {
            "firstName": first,
            "lastName": last,
            "birthDate": dob,
            "email": email,
            "phoneNumber": "",
            "organization": {"id": uni["id"], "idExtended": str(uni["id"]), "name": uni["name"]},
            "deviceFingerprintHash": fingerprint,
            "locale": "en-US",
            "metadata": {
                "marketConsentValue": False,
                "verificationId": vid,
                "refererUrl": f"{SHEERID_BASE}/verify/{program_id}/?verificationId={vid}",
                "flags": '{"collect-info-step-email-first":"default","doc-upload-considerations":"default","doc-upload-may24":"default","doc-upload-redesign-use-legacy-message-keys":false,"docUpload-assertion-checklist":"default","font-size":"default","include-cvec-field-france-student":"not-labeled-optional"}',
                "submissionOptIn": (
                    "By submitting the personal information above, I acknowledge that my "
                    "personal information is being collected under the privacy policy of the "
                    "business from which I am seeking a discount"
                ),
            },
        }

        data, status = await _api_request(client, "POST", f"/verification/{vid}/step/collectStudentPersonalInfo", body)
        if status != 200:
            return {"success": False, "error": f"فشل إرسال البيانات: HTTP {status}"}
        if data.get("currentStep") == "error":
            return {"success": False, "error": f"خطأ SheerID: {data.get('errorIds', [])}"}

        step = data.get("currentStep", "")
        if step in ("sso", "collectStudentPersonalInfo"):
            await _api_request(client, "DELETE", f"/verification/{vid}/step/sso")

        upload_body = {"files": [{"fileName": "student_card.png", "mimeType": "image/png", "fileSize": len(doc)}]}
        data, status = await _api_request(client, "POST", f"/verification/{vid}/step/docUpload", upload_body)
        if not data.get("documents"):
            return {"success": False, "error": "لم يتم الحصول على رابط الرفع"}

        upload_url = data["documents"][0].get("uploadUrl")
        if not upload_url or not await _upload_s3(client, upload_url, doc):
            return {"success": False, "error": "فشل رفع المستند"}

        data, _ = await _api_request(client, "POST", f"/verification/{vid}/step/completeDocUpload")

    return {
        "success": True,
        "student": f"{first} {last}",
        "email": email,
        "school": uni["name"],
        "step": data.get("currentStep", "pending"),
        "redirect": data.get("redirectUrl"),
    }


async def verify_teacher(url: str) -> Dict[str, Any]:
    """Teacher verification flow (Bolt.new)."""
    vid = _parse_verification_id(url)
    if not vid:
        return {"success": False, "error": "رابط غير صالح — لم يتم العثور على verificationId"}

    first, last = _generate_name()
    uni = _weighted_choice(TEACHER_UNIVERSITIES)
    email = _generate_email(first, last, uni["domain"])
    dob = _generate_teacher_dob()
    fingerprint = _generate_fingerprint()
    program_id = PROGRAM_IDS["boltnew"]

    log.info("Teacher verify: %s %s @ %s (vid=%s…)", first, last, uni["name"], vid[:12])

    _api_proxy = _get_random_proxy()
    async with httpx.AsyncClient(timeout=30, proxy=_api_proxy) as client:
        err = await _check_link(client, vid)
        if err:
            return {"success": False, "error": err}

        doc = _generate_teacher_cert_image(first, last, uni["name"])

        body = {
            "firstName": first,
            "lastName": last,
            "birthDate": dob,
            "email": email,
            "phoneNumber": "",
            "organization": {"id": uni["id"], "idExtended": str(uni["id"]), "name": uni["name"]},
            "deviceFingerprintHash": fingerprint,
            "locale": "en-US",
            "metadata": {
                "marketConsentValue": False,
                "verificationId": vid,
                "refererUrl": f"{SHEERID_BASE}/verify/{program_id}/?verificationId={vid}",
                "submissionOptIn": (
                    "By submitting the personal information above, I acknowledge that my "
                    "personal information is being collected under the privacy policy of the "
                    "business from which I am seeking a discount"
                ),
            },
        }

        data, status = await _api_request(client, "POST", f"/verification/{vid}/step/collectTeacherPersonalInfo", body)
        if status != 200:
            return {"success": False, "error": f"فشل إرسال البيانات: HTTP {status}"}
        if data.get("currentStep") == "error":
            return {"success": False, "error": f"خطأ SheerID: {data.get('errorIds', [])}"}

        step = data.get("currentStep", "")
        if step in ("sso", "collectTeacherPersonalInfo"):
            await _api_request(client, "DELETE", f"/verification/{vid}/step/sso")

        upload_body = {"files": [{"fileName": "teacher_certificate.png", "mimeType": "image/png", "fileSize": len(doc)}]}
        data, status = await _api_request(client, "POST", f"/verification/{vid}/step/docUpload", upload_body)
        if not data.get("documents"):
            return {"success": False, "error": "لم يتم الحصول على رابط الرفع"}

        upload_url = data["documents"][0].get("uploadUrl")
        if not upload_url or not await _upload_s3(client, upload_url, doc):
            return {"success": False, "error": "فشل رفع المستند"}

        data, _ = await _api_request(client, "POST", f"/verification/{vid}/step/completeDocUpload")

    return {
        "success": True,
        "teacher": f"{first} {last}",
        "email": email,
        "school": uni["name"],
        "step": data.get("currentStep", "pending"),
        "redirect": data.get("redirectUrl"),
    }


async def verify_k12(url: str) -> Dict[str, Any]:
    """K12 teacher verification flow (ChatGPT Plus)."""
    vid = _parse_verification_id(url)
    if not vid:
        return {"success": False, "error": "رابط غير صالح — لم يتم العثور على verificationId"}

    first, last = _generate_name()
    school = _weighted_choice(K12_SCHOOLS)
    email = f"{first.lower()}.{last.lower()}{random.randint(100, 999)}@{random.choice(['gmail.com', 'yahoo.com', 'outlook.com'])}"
    dob = _generate_teacher_dob()
    fingerprint = _generate_fingerprint()
    program_id = PROGRAM_IDS["k12"]

    log.info("K12 verify: %s %s @ %s (vid=%s…)", first, last, school["name"], vid[:12])

    _api_proxy = _get_random_proxy()
    async with httpx.AsyncClient(timeout=30, proxy=_api_proxy) as client:
        err = await _check_link(client, vid)
        if err:
            return {"success": False, "error": err}

        body = {
            "firstName": first,
            "lastName": last,
            "birthDate": dob,
            "email": email,
            "phoneNumber": "",
            "organization": {"id": school["id"], "idExtended": str(school["id"]), "name": school["name"]},
            "deviceFingerprintHash": fingerprint,
            "locale": "en-US",
            "metadata": {
                "marketConsentValue": False,
                "submissionOptIn": (
                    "By submitting the personal information above, I acknowledge that my "
                    "personal information is being collected under the privacy policy of the "
                    "business from which I am seeking a discount"
                ),
            },
        }

        data, status = await _api_request(client, "POST", f"/verification/{vid}/step/collectTeacherPersonalInfo", body)
        if status != 200:
            return {"success": False, "error": f"فشل إرسال البيانات: HTTP {status}"}
        if data.get("currentStep") == "error":
            return {"success": False, "error": f"خطأ SheerID: {data.get('errorIds', [])}"}

        step = data.get("currentStep", "")

        if step == "success":
            return {
                "success": True,
                "teacher": f"{first} {last}",
                "email": email,
                "school": school["name"],
                "step": "success",
                "redirect": data.get("redirectUrl"),
            }

        if step in ("sso", "collectTeacherPersonalInfo"):
            await _api_request(client, "DELETE", f"/verification/{vid}/step/sso")

        doc = _generate_k12_badge(first, last, school["name"])
        upload_body = {"files": [{"fileName": "teacher_badge.png", "mimeType": "image/png", "fileSize": len(doc)}]}
        data, status = await _api_request(client, "POST", f"/verification/{vid}/step/docUpload", upload_body)
        if not data.get("documents"):
            return {"success": False, "error": "لم يتم الحصول على رابط الرفع"}

        upload_url = data["documents"][0].get("uploadUrl")
        if not upload_url or not await _upload_s3(client, upload_url, doc):
            return {"success": False, "error": "فشل رفع المستند"}

        data, _ = await _api_request(client, "POST", f"/verification/{vid}/step/completeDocUpload")

    return {
        "success": True,
        "teacher": f"{first} {last}",
        "email": email,
        "school": school["name"],
        "step": data.get("currentStep", "pending"),
        "redirect": data.get("redirectUrl"),
    }


BRANCH_ORG_MAP: Dict[str, Dict[str, Any]] = {
    "Army": {"id": 4070, "name": "Army"},
    "Air Force": {"id": 4073, "name": "Air Force"},
    "Navy": {"id": 4072, "name": "Navy"},
    "Marine Corps": {"id": 4071, "name": "Marine Corps"},
    "Coast Guard": {"id": 4074, "name": "Coast Guard"},
    "Space Force": {"id": 4544268, "name": "Space Force"},
}


async def verify_veterans(url: str) -> Dict[str, Any]:
    """Veterans / military verification flow (2-step: militaryStatus then personalInfo)."""
    vid = _parse_verification_id(url)
    if not vid:
        return {"success": False, "error": "رابط غير صالح — لم يتم العثور على verificationId"}

    first, last = _generate_name()
    dob = f"{random.randint(1970, 2000)}-{random.randint(1, 12):02d}-{random.randint(1, 28):02d}"
    email = f"{first.lower()}.{last.lower()}{random.randint(100, 999)}@{random.choice(['gmail.com', 'yahoo.com', 'outlook.com'])}"
    fingerprint = _generate_fingerprint()
    program_id = PROGRAM_IDS["veterans"]

    discharge_date = "2025-01-02"
    branch_name = random.choice(list(BRANCH_ORG_MAP.keys()))
    org = BRANCH_ORG_MAP[branch_name]

    log.info("Veterans verify: %s %s branch=%s (vid=%s…)", first, last, branch_name, vid[:12])

    _api_proxy = _get_random_proxy()
    async with httpx.AsyncClient(timeout=30, proxy=_api_proxy) as client:
        err = await _check_link(client, vid)
        if err:
            return {"success": False, "error": err}

        # Step 1: Submit military status as VETERAN
        data, status = await _api_request(
            client, "POST",
            f"/verification/{vid}/step/collectMilitaryStatus",
            {"status": "VETERAN"},
        )
        if status != 200:
            return {"success": False, "error": f"فشل إرسال حالة الخدمة: HTTP {status}"}

        # Step 2: Submit personal info
        referer = f"{SHEERID_BASE}/verify/{program_id}/?verificationId={vid}"
        body = {
            "firstName": first,
            "lastName": last,
            "birthDate": dob,
            "email": email,
            "phoneNumber": "",
            "organization": org,
            "dischargeDate": discharge_date,
            "deviceFingerprintHash": fingerprint,
            "locale": "en-US",
            "country": "US",
            "metadata": {
                "marketConsentValue": False,
                "refererUrl": referer,
                "verificationId": vid,
                "submissionOptIn": (
                    "By submitting the personal information above, I acknowledge that my "
                    "personal information is being collected under the privacy policy of the "
                    "business from which I am seeking a discount"
                ),
            },
        }

        data, status = await _api_request(
            client, "POST",
            f"/verification/{vid}/step/collectInactiveMilitaryPersonalInfo",
            body,
        )
        if status != 200:
            return {"success": False, "error": f"فشل إرسال البيانات: HTTP {status}"}
        if data.get("currentStep") == "error":
            return {"success": False, "error": f"خطأ SheerID: {data.get('errorIds', [])}"}

    return {
        "success": True,
        "person": f"{first} {last}",
        "email": email,
        "branch": branch_name,
        "step": data.get("currentStep", "pending"),
        "redirect": data.get("redirectUrl"),
    }


# ---------------------------------------------------------------------------
# Auto Gemini verification (no link needed)
# ---------------------------------------------------------------------------

ProgressCallback = Callable[[str], Awaitable[None]]

GEMINI_STEPS = [
    "الإيميل",
    "كلمة السر",
    "المصادقة الثنائية",
    "طريقة الدفع",
    "إضافة طريقة دفع",
    "التحقق من العرض",
    "المطالبة بالعرض",
    "معالجة الدفع",
    "اكتمال",
]


def _build_progress(current_idx: int, error: str = "", detail: str = "") -> str:
    """Build a progress string showing all 9 steps with status."""
    lines: list[str] = []
    for i, step in enumerate(GEMINI_STEPS, 1):
        if i - 1 < current_idx:
            lines.append(f"  ✅  {i}. {step}")
        elif i - 1 == current_idx and error:
            lines.append(f"  ❌  {i}. {step}")
        elif i - 1 == current_idx:
            lines.append(f"  ⏳  {i}. {step}")
        else:
            lines.append(f"  ⬜  {i}. {step}")
    if detail:
        lines.append(f"\nℹ️ {detail}")
    if error:
        lines.append(f"\n❌ {error}")
    return "\n".join(lines)


async def _google_login_and_claim(
    gmail: str,
    gmail_password: str,
    totp_code: str,
    redirect_url: str,
    on_progress: ProgressCallback,
) -> bool:
    """Log into Google with Playwright and claim offer via redirect URL."""
    from playwright.async_api import async_playwright
    from playwright_stealth import Stealth

    _stealth_ua = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.6778.86 Safari/537.36"
    )
    stealth = Stealth(
        navigator_user_agent_override=_stealth_ua,
        navigator_vendor_override="Google Inc.",
        navigator_platform_override="Win32",
    )

    # Parse proxy from pool (rotated)
    _proxy_url = _get_random_proxy()
    _proxy_cfg = None
    if _proxy_url:
        from urllib.parse import urlparse
        _p = urlparse(_proxy_url)
        _proxy_cfg = {"server": f"{_p.scheme}://{_p.hostname}:{_p.port}"}
        if _p.username:
            _proxy_cfg["username"] = _p.username
        if _p.password:
            _proxy_cfg["password"] = _p.password
        log.info("Playwright browser using proxy: %s:%s", _p.hostname, _p.port)

    async with async_playwright() as pw:
        _launch_kwargs: Dict[str, Any] = {
            "headless": True,
            "args": [
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
                "--disable-dev-shm-usage",
                "--disable-extensions",
                "--window-size=1280,800",
            ],
        }
        if _proxy_cfg:
            _launch_kwargs["proxy"] = _proxy_cfg
        browser = await pw.chromium.launch(**_launch_kwargs)
        ctx = await browser.new_context(
            user_agent=_stealth_ua,
            viewport={"width": 1280, "height": 800},
            locale="en-US",
        )
        await stealth.apply_stealth_async(ctx)
        page = await ctx.new_page()

        try:
            # Step 5: Payment method — go to Google sign-in (with retry on timeout)
            await on_progress(_build_progress(4))
            _signin_urls = [
                "https://accounts.google.com/v3/signin/identifier?flowName=GlifWebSignIn&flowEntry=ServiceLogin",
                "https://accounts.google.com/ServiceLogin",
                "https://accounts.google.com/",
            ]
            for _attempt, _surl in enumerate(_signin_urls):
                try:
                    log.info("Sign-in attempt %d: %s", _attempt + 1, _surl)
                    await page.goto(_surl, wait_until="domcontentloaded", timeout=90000)
                    break
                except Exception as _nav_err:
                    log.warning("Sign-in nav attempt %d failed: %s", _attempt + 1, _nav_err)
                    if _attempt == len(_signin_urls) - 1:
                        raise
                    await asyncio.sleep(random.uniform(3, 6))
            await asyncio.sleep(random.uniform(2, 4))

            # Enter email
            email_input = page.locator('input[type="email"]')
            await email_input.click()
            await asyncio.sleep(random.uniform(0.3, 0.8))
            await email_input.type(gmail, delay=random.randint(40, 120))
            await asyncio.sleep(random.uniform(0.5, 1.5))
            next_btn = page.locator("#identifierNext")
            if await next_btn.count() == 0:
                next_btn = page.get_by_role("button", name="Next")
            await next_btn.click()
            await asyncio.sleep(random.uniform(3, 5))

            await on_progress(_build_progress(5))

            # Check for "couldn't find account" error after email
            email_error = page.locator("[jsname='B34EJ'], .o6cuMc, .dEOOab, .Ekjuhf")
            if await email_error.count() > 0:
                err_text = await email_error.first.text_content()
                if err_text and err_text.strip():
                    log.warning("Google email error: %s", err_text.strip())
                    await on_progress(_build_progress(4, error=f"خطأ الإيميل: {err_text.strip()}"))
                    return False

            # Step 6: Add payment — enter password
            pwd_input = page.locator('input[type="password"]:visible')
            try:
                await pwd_input.wait_for(state="visible", timeout=15000)
            except Exception:
                title = await page.title()
                page_text = await page.content()
                if "find your Google Account" in page_text or "العثور على" in page_text:
                    await on_progress(_build_progress(4, error="الإيميل غير موجود في Google"))
                    return False
                if "couldn" in title.lower() and "sign" in title.lower():
                    log.warning("Google 'Couldn't sign you in' in claim flow")
                await on_progress(_build_progress(5, error=f"فشل الوصول لصفحة كلمة المرور — {title}"))
                return False
            await pwd_input.click()
            await asyncio.sleep(random.uniform(0.3, 0.8))
            await pwd_input.type(gmail_password, delay=random.randint(30, 90))
            await asyncio.sleep(random.uniform(0.5, 1))
            pwd_next = page.locator("#passwordNext")
            if await pwd_next.count() == 0:
                pwd_next = page.get_by_role("button", name="Next")
            await pwd_next.click()
            await asyncio.sleep(random.uniform(3, 5))

            # Check for error (wrong password)
            error_el = page.locator("[jsname='B34EJ'], .o6cuMc, .dEOOab")
            if await error_el.count() > 0:
                error_text = await error_el.first.text_content()
                log.warning("Google login error: %s", error_text)
                await on_progress(_build_progress(5, error=f"خطأ تسجيل الدخول: {error_text}"))
                return False

            # Check for 2FA prompt
            await asyncio.sleep(2)
            totp_input = page.locator('input[type="tel"]:visible')
            if await totp_input.count() > 0:
                await totp_input.fill(totp_code)
                totp_next = page.get_by_role("button", name="Next")
                if await totp_next.count() > 0:
                    await totp_next.click()
                await asyncio.sleep(3)

            await on_progress(_build_progress(6))

            # Step 7-8: Check offer & Claim — navigate to redirect URL
            await on_progress(_build_progress(7))
            await page.goto(redirect_url, wait_until="domcontentloaded", timeout=90000)
            await asyncio.sleep(3)

            # Try to click any "Claim" / "Get offer" / "Continue" button
            for selector in [
                "button:has-text('Claim')",
                "button:has-text('Get')",
                "button:has-text('Continue')",
                "button:has-text('Start')",
                "a:has-text('Claim')",
                "a:has-text('Get')",
            ]:
                btn = page.locator(selector).first
                if await btn.count() > 0:
                    await btn.click()
                    await asyncio.sleep(3)
                    break

            await on_progress(_build_progress(8))

            # Step 9: Process payment
            await asyncio.sleep(2)
            # Check for any confirmation buttons
            for selector in [
                "button:has-text('Subscribe')",
                "button:has-text('Confirm')",
                "button:has-text('Accept')",
                "button:has-text('Done')",
            ]:
                btn = page.locator(selector).first
                if await btn.count() > 0:
                    await btn.click()
                    await asyncio.sleep(2)
                    break

            await on_progress(_build_progress(9))
            await asyncio.sleep(1)
            await on_progress(_build_progress(10))

            return True

        except Exception as exc:
            log.warning("Google login/claim failed: %s", exc)
            return False
        finally:
            await browser.close()


async def verify_gemini_auto(
    on_progress: ProgressCallback,
    gmail: str = "",
    gmail_password: str = "",
    totp_secret: str = "",
    user_id: int = 0,
) -> Dict[str, Any]:
    """Full auto Gemini/Google One verification with user's real Gmail.

    Args:
        totp_secret: The TOTP secret key (base32) — NOT the 6-digit code.
                     The bot generates the current code automatically.
        user_id: Telegram user ID — used to track which card was assigned.

    Steps (9):
    1. الإيميل         — Google login: enter email
    2. كلمة السر       — Google login: enter password
    3. المصادقة الثنائية — Google login: 2FA
    4. طريقة الدفع      — SheerID create verification
    5. إضافة طريقة دفع  — SheerID submit student info
    6. التحقق من العرض   — SheerID upload document
    7. المطالبة بالعرض   — claim offer via redirect
    8. معالجة الدفع      — confirm subscription (+ auto payment card)
    9. اكتمال           — done
    """
    program_id = PROGRAM_IDS["google_one"]

    first, last = _generate_name()
    uni = _weighted_choice(GOOGLE_ONE_UNIVERSITIES)
    student_email = _generate_email(first, last, uni["domain"])
    dob = _generate_student_dob()
    fingerprint = _generate_fingerprint()

    log.info("Gemini auto-verify: %s %s @ %s (gmail=%s)", first, last, uni["name"], gmail)

    # Validate inputs before launching browser
    if not gmail or "@" not in gmail:
        await on_progress(_build_progress(0, error="إيميل غير صالح"))
        return {"success": False, "error": "إيميل غير صالح"}
    if not gmail_password or len(gmail_password) < 6:
        await on_progress(_build_progress(1, error="كلمة المرور قصيرة جداً"))
        return {"success": False, "error": "كلمة المرور يجب أن تكون 6 أحرف على الأقل"}

    # Validate TOTP secret early, but generate code lazily right before use
    totp_obj = None
    if totp_secret:
        try:
            import pyotp
            clean_secret = totp_secret.replace(" ", "").strip().upper()
            totp_obj = pyotp.TOTP(clean_secret)
            totp_obj.now()  # validate the secret is valid base32
            log.info("TOTP secret validated for %s", gmail)
        except Exception as exc:
            log.warning("Failed to validate TOTP secret: %s", exc)
            await on_progress(_build_progress(2, error=f"مفتاح 2FA غير صالح: {exc}"))
            return {"success": False, "error": f"مفتاح 2FA السري غير صالح: {exc}"}

    from playwright.async_api import async_playwright
    from playwright_stealth import Stealth

    browser = None
    page = None
    pw_instance = None
    ctx_browser = None
    cdp_mode = False
    result: Dict[str, Any] = {"success": False, "error": "خطأ غير متوقع"}

    _STEALTH_UA = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.6778.86 Safari/537.36"
    )
    stealth = Stealth(
        navigator_user_agent_override=_STEALTH_UA,
        navigator_vendor_override="Google Inc.",
        navigator_platform_override="Win32",
    )

    # Parse proxy from pool (rotated across multiple servers)
    proxy_url = _get_random_proxy()
    proxy_cfg = None
    if proxy_url:
        from urllib.parse import urlparse
        p = urlparse(proxy_url)
        proxy_cfg = {"server": f"{p.scheme}://{p.hostname}:{p.port}"}
        if p.username:
            proxy_cfg["username"] = p.username
        if p.password:
            proxy_cfg["password"] = p.password
        log.info("Using proxy: %s://%s:%s", p.scheme, p.hostname, p.port)

    try:
        pw_instance = await async_playwright().start()

        # Try CDP connection to real Chrome first (avoids Google bot detection)
        try:
            browser = await pw_instance.chromium.connect_over_cdp(
                os.environ.get("CHROME_CDP_URL", "http://localhost:29229"),
                timeout=5000,
            )
            cdp_mode = True
            ctx_opts: Dict[str, Any] = {
                "user_agent": _STEALTH_UA,
                "viewport": {"width": 1280, "height": 800},
                "locale": "en-US",
            }
            if proxy_cfg:
                ctx_opts["proxy"] = proxy_cfg
            ctx_browser = await browser.new_context(**ctx_opts)
            log.info("Using CDP connection to real Chrome browser (fresh context)")
        except Exception:
            cdp_mode = False
            log.info("CDP not available, launching headless Chromium")
            launch_args = [
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
                "--disable-dev-shm-usage",
                "--disable-extensions",
                "--window-size=1280,800",
            ]
            launch_kwargs: Dict[str, Any] = {
                "headless": True,
                "args": launch_args,
            }
            if proxy_cfg:
                launch_kwargs["proxy"] = proxy_cfg
            browser = await pw_instance.chromium.launch(**launch_kwargs)
            ctx_browser = await browser.new_context(
                user_agent=_STEALTH_UA,
                viewport={"width": 1280, "height": 800},
                locale="en-US",
            )

        # Apply stealth to the context so ALL pages get stealth automatically
        await stealth.apply_stealth_async(ctx_browser)
        page = await ctx_browser.new_page()

        # Helper: enter email and click Next on current page
        async def _enter_email_on_page(p, email_text):
            email_el = p.locator('input[type="email"]')
            if await email_el.count() == 0:
                return False
            await email_el.click()
            await asyncio.sleep(random.uniform(0.3, 0.8))
            await email_el.type(email_text, delay=random.randint(50, 130))
            await asyncio.sleep(random.uniform(0.8, 1.5))
            nxt = p.locator("#identifierNext")
            if await nxt.count() == 0:
                nxt = p.get_by_role("button", name="Next")
            await nxt.click()
            await asyncio.sleep(random.uniform(4, 6))
            return True

        # Google sign-in URLs to try (in order of preference)
        _SIGNIN_URLS = [
            "https://accounts.google.com/v3/signin/identifier?flowName=GlifWebSignIn&flowEntry=ServiceLogin",
            "https://accounts.google.com/ServiceLogin",
            "https://accounts.google.com/",
        ]

        # ── Step 1: الإيميل — enter email in Google ──
        await on_progress(_build_progress(0, detail=f"تسجيل الدخول بـ {gmail}..."))

        signed_in = False
        for attempt, signin_url in enumerate(_SIGNIN_URLS):
            log.info("Google sign-in attempt %d with URL: %s", attempt + 1, signin_url)

            if attempt > 0:
                # Create fresh page for retries (clean cookies/state)
                await page.close()
                page = await ctx_browser.new_page()
                await stealth.apply_stealth_async(page)
                await asyncio.sleep(random.uniform(2, 4))

            await page.goto(signin_url, wait_until="domcontentloaded", timeout=90000)
            await asyncio.sleep(random.uniform(2, 4))

            # Check if email input is visible
            if not await _enter_email_on_page(page, gmail):
                cur_url = page.url
                title = await page.title()
                log.warning("Attempt %d: no email input. URL=%s title=%s", attempt + 1, cur_url, title)
                continue

            # Check for "Couldn't sign you in" page
            cur_title = await page.title()
            if "couldn" in cur_title.lower() and "sign" in cur_title.lower():
                log.warning("Attempt %d: 'Couldn't sign you in' (URL: %s)", attempt + 1, signin_url)
                await on_progress(_build_progress(0, detail=f"محاولة {attempt + 1}: فشلت، جاري إعادة المحاولة..."))
                continue

            # Check for email error
            email_error = page.locator("[jsname='B34EJ'], .o6cuMc, .dEOOab, .Ekjuhf")
            if await email_error.count() > 0:
                err_text = await email_error.first.text_content()
                if err_text and err_text.strip():
                    log.warning("Google email error: %s", err_text.strip())
                    await on_progress(_build_progress(0, error=f"خطأ: {err_text.strip()}"))
                    result = {"success": False, "error": f"خطأ الإيميل: {err_text.strip()}"}
                    return result

            signed_in = True
            break

        if not signed_in:
            await on_progress(_build_progress(0, error="فشل تسجيل الدخول — Google يرفض الاتصال من هذا السيرفر"))
            result = {"success": False, "error": "فشل تسجيل الدخول (Couldn't sign you in) — Google يرفض الاتصال من هذا السيرفر. جرّب بعد فترة أو من سيرفر آخر."}
            return result

        await on_progress(_build_progress(1, detail="تم قبول الإيميل، إدخال كلمة السر..."))

        # ── Step 2: كلمة السر — enter password ──
        pwd_input = page.locator('input[type="password"]:visible')
        try:
            await pwd_input.wait_for(state="visible", timeout=20000)
        except Exception:
            cur_url = page.url
            title = await page.title()
            page_text = await page.inner_text("body")
            log.warning(
                "Google pwd page not found. URL=%s title=%s body_snippet=%s",
                cur_url, title, page_text[:500],
            )

            # Handle "Couldn't sign you in" — try one more fresh attempt
            if "couldn" in title.lower() and "sign" in title.lower():
                log.info("Password step: 'Couldn't sign you in' — trying fresh page")
                await page.close()
                page = await ctx_browser.new_page()
                await stealth.apply_stealth_async(page)
                await asyncio.sleep(random.uniform(3, 5))
                alt_url = "https://accounts.google.com/v3/signin/identifier?flowName=GlifWebSignIn&flowEntry=ServiceLogin"
                await page.goto(alt_url, wait_until="domcontentloaded", timeout=90000)
                await asyncio.sleep(random.uniform(3, 5))
                if await _enter_email_on_page(page, gmail):
                    try:
                        pwd_input = page.locator('input[type="password"]:visible')
                        await pwd_input.wait_for(state="visible", timeout=15000)
                    except Exception:
                        retry_title = await page.title()
                        detail = f"الصفحة: {retry_title} | الرابط: {page.url[:80]}"
                        await on_progress(_build_progress(1, error="فشل الوصول لصفحة كلمة المرور بعد إعادة المحاولة", detail=detail))
                        result = {"success": False, "error": f"فشل الوصول لصفحة كلمة المرور — {retry_title}"}
                        return result
                else:
                    await on_progress(_build_progress(0, error="فشل إعادة المحاولة"))
                    result = {"success": False, "error": f"فشل الوصول لصفحة كلمة المرور — {title}"}
                    return result
            else:
                # Check specific Google pages
                if "find your Google Account" in page_text or "العثور على" in page_text:
                    await on_progress(_build_progress(0, error="الإيميل غير موجود في Google"))
                    result = {"success": False, "error": "الإيميل غير موجود في Google"}
                    return result
                if "captcha" in page_text.lower() or "robot" in page_text.lower():
                    await on_progress(_build_progress(1, error="Google يطلب CAPTCHA — جرّب لاحقاً"))
                    result = {"success": False, "error": "Google يطلب CAPTCHA — جرّب بعد فترة"}
                    return result
                if "verify" in cur_url.lower() or "challenge" in cur_url.lower():
                    await on_progress(_build_progress(1, error="Google يطلب تحقق أمني إضافي"))
                    result = {"success": False, "error": f"Google يطلب تحقق أمني إضافي ({title})"}
                    return result

                # Try alternative password selectors
                alt_pwd = page.locator('input[name="Passwd"], input[name="password"], input[aria-label="Password"]')
                if await alt_pwd.count() > 0:
                    pwd_input = alt_pwd.first
                    log.info("Found password input via alternative selector")
                else:
                    detail = f"الصفحة: {title} | الرابط: {cur_url[:80]}"
                    await on_progress(_build_progress(1, error="فشل الوصول لصفحة كلمة المرور", detail=detail))
                    result = {"success": False, "error": f"فشل الوصول لصفحة كلمة المرور — {title}"}
                    return result

        await pwd_input.click()
        await asyncio.sleep(random.uniform(0.3, 0.8))
        await pwd_input.type(gmail_password, delay=random.randint(30, 90))
        await asyncio.sleep(random.uniform(0.5, 1.5))
        pwd_next = page.locator("#passwordNext")
        if await pwd_next.count() == 0:
            pwd_next = page.get_by_role("button", name="Next")
        await pwd_next.click()
        await asyncio.sleep(random.uniform(4, 6))

        # Check for wrong password error
        pwd_error = page.locator("[jsname='B34EJ'], .o6cuMc, .dEOOab")
        if await pwd_error.count() > 0:
            err_text = await pwd_error.first.text_content()
            if err_text and err_text.strip() and ("password" in err_text.lower() or "كلمة" in err_text):
                log.warning("Google password error: %s", err_text.strip())
                await on_progress(_build_progress(1, error=f"خطأ: {err_text.strip()}"))
                result = {"success": False, "error": f"كلمة المرور خاطئة: {err_text.strip()}"}
                return result

        # Check page after password entry
        cur_url = page.url
        if "signin/rejected" in cur_url.lower():
            title = await page.title()
            log.warning("Google rejected sign-in: URL=%s", cur_url)
            await on_progress(_build_progress(1, error=f"Google رفض تسجيل الدخول: {title}"))
            result = {"success": False, "error": f"Google رفض تسجيل الدخول: {title}"}
            return result

        await on_progress(_build_progress(2, detail="تم قبول كلمة السر، فحص المصادقة الثنائية..."))

        # ── Step 3: المصادقة الثنائية — handle 2FA ──
        await asyncio.sleep(2)

        # Google 2FA comes in many forms; try to detect and handle each
        is_2fa_page = "challenge" in page.url.lower()

        # Look for TOTP / code input (multiple selectors for different Google UIs)
        totp_input = page.locator(
            'input[type="tel"]:visible, '
            'input[id="totpPin"]:visible, '
            'input[name="totpPin"]:visible, '
            'input[aria-label*="code"i]:visible, '
            'input[aria-label*="رمز"]:visible'
        )

        if await totp_input.count() > 0:
            if totp_obj:
                totp_code = totp_obj.now()  # generate fresh code right before use
                await totp_input.first.fill(totp_code)
                # Find and click Next button
                totp_next = page.locator("#totpNext")
                if await totp_next.count() == 0:
                    totp_next = page.get_by_role("button", name="Next")
                if await totp_next.count() > 0:
                    await totp_next.click()
                await asyncio.sleep(4)

                # Check for 2FA error
                totp_error = page.locator("[jsname='B34EJ'], .o6cuMc, .dEOOab, .OyEIQ")
                if await totp_error.count() > 0:
                    err_text = await totp_error.first.text_content()
                    if err_text and err_text.strip():
                        log.warning("Google 2FA error: %s", err_text.strip())
                        await on_progress(_build_progress(2, error=f"رمز 2FA خاطئ: {err_text.strip()}"))
                        result = {"success": False, "error": f"رمز 2FA خاطئ: {err_text.strip()}"}
                        return result

                await on_progress(_build_progress(3, detail="تم تسجيل الدخول بنجاح!"))
            else:
                await on_progress(_build_progress(2, error="الحساب يتطلب 2FA — أعد المحاولة وأرسل مفتاح 2FA السري"))
                result = {"success": False, "error": "الحساب يتطلب مفتاح المصادقة الثنائية السري (2FA Secret Key)"}
                return result
        elif is_2fa_page:
            # 2FA page but no TOTP input — phone prompt, security key, etc.
            title = await page.title()
            page_text = await page.inner_text("body")
            log.warning("Google 2FA page without TOTP input. URL=%s title=%s body=%s", page.url, title, page_text[:300])
            await on_progress(_build_progress(2, detail="جاري البحث عن طريقة Authenticator..."))

            # Always try "Try another way" first to switch to Authenticator
            try:
                try_another = page.locator(
                    "button:has-text('Try another way'), "
                    "a:has-text('Try another way'), "
                    "button:has-text('طريقة أخرى'), "
                    "a:has-text('طريقة أخرى'), "
                    "button:has-text('try another way')"
                )
                if await try_another.count() > 0:
                    log.info("Clicking 'Try another way'")
                    await try_another.first.click()
                    # Wait for page to settle after click
                    try:
                        await page.wait_for_load_state("domcontentloaded", timeout=10000)
                    except Exception:
                        pass
                    await asyncio.sleep(2)

                    # Log what options are available (with short timeout)
                    try:
                        options_text = await page.inner_text("body", timeout=5000)
                        log.info("2FA options page: %s", options_text[:500])
                    except Exception:
                        options_text = ""
                        log.warning("Could not read 2FA options page text")

                    # Log all available 2FA options for debugging
                    try:
                        all_2fa = await page.locator("li").all_text_contents()
                        log.info("2FA options after 'Try another way': %s", [o.strip()[:60] for o in all_2fa if o.strip()][:8])
                    except Exception:
                        pass

                    # Look for "Google Authenticator" or TOTP-specific option
                    auth_option = page.locator(
                        "li:has-text('Authenticator'), "
                        "li:has-text('Google Authenticator'), "
                        "div[role='link']:has-text('Authenticator'), "
                        "div[data-challengetype='6'], "
                        "li:has-text('authenticator app'), "
                        "li:has-text('Enter a code from')"
                    )
                    if await auth_option.count() > 0:
                        auth_text = await auth_option.first.text_content()
                        log.info("Selecting authenticator option: '%s'", auth_text)
                        await auth_option.first.click()
                        try:
                            await page.wait_for_load_state("domcontentloaded", timeout=10000)
                        except Exception:
                            pass
                        await asyncio.sleep(2)

                        # Now look for TOTP input
                        totp_input2 = page.locator(
                            'input[type="tel"]:visible, '
                            'input[id="totpPin"]:visible, '
                            'input[name="totpPin"]:visible'
                        )
                        if await totp_input2.count() > 0 and totp_obj:
                            totp_code2 = totp_obj.now()
                            log.info("Entering TOTP code via alternate path")
                            await totp_input2.first.fill(totp_code2)
                            totp_next2 = page.locator("#totpNext")
                            if await totp_next2.count() == 0:
                                totp_next2 = page.get_by_role("button", name="Next")
                            if await totp_next2.count() > 0:
                                await totp_next2.click()
                            await asyncio.sleep(4)

                            # Check for 2FA error after submission
                            totp_err = page.locator("[jsname='B34EJ'], .o6cuMc, .dEOOab, .OyEIQ")
                            if await totp_err.count() > 0:
                                err_text = await totp_err.first.text_content()
                                if err_text and err_text.strip():
                                    log.warning("Google 2FA error (alt): %s", err_text.strip())
                                    await on_progress(_build_progress(2, error=f"رمز 2FA خاطئ: {err_text.strip()}"))
                                    result = {"success": False, "error": f"رمز 2FA خاطئ: {err_text.strip()}"}
                                    return result

                            await on_progress(_build_progress(3, detail="تم تسجيل الدخول بنجاح!"))
                        elif totp_obj:
                            await on_progress(_build_progress(2, error="لم يتم العثور على حقل إدخال رمز 2FA"))
                            result = {"success": False, "error": "لم يتم العثور على حقل إدخال رمز 2FA"}
                            return result
                        else:
                            await on_progress(_build_progress(2, error="الحساب يتطلب 2FA — أرسل مفتاح 2FA السري"))
                            result = {"success": False, "error": "الحساب يتطلب مفتاح المصادقة الثنائية السري (2FA Secret Key)"}
                            return result
                    else:
                        # No authenticator option found
                        try:
                            all_options = await page.locator("li").all_text_contents()
                            log.warning("No authenticator option. Available: %s", all_options[:5])
                        except Exception:
                            log.warning("No authenticator option and couldn't list alternatives")
                        await on_progress(_build_progress(2, error="Google Authenticator غير مفعّل على هذا الحساب"))
                        result = {"success": False, "error": "Google Authenticator غير مفعّل — فعّله من إعدادات الحساب أولاً"}
                        return result
                else:
                    # No "Try another way" — we may already be on the selection page
                    log.info("No 'Try another way' button — checking if already on selection page")
                    # Log all available 2FA options for debugging
                    try:
                        all_2fa = await page.locator("li").all_text_contents()
                        log.info("2FA options on selection page: %s", [o.strip()[:60] for o in all_2fa if o.strip()][:8])
                    except Exception:
                        pass

                    auth_option_direct = page.locator(
                        "li:has-text('Authenticator'), "
                        "li:has-text('Google Authenticator'), "
                        "div[role='link']:has-text('Authenticator'), "
                        "div[data-challengetype='6'], "
                        "li:has-text('authenticator app'), "
                        "li:has-text('Enter a code from')"
                    )
                    if await auth_option_direct.count() > 0:
                        auth_text = await auth_option_direct.first.text_content()
                        log.info("Found authenticator on selection page: '%s'", auth_text)
                        await auth_option_direct.first.click()
                        try:
                            await page.wait_for_load_state("domcontentloaded", timeout=10000)
                        except Exception:
                            pass
                        await asyncio.sleep(2)

                        # Now look for TOTP input
                        totp_input3 = page.locator(
                            'input[type="tel"]:visible, '
                            'input[id="totpPin"]:visible, '
                            'input[name="totpPin"]:visible'
                        )
                        if await totp_input3.count() > 0 and totp_obj:
                            totp_code3 = totp_obj.now()
                            log.info("Entering TOTP code via selection page path")
                            await totp_input3.first.fill(totp_code3)
                            totp_next3 = page.locator("#totpNext")
                            if await totp_next3.count() == 0:
                                totp_next3 = page.get_by_role("button", name="Next")
                            if await totp_next3.count() > 0:
                                await totp_next3.click()
                            await asyncio.sleep(4)

                            totp_err3 = page.locator("[jsname='B34EJ'], .o6cuMc, .dEOOab, .OyEIQ")
                            if await totp_err3.count() > 0:
                                err_text = await totp_err3.first.text_content()
                                if err_text and err_text.strip():
                                    log.warning("Google 2FA error (selection): %s", err_text.strip())
                                    await on_progress(_build_progress(2, error=f"رمز 2FA خاطئ: {err_text.strip()}"))
                                    result = {"success": False, "error": f"رمز 2FA خاطئ: {err_text.strip()}"}
                                    return result

                            await on_progress(_build_progress(3, detail="تم تسجيل الدخول بنجاح!"))
                        elif totp_obj:
                            await on_progress(_build_progress(2, error="لم يتم العثور على حقل إدخال رمز 2FA"))
                            result = {"success": False, "error": "لم يتم العثور على حقل إدخال رمز 2FA"}
                            return result
                        else:
                            await on_progress(_build_progress(2, error="الحساب يتطلب 2FA — أرسل مفتاح 2FA السري"))
                            result = {"success": False, "error": "الحساب يتطلب مفتاح المصادقة الثنائية السري (2FA Secret Key)"}
                            return result
                    else:
                        log.warning("No 'Try another way' and no authenticator option on page")
                        try:
                            all_opts = await page.locator("li").all_text_contents()
                            log.warning("Available 2FA options: %s", all_opts[:5])
                        except Exception:
                            pass
                        await on_progress(_build_progress(2, error="Google Authenticator غير مفعّل على هذا الحساب"))
                        result = {"success": False, "error": "Google Authenticator غير مفعّل — فعّله من إعدادات الحساب أولاً"}
                        return result
            except Exception as taw_exc:
                log.warning("Error in 'Try another way' flow: %s", taw_exc)
                await on_progress(_build_progress(2, error=f"خطأ في التحول لـ Authenticator: {taw_exc}"))
                result = {"success": False, "error": f"فشل التحول لـ Google Authenticator: {taw_exc}"}
                return result
        else:
            await on_progress(_build_progress(3, detail="تم تسجيل الدخول بنجاح! (بدون 2FA)"))

        log.info("Google login succeeded for %s", gmail)

        # ── Step 4: طريقة الدفع — SheerID create verification ──
        await on_progress(_build_progress(3, detail="جاري إنشاء التحقق في SheerID..."))

        # Use proxy for SheerID API calls too (avoids fraud detection)
        _api_proxy = _get_random_proxy()
        log.info("Using proxy for SheerID API: %s", _api_proxy[:30] + "..." if _api_proxy else "none")
        async with httpx.AsyncClient(timeout=30, proxy=_api_proxy) as client:
            create_data, create_status = await _api_request(
                client, "POST",
                "/verification",
                {"programId": program_id},
            )
            log.info("SheerID create: status=%s data=%s", create_status, str(create_data)[:300])
            if create_status not in (200, 201) or not create_data.get("verificationId"):
                err_msg = f"فشل إنشاء التحقق: HTTP {create_status}"
                log.error("SheerID create failed: %s %s", create_status, create_data)
                await on_progress(_build_progress(3, error=err_msg))
                result = {"success": False, "error": err_msg}
                return result

            vid = create_data["verificationId"]
            log.info("Gemini auto: created verification %s", vid)
            await on_progress(_build_progress(4, detail=f"تم إنشاء التحقق ({vid[:8]}...)، إرسال بيانات الطالب..."))

            # ── Step 5: إضافة طريقة دفع — submit student info ──
            referer = f"{SHEERID_BASE}/verify/{program_id}/?verificationId={vid}"
            body = {
                "firstName": first,
                "lastName": last,
                "birthDate": dob,
                "email": student_email,
                "phoneNumber": "",
                "organization": {"id": uni["id"], "idExtended": str(uni["id"]), "name": uni["name"]},
                "deviceFingerprintHash": fingerprint,
                "locale": "en-US",
                "metadata": {
                    "marketConsentValue": False,
                    "verificationId": vid,
                    "refererUrl": referer,
                    "flags": '{"collect-info-step-email-first":"default","doc-upload-considerations":"default","doc-upload-may24":"default","doc-upload-redesign-use-legacy-message-keys":false,"docUpload-assertion-checklist":"default","font-size":"default","include-cvec-field-france-student":"not-labeled-optional"}',
                    "submissionOptIn": (
                        "By submitting the personal information above, I acknowledge that my "
                        "personal information is being collected under the privacy policy of the "
                        "business from which I am seeking a discount"
                    ),
                },
            }

            data, status = await _api_request(
                client, "POST",
                f"/verification/{vid}/step/collectStudentPersonalInfo",
                body,
            )
            log.info("SheerID student info: status=%s step=%s", status, data.get("currentStep"))
            if status != 200:
                err_msg = f"فشل إرسال بيانات الطالب: HTTP {status}"
                log.error("SheerID student info failed: %s %s", status, str(data)[:500])
                await on_progress(_build_progress(4, error=err_msg))
                result = {"success": False, "error": err_msg}
                return result
            if data.get("currentStep") == "error":
                err_msg = f"خطأ SheerID: {data.get('errorIds', [])}"
                log.error("SheerID student info error: %s", data)
                await on_progress(_build_progress(4, error=err_msg))
                result = {"success": False, "error": err_msg}
                return result

            await on_progress(_build_progress(5, detail="تم إرسال البيانات، رفع المستندات..."))

            # ── Step 6: التحقق من العرض — skip SSO + upload document ──
            step = data.get("currentStep", "")
            log.info("SheerID after student info: step=%s", step)
            if step in ("sso", "collectStudentPersonalInfo"):
                sso_data, sso_status = await _api_request(client, "DELETE", f"/verification/{vid}/step/sso")
                log.info("SheerID skip SSO: status=%s", sso_status)

            # Generate document: transcript 70% of the time (higher success), ID card 30%
            if random.random() < 0.7:
                doc = _generate_transcript_image(first, last, uni["name"], dob)
                doc_filename = "transcript.png"
                log.info("Using academic transcript document")
            else:
                doc = _generate_student_id_image(first, last, uni["name"])
                doc_filename = "student_card.png"
                log.info("Using student ID card document")

            upload_body = {"files": [{"fileName": doc_filename, "mimeType": "image/png", "fileSize": len(doc)}]}
            data, status = await _api_request(client, "POST", f"/verification/{vid}/step/docUpload", upload_body)
            log.info("SheerID docUpload: status=%s docs=%s", status, bool(data.get("documents")))
            if not data.get("documents"):
                err_msg = f"فشل الحصول على رابط الرفع (HTTP {status})"
                log.error("SheerID docUpload failed: %s", str(data)[:500])
                await on_progress(_build_progress(5, error=err_msg))
                result = {"success": False, "error": err_msg}
                return result

            upload_url = data["documents"][0].get("uploadUrl")
            if not upload_url or not await _upload_s3(client, upload_url, doc):
                err_msg = "فشل رفع المستند إلى S3"
                await on_progress(_build_progress(5, error=err_msg))
                result = {"success": False, "error": err_msg}
                return result

            log.info("SheerID doc uploaded to S3 successfully")
            data, complete_status = await _api_request(client, "POST", f"/verification/{vid}/step/completeDocUpload")
            final_step = data.get("currentStep", "unknown")
            redirect_url = data.get("redirectUrl", "")
            log.info(
                "SheerID completeDocUpload: status=%s step=%s redirect=%s",
                complete_status, final_step, redirect_url[:80] if redirect_url else "none",
            )

            await on_progress(_build_progress(6, detail=f"حالة التحقق: {final_step}"))

            # Check if SheerID verification was actually approved
            if final_step == "success" and redirect_url:
                await on_progress(_build_progress(6, detail="تم التحقق بنجاح! المطالبة بالعرض..."))
            elif final_step in ("docReview", "pending"):
                # Poll SheerID until verification is approved or rejected (max 5 minutes)
                await on_progress(_build_progress(6, detail=f"التحقق قيد المراجعة ({final_step})... انتظار الموافقة"))
                max_polls = 30
                poll_interval = 10
                for poll_i in range(max_polls):
                    await asyncio.sleep(poll_interval)
                    poll_data, poll_status = await _api_request(client, "GET", f"/verification/{vid}")
                    poll_step = poll_data.get("currentStep", "unknown")
                    poll_redirect = poll_data.get("redirectUrl", "")
                    log.info("SheerID poll %d/%d: step=%s redirect=%s", poll_i + 1, max_polls, poll_step, bool(poll_redirect))

                    if poll_step == "success" and poll_redirect:
                        final_step = poll_step
                        redirect_url = poll_redirect
                        await on_progress(_build_progress(6, detail="تم التحقق بنجاح! المطالبة بالعرض..."))
                        break
                    elif poll_step == "error":
                        err_ids = poll_data.get("errorIds", [])
                        err_msg = f"SheerID رفض التحقق: {err_ids}"
                        await on_progress(_build_progress(6, error=err_msg))
                        result = {"success": False, "error": err_msg}
                        return result
                    else:
                        remaining = (max_polls - poll_i - 1) * poll_interval
                        await on_progress(_build_progress(6, detail=f"قيد المراجعة... ({remaining}ث متبقي)"))
                else:
                    # Timed out waiting for approval — return failure so credit is refunded
                    await on_progress(_build_progress(6, error="انتهت مهلة الانتظار — التحقق لا زال قيد المراجعة"))
                    result = {"success": False, "error": f"SheerID لم يوافق خلال 5 دقائق (الحالة: {final_step}) — جرّب مرة أخرى"}
                    return result
            elif final_step == "error":
                err_ids = data.get("errorIds", [])
                err_msg = f"SheerID رفض التحقق: {err_ids}"
                await on_progress(_build_progress(6, error=err_msg))
                result = {"success": False, "error": err_msg}
                return result

        # ── Step 7: المطالبة بالعرض — claim via redirect ──
        if redirect_url and page:
            try:
                log.info("Navigating to redirect URL: %s", redirect_url)
                await page.goto(redirect_url, wait_until="domcontentloaded", timeout=90000)
                await asyncio.sleep(3)

                # Log what Google shows at the redirect URL
                claim_url = page.url
                claim_title = await page.title()
                claim_text = await page.inner_text("body")
                log.info(
                    "Redirect page: URL=%s title=%s body_preview=%s",
                    claim_url, claim_title, claim_text[:500],
                )
                await page.screenshot(path="/tmp/gemini_claim_page.png")

                await on_progress(_build_progress(7, detail=f"صفحة العرض: {claim_title}"))

                # Try to find and click claim/redeem buttons
                claimed = False
                for selector in [
                    "button:has-text('Claim')", "button:has-text('Redeem')",
                    "button:has-text('Get')", "button:has-text('Continue')",
                    "button:has-text('Start')", "button:has-text('Activate')",
                    "a:has-text('Claim')", "a:has-text('Redeem')",
                    "a:has-text('Get started')", "a:has-text('Activate')",
                ]:
                    btn = page.locator(selector).first
                    if await btn.count() > 0:
                        btn_text = await btn.text_content()
                        log.info("Clicking claim button: '%s'", btn_text)
                        await btn.click()
                        await asyncio.sleep(4)
                        claimed = True
                        break

                if not claimed:
                    log.warning("No claim button found on redirect page")

                after_claim_url = page.url
                after_claim_title = await page.title()
                log.info("After claim click: URL=%s title=%s", after_claim_url, after_claim_title)

                await on_progress(_build_progress(7, detail=f"تم المطالبة ({after_claim_title})، معالجة الدفع..."))

                # ── Step 8: معالجة الدفع — auto-fill payment card if needed ──
                await asyncio.sleep(2)

                # Check if Google asks for a payment method (card form)
                card_input = page.locator(
                    'input[name="cardnumber"], input[autocomplete="cc-number"], '
                    'input[id*="card"], input[aria-label*="Card number"], '
                    'input[aria-label*="رقم البطاقة"]'
                )
                if await card_input.count() > 0:
                    log.info("Payment card form detected — attempting auto-fill")
                    from bot.db.models import get_next_card, mark_card_used
                    payment_card = await get_next_card()
                    if payment_card:
                        try:
                            await on_progress(_build_progress(8, detail="إدخال بطاقة الدفع..."))
                            # Fill card number
                            await card_input.first.click()
                            await asyncio.sleep(random.uniform(0.3, 0.6))
                            await card_input.first.type(payment_card["card_number"], delay=random.randint(30, 80))
                            await asyncio.sleep(random.uniform(0.3, 0.6))

                            # Fill card holder name
                            name_input = page.locator(
                                'input[name="ccname"], input[autocomplete="cc-name"], '
                                'input[aria-label*="Name on card"], input[aria-label*="اسم"]'
                            )
                            if await name_input.count() > 0:
                                await name_input.first.click()
                                await asyncio.sleep(random.uniform(0.2, 0.4))
                                await name_input.first.type(payment_card["card_holder"], delay=random.randint(30, 80))

                            # Fill expiry
                            expiry_input = page.locator(
                                'input[name="ccexp"], input[autocomplete="cc-exp"], '
                                'input[aria-label*="Expir"], input[aria-label*="انتهاء"]'
                            )
                            if await expiry_input.count() > 0:
                                exp_str = f"{payment_card['expiry_month']:02d}/{payment_card['expiry_year'] % 100:02d}"
                                await expiry_input.first.click()
                                await asyncio.sleep(random.uniform(0.2, 0.4))
                                await expiry_input.first.type(exp_str, delay=random.randint(30, 80))
                            else:
                                # Separate month/year fields
                                month_input = page.locator('input[autocomplete="cc-exp-month"], select[autocomplete="cc-exp-month"]')
                                year_input = page.locator('input[autocomplete="cc-exp-year"], select[autocomplete="cc-exp-year"]')
                                if await month_input.count() > 0:
                                    await month_input.first.fill(f"{payment_card['expiry_month']:02d}")
                                if await year_input.count() > 0:
                                    await year_input.first.fill(str(payment_card['expiry_year']))

                            # Fill CVV
                            cvv_input = page.locator(
                                'input[name="cvc"], input[autocomplete="cc-csc"], '
                                'input[aria-label*="CVC"], input[aria-label*="CVV"], '
                                'input[aria-label*="Security code"]'
                            )
                            if await cvv_input.count() > 0:
                                await cvv_input.first.click()
                                await asyncio.sleep(random.uniform(0.2, 0.4))
                                await cvv_input.first.type(payment_card["cvv"], delay=random.randint(30, 80))

                            await asyncio.sleep(random.uniform(0.5, 1))

                            # Mark card as used
                            if user_id:
                                await mark_card_used(payment_card["id"], user_id)
                            log.info("Payment card #%d filled successfully", payment_card["id"])
                        except Exception as card_exc:
                            log.warning("Failed to fill payment card: %s", card_exc)
                    else:
                        log.warning("No available payment cards in database")
                        await on_progress(_build_progress(8, detail="⚠️ لا توجد بطاقات متاحة — أضف بطاقة عبر /addcard"))

                # Click confirm/subscribe buttons
                for selector in [
                    "button:has-text('Subscribe')", "button:has-text('Confirm')",
                    "button:has-text('Accept')", "button:has-text('Done')",
                    "button:has-text('Start trial')", "button:has-text('Agree')",
                    "button:has-text('Buy')", "button:has-text('Submit')",
                ]:
                    btn = page.locator(selector).first
                    if await btn.count() > 0:
                        btn_text = await btn.text_content()
                        log.info("Clicking confirm button: '%s'", btn_text)
                        await btn.click()
                        await asyncio.sleep(3)
                        break

                final_url = page.url
                final_title = await page.title()
                log.info("Final state: URL=%s title=%s", final_url, final_title)

            except Exception as exc:
                log.warning("Google claim redirect failed: %s", exc)
                await on_progress(_build_progress(7, error=f"خطأ في المطالبة: {exc}"))
        elif not redirect_url:
            log.warning("No redirect URL from SheerID (step=%s)", final_step)
            await on_progress(_build_progress(7, detail=f"لا يوجد رابط عرض — حالة التحقق: {final_step}"))
        else:
            await on_progress(_build_progress(7))

        await on_progress(_build_progress(8))

        # ── Step 9: اكتمال ──
        await asyncio.sleep(0.5)

        # Only report success if SheerID actually approved AND we had a redirect URL
        if final_step == "success" and redirect_url:
            await on_progress(_build_progress(9))
            result = {
                "success": True,
                "student": f"{first} {last}",
                "email": student_email,
                "gmail": gmail,
                "school": uni["name"],
                "step": final_step,
                "redirect": redirect_url,
                "verificationId": vid,
            }
        else:
            await on_progress(_build_progress(8, error=f"لم يكتمل التحقق — حالة SheerID: {final_step}"))
            result = {
                "success": False,
                "error": f"SheerID لم يوافق على التحقق (الحالة: {final_step})",
                "student": f"{first} {last}",
                "email": student_email,
                "gmail": gmail,
                "school": uni["name"],
                "step": final_step,
                "verificationId": vid,
            }
        return result

    except Exception as exc:
        log.warning("Gemini auto-verify failed: %s", exc)
        await on_progress(_build_progress(0, error=f"فشل: {exc}"))
        result = {"success": False, "error": f"فشل: {exc}"}
        return result

    finally:
        # In CDP mode, close the incognito context (not the shared browser)
        if cdp_mode and ctx_browser:
            try:
                await ctx_browser.close()
            except Exception:
                pass
        elif browser:
            try:
                await browser.close()
            except Exception:
                pass
        if pw_instance:
            try:
                await pw_instance.stop()
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------
VERIFY_ROUTER: Dict[str, Any] = {
    "spotify": verify_student,
    "youtube": verify_student,
    "google_one": verify_student,
    "perplexity": verify_student,
    "boltnew": verify_teacher,
    "k12": verify_k12,
    "veterans": verify_veterans,
}


async def run_verification(service_key: str, url: str) -> Dict[str, Any]:
    """Entry point — dispatches to the correct verification function."""
    func = VERIFY_ROUTER.get(service_key)
    if not func:
        return {"success": False, "error": f"خدمة غير مدعومة: {service_key}"}
    if func in (verify_student,):
        return await func(url, service_key)
    return await func(url)
