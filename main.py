from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

import requests
import json
from indic_transliteration import sanscript
from indic_transliteration.sanscript import transliterate

app = FastAPI()

# -------------------------
# CORS (for Vercel frontend)
# -------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # later restrict to your Vercel URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------
# NORMALIZE
# -------------------------
def normalize(text):
    if not text:
        return ""

    text = text.strip().lower()

    try:
        text = transliterate(text, sanscript.DEVANAGARI, sanscript.ITRANS)
    except:
        pass

    text = text.replace("aa", "a").replace("ee", "i").replace("oo", "u")

    return text


def close_match(q, t):
    return (
        t == q or
        t.startswith(q) or
        q.startswith(t)
    )


# -------------------------
# DATA LOAD (ONCE)
# -------------------------
DATA_URL = "https://drive.google.com/uc?export=download&id=1tfYsu-wHTUANOIT9pc_NYlQQiytlE01U"

DATABASE = []
INDEX = {}


def load_data():
    global DATABASE, INDEX

    print("Downloading voter data...")

    try:
        res = requests.get(DATA_URL, timeout=25)
        res.raise_for_status()
        data = res.json()
    except Exception as e:
        print("❌ Failed to load data:", e)
        data = []

    DATABASE = data

    # Build index
    INDEX = {}
    for r in DATABASE:
        tokens = r.get("search_tokens", [])
        normalized = [normalize(t) for t in tokens]
        r["tokens"] = normalized

        if normalized:
            surname = normalized[0]
            if surname not in INDEX:
                INDEX[surname] = []
            INDEX[surname].append(r)

    print(f"✅ Loaded {len(DATABASE)} records")


# Load once at startup
load_data()


# -------------------------
# HEALTH CHECK
# -------------------------
@app.get("/health")
def health():
    return {"status": "ok", "records": len(DATABASE)}


# -------------------------
# HOME (for testing)
# -------------------------
@app.get("/", response_class=HTMLResponse)
def home():
    with open("index.html") as f:
        return f.read()


# -------------------------
# SEARCH API
# -------------------------
@app.get("/search")
def search_api(surname: str = "", firstname: str = ""):

    surname = normalize(surname)
    firstname = normalize(firstname)

    if not surname and not firstname:
        return {"results": []}

    strong = []
    medium = []

    # Use index for speed
    if surname and surname in INDEX:
        candidates = INDEX[surname]
    else:
        candidates = DATABASE

    for r in candidates:

        tokens = r.get("tokens", [])

        s_match = False
        f_match = False

        # SURNAME
        if surname and tokens:
            if close_match(surname, tokens[0]):
                s_match = True

        # FIRSTNAME
        if firstname:
            for t in tokens[1:]:
                if close_match(firstname, t):
                    f_match = True
                    break

        # LOGIC
        if surname and not firstname:
            if s_match:
                strong.append(r)

        elif firstname and not surname:
            if f_match:
                strong.append(r)

        else:
            if s_match and f_match:
                strong.append(r)
            elif s_match or f_match:
                medium.append(r)

    return {"results": strong + medium}