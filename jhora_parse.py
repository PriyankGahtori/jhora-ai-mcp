#!/usr/bin/env python3
"""
Parse JHora clipboard exports → structured JSON.
Originals kept untouched.

Output: jhora_data/<name>/<timestamp>/
  chart_data.txt   — original
  divisionals.txt  — original
  parsed.json      — raw structured
  parsed_dev.json  — clean dev-friendly (abbr kept)
  parsed_llm.json  — fully expanded for LLM/UI + ASCII charts
"""

import re, json, os, sys
from datetime import datetime

WINE_TEMP = os.path.expanduser("~/Library/Application Support/CrossOver/Bottles/Jagannatha Hora Vedic Astrology Software/drive_c/windows/temp")
_script_dir = os.path.dirname(os.path.abspath(__file__))
OUT_BASE     = sys.argv[1] if len(sys.argv) > 1 else os.path.join(_script_dir, 'jhora_data')
NAME_OVERRIDE = sys.argv[2] if len(sys.argv) > 2 else None

# ── Lookup tables ─────────────────────────────────────────────────────────────

SIGN_MAP = {
    'Ar':0,'Ta':30,'Ge':60,'Cn':90,'Le':120,'Vi':150,
    'Li':180,'Sc':210,'Sg':240,'Cp':270,'Aq':300,'Pi':330
}

SIGN_FULL = {
    'Ar':'Aries','Ta':'Taurus','Ge':'Gemini','Cn':'Cancer',
    'Le':'Leo','Vi':'Virgo','Li':'Libra','Sc':'Scorpio',
    'Sg':'Sagittarius','Cp':'Capricorn','Aq':'Aquarius','Pi':'Pisces'
}

NAKSHATRA_FULL = {
    'Aswi':'Ashwini','Bhar':'Bharani','Krit':'Krittika',
    'Rohi':'Rohini','Mrig':'Mrigashira','Ardr':'Ardra',
    'Puna':'Punarvasu','Push':'Pushyami','Asre':'Ashlesha',
    'Magh':'Magha','PPha':'Purva Phalguni','UPha':'Uttara Phalguni',
    'Hast':'Hasta','Chit':'Chitra','Swat':'Swati',
    'Visa':'Vishakha','Anur':'Anuradha','Jye':'Jyeshtha',
    'Mool':'Mula','PSha':'Purva Ashadha','USha':'Uttara Ashadha',
    'Srav':'Shravana','Dhan':'Dhanishtha','Sata':'Shatabhisha',
    'PBha':'Purva Bhadrapada','UBha':'Uttara Bhadrapada','Reva':'Revati'
}

NAKSHATRA_LORD = {
    'Ashwini':'Ketu','Bharani':'Venus','Krittika':'Sun',
    'Rohini':'Moon','Mrigashira':'Mars','Ardra':'Rahu',
    'Punarvasu':'Jupiter','Pushyami':'Saturn','Ashlesha':'Mercury',
    'Magha':'Ketu','Purva Phalguni':'Venus','Uttara Phalguni':'Sun',
    'Hasta':'Moon','Chitra':'Mars','Swati':'Rahu',
    'Vishakha':'Jupiter','Anuradha':'Saturn','Jyeshtha':'Mercury',
    'Mula':'Ketu','Purva Ashadha':'Venus','Uttara Ashadha':'Sun',
    'Shravana':'Moon','Dhanishtha':'Mars','Shatabhisha':'Rahu',
    'Purva Bhadrapada':'Jupiter','Uttara Bhadrapada':'Saturn','Revati':'Mercury'
}

KARAKA_FULL = {
    'AK':'Atmakaraka','AmK':'Amatyakaraka','BK':'Bhratrukaraka',
    'MK':'Matrukaraka','PiK':'Pitrukaraka','PK':'Putrakaraka',
    'GK':'Gnatikaraka','DK':'Darakaraka'
}

PLANET_FULL_AV = {
    'As':'Lagna','Su':'Sun','Mo':'Moon','Ma':'Mars',
    'Me':'Mercury','Ju':'Jupiter','Ve':'Venus','Sa':'Saturn'
}

DIV_FULL = {
    'D1':'Rasi (D1)','D2':'Hora (D2)','D3':'Drekkana (D3)',
    'D4':'Chaturthamsa (D4)','D5':'Panchamsa (D5)','D6':'Shashthamsa (D6)',
    'D7':'Saptamsa (D7)','D8':'Ashtamsa (D8)','D9':'Navamsa (D9)',
    'D10':'Dasamsa (D10)','D11':'Rudramsa (D11)','D12':'Dwadasamsa (D12)',
    'D16':'Shodasamsa (D16)','D20':'Vimsamsa (D20)','D24':'Siddhamsa (D24)',
    'D27':'Nakshatramsa (D27)','D30':'Trimsamsa (D30)','D40':'Khavedamsa (D40)',
    'D45':'Akshavedamsa (D45)','D60':'Shashtiamsa (D60)',
    'D81':'Nava-Navamsa (D81)','D108':'Ashtottaramsa (D108)',
    'D144':'Dwadasa-Dwadasamsa (D144)','D0':'Special (D0)'
}

WEEKDAY_LORD = {
    'Sunday':'Sun','Monday':'Moon','Tuesday':'Mars','Wednesday':'Mercury',
    'Thursday':'Jupiter','Friday':'Venus','Saturday':'Saturn'
}

# ── Helpers ───────────────────────────────────────────────────────────────────

def parse_dms(deg, sign, min_, sec):
    base = SIGN_MAP.get(sign, 0)
    return round(base + int(deg) + int(min_)/60 + float(sec)/3600, 6)

def fmt_degree(deg, mins):
    return f"{deg}°{mins:02d}'"

def _expand_panchang_field(raw):
    """'Krishna Panchami (Ju) (91.18% left)' → {name, lord_abbr, remaining_pct}"""
    result = {'raw': raw}
    m = re.search(r'\(([\d.]+)%\s*left\)', raw)
    if m:
        result['remaining_pct'] = float(m.group(1))
    lord_m = re.search(r'\(([A-Z][a-z]?)\)', raw)
    if lord_m:
        result['lord_abbr'] = lord_m.group(1)
    result['name'] = re.sub(r'\s*\([^)]*\)', '', raw).strip()
    return result

# ── Core parsers ──────────────────────────────────────────────────────────────

def parse_chart(text):
    lines = text.splitlines()
    result = {'birth_info': {}, 'panchang': {}, 'planets': {},
              'karakas': {}, 'ashtakavarga': {}, 'shadbala': {}}

    # Birth info
    for line in lines:
        if m := re.match(r'^Date:\s+(.+)', line):
            result['birth_info']['date'] = m.group(1).strip()
        elif m := re.match(r'^Time:\s+(.+)', line):
            result['birth_info']['time'] = m.group(1).strip()
        elif m := re.match(r'^Time Zone:\s+(.+)', line):
            result['birth_info']['timezone'] = m.group(1).strip()
        elif m := re.match(r'^Place:\s+(.+)', line):
            result['birth_info']['place'] = m.group(1).strip()
        elif m := re.match(r'^Ayanamsa:\s+(.+)', line):
            result['birth_info']['ayanamsa'] = m.group(1).strip()
        elif m := re.match(r'^Sidereal Time:\s+(.+)', line):
            result['birth_info']['sidereal_time'] = m.group(1).strip()
        elif m := re.match(r'^Altitude:\s+(.+)', line):
            result['birth_info']['altitude'] = m.group(1).strip()

    # Panchang
    panchang_keys = ['Tithi','Vedic Weekday','Nakshatra','Yoga','Karana',
                     'Hora Lord','Mahakala Hora','Kaala Lord',
                     'Sunrise','Sunset','Janma Ghatis','Lunar Yr-Mo']
    for line in lines:
        for key in panchang_keys:
            if m := re.match(rf'^{re.escape(key)}:\s+(.+)', line):
                result['panchang'][key] = m.group(1).strip()

    # Planet table
    planet_re = re.compile(
        r'^([\w\s\-\(\)]+?)\s{2,}(\d+)\s+([A-Z][a-z])\s+(\d+)\'\s+([\d.]+)"\s+'
        r'(\w+)\s+(\d+)\s+(\w+)\s+(\w+)'
    )
    for line in lines:
        if m := planet_re.match(line):
            raw_body = re.sub(r'\s*-\s*\w+$', '', m.group(1)).strip()
            retro = bool(re.search(r'\(R\)', raw_body, re.IGNORECASE))
            body  = re.sub(r'\s*\(R\)\s*', '', raw_body, flags=re.IGNORECASE).strip()
            result['planets'][body] = {
                'longitude': parse_dms(m.group(2), m.group(3), m.group(4), m.group(5)),
                'longitude_str': f"{m.group(2)} {m.group(3)} {m.group(4)}' {m.group(5)}\"",
                'nakshatra': m.group(6),
                'pada': int(m.group(7)),
                'rasi': m.group(8),
                'navamsa': m.group(9),
                'retrograde': retro,
            }

    # Vimsottari Dasa
    result['dasha'] = {}
    in_dasha = False
    current_maha = None
    DASHA_LORDS = {'Sun','Moon','Mars','Rah','Jup','Sat','Merc','Ket','Ven'}
    antar_re = re.compile(r'(\w+)\s+(\d{4}-\d{2}-\d{2})')
    for line in lines:
        if line.strip().startswith('Vimsottari Dasa'):
            in_dasha = True; continue
        if not in_dasha: continue
        if line.strip() == '':
            if current_maha and result['dasha']:
                current_maha = None
            continue
        # stop at next dasa section
        if re.match(r'^[A-Z][a-z].*Dasa\s', line) and current_maha is None:
            in_dasha = False; break
        stripped = line.strip()
        # mahadasha line starts with planet name flush left (no leading spaces)
        maha_m = re.match(r'^(\w+)\s{2,}(.+)', line)
        if maha_m and maha_m.group(1) in DASHA_LORDS and not line.startswith(' '):
            current_maha = maha_m.group(1)
            result['dasha'][current_maha] = {'antardashas': {}}
            rest = maha_m.group(2)
            for am in antar_re.finditer(rest):
                result['dasha'][current_maha]['antardashas'][am.group(1)] = am.group(2)
        elif current_maha and line.startswith(' '):
            for am in antar_re.finditer(stripped):
                result['dasha'][current_maha]['antardashas'][am.group(1)] = am.group(2)

    # derive mahadasha start = first antardasha start
    for maha, mdata in result['dasha'].items():
        starts = list(mdata['antardashas'].values())
        mdata['start'] = starts[0] if starts else ''

    # Karakas
    in_karaka = False
    for line in lines:
        if 'Chara karaka' in line:
            in_karaka = True; continue
        if in_karaka:
            if m := re.match(r'^(\w+)\s+(\w+)\s+(.+)', line):
                result['karakas'][m.group(1)] = {
                    'planet': m.group(2), 'meaning': m.group(3).strip()}
            elif line.strip() == '' and result['karakas']:
                in_karaka = False

    # Shadbala
    in_shad = False
    for line in lines:
        if 'Shadbala' in line and 'rupas' in line:
            in_shad = True; continue
        if in_shad:
            if m := re.match(r'^(\w+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)', line):
                result['shadbala'][m.group(1)] = {
                    'rupas': float(m.group(2)),
                    'virupas': float(m.group(3)),
                    'pct_strength': float(m.group(4)),
                    'ishta': float(m.group(5)),
                    'kashta': float(m.group(6)),
                }
            elif line.strip() == '' and result['shadbala']:
                in_shad = False

    # Ashtakavarga
    SIGNS = ['Ar','Ta','Ge','Cn','Le','Vi','Li','Sc','Sg','Cp','Aq','Pi']
    in_av = False
    av_section = {}
    for line in lines:
        if line.strip().startswith('Ashtakavarga of Rasi Chart'):
            in_av = True; continue
        if not in_av: continue
        if re.match(r'^\s+(Ar\s+)', line): continue
        m = re.match(r'^(As|Su|Mo|Ma|Me|Ju|Ve|Sa)\s+([\d\s*]+)$', line.strip())
        if m:
            planet = m.group(1)
            vals = re.findall(r'(\d+)\*?', m.group(2))
            if len(vals) == 12:
                av_section[planet] = {SIGNS[i]: int(vals[i]) for i in range(12)}
            continue
        if 'Sodhya Pinda' in line:
            in_av = False; break
    result['ashtakavarga'] = av_section

    return result


def parse_divisionals(text):
    lines = text.splitlines()
    header_line = next((l for l in lines if l.strip().startswith('Body')), None)
    if not header_line:
        return {}

    body_end = header_line.index('D-')
    label_re = re.compile(r'(D-\d+(?:\s*(?:\([\w\s]+\)|x\s*D-\d+))?)')
    raw = [(m.group(1), m.start()) for m in label_re.finditer(header_line)]

    def norm(s):
        s = re.sub(r'\s*\(.*?\)', '', s)
        s = re.sub(r'\s+x\s+D-\d+', '', s)
        s = re.sub(r'\s+', '', s)
        return s.replace('-', '')

    col_names = [norm(label) for label, _ in raw]
    cell_re   = re.compile(r'(\d+)([A-Z][a-z])(\d+)')
    # result keyed by chart first, then planet
    result    = {c: {} for c in col_names}

    for line in lines:
        if not line.strip() or 'Body' in line[:10]: continue
        body = re.sub(r'\s*\(R\)\s*', '', line[:body_end], flags=re.IGNORECASE).strip()
        if not body: continue
        tokens = line[body_end:].split()
        for i, token in enumerate(tokens):
            if i >= len(col_names): break
            m = cell_re.fullmatch(token)
            if m:
                deg, sign, mins = int(m.group(1)), m.group(2), int(m.group(3))
                if sign in SIGN_MAP:
                    lon = round(SIGN_MAP[sign] + deg + mins/60, 4)
                    result[col_names[i]][body] = {'sign': sign, 'deg': deg, 'min': mins, 'lon': lon}
    # drop empty charts
    return {k: v for k, v in result.items() if v}


def parse_charts(text):
    """Extract ASCII chart blocks from chart_data.txt.
    Returns {chart_name: ascii_string}
    """
    charts = {}
    lines  = text.splitlines()
    i = 0
    while i < len(lines):
        # Detect label line: non-empty, followed by +---+ border
        if (i + 1 < len(lines)
                and lines[i].strip()
                and re.match(r'^\+[-]+\+', lines[i+1].strip())):
            label = lines[i].strip()
            # Collect until closing +---+
            block = [lines[i+1]]
            j = i + 2
            while j < len(lines):
                block.append(lines[j])
                if re.match(r'^\+[-]+\+', lines[j].strip()):
                    break
                j += 1
            charts[label] = '\n'.join(block)
            i = j + 1
            continue
        i += 1
    return charts


# ── Transforms ────────────────────────────────────────────────────────────────

def _iso_ts(ts):
    """'20260522_192543' → '2026-05-22T19:25:43'"""
    try:
        dt = datetime.strptime(ts, '%Y%m%d_%H%M%S')
        return dt.strftime('%Y-%m-%dT%H:%M:%S')
    except Exception:
        return ts


def transform_dev(raw):
    """Clean, consistent, abbreviations kept. Adds totals to AV."""
    c   = raw['chart']
    ts  = _iso_ts(raw['extracted_at'])
    out = {
        'meta': {'name': raw['name'], 'extracted_at': ts, 'version': 'dev'},
        'birth': c['birth_info'],
        'panchang': {},
        'planets': {},
        'karakas': {},
        'dasha': c.get('dasha', {}),
        'shadbala': {},
        'ashtakavarga': {},
        'divisionals': {},
    }

    # Panchang — parse out lord/remaining_pct
    pk = c['panchang']
    for key, val in pk.items():
        snake = key.lower().replace(' ', '_')
        parsed = _expand_panchang_field(val)
        out['panchang'][snake] = {
            'name': parsed['name'],
            **({'lord': parsed['lord_abbr']} if 'lord_abbr' in parsed else {}),
            **({'remaining_pct': parsed['remaining_pct']} if 'remaining_pct' in parsed else {}),
        } if 'lord_abbr' in parsed or 'remaining_pct' in parsed else val

    # Planets — drop longitude_str, keep abbr
    for body, p in c['planets'].items():
        out['planets'][body] = {
            'longitude': p['longitude'],
            'sign': p['rasi'],
            'sign_degree': int(p['longitude_str'].split()[0]),
            'sign_minute': int(p['longitude_str'].split()[2].replace("'", "")),
            'nakshatra': p['nakshatra'],
            'pada': p['pada'],
            'navamsa': p['navamsa'],
            'retrograde': p.get('retrograde', False),
        }

    # Karakas — abbr keys, planet only
    for k, v in c['karakas'].items():
        out['karakas'][k] = v['planet']

    # Shadbala
    out['shadbala'] = c['shadbala']

    # Ashtakavarga — add total
    for planet, signs in c['ashtakavarga'].items():
        out['ashtakavarga'][planet] = {**signs, 'total': sum(signs.values())}

    # Divisionals — chart → planet → position (abbr)
    for chart_key, planets in raw['divisionals'].items():
        out['divisionals'][chart_key] = {
            body: {'sign': pos['sign'], 'deg': pos['deg'], 'min': pos['min'], 'lon': pos['lon']}
            for body, pos in planets.items()
        }

    return out


def transform_llm(raw, charts=None):
    """Fully expanded for LLM — full names, ASCII charts included."""
    c   = raw['chart']
    ts  = _iso_ts(raw['extracted_at'])
    out = {
        'meta': {'name': raw['name'], 'extracted_at': ts, 'version': 'llm'},
        'birth': c['birth_info'],
        'panchang': {},
        'planets': {},
        'karakas': {},
        'dasha': c.get('dasha', {}),
        'shadbala': {},
        'ashtakavarga': {},
        'divisionals': {},
        'charts': charts or {},
    }

    # Panchang — full names
    PANCHANG_PLANET = {'Su':'Sun','Mo':'Moon','Ma':'Mars','Me':'Mercury',
                       'Ju':'Jupiter','Ve':'Venus','Sa':'Saturn',
                       'Ra':'Rahu','Ke':'Ketu'}
    pk = c['panchang']
    for key, val in pk.items():
        snake = key.lower().replace(' ', '_')
        parsed = _expand_panchang_field(val)
        lord_full = PANCHANG_PLANET.get(parsed.get('lord_abbr',''), parsed.get('lord_abbr',''))
        if 'lord_abbr' in parsed or 'remaining_pct' in parsed:
            entry = {'name': parsed['name']}
            if lord_full: entry['lord'] = lord_full
            if 'remaining_pct' in parsed: entry['remaining_pct'] = parsed['remaining_pct']
            out['panchang'][snake] = entry
        else:
            out['panchang'][snake] = val

    # Weekday lord
    wd = out['panchang'].get('vedic_weekday', {})
    if isinstance(wd, dict):
        wd_name = wd.get('name', '')
        wd['lord'] = WEEKDAY_LORD.get(wd_name, '')

    # Planets — full sign/nakshatra names
    for body, p in c['planets'].items():
        nak_abbr = p['nakshatra']
        nak_full = NAKSHATRA_FULL.get(nak_abbr, nak_abbr)
        nak_lord = NAKSHATRA_LORD.get(nak_full, '')
        sign_abbr = p['rasi']
        nav_abbr  = p['navamsa']
        deg = int(p['longitude_str'].split()[0])
        mins = int(p['longitude_str'].split()[2].replace("'",""))
        out['planets'][body] = {
            'longitude': p['longitude'],
            'sign': SIGN_FULL.get(sign_abbr, sign_abbr),
            'sign_degree': fmt_degree(deg, mins),
            'nakshatra': nak_full,
            'nakshatra_lord': nak_lord,
            'pada': p['pada'],
            'navamsa_sign': SIGN_FULL.get(nav_abbr, nav_abbr),
            'retrograde': p.get('retrograde', False),
        }

    # Karakas — full names
    for k, v in c['karakas'].items():
        full_k = KARAKA_FULL.get(k, k)
        out['karakas'][full_k] = v['planet']

    # Shadbala — rename ishta/kashta
    for planet, s in c['shadbala'].items():
        out['shadbala'][planet] = {
            'rupas': s['rupas'],
            'virupas': s['virupas'],
            'pct_strength': s['pct_strength'],
            'ishta_phala': s['ishta'],
            'kashta_phala': s['kashta'],
        }

    # Ashtakavarga — full planet + sign names, add total
    for planet_abbr, signs in c['ashtakavarga'].items():
        planet_full = PLANET_FULL_AV.get(planet_abbr, planet_abbr)
        bindus = {SIGN_FULL.get(s, s): v for s, v in signs.items()}
        out['ashtakavarga'][planet_full] = {
            'bindus': bindus,
            'total': sum(signs.values()),
        }

    # Divisionals — chart → planet → position (full names)
    for chart_key, planets in raw['divisionals'].items():
        chart_name = DIV_FULL.get(chart_key, chart_key)
        out['divisionals'][chart_name] = {
            body: {
                'sign': SIGN_FULL.get(pos['sign'], pos['sign']),
                'degree': fmt_degree(pos['deg'], pos['min']),
                'longitude': pos['lon'],
            }
            for body, pos in planets.items()
        }

    return out


CORE_BODIES = {
    'Lagna', 'Sun', 'Moon', 'Mars', 'Mercury', 'Jupiter',
    'Venus', 'Saturn', 'Rahu', 'Ketu',
    'Maandi', 'Gulika', 'Hora Lagna', 'Ghati Lagna', 'Bhava Lagna'
}

def transform_core(raw, charts=None):
    """Minimal version — 14 core bodies, full names, essentials only."""
    llm = transform_llm(raw, charts)
    ts  = _iso_ts(raw['extracted_at'])
    out = {
        'meta': {'name': raw['name'], 'extracted_at': ts, 'version': 'core'},
        'birth':        llm['birth'],
        'panchang':     llm['panchang'],
        'planets':      {b: v for b, v in llm['planets'].items() if b in CORE_BODIES},
        'karakas':      llm['karakas'],
        'dasha':        llm.get('dasha', {}),
        'shadbala':     {b: v for b, v in llm['shadbala'].items() if b in CORE_BODIES},
        'ashtakavarga': {b: v for b, v in llm['ashtakavarga'].items() if b in CORE_BODIES},
        'divisionals':  {
            chart: {body: pos for body, pos in planets.items() if body in CORE_BODIES}
            for chart, planets in llm['divisionals'].items()
        },
        'charts':       llm.get('charts', {}),
    }
    return out


# ── Save ──────────────────────────────────────────────────────────────────────

def save(name, chart_text, div_text, chart_parsed, div_parsed, charts):
    ts   = datetime.now().strftime('%Y%m%d_%H%M%S')
    safe = re.sub(r'[^\w\-]', '_', name)
    out_dir = os.path.join(OUT_BASE, safe, ts)
    os.makedirs(out_dir, exist_ok=True)

    with open(os.path.join(out_dir, 'chart_data.txt'),  'w') as f: f.write(chart_text)
    with open(os.path.join(out_dir, 'divisionals.txt'), 'w') as f: f.write(div_text)

    raw  = {'name': name, 'extracted_at': ts, 'chart': chart_parsed, 'divisionals': div_parsed}
    dev  = transform_dev(raw)
    llm  = transform_llm(raw, charts)
    core = transform_core(raw, charts)

    for fname, data in [
        ('parsed.json',      raw),
        ('parsed_dev.json',  dev),
        ('parsed_llm.json',  llm),
        ('parsed_core.json', core),
    ]:
        with open(os.path.join(out_dir, fname), 'w') as f:
            json.dump(data, f, indent=2)

    print(f"Saved to: {out_dir}")
    print(f"  chart_data.txt    — original")
    print(f"  divisionals.txt   — original")
    print(f"  parsed.json       — raw")
    print(f"  parsed_dev.json   — dev (abbr)")
    print(f"  parsed_llm.json   — llm (expanded + charts)")
    print(f"  parsed_core.json  — core (14 bodies, full names)")
    return out_dir, os.path.join(out_dir, 'parsed.json')


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    chart_path = os.path.join(WINE_TEMP, 'chart_data.txt')
    div_path   = os.path.join(WINE_TEMP, 'divisionals.txt')

    with open(chart_path) as f: chart_text = f.read()
    if not chart_text.strip():
        print("ERROR: chart_data.txt empty — JHora clipboard copy failed.")
        sys.exit(1)

    div_text = ''
    if os.path.exists(div_path):
        with open(div_path) as f: div_text = f.read()

    extracted_name = chart_text.splitlines()[0].split('\\')[-1].strip() or 'chart'
    name = NAME_OVERRIDE if NAME_OVERRIDE else extracted_name

    chart_parsed = parse_chart(chart_text)
    has_tabular_div = div_text and div_text.splitlines()[0].strip().startswith('Body')
    div_parsed   = parse_divisionals(div_text) if has_tabular_div else {}
    charts       = parse_charts(chart_text)

    out_dir, _ = save(name, chart_text, div_text, chart_parsed, div_parsed, charts)

    print(f"\n── Planets ({len(chart_parsed['planets'])}) ──")
    for body, p in list(chart_parsed['planets'].items())[:12]:
        print(f"  {body:25s} {p['longitude_str']:20s} → {p['longitude']:.4f}°  {p['nakshatra']} pada {p['pada']}")

    div_charts = list(div_parsed.keys())
    if div_charts:
        sample = div_parsed[div_charts[0]]
        print(f"\n── Divisionals: {len(div_charts)} charts × {len(sample)} bodies ──")
        print(f"  Charts: {', '.join(div_charts[:10])}...")
        print(f"  Bodies: {', '.join(list(sample.keys())[:6])}...")

    if charts:
        print(f"\n── ASCII Charts: {len(charts)} ──")
        print(f"  {', '.join(list(charts.keys())[:6])}...")

    print(f"\nDone. Output: {out_dir}")


if __name__ == '__main__':
    main()
