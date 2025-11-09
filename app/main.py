from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse
import os, re, requests
from typing import List, Dict, Any, Optional
from datetime import datetime
from dateparser import parse as parse_date
import time

# ------------------------------------------------------------
# Config
# ------------------------------------------------------------
# Canonical base (HTTPS). You may override via env if needed.
BASE_URL = os.getenv(
    "MESSAGES_BASE_URL",
    "https://november7-730026606190.europe-west1.run.app"
).rstrip("/")

# The public API we call (GET)
MESSAGES_API = f"{BASE_URL}/messages"     # (no trailing slash needed)
PAGE_SIZE   = int(os.getenv("PAGE_SIZE", "100"))
MAX_PAGES   = int(os.getenv("MAX_PAGES", "10"))

app = FastAPI(title="Member QA")
@app.get("/health")
def health():
    return {"ok": True}

@app.get("/env")
def env():
    return {
        "BASE_URL": BASE_URL,
        "MESSAGES_API": MESSAGES_API,
        "PAGE_SIZE": PAGE_SIZE,
        "MAX_PAGES": MAX_PAGES,
    }

@app.get("/debug/messages")
def debug_messages():
    import time, requests
    url = f"{MESSAGES_API}?skip=0&limit=2"
    t0 = time.time()
    try:
        r = requests.get(url, timeout=20)
        return {
            "url": r.url,
            "status": r.status_code,
            "elapsed_ms": int((time.time()-t0)*1000),
            "body_snippet": r.text[:300]
        }
    except Exception as e:
        return {"url": url, "status": None, "error": str(e)}


# ------------------------------------------------------------
# Lightweight NLP patterns
# ------------------------------------------------------------
# Name with letters, digits/underscore (for unicode letters), apostrophes, and hyphens
NAME_PAT = r"([A-Z][\w'’\-]+(?:\s+[A-Z][\w'’\-]+)?)"

# Expanded patterns to detect more natural travel phrasing
TRIP_PATTERNS = [
    # “trip/going/traveling to Paris …”
    r"\b(?:trip|going|travel(?:ling)?)\s+to\s+(?P<place>[A-Z][A-Za-z\s\-]+)\b(?P<context>[^.?!]*)",

    # “book/reserve/arrange … to/in Santorini …”
    r"\b(?:book|reserve|arrange).+?\b(?:to|in)\s+(?P<place>[A-Z][A-Za-z\s\-]+)\b(?P<context>[^.?!]*)",

    # NEW → “arrange … for a weekend in Monaco …”
    r"\b(?:book|reserve|arrange).+?\bfor\s+(?P<context>[^.?!]*?)\s+in\s+(?P<place>[A-Z][A-Za-z\s\-]+)",

    # “for (a/the/first week/… weekend) in Monaco …”
    r"\bfor\s+(?P<context>(?:the|a)?\s*(?:first|second|third|last)?\s*(?:weekend|week|month)\s*(?:of\s+[A-Z][a-z]+)?)\s+in\s+(?P<place>[A-Z][A-Za-z\s\-]+)"
]


DATE_CUE = re.compile(
    r"("  # one token/date phrase only
    r"\b\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?\b|"                                              # 5/09, 05-09-2025
    r"\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?\s+\d{1,2}(?:,\s*\d{4})?\b|"  # May 9, 2025
    r"\b(?:today|tomorrow|this\s+(?:mon|tue|wed|thu|fri|sat|sun|monday|tuesday|wednesday|thursday|friday|saturday|sunday|week|month)|"
    r"next\s+(?:week|month|mon|tue|wed|thu|fri|sat|sun|monday|tuesday|wednesday|thursday|friday|saturday|sunday))\b|"
    r"\b(?:first|second|third|last)\s+week(?:\s+of)?\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\b"
    r")",
    re.I
)

SECONDARY_DATE_PHRASE = re.compile(
    r"\b(?:first|second|third|last)\s+week(?:\s+of)?\s+[A-Z][a-z]+", re.I
)

CARS_PATTERNS = [
    r"(?i)\b(?:have|own|got)\s+(?P<num>\d+)\s+car[s]?\b"
]
PHONE_PATTERNS = [
    r"\b(?:\+?\d{1,2}[\s\-\.]?)?(?:\(?\d{3}\)?[\s\-\.]?)\d{3}[\s\-\.]?\d{4}\b"
]

FAV_RESTAURANTS_PATTERNS = [
    r"(?i)\bfavorite restaurant[s]?\s*(?:are|is|:)?\s*(?P<list>[A-Za-z0-9&'’\-.\s,]+)",
    r"(?i)\bI\s+love\s+eating\s+at\s+(?P<list>[A-Za-z0-9&'’\-.\s,]+)"
]
NON_TRIP_KEYWORDS = {"dinner","lunch","restaurant","reservation","table","tasting menu"}

def looks_like_non_trip(text: str) -> bool:
    t = text.lower()
    return any(k in t for k in NON_TRIP_KEYWORDS)


# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------
def fetch_messages_all() -> Optional[List[Dict[str, Any]]]:
    def get_page(skip: int, limit: int) -> Optional[Dict[str, Any]]:
        url = MESSAGES_API
        for _ in range(3):                      # up to 3 tries
            try:
                r = requests.get(url, params={"skip": skip, "limit": limit}, timeout=20)
                if r.status_code == 200:
                    return r.json()
            except Exception:
                pass
            time.sleep(0.5)
        return None

    try:
        items: List[Dict[str, Any]] = []
        skip = 0
        pages = 0
        while pages < MAX_PAGES:
            data = get_page(skip, PAGE_SIZE)
            if data is None:
                return None  # keep output format contract at /ask
            page_items = data.get("items", [])
            items.extend(page_items)
            skip += PAGE_SIZE
            pages += 1
            if len(page_items) < PAGE_SIZE:
                break
        return items
    except Exception:
        return None


def guess_user_from_question(q: str) -> Optional[str]:
    # “Amira’s …”
    m = re.search(rf"(?i)\b{NAME_PAT}'s\b", q)
    if m: return m.group(1)
    # “does Vikram Desai …”, “is Layla …”
    m = re.search(rf"(?i)\b(?:is|does|are)\s+{NAME_PAT}\b", q)
    if m: return m.group(1)
    # fallback: first capitalized token
    m = re.search(rf"\b{NAME_PAT}\b", q)
    return m.group(1) if m else None

def detect_type(q: str) -> str:
    ql = q.lower()
    if "trip" in ql or "going to" in ql or ql.startswith("when is") or "book" in ql:
        return "trip"
    if "how many car" in ql or "cars does" in ql:
        return "cars"
    if "favorite restaurant" in ql or "favourite restaurant" in ql or "restaurants" in ql:
        return "restaurants"
    if "phone" in ql or "number" in ql or "contact" in ql:
        return "phone"

    return "generic"

def normalize_date_relative(raw: str, ts_iso: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    settings = {"PREFER_DATES_FROM": "future"}
    if ts_iso:
        try:
            base = datetime.fromisoformat(ts_iso.replace("Z", "+00:00"))
            settings["RELATIVE_BASE"] = base
        except Exception:
            pass
    dt = parse_date(raw, settings=settings)
    return dt.strftime("%Y-%m-%d") if dt else None

def extract_trip(text: str, target_place: Optional[str], ts_iso: Optional[str]) -> Optional[str]:
    for pat in TRIP_PATTERNS:
        # add re.I here so "Book"/"BOOK"/"book" all match
        for m in re.finditer(pat, text, flags=re.I):
            place = (m.group("place") or "").strip()
            if target_place and place and target_place.lower() not in place.lower():
                continue

            context = (m.groupdict().get("context") or "")
            dm = DATE_CUE.search(context) or DATE_CUE.search(text)
            if dm:
                dnorm = normalize_date_relative(dm.group(1), ts_iso)
                return dnorm or dm.group(1).strip()

            pm = SECONDARY_DATE_PHRASE.search(context) or SECONDARY_DATE_PHRASE.search(text)
            if pm:
                phrase = pm.group(0)
                dnorm = normalize_date_relative(phrase, ts_iso)
                return dnorm or phrase.strip()

            simple = context.strip()
            if simple and re.search(r"\b(weekend|week|month)\b", simple, re.I):
                dnorm = normalize_date_relative(simple, ts_iso)
                return dnorm or simple
    return None

def extract_cars(text: str) -> Optional[str]:
    for pat in CARS_PATTERNS:
        m = re.search(pat, text)
        if m:
            return m.group("num")
    return None
def extract_phone(text: str) -> Optional[str]:
    for pat in PHONE_PATTERNS:
        m = re.search(pat, text)
        if m:
            return m.group(0)
    return None


def extract_restaurants(text: str) -> Optional[List[str]]:
    for pat in FAV_RESTAURANTS_PATTERNS:
        m = re.search(pat, text)
        if not m:
            continue
        raw = m.group("list")
        # split, clean, keep likely proper names
        items = [s.strip(" .") for s in raw.split(",") if s.strip()]
        items = [x for x in items if re.match(r"[A-Z]", x) or "&" in x or "'" in x]
        if items:
            return items[:5]
    return None

# ------------------------------------------------------------
# Public endpoint: /ask
# ------------------------------------------------------------
# ------------------------------------------------------------
# Public endpoint: /ask
# ------------------------------------------------------------
@app.get("/ask")
def ask(question: str = Query(..., description="Natural-language question")):
    try:
        msgs = fetch_messages_all()
        if msgs is None:
            return JSONResponse({
                "answer": "Sorry—couldn’t reach the messages service. Please try again."
            })

        who = guess_user_from_question(question)
        if not who:
            return JSONResponse({
                "answer": "I could not identify the user in your question."
            })

        qtype = detect_type(question)

        # Filter messages for this user (case-insensitive prefix match)
        candidates = [
            m for m in msgs
            if str(m.get("user_name", "")).lower().startswith(who.lower())
        ]
        if not candidates:
            return JSONResponse({"answer": f"I do not see messages for {who}."})

        # ----------------------------
        # Trip-related questions
        # ----------------------------
        if qtype == "trip":
            dest = None
            m = re.search(r"\bto\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)", question)
            if m:
                dest = m.group(1)

            # loop through all candidate messages (most recent first)
            for cm in sorted(candidates, key=lambda x: x.get("timestamp", ""), reverse=True):
                when = extract_trip(cm.get("message", ""), dest, cm.get("timestamp"))
                if when:
                    if dest:
                        return JSONResponse({
                            "answer": f"{who} is planning the trip to {dest} on {when}."
                        })
                    else:
                        return JSONResponse({
                            "answer": f"{who} is planning the trip on {when}."
                        })

            # ✅ only return not found AFTER checking all messages
            return JSONResponse({
                "answer": f"I could not find a trip date for {who}."
            })

        # ----------------------------
        # Car ownership
        # ----------------------------
        if qtype == "cars":
            for cm in candidates:
                num = extract_cars(cm.get("message", ""))
                if num:
                    return JSONResponse({
                        "answer": f"{who} has {num} car(s)."
                    })
            return JSONResponse({
                "answer": f"I could not find how many cars {who} has."
            })

        # ----------------------------
        # Favorite restaurants
        # ----------------------------
        if qtype == "restaurants":
            for cm in candidates:
                lst = extract_restaurants(cm.get("message", ""))
                if lst:
                    return JSONResponse({
                        "answer": f"{who}'s favorite restaurants: {', '.join(lst)}"
                    })
            return JSONResponse({
                "answer": f"I could not find favorite restaurants for {who}."
            })
        if qtype == "phone":
            for cm in candidates:
                phone = extract_phone(cm.get("message", ""))
                if phone:
                    return JSONResponse({"answer": f"{who}'s phone number is {phone}."})
            return JSONResponse({"answer": f"I could not find a phone number for {who}."})


        # ----------------------------
        # Generic fallback
        # ----------------------------
        latest = sorted(candidates, key=lambda x: x.get("timestamp", ""))[-1]
        return JSONResponse({
            "answer": f"Not sure. Latest message from {who}: {latest.get('message', '(no text)')}"
        })

    except Exception as e:
        return JSONResponse({
            "answer": f"Sorry—something went wrong processing that question: {str(e)}"
        })
