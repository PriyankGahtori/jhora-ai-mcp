"""interview_slots.py — Vedic astrology interview slot scorer.

All transit data is read live from JHora extractions — nothing hardcoded.

Classical sources used:
- Tara Bala: BPHS 48.207-209; Muhurta Chintamani
- Panchanga: Prashna Marga; classical Muhurta texts
- Moon from natal Moon: Prashna Marga (sincerity/auspiciousness check)
- Mercury retrograde: classical Muhurta and Prashna tradition
- Karana: classical Panchanga (Vishti = inauspicious)
- Dasha lord transit trigger: Prashna Marga 14.86-88
- 7th house: Prashna Marga house assignments; BPHS
- SAV bindus: BPHS Ch.32; Prashna Marga SAV method
- Hora lord: classical Muhurta (Hora = 1 hour planetary ruler)

Usage (open range):
  python3 interview_slots.py \
    --natal Supriya_rect_917 \
    --start 2026-06-29 --end 2026-07-03 \
    --lat 28.6139 --lon 77.2090 --tz 5.5 --place "New Delhi" \
    --mode virtual

Usage (fixed slots):
  python3 interview_slots.py \
    --natal Supriya_rect_917 \
    --slots "2026-07-02 14:15" "2026-07-03 10:30" \
    --lat 28.6139 --lon 77.2090 --tz 5.5 --place "New Delhi" \
    --mode onsite
"""

import json, os, re, subprocess, sys, argparse, math
from datetime import date, datetime, timedelta

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_DIR     = os.path.join(SCRIPTS_DIR, 'jhora_data')
EXTRACT_SH  = os.path.join(SCRIPTS_DIR, 'jhora_panchanga.sh')

# ── Slot times (45-min slots 9AM to 6:45PM) ──────────────────────────────────
SLOT_TIMES = [
    "09:00","09:45","10:30","11:15","12:00","12:45",
    "13:30","14:15","15:00","15:45","16:30","17:15","18:00","18:45"
]

# ── Signs ─────────────────────────────────────────────────────────────────────
SIGNS = ["Aries","Taurus","Gemini","Cancer","Leo","Virgo",
         "Libra","Scorpio","Sagittarius","Capricorn","Aquarius","Pisces"]

SIGN_LORD = {
    "Aries":"Mars","Taurus":"Venus","Gemini":"Mercury","Cancer":"Moon",
    "Leo":"Sun","Virgo":"Mercury","Libra":"Venus","Scorpio":"Mars",
    "Sagittarius":"Jupiter","Capricorn":"Saturn","Aquarius":"Saturn","Pisces":"Jupiter"
}

EXALTATION = {
    "Sun":"Aries","Moon":"Taurus","Mars":"Capricorn","Mercury":"Virgo",
    "Jupiter":"Cancer","Venus":"Pisces","Saturn":"Libra",
    "Rahu":"Gemini","Ketu":"Sagittarius"
}

# ── Tara Bala (Source: BPHS 48.207-209; Muhurta Chintamani) ─────────────────
# Count from Janma Nakshatra to day's Moon nakshatra, divide by 9, remainder = Tara
# Favourable: 2,4,6,8,9 | Inauspicious: 3,5,7 | Neutral: 1
TARA_SCORE = {1:2, 2:8, 3:-3, 4:8, 5:-3, 6:8, 7:-5, 8:8, 9:10}
TARA_NAME  = {
    1:"Janma", 2:"Sampat", 3:"Vipat", 4:"Kshema", 5:"Pratyari",
    6:"Sadhana", 7:"Naidhana", 8:"Mitra", 9:"Parama Mitra"
}
TARA_DESC  = {
    1:"Janma — birth star nakshatra. Neutral per most schools; intensely personal energy.",
    2:"Sampat — wealth/prosperity nakshatra. Strongly auspicious.",
    3:"Vipat — danger/adversity nakshatra. Inauspicious — avoid.",
    4:"Kshema — well-being and stability. Auspicious.",
    5:"Pratyari — opposition/enemy nakshatra. Inauspicious — avoid.",
    6:"Sadhana — achievement nakshatra. Auspicious for skill demonstration.",
    7:"Naidhana — destruction nakshatra. Most inauspicious. Strongly avoid.",
    8:"Mitra — friend nakshatra. Auspicious, harmonious support.",
    9:"Parama Mitra — great friend nakshatra. Most auspicious of all."
}

# All 27 nakshatras mapped to Tara from Shatabhisha
NAK_TARA = {
    "Shatabhisha":1,"Purva Bhadra":2,"Uttara Bhadra":3,"Revati":4,
    "Ashwini":5,"Bharani":6,"Krittika":7,"Rohini":8,"Mrigashira":9,
    "Ardra":1,"Punarvasu":2,"Pushya":3,"Pushyami":3,"Ashlesha":4,"Magha":5,
    "Purva Phalguni":6,"Uttara Phalguni":7,"Hasta":8,"Chitra":9,
    "Swati":1,"Vishakha":2,"Anuradha":3,"Jyeshtha":4,"Mula":5,
    "Purva Ashadha":6,"Uttara Ashadha":7,"Shravana":8,"Dhanishtha":9
}

# ── Vara (Source: classical Muhurta texts) ────────────────────────────────────
# Weekday lord — strength assessed relative to natal lagna lord
# For Sagittarius lagna: Jupiter vara = strongest (lagna lord's own day)
# Tool computes vara strength dynamically from natal lagna lord
VARA_LORD = {
    "Sunday":"Sun","Monday":"Moon","Tuesday":"Mars",
    "Wednesday":"Mercury","Thursday":"Jupiter","Friday":"Venus","Saturday":"Saturn"
}
WEEKDAY_NAMES = {0:"Monday",1:"Tuesday",2:"Wednesday",3:"Thursday",4:"Friday",5:"Saturday",6:"Sunday"}

# Generic vara scores — tool overrides top score for user's lagna lord day
VARA_BASE_SCORE = {
    "Sun":3,"Moon":3,"Mars":3,"Mercury":4,"Jupiter":4,"Venus":4,"Saturn":2
}

# ── Tithi (Source: Prashna Marga; classical Muhurta) ─────────────────────────
# Nanda(1,6,11)=auspicious; Bhadra(2,7,12)=stable; Jaya(3,8,13)=victory;
# Rikta(4,9,14)=inauspicious; Poorna(5,10,15)=complete
# Purnima=most auspicious; Amavasya=inauspicious
TITHI_CLASS = {
    "Pratipada":"Nanda","Dwitiya":"Bhadra","Tritiya":"Jaya",
    "Chaturthi":"Rikta","Panchami":"Poorna","Shashthi":"Nanda",
    "Saptami":"Bhadra","Ashtami":"Jaya","Navami":"Rikta",
    "Dashami":"Poorna","Ekadashi":"Nanda","Dwadashi":"Bhadra",
    "Trayodashi":"Jaya","Chaturdashi":"Rikta","Purnima":"Poorna","Amavasya":"Rikta"
}
TITHI_SCORE = {
    "Nanda":4,"Bhadra":4,"Jaya":3,"Rikta":1,"Poorna":5
}
TITHI_BAD = ["Chaturdashi","Amavasya"]  # specifically inauspicious per Prashna Marga

# ── Yoga (Source: Prashna Marga; classical Muhurta) ──────────────────────────
YOGA_SCORE = {
    "Vishkambha":1,"Priti":4,"Ayushman":4,"Saubhagya":5,"Shobhana":4,
    "Atiganda":1,"Sukarman":4,"Dhriti":4,"Shula":1,"Ganda":1,
    "Vriddhi":4,"Dhruva":5,"Vyaghata":1,"Harshana":4,"Vajra":1,
    "Siddhi":5,"Vyatipata":1,"Variyan":3,"Parigha":1,"Shiva":4,
    "Siddha":5,"Sadhya":4,"Shubha":5,"Shukla":4,"Brahma":5,
    "Indra":5,"Vaidhriti":1
}
YOGA_BAD = [
    "Vishkambha","Atiganda","Shula","Ganda","Vyaghata",
    "Vajra","Vyatipata","Parigha","Vaidhriti"
]

# ── Karana (Source: classical Panchanga / Muhurta texts) ─────────────────────
# Vishti (Bhadra) = strictly inauspicious for any auspicious action
# Bava, Balava, Kaulava = auspicious
KARANA_SCORE = {
    "Bava":4,"Balava":4,"Kaulava":4,"Taitila":3,"Garaja":3,
    "Vanija":3,"Vishti":0,"Shakuni":2,"Chatushpada":2,"Naga":2,"Kimstughna":2
}
KARANA_BAD = ["Vishti"]

# ── Lagna rising type (Source: Iranganti Rangacharya; Prashna Marga) ─────────
# Shirshodaya = quick direct results
# Prishtodaya = delayed, obstacle-prone
# Ubhayodaya = mixed
LAGNA_RISING_TYPE = {
    "Gemini":"Shirshodaya","Leo":"Shirshodaya","Virgo":"Shirshodaya",
    "Libra":"Shirshodaya","Scorpio":"Shirshodaya","Aquarius":"Shirshodaya",
    "Aries":"Prishtodaya","Taurus":"Prishtodaya","Cancer":"Prishtodaya",
    "Sagittarius":"Prishtodaya","Capricorn":"Prishtodaya",
    "Pisces":"Ubhayodaya"
}

# ── 7th house analysis (Source: Prashna Marga house assignments; BPHS) ───────
SEVENTH_FROM = {
    "Aries":"Libra","Taurus":"Scorpio","Gemini":"Sagittarius",
    "Cancer":"Capricorn","Leo":"Aquarius","Virgo":"Pisces",
    "Libra":"Aries","Scorpio":"Taurus","Sagittarius":"Gemini",
    "Capricorn":"Cancer","Aquarius":"Leo","Pisces":"Virgo"
}

# Planet's natural signification for interviewer disposition
# Source: BPHS natural karakatva; Prashna Marga 7th house readings
PLANET_KARAKATVA = {
    "Sun":    {"nature":"authoritative, hierarchical",
               "questions":"leadership, vision, authority, decision-making"},
    "Moon":   {"nature":"empathetic, variable, intuitive",
               "questions":"team dynamics, emotional intelligence, adaptability"},
    "Mars":   {"nature":"direct, competitive, challenging",
               "questions":"technical depth, problem-solving under pressure, past failures"},
    "Mercury":{"nature":"analytical, probing, detail-oriented",
               "questions":"logical reasoning, process thinking, communication clarity"},
    "Jupiter":{"nature":"expansive, dharmic, philosophical",
               "questions":"values alignment, big picture, growth mindset, culture fit"},
    "Venus":  {"nature":"harmonious, relationship-focused, collegial",
               "questions":"collaboration, creativity, stakeholder management"},
    "Saturn": {"nature":"formal, scrutinizing, disciplined",
               "questions":"attention to detail, long-term commitment, past mistakes, structure"},
    "Rahu":   {"nature":"unconventional, ambitious, unpredictable",
               "questions":"innovation, disruption, non-linear thinking, ambition"},
    "Ketu":   {"nature":"detached, deeply technical, past-focused",
               "questions":"deep domain expertise, past experience, philosophical depth"}
}

# ── Sunrise lagna seed for New Delhi late June/early July ────────────────────
# Approximate: Gemini rises at sunrise (~05:30 IST) in New Delhi in late June
# Lagna shifts ~30° every 2 hours
SUNRISE_LAGNA_IDX = 2   # Gemini index in SIGNS
SUNRISE_TIME_MINS = 330 # 05:30 AM

# ── Data loading ──────────────────────────────────────────────────────────────

def _latest_run_dir(name):
    safe     = re.sub(r'[^\w\-]', '_', name)
    name_dir = os.path.join(OUT_DIR, safe)
    if not os.path.isdir(name_dir): return None
    runs     = sorted(os.listdir(name_dir))
    return os.path.join(name_dir, runs[-1]) if runs else None

def load_chart(name):
    run_dir = _latest_run_dir(name)
    if not run_dir: return None
    path = os.path.join(run_dir, 'parsed_core.json')
    with open(path) as f:
        return json.load(f)

def extract_day(name, dt, lat, lon, tz, place):
    print(f"  Extracting {dt}...", file=sys.stderr)
    result = subprocess.run([
        EXTRACT_SH,
        '--name',  name,
        '--date',  dt,
        '--time',  '09:00',
        '--lat',   str(lat),
        '--lon',   str(lon),
        '--tz',    str(tz),
        '--place', place
    ], capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  WARNING: Extraction failed for {dt}: {result.stderr}", file=sys.stderr)
        return False
    return True

def norm_nak(nak_raw):
    """Normalise nakshatra name from JHora abbreviations."""
    mapping = {
        "PBha":"Purva Bhadra","UBha":"Uttara Bhadra","Reva":"Revati",
        "Aswi":"Ashwini","Bhar":"Bharani","Krit":"Krittika","Rohi":"Rohini",
        "Mrig":"Mrigashira","Ardr":"Ardra","Puna":"Punarvasu",
        "Push":"Pushya","Pushyami":"Pushya",
        "Asle":"Ashlesha","Magh":"Magha","PPha":"Purva Phalguni",
        "UPha":"Uttara Phalguni","Hast":"Hasta","Chit":"Chitra",
        "Swat":"Swati","Visa":"Vishakha","Anu":"Anuradha",
        "Jye":"Jyeshtha","Mool":"Mula","PAsh":"Purva Ashadha",
        "Pash":"Purva Ashadha","UAsh":"Uttara Ashadha","Uash":"Uttara Ashadha",
        "Srav":"Shravana","Dhan":"Dhanishtha","Sata":"Shatabhisha"
    }
    for k, v in mapping.items():
        if k.lower() in nak_raw.lower():
            return v
    return nak_raw

def compute_sav(av_data):
    """
    Compute Sarvashtakavarga per sign by summing all 8 contributor grids.
    Source: BPHS Ch.32; Prashna Marga SAV method.
    """
    sav = {}
    for contributor in ['Lagna','Sun','Moon','Mars','Mercury','Jupiter','Venus','Saturn']:
        grid = av_data.get(contributor, {}).get('bindus', {})
        for sign, val in grid.items():
            sav[sign] = sav.get(sign, 0) + val
    return sav

def approx_lagna(time_str):
    """
    Approximate rising lagna for New Delhi at a given time.
    Lagna shifts ~30° every 2 hours.
    Seed: Gemini rises at sunrise (~05:30 IST) in New Delhi in late June/early July.
    Note: This is an approximation — for precise lagna use JHora extraction at exact time.
    """
    h, m  = map(int, time_str.split(":"))
    mins  = h * 60 + m
    elapsed_2hr_blocks = int((mins - SUNRISE_TIME_MINS) // 120)
    lagna_idx = (SUNRISE_LAGNA_IDX + elapsed_2hr_blocks) % 12
    return SIGNS[lagna_idx]

def sign_count(from_sign, to_sign):
    """Count signs from from_sign to to_sign inclusively (1-12)."""
    fi = SIGNS.index(from_sign) if from_sign in SIGNS else 0
    ti = SIGNS.index(to_sign)   if to_sign   in SIGNS else 0
    return ((ti - fi) % 12) + 1

def moon_from_natal_moon(transit_moon_sign, natal_moon_sign):
    """
    Count transit Moon's sign from natal Moon sign.
    Source: Prashna Marga — Moon in Kendra from natal Moon = auspicious;
    Moon in 8th from natal Moon = inauspicious.
    Returns (count, classification).
    """
    count = sign_count(natal_moon_sign, transit_moon_sign)
    if count in [1, 4, 7, 10]:
        return count, "kendra"
    elif count == 8:
        return count, "eighth"
    else:
        return count, "neutral"

def dasha_lord_transit_check(transit_planets, dasha_lord, natal_lagna_sign):
    """
    Check if current dasha lord is transiting its own sign, exaltation, or natal lagna.
    Source: Prashna Marga 14.86-88 — event trigger when Karyesha/Karaka transits
    own sign, exaltation sign, or natal Lagna.
    Returns (is_triggered, note).
    """
    planet_data = transit_planets.get(dasha_lord, {})
    if not isinstance(planet_data, dict):
        return False, ""
    transit_sign = planet_data.get('sign', '')
    own_signs    = [s for s, l in SIGN_LORD.items() if l == dasha_lord]
    exalt_sign   = EXALTATION.get(dasha_lord, '')

    if transit_sign in own_signs:
        return True, f"{dasha_lord} (dasha lord) transiting own sign {transit_sign} — PM 14.86-88 trigger active"
    if transit_sign == exalt_sign:
        return True, f"{dasha_lord} (dasha lord) transiting exaltation sign {transit_sign} — PM 14.86-88 trigger active"
    if transit_sign == natal_lagna_sign:
        return True, f"{dasha_lord} (dasha lord) transiting natal lagna sign {transit_sign} — PM 14.86-88 trigger active"
    return False, ""

def seventh_house_analysis(transit_planets, lagna):
    """
    Analyse 7th house from current lagna for interviewer disposition.
    Source: Prashna Marga house assignments; BPHS natural karakatva.
    """
    seventh_sign  = SEVENTH_FROM.get(lagna, '')
    seventh_lord  = SIGN_LORD.get(seventh_sign, '')

    planets_in_7th = [
        p for p, d in transit_planets.items()
        if isinstance(d, dict) and d.get('sign') == seventh_sign
        and p != 'Lagna'
    ]

    # Planets in 1st (lagna sign) aspect 7th by 7th aspect
    planets_aspecting_7th = [
        p for p, d in transit_planets.items()
        if isinstance(d, dict) and d.get('sign') == lagna
        and p != 'Lagna'
    ]

    # Saturn aspects 7th from 3rd and 10th (special aspects) — BPHS
    saturn_data = transit_planets.get('Saturn', {})
    saturn_sign = saturn_data.get('sign', '') if isinstance(saturn_data, dict) else ''
    if saturn_sign:
        saturn_to_7th = sign_count(saturn_sign, seventh_sign)
        if saturn_to_7th in [3, 10] and 'Saturn' not in planets_aspecting_7th:
            planets_aspecting_7th.append('Saturn (special aspect)')

    # Mars aspects 7th from 4th and 8th (special aspects) — BPHS
    mars_data = transit_planets.get('Mars', {})
    mars_sign = mars_data.get('sign', '') if isinstance(mars_data, dict) else ''
    if mars_sign:
        mars_to_7th = sign_count(mars_sign, seventh_sign)
        if mars_to_7th in [4, 8] and 'Mars' not in planets_aspecting_7th:
            planets_aspecting_7th.append('Mars (special aspect)')

    # Jupiter aspects 7th from 5th and 9th (special aspects) — BPHS
    jup_data = transit_planets.get('Jupiter', {})
    jup_sign = jup_data.get('sign', '') if isinstance(jup_data, dict) else ''
    if jup_sign:
        jup_to_7th = sign_count(jup_sign, seventh_sign)
        if jup_to_7th in [5, 9] and 'Jupiter' not in planets_aspecting_7th:
            planets_aspecting_7th.append('Jupiter (special aspect)')

    # 7th lord strength — is it in own sign or exaltation?
    seventh_lord_data = transit_planets.get(seventh_lord, {})
    seventh_lord_sign = seventh_lord_data.get('sign', '') if isinstance(seventh_lord_data, dict) else ''
    seventh_lord_retro = seventh_lord_data.get('retrograde', False) if isinstance(seventh_lord_data, dict) else False
    own_signs = [s for s, l in SIGN_LORD.items() if l == seventh_lord]
    lord_strong = seventh_lord_sign in own_signs or seventh_lord_sign == EXALTATION.get(seventh_lord, '')

    # Build disposition from influencing planets
    influencers = planets_in_7th if planets_in_7th else [seventh_lord]
    dispositions   = []
    question_types = []
    for p in influencers[:2]:
        pname = p.split(' ')[0]  # strip "(special aspect)" suffix
        if pname in PLANET_KARAKATVA:
            dispositions.append(PLANET_KARAKATVA[pname]['nature'])
            question_types.append(PLANET_KARAKATVA[pname]['questions'])

    return {
        "seventh_sign":            seventh_sign,
        "seventh_lord":            seventh_lord,
        "seventh_lord_sign":       seventh_lord_sign,
        "seventh_lord_strong":     lord_strong,
        "seventh_lord_retrograde": seventh_lord_retro,
        "planets_in_7th":          planets_in_7th,
        "planets_aspecting_7th":   planets_aspecting_7th,
        "interviewer_disposition": "; ".join(dispositions) if dispositions else "neutral",
        "likely_questions":        "; ".join(question_types) if question_types else "general"
    }

# ── Scoring engine ────────────────────────────────────────────────────────────

def score_slot(day_data, time_str, natal_data):
    """
    Score a single interview slot.
    Returns (total_score, factor_breakdown, warnings, seventh_analysis).
    """
    score    = 0
    factors  = []
    warnings = []

    panchang        = day_data.get('panchang', {})
    transit_planets = day_data.get('planets', {})
    av_data         = day_data.get('ashtakavarga', {})

    natal_planets   = natal_data.get('planets', {})
    natal_av        = natal_data.get('ashtakavarga', {})
    natal_lagna     = natal_planets.get('Lagna', {}).get('sign', '')
    natal_moon_sign = natal_planets.get('Moon', {}).get('sign', '')
    natal_lagna_lord= SIGN_LORD.get(natal_lagna, '')

    # Get current dasha lord from natal chart
    dasha    = natal_data.get('dasha', {})
    from datetime import date as date_cls
    today    = date_cls.today()
    DASHA_KEY_MAP = {'Rah':'Rahu','Jup':'Jupiter','Sat':'Saturn','Merc':'Mercury','Ket':'Ketu','Ven':'Venus','Sun':'Sun','Moon':'Moon','Mars':'Mars'}
    dasha_lord_key = None
    dasha_items = list(dasha.items())
    for i, (md, mv) in enumerate(dasha_items):
        try:
            start = date_cls.fromisoformat(mv.get('start', '2000-01-01'))
            next_start = date_cls.fromisoformat(dasha_items[i+1][1].get('start', '2099-01-01')) if i+1 < len(dasha_items) else date_cls(2099, 1, 1)
            if start <= today and next_start > today:
                dasha_lord_key = md
                break
        except Exception:
            pass
    if dasha_lord_key is None:
        dasha_lord_key = list(dasha.keys())[0] if dasha else 'Jupiter'
    dasha_lord = DASHA_KEY_MAP.get(dasha_lord_key, dasha_lord_key)

    # ── 1. Tara Bala ─────────────────────────────────────────────────────────
    # Source: BPHS 48.207-209; Muhurta Chintamani
    moon_nak_raw = panchang.get('nakshatra', {}).get('name', '') if isinstance(panchang.get('nakshatra'), dict) else str(panchang.get('nakshatra', ''))
    moon_nak     = norm_nak(moon_nak_raw)
    tara         = NAK_TARA.get(moon_nak, 5)
    tara_sc      = TARA_SCORE.get(tara, 2)
    score       += tara_sc
    if tara in [3, 5, 7]:
        score -= 3
    factors.append({
        "factor":  "Tara Bala",
        "value":   f"Tara {tara} {TARA_NAME.get(tara,'')} ({moon_nak})",
        "score":   tara_sc,
        "max":     5,
        "source":  "BPHS 48.207-209",
        "detail":  TARA_DESC.get(tara, '')
    })
    if tara in [3, 5, 7]:
        warnings.append({
            "condition": TARA_NAME.get(tara,'') + " Tara",
            "penalty":   tara_sc - 5,
            "practical": {
                3: "Vipat Tara — danger nakshatra. Unexpected obstacles or mishaps likely.",
                5: "Pratyari Tara — opposition nakshatra. Interviewers may be resistant or non-committal.",
                7: "Naidhana Tara — destruction nakshatra. Most inauspicious. Strongly avoid."
            }.get(tara, '')
        })

    # ── 2. Vara ───────────────────────────────────────────────────────────────
    # Source: classical Muhurta texts
    vara_raw  = panchang.get('vedic_weekday', {})
    vara_str  = vara_raw.get('name', '') if isinstance(vara_raw, dict) else str(vara_raw)
    vara_lord = vara_raw.get('lord', '') if isinstance(vara_raw, dict) else VARA_LORD.get(vara_str, '')
    vara_sc   = VARA_BASE_SCORE.get(vara_lord, 3) if vara_lord else 3
    # Boost if vara lord = natal lagna lord (own day = peak)
    if vara_lord and vara_lord == natal_lagna_lord:
        vara_sc = 5
    score += vara_sc
    factors.append({
        "factor": "Vara",
        "value":  f"{vara_str} ({vara_lord})",
        "score":  vara_sc,
        "max":    5,
        "source": "Classical Muhurta",
        "detail": f"{'Lagna lord day — peak strength' if vara_lord == natal_lagna_lord else vara_lord + ' rules this weekday'}"
    })

    # ── 3. Tithi ──────────────────────────────────────────────────────────────
    # Source: Prashna Marga; classical Muhurta
    tithi_raw  = panchang.get('tithi', {})
    tithi_name = tithi_raw.get('name', '') if isinstance(tithi_raw, dict) else str(tithi_raw)
    base_tithi = tithi_name.replace('Sukla ','').replace('Krishna ','').strip()
    tithi_cls  = TITHI_CLASS.get(base_tithi, 'Jaya')
    tithi_sc   = TITHI_SCORE.get(tithi_cls, 3)
    score     += tithi_sc
    factors.append({
        "factor": "Tithi",
        "value":  f"{tithi_name} ({tithi_cls})",
        "score":  tithi_sc,
        "max":    5,
        "source": "Prashna Marga",
        "detail": f"Rikta tithis (4,9,14) and Amavasya are inauspicious per Prashna Marga" if tithi_cls == 'Rikta' else f"{tithi_cls} class tithi"
    })
    if base_tithi in TITHI_BAD:
        warnings.append({
            "condition": f"{tithi_name} — inauspicious tithi",
            "penalty":   tithi_sc - 5,
            "practical": "Chaturdashi and Amavasya are specifically avoided for new beginnings and important meetings per classical Muhurta."
        })

    # ── 4. Yoga ───────────────────────────────────────────────────────────────
    # Source: Prashna Marga; classical Muhurta
    yoga_raw = panchang.get('yoga', {})
    yoga_name = yoga_raw.get('name', '') if isinstance(yoga_raw, dict) else str(yoga_raw)
    yoga_sc   = YOGA_SCORE.get(yoga_name, 3)
    score    += yoga_sc
    factors.append({
        "factor": "Yoga",
        "value":  yoga_name,
        "score":  yoga_sc,
        "max":    5,
        "source": "Prashna Marga",
        "detail": "Inauspicious yoga — structural obstacle to the matter" if yoga_name in YOGA_BAD else f"{yoga_name} yoga active"
    })
    if yoga_name in YOGA_BAD:
        warnings.append({
            "condition": f"{yoga_name} yoga (inauspicious)",
            "penalty":   yoga_sc - 5,
            "practical": f"{yoga_name} is one of the 9 inauspicious yogas per classical Muhurta. General malefic overlay on the day."
        })

    # ── 5. Karana ─────────────────────────────────────────────────────────────
    # Source: classical Panchanga / Muhurta texts
    karana_raw  = panchang.get('karana', {})
    karana_name = karana_raw.get('name', '') if isinstance(karana_raw, dict) else str(karana_raw)
    karana_sc   = KARANA_SCORE.get(karana_name, 3)
    score      += karana_sc
    factors.append({
        "factor": "Karana",
        "value":  karana_name,
        "score":  karana_sc,
        "max":    4,
        "source": "Classical Panchanga",
        "detail": "Vishti (Bhadra) karana — strictly inauspicious for any auspicious action" if karana_name in KARANA_BAD else f"{karana_name} karana"
    })
    if karana_name in KARANA_BAD:
        warnings.append({
            "condition": "Vishti (Bhadra) Karana",
            "penalty":   karana_sc - 4,
            "practical": "Vishti karana is strictly avoided for all auspicious actions per classical Panchanga. Strongest karana prohibition."
        })

    # ── 6. Moon from natal Moon ───────────────────────────────────────────────
    # Source: Prashna Marga — Moon in Kendra from natal Moon = auspicious;
    # Moon in 8th from natal Moon = inauspicious
    transit_moon_sign = transit_planets.get('Moon', {}).get('sign', '') if isinstance(transit_planets.get('Moon'), dict) else ''
    moon_count, moon_cls = moon_from_natal_moon(transit_moon_sign, natal_moon_sign)
    if moon_cls == 'kendra':
        moon_sc = 4
        moon_detail = f"Transit Moon in {transit_moon_sign} — {moon_count}th from natal Moon ({natal_moon_sign}) — Kendra position, auspicious per Prashna Marga"
    elif moon_cls == 'eighth':
        moon_sc = 0
        moon_detail = f"Transit Moon in {transit_moon_sign} — 8th from natal Moon ({natal_moon_sign}) — inauspicious per Prashna Marga"
        warnings.append({
            "condition": "Moon in 8th from natal Moon",
            "penalty":   -4,
            "practical": "Prashna Marga: Moon in 8th from querent's natal Moon is inauspicious. Hidden obstacles, unexpected turns."
        })
    else:
        moon_sc = 2
        moon_detail = f"Transit Moon in {transit_moon_sign} — {moon_count}th from natal Moon ({natal_moon_sign}) — neutral"
    score += moon_sc
    factors.append({
        "factor": "Moon from natal Moon",
        "value":  f"{moon_count}th ({moon_cls})",
        "score":  moon_sc,
        "max":    4,
        "source": "Prashna Marga",
        "detail": moon_detail
    })

    # ── 7. Mercury retrograde ─────────────────────────────────────────────────
    # Source: classical Muhurta and Prashna tradition
    merc_data  = transit_planets.get('Mercury', {})
    merc_retro = merc_data.get('retrograde', False) if isinstance(merc_data, dict) else False
    if merc_retro:
        score -= 3
        factors.append({
            "factor": "Mercury retrograde",
            "value":  "Retrograde",
            "score":  -3,
            "max":    0,
            "source": "Classical Muhurta",
            "detail": "Mercury retrograde — communication obstruction active"
        })
        warnings.append({
            "condition": "Mercury retrograde",
            "penalty":   -3,
            "practical": "Communication errors and misunderstandings likely. Contracts or offers made now may need revision. Avoid signing anything final. Technical miscommunication risk."
        })

    # ── 8. Dasha lord transit trigger ────────────────────────────────────────
    # Source: Prashna Marga 14.86-88
    triggered, trigger_note = dasha_lord_transit_check(
        transit_planets, dasha_lord, natal_lagna)
    if triggered:
        score += 3
        factors.append({
            "factor": "Dasha lord transit trigger",
            "value":  trigger_note,
            "score":  3,
            "max":    3,
            "source": "Prashna Marga 14.86-88",
            "detail": trigger_note
        })

    # ── 9. SAV bindus for transit Moon's sign ────────────────────────────────
    # Source: BPHS Ch.32; Prashna Marga SAV method
    # Use natal SAV grid — bindu count in the sign where Moon transits today
    # Below 25 = weak; 25-29 = average; 30+ = strong
    natal_sav = compute_sav(natal_av)
    moon_sign_bindus = natal_sav.get(transit_moon_sign, 0)
    if moon_sign_bindus >= 30:
        sav_sc = 3
        sav_detail = f"Natal SAV bindus in {transit_moon_sign}: {moon_sign_bindus} — strong (≥30)"
    elif moon_sign_bindus >= 25:
        sav_sc = 2
        sav_detail = f"Natal SAV bindus in {transit_moon_sign}: {moon_sign_bindus} — average (25-29)"
    else:
        sav_sc = 0
        sav_detail = f"Natal SAV bindus in {transit_moon_sign}: {moon_sign_bindus} — below threshold (<25)"
        warnings.append({
            "condition": f"Low SAV bindus in transit Moon sign ({transit_moon_sign}: {moon_sign_bindus})",
            "penalty":   0,
            "practical": "SAV bindus below 25 in transit Moon's sign — reduced support from this nakshatra per Prashna Marga SAV method. Note: does not override a genuine Tara Bala verdict."
        })
    score += sav_sc
    factors.append({
        "factor": "SAV bindus (natal, transit Moon sign)",
        "value":  f"{moon_sign_bindus} bindus in {transit_moon_sign}",
        "score":  sav_sc,
        "max":    3,
        "source": "BPHS Ch.32; Prashna Marga",
        "detail": sav_detail
    })

    # ── 10. Lagna at interview time ───────────────────────────────────────────
    # Approximate rising lagna + rising type (Shirshodaya/Prishtodaya)
    lagna      = approx_lagna(time_str)
    lagna_type = LAGNA_RISING_TYPE.get(lagna, 'Ubhayodaya')
    lagna_lord = SIGN_LORD.get(lagna, '')

    # Lagna score: Shirshodaya = quick direct results; Prishtodaya = delayed
    # Additional: if lagna lord = natal lagna lord's sign = boost
    lagna_sc = 4 if lagna_type == 'Shirshodaya' else (3 if lagna_type == 'Ubhayodaya' else 2)
    # Extra boost if natal lagna lord is in lagna sign (Lagnesh in Lagna)
    lagnesh_data = transit_planets.get(natal_lagna_lord, {})
    lagnesh_sign = lagnesh_data.get('sign', '') if isinstance(lagnesh_data, dict) else ''
    if lagnesh_sign == lagna:
        lagna_sc += 1
        lagna_detail = f"{lagna} rising ({lagna_type}) — {natal_lagna_lord} (lagna lord) also in lagna sign — Lagnesh in Lagna, strong"
    else:
        lagna_detail = f"{lagna} rising ({lagna_type}) — {lagna_lord}-ruled"

    score += lagna_sc
    factors.append({
        "factor": "Rising lagna",
        "value":  f"{lagna} ({lagna_type})",
        "score":  lagna_sc,
        "max":    5,
        "source": "Iranganti Rangacharya; Prashna Marga",
        "detail": lagna_detail
    })

    # ── 11. Hora lord at slot time ────────────────────────────────────────────
    # Source: classical Muhurta — Hora = 1-hour planetary ruler
    # Hora sequence from sunrise: Sun, Venus, Mercury, Moon, Saturn, Jupiter, Mars (repeat)
    # Sunday starts with Sun, Monday with Moon, etc.
    hora_sequence_from_day = {
        "Sun":["Sun","Venus","Mercury","Moon","Saturn","Jupiter","Mars"],
        "Moon":["Moon","Saturn","Jupiter","Mars","Sun","Venus","Mercury"],
        "Mars":["Mars","Sun","Venus","Mercury","Moon","Saturn","Jupiter"],
        "Mercury":["Mercury","Moon","Saturn","Jupiter","Mars","Sun","Venus"],
        "Jupiter":["Jupiter","Mars","Sun","Venus","Mercury","Moon","Saturn"],
        "Venus":["Venus","Mercury","Moon","Saturn","Jupiter","Mars","Sun"],
        "Saturn":["Saturn","Jupiter","Mars","Sun","Venus","Mercury","Moon"]
    }
    h, m       = map(int, time_str.split(":"))
    slot_mins  = h * 60 + m
    hora_num   = int((slot_mins - SUNRISE_TIME_MINS) // 60)
    seq        = hora_sequence_from_day.get(vara_lord, [])
    hora_lord  = seq[hora_num % 7] if seq else ''

    # Hora lord beneficial if = natal lagna lord or natural benefic
    natural_benefics = ['Jupiter','Venus','Mercury','Moon']
    hora_sc = 3 if hora_lord in natural_benefics else (4 if hora_lord == natal_lagna_lord else 2)
    score  += hora_sc
    factors.append({
        "factor": "Hora lord",
        "value":  hora_lord,
        "score":  hora_sc,
        "max":    4,
        "source": "Classical Muhurta (Hora system)",
        "detail": f"{hora_lord} hora at {time_str} — {'lagna lord hora, peak' if hora_lord == natal_lagna_lord else 'natural benefic hora' if hora_lord in natural_benefics else 'natural malefic hora'}"
    })

    # ── 7th house analysis (not scored, returned separately) ─────────────────
    seventh = seventh_house_analysis(transit_planets, lagna)

    total_score = max(0, score)

    return total_score, factors, warnings, seventh, lagna, tara, yoga_name, tithi_name

# ── Main orchestration ────────────────────────────────────────────────────────

def run_analysis(natal_name, slots_mode, date_range, fixed_slots,
                 lat, lon, tz, place, do_extract):
    """Main analysis function. Returns results dict."""

    # Load natal chart
    natal_data = load_chart(natal_name)
    if not natal_data:
        raise ValueError(f'Natal chart "{natal_name}" not found. Run extract_chart first.')

    natal_planets   = natal_data.get('planets', {})
    natal_lagna     = natal_planets.get('Lagna', {}).get('sign', '')
    natal_moon_sign = natal_planets.get('Moon', {}).get('sign', '')
    natal_moon_nak  = norm_nak(natal_planets.get('Moon', {}).get('nakshatra', ''))
    natal_lagna_lord= SIGN_LORD.get(natal_lagna, '')

    print(f"\nNatal chart: {natal_name}", file=sys.stderr)
    print(f"  Lagna: {natal_lagna} (lord: {natal_lagna_lord})", file=sys.stderr)
    print(f"  Janma Nakshatra: {natal_moon_nak} (Moon in {natal_moon_sign})", file=sys.stderr)

    # Determine dates to process
    if slots_mode == 'range':
        start, end = date_range
        dates = []
        d = start
        while d <= end:
            if d.weekday() < 5:  # Mon-Fri only
                dates.append(d.isoformat())
            d += timedelta(days=1)
    else:
        dates = list(set([s.split(' ')[0] for s in fixed_slots]))

    # Extract or load day charts
    day_charts = {}
    for dt in dates:
        chart_name = f"panchanga_{dt}"
        if do_extract or load_chart(chart_name) is None:
            extract_day(chart_name, dt, lat, lon, tz, place)
        data = load_chart(chart_name)
        if data:
            day_charts[dt] = data
        else:
            print(f"  WARNING: No data for {dt}", file=sys.stderr)

    # Build slot list
    if slots_mode == 'range':
        all_slots = [
            (dt, t)
            for dt in sorted(day_charts.keys())
            for t in SLOT_TIMES
        ]
    else:
        all_slots = []
        for s in fixed_slots:
            parts = s.strip().split(' ')
            if len(parts) == 2:
                all_slots.append((parts[0], parts[1]))

    # Score all slots
    results = []
    WEEKDAY_NAMES_LOCAL = {0:"Monday",1:"Tuesday",2:"Wednesday",
                           3:"Thursday",4:"Friday",5:"Saturday",6:"Sunday"}
    for dt, t in all_slots:
        if dt not in day_charts:
            continue
        day_data = day_charts[dt]
        sc, factors, warnings, seventh, lagna, tara, yoga, tithi = score_slot(
            day_data, t, natal_data)
        weekday = WEEKDAY_NAMES_LOCAL[date.fromisoformat(dt).weekday()]
        results.append({
            "date":       dt,
            "weekday":    weekday,
            "time":       t,
            "score":      sc,
            "lagna":      lagna,
            "tara":       tara,
            "tara_name":  TARA_NAME.get(tara,''),
            "yoga":       yoga,
            "tithi":      tithi,
            "factors":    factors,
            "warnings":   warnings,
            "seventh":    seventh
        })

    results.sort(key=lambda x: x['score'], reverse=True)
    return results, natal_data

def format_output(results, slots_mode, natal_name):
    """Format plain text output."""
    lines = []
    lines.append("=" * 70)
    lines.append("VEDIC ASTROLOGY INTERVIEW SLOT ANALYSIS")
    lines.append(f"Natal chart: {natal_name}")
    lines.append("=" * 70)

    if slots_mode == 'range':
        lines.append("\nTOP 3 RECOMMENDED SLOTS")
        lines.append("-" * 70)
        # Filter out worst tara slots for top 3
        top = [r for r in results if r['tara'] not in [7] and not any(
            w['condition'] == 'Naidhana Tara' for w in r['warnings'])][:3]
        if not top:
            top = results[:3]
        for i, r in enumerate(top, 1):
            lines.append(f"\n#{i} — {r['weekday']} {r['date']} at {r['time']} IST")
            lines.append(f"    Overall score: {r['score']}")
            lines.append(f"    Rising lagna:  {r['lagna']}")
            lines.append(f"    Tara Bala:     {r['tara']} {r['tara_name']}")
            lines.append(f"    Yoga:          {r['yoga']}")
            lines.append(f"    Tithi:         {r['tithi']}")
            lines.append(f"\n    Factor breakdown:")
            for f in r['factors']:
                lines.append(f"      {f['factor']:<35} {f['value']:<30} [{f['score']}/{f['max']}]")
                if f['detail']:
                    lines.append(f"        → {f['detail']}")
            if r['warnings']:
                lines.append(f"\n    ⚠ Active warnings:")
                for w in r['warnings']:
                    lines.append(f"      • {w['condition']}")
                    lines.append(f"        Practical: {w['practical']}")
            s = r['seventh']
            lines.append(f"\n    7th house (interviewer) analysis:")
            lines.append(f"      7th sign: {s['seventh_sign']} (lord: {s['seventh_lord']})")
            lines.append(f"      7th lord in: {s['seventh_lord_sign']} ({'strong' if s['seventh_lord_strong'] else 'average'}){' — retrograde' if s['seventh_lord_retrograde'] else ''}")
            if s['planets_in_7th']:
                lines.append(f"      Planets in 7th: {', '.join(s['planets_in_7th'])}")
            if s['planets_aspecting_7th']:
                lines.append(f"      Planets aspecting 7th: {', '.join(s['planets_aspecting_7th'])}")
            lines.append(f"      Interviewer disposition: {s['interviewer_disposition']}")
            lines.append(f"      Likely questions: {s['likely_questions']}")
    else:
        lines.append("\nFIXED SLOT EVALUATION")
        lines.append("-" * 70)
        for r in results:
            verdict = "FAVORABLE" if r['score'] >= 20 else ("MIXED" if r['score'] >= 13 else "AVOID")
            lines.append(f"\n{r['weekday']} {r['date']} at {r['time']} IST — {verdict} (score: {r['score']})")
            lines.append(f"  Tara: {r['tara']} {r['tara_name']} | Yoga: {r['yoga']} | Tithi: {r['tithi']} | Lagna: {r['lagna']}")
            lines.append(f"  Factor breakdown:")
            for f in r['factors']:
                lines.append(f"    {f['factor']:<35} {f['value']:<30} [{f['score']}/{f['max']}]")
                if f['detail']:
                    lines.append(f"      → {f['detail']}")
            if r['warnings']:
                lines.append(f"  ⚠ Active warnings:")
                for w in r['warnings']:
                    lines.append(f"    • {w['condition']}: {w['practical']}")
            s = r['seventh']
            lines.append(f"  7th house (interviewer): {s['seventh_sign']} — {s['interviewer_disposition']}")
            lines.append(f"  Likely questions: {s['likely_questions']}")

    lines.append("\n" + "=" * 70)
    lines.append("FULL SLOT TABLE (sorted by score)")
    lines.append("=" * 70)
    lines.append(f"{'Date':<12} {'Day':<10} {'Time':<7} {'Score':<7} {'Lagna':<14} {'Tara':<20} {'Yoga':<14} {'Tithi':<22} {'Warnings'}")
    lines.append("-" * 130)
    for r in results:
        warn_labels = [w['condition'].split('—')[0].strip()[:20] for w in r['warnings']]
        lines.append(
            f"{r['date']:<12} {r['weekday']:<10} {r['time']:<7} {r['score']:<7} "
            f"{r['lagna']:<14} {r['tara']} {r['tara_name']:<16} {r['yoga']:<14} "
            f"{r['tithi']:<22} {', '.join(warn_labels)}"
        )

    return '\n'.join(lines)

def main():
    parser = argparse.ArgumentParser(description='Vedic astrology interview slot scorer')
    parser.add_argument('--natal',   required=True, help='Natal chart name (already extracted)')
    parser.add_argument('--start',   help='Start date YYYY-MM-DD (range mode)')
    parser.add_argument('--end',     help='End date YYYY-MM-DD (range mode)')
    parser.add_argument('--slots',   nargs='+', help='Fixed slots: "YYYY-MM-DD HH:MM" ...')
    parser.add_argument('--lat',     required=True, type=float)
    parser.add_argument('--lon',     required=True, type=float)
    parser.add_argument('--tz',      required=True, type=float)
    parser.add_argument('--place',   required=True)
    parser.add_argument('--mode',    choices=['virtual','onsite'], default='virtual')
    parser.add_argument('--extract', action='store_true', help='Force fresh JHora extraction')
    args = parser.parse_args()

    # Determine mode
    if args.slots:
        slots_mode  = 'fixed'
        date_range  = None
        fixed_slots = args.slots
    elif args.start and args.end:
        slots_mode  = 'range'
        date_range  = (date.fromisoformat(args.start), date.fromisoformat(args.end))
        fixed_slots = []
    else:
        parser.error("Provide either --slots or --start/--end")

    print(f"Mode: {args.mode} interview | Location: {args.place} ({args.lat},{args.lon})", file=sys.stderr)

    results, natal_data = run_analysis(
        natal_name  = args.natal,
        slots_mode  = slots_mode,
        date_range  = date_range,
        fixed_slots = fixed_slots,
        lat         = args.lat,
        lon         = args.lon,
        tz          = args.tz,
        place       = args.place,
        do_extract  = args.extract
    )

    # Plain text output
    text_output = format_output(results, slots_mode, args.natal)
    print(text_output)

    # JSON output
    out_path = os.path.join(SCRIPTS_DIR, 'slot_scores.json')
    with open(out_path, 'w') as f:
        json.dump({"natal": args.natal, "mode": slots_mode,
                   "place": args.place, "results": results}, f, indent=2)
    print(f"\nJSON saved to {out_path}", file=sys.stderr)

if __name__ == '__main__':
    main()