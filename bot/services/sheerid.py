"""SheerID async verification engine for all supported services."""
from __future__ import annotations

import asyncio
import hashlib
import logging
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
    components = [
        str(int(time.time() * 1000)),
        str(random.random()),
        random.choice(["1920x1080", "1366x768", "1536x864", "1440x900"]),
        str(random.choice([-8, -7, -6, -5, -4, 0, 1, 2, 3, 8, 9])),
        random.choice(["en-US", "en-GB", "en-CA"]),
        random.choice(["Win32", "MacIntel", "Linux x86_64"]),
        str(random.randint(1, 16)),
        str(random.randint(2, 32)),
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

    async with httpx.AsyncClient(timeout=30) as client:
        err = await _check_link(client, vid)
        if err:
            return {"success": False, "error": err}

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

    async with httpx.AsyncClient(timeout=30) as client:
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

    async with httpx.AsyncClient(timeout=30) as client:
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

    async with httpx.AsyncClient(timeout=30) as client:
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

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True, args=["--no-sandbox"])
        ctx = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        )
        page = await ctx.new_page()

        try:
            # Step 5: Payment method — go to Google sign-in
            await on_progress(_build_progress(4))
            await page.goto("https://accounts.google.com/signin", wait_until="networkidle", timeout=30000)
            await asyncio.sleep(1)

            # Enter email
            email_input = page.locator('input[type="email"]')
            await email_input.fill(gmail)
            next_btn = page.locator("#identifierNext")
            if await next_btn.count() == 0:
                next_btn = page.get_by_role("button", name="Next")
            await next_btn.click()
            await asyncio.sleep(3)

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
                # Check if there's an error message
                page_text = await page.content()
                if "find your Google Account" in page_text or "العثور على" in page_text:
                    await on_progress(_build_progress(4, error="الإيميل غير موجود في Google"))
                    return False
                await on_progress(_build_progress(5, error="فشل الوصول لصفحة كلمة المرور"))
                return False
            await pwd_input.fill(gmail_password)
            pwd_next = page.locator("#passwordNext")
            if await pwd_next.count() == 0:
                pwd_next = page.get_by_role("button", name="Next")
            await pwd_next.click()
            await asyncio.sleep(3)

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
            await page.goto(redirect_url, wait_until="networkidle", timeout=30000)
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
    totp_code: str = "",
) -> Dict[str, Any]:
    """Full auto Gemini/Google One verification with user's real Gmail.

    Steps (9):
    1. الإيميل         — Google login: enter email
    2. كلمة السر       — Google login: enter password
    3. المصادقة الثنائية — Google login: 2FA
    4. طريقة الدفع      — SheerID create verification
    5. إضافة طريقة دفع  — SheerID submit student info
    6. التحقق من العرض   — SheerID upload document
    7. المطالبة بالعرض   — claim offer via redirect
    8. معالجة الدفع      — confirm subscription
    9. اكتمال           — done
    """
    program_id = PROGRAM_IDS["google_one"]

    first, last = _generate_name()
    uni = _weighted_choice(STUDENT_UNIVERSITIES)
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

    from playwright.async_api import async_playwright

    browser = None
    page = None
    pw_instance = None
    result: Dict[str, Any] = {"success": False, "error": "خطأ غير متوقع"}

    try:
        pw_instance = await async_playwright().start()
        browser = await pw_instance.chromium.launch(headless=True, args=["--no-sandbox"])
        ctx_browser = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        )
        page = await ctx_browser.new_page()

        # ── Step 1: الإيميل — enter email in Google ──
        await on_progress(_build_progress(0, detail=f"تسجيل الدخول بـ {gmail}..."))
        await page.goto("https://accounts.google.com/signin", wait_until="networkidle", timeout=30000)
        await asyncio.sleep(1)

        email_input = page.locator('input[type="email"]')
        await email_input.fill(gmail)
        next_btn = page.locator("#identifierNext")
        if await next_btn.count() == 0:
            next_btn = page.get_by_role("button", name="Next")
        await next_btn.click()
        await asyncio.sleep(3)

        # Check for email error
        email_error = page.locator("[jsname='B34EJ'], .o6cuMc, .dEOOab, .Ekjuhf")
        if await email_error.count() > 0:
            err_text = await email_error.first.text_content()
            if err_text and err_text.strip():
                log.warning("Google email error: %s", err_text.strip())
                await on_progress(_build_progress(0, error=f"خطأ: {err_text.strip()}"))
                result = {"success": False, "error": f"خطأ الإيميل: {err_text.strip()}"}
                return result

        await on_progress(_build_progress(1, detail="تم قبول الإيميل، إدخال كلمة السر..."))

        # ── Step 2: كلمة السر — enter password ──
        pwd_input = page.locator('input[type="password"]:visible')
        try:
            await pwd_input.wait_for(state="visible", timeout=15000)
        except Exception:
            page_text = await page.content()
            if "find your Google Account" in page_text or "العثور على" in page_text:
                await on_progress(_build_progress(0, error="الإيميل غير موجود في Google"))
                result = {"success": False, "error": "الإيميل غير موجود في Google"}
                return result
            await on_progress(_build_progress(1, error="فشل الوصول لصفحة كلمة المرور"))
            result = {"success": False, "error": "فشل الوصول لصفحة كلمة المرور"}
            return result

        await pwd_input.fill(gmail_password)
        pwd_next = page.locator("#passwordNext")
        if await pwd_next.count() == 0:
            pwd_next = page.get_by_role("button", name="Next")
        await pwd_next.click()
        await asyncio.sleep(3)

        # Check for wrong password error
        pwd_error = page.locator("[jsname='B34EJ'], .o6cuMc, .dEOOab")
        if await pwd_error.count() > 0:
            err_text = await pwd_error.first.text_content()
            if err_text and err_text.strip() and ("password" in err_text.lower() or "كلمة" in err_text):
                log.warning("Google password error: %s", err_text.strip())
                await on_progress(_build_progress(1, error=f"خطأ: {err_text.strip()}"))
                result = {"success": False, "error": f"كلمة المرور خاطئة: {err_text.strip()}"}
                return result

        await on_progress(_build_progress(2, detail="تم قبول كلمة السر، فحص المصادقة الثنائية..."))

        # ── Step 3: المصادقة الثنائية — handle 2FA ──
        await asyncio.sleep(2)
        totp_input = page.locator('input[type="tel"]:visible')
        if await totp_input.count() > 0 and totp_code and totp_code != "000000":
            await totp_input.fill(totp_code)
            totp_next = page.get_by_role("button", name="Next")
            if await totp_next.count() > 0:
                await totp_next.click()
            await asyncio.sleep(3)
            await on_progress(_build_progress(3, detail="تم تسجيل الدخول بنجاح!"))
        else:
            await on_progress(_build_progress(3, detail="تم تسجيل الدخول بنجاح! (بدون 2FA)"))

        log.info("Google login succeeded for %s", gmail)

        # ── Step 4: طريقة الدفع — SheerID create verification ──
        await on_progress(_build_progress(3, detail="جاري إنشاء التحقق..."))
        async with httpx.AsyncClient(timeout=30) as client:
            create_data, create_status = await _api_request(
                client, "POST",
                "/verification",
                {"programId": program_id},
            )
            if create_status not in (200, 201) or not create_data.get("verificationId"):
                err_msg = "فشل إنشاء التحقق التلقائي"
                await on_progress(_build_progress(3, error=err_msg))
                result = {"success": False, "error": err_msg}
                return result

            vid = create_data["verificationId"]
            log.info("Gemini auto: created verification %s", vid)
            await on_progress(_build_progress(4, detail="تم إنشاء التحقق، إرسال البيانات..."))

            # ── Step 5: إضافة طريقة دفع — submit student info ──
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
                    "refererUrl": f"{SHEERID_BASE}/verify/{program_id}/?verificationId={vid}",
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
            if status != 200:
                err_msg = f"فشل إرسال بيانات الطالب: HTTP {status}"
                await on_progress(_build_progress(4, error=err_msg))
                result = {"success": False, "error": err_msg}
                return result
            if data.get("currentStep") == "error":
                err_msg = f"خطأ SheerID: {data.get('errorIds', [])}"
                await on_progress(_build_progress(4, error=err_msg))
                result = {"success": False, "error": err_msg}
                return result

            await on_progress(_build_progress(5, detail="تم إرسال البيانات، رفع المستندات..."))

            # ── Step 6: التحقق من العرض — skip SSO + upload document ──
            step = data.get("currentStep", "")
            if step in ("sso", "collectStudentPersonalInfo"):
                await _api_request(client, "DELETE", f"/verification/{vid}/step/sso")

            doc = _generate_student_id_image(first, last, uni["name"])
            upload_body = {"files": [{"fileName": "student_card.png", "mimeType": "image/png", "fileSize": len(doc)}]}
            data, status = await _api_request(client, "POST", f"/verification/{vid}/step/docUpload", upload_body)
            if not data.get("documents"):
                err_msg = "فشل الحصول على رابط الرفع"
                await on_progress(_build_progress(5, error=err_msg))
                result = {"success": False, "error": err_msg}
                return result

            upload_url = data["documents"][0].get("uploadUrl")
            if not upload_url or not await _upload_s3(client, upload_url, doc):
                err_msg = "فشل رفع المستند"
                await on_progress(_build_progress(5, error=err_msg))
                result = {"success": False, "error": err_msg}
                return result

            data, _ = await _api_request(client, "POST", f"/verification/{vid}/step/completeDocUpload")
            await on_progress(_build_progress(6, detail="تم رفع المستندات، المطالبة بالعرض..."))

        # ── Step 7: المطالبة بالعرض — claim via redirect ──
        redirect_url = data.get("redirectUrl", "")
        if redirect_url and page:
            try:
                await page.goto(redirect_url, wait_until="networkidle", timeout=30000)
                await asyncio.sleep(3)

                for selector in [
                    "button:has-text('Claim')", "button:has-text('Get')",
                    "button:has-text('Continue')", "button:has-text('Start')",
                    "a:has-text('Claim')", "a:has-text('Get')",
                ]:
                    btn = page.locator(selector).first
                    if await btn.count() > 0:
                        await btn.click()
                        await asyncio.sleep(3)
                        break

                await on_progress(_build_progress(7, detail="تم المطالبة، معالجة الدفع..."))

                # ── Step 8: معالجة الدفع — confirm subscription ──
                for selector in [
                    "button:has-text('Subscribe')", "button:has-text('Confirm')",
                    "button:has-text('Accept')", "button:has-text('Done')",
                ]:
                    btn = page.locator(selector).first
                    if await btn.count() > 0:
                        await btn.click()
                        await asyncio.sleep(2)
                        break

            except Exception as exc:
                log.warning("Google claim redirect failed: %s", exc)
        else:
            await on_progress(_build_progress(7))

        await on_progress(_build_progress(8))

        # ── Step 9: اكتمال ──
        await asyncio.sleep(0.5)
        await on_progress(_build_progress(9))

        result = {
            "success": True,
            "student": f"{first} {last}",
            "email": student_email,
            "gmail": gmail,
            "school": uni["name"],
            "step": data.get("currentStep", "pending"),
            "redirect": redirect_url,
        }
        return result

    except Exception as exc:
        log.warning("Gemini auto-verify failed: %s", exc)
        await on_progress(_build_progress(0, error=f"فشل: {exc}"))
        result = {"success": False, "error": f"فشل: {exc}"}
        return result

    finally:
        if browser:
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
