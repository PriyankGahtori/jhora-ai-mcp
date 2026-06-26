#!/usr/bin/env python3
"""
JHora MCP server — stdio JSON-RPC 2.0 (Model Context Protocol)
"""

import json, os, re, subprocess, sys
from datetime import date as _date, timedelta as _timedelta

SCRIPTS_DIR  = os.path.dirname(os.path.abspath(__file__))
EXTRACT_SH   = os.path.join(SCRIPTS_DIR, 'jhora_extract.sh')
INTERVIEW_PY = os.path.join(SCRIPTS_DIR, 'interview_slots.py')
OUT_DIR      = os.path.join(SCRIPTS_DIR, 'jhora_data')

def _latest_run_dir(name):
    safe     = re.sub(r'[^\w\-]', '_', name)
    name_dir = os.path.join(OUT_DIR, safe)
    if not os.path.isdir(name_dir): return None
    runs = sorted(os.listdir(name_dir))
    return os.path.join(name_dir, runs[-1]) if runs else None

def _load_format(run_dir, fmt='core'):
    fname = {'raw':'parsed.json','dev':'parsed_dev.json',
             'llm':'parsed_llm.json','core':'parsed_core.json'}.get(fmt, 'parsed_core.json')
    with open(os.path.join(run_dir, fname)) as f:
        return json.load(f)

def _list_charts():
    if not os.path.isdir(OUT_DIR): return []
    charts = []
    for safe in sorted(os.listdir(OUT_DIR)):
        name_dir = os.path.join(OUT_DIR, safe)
        if not os.path.isdir(name_dir): continue
        runs = sorted(os.listdir(name_dir))
        if not runs: continue
        run_dir = os.path.join(name_dir, runs[-1])
        try:
            meta = _load_format(run_dir, 'core')['meta']
            charts.append({'id': safe, 'name': meta['name'],
                           'extracted_at': meta['extracted_at'], 'runs': len(runs)})
        except Exception:
            pass
    return charts

def _run_extraction(params):
    required = ['name','date','time','lat','lon','tz']
    missing  = [k for k in required if not str(params.get(k,'')).strip()]
    if missing:
        return None, f'Missing fields: {", ".join(missing)}'
    cmd = [EXTRACT_SH,
           '--name',  str(params['name']),
           '--date',  str(params['date']),
           '--time',  str(params['time']),
           '--lat',   str(params['lat']),
           '--lon',   str(params['lon']),
           '--tz',    str(params['tz'])]
    if params.get('place'):
        cmd += ['--place', str(params['place'])]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        return None, result.stderr
    safe    = re.sub(r'[^\w\-]', '_', str(params['name']))
    run_dir = _latest_run_dir(safe) or _latest_run_dir(str(params['name']))
    return run_dir, None

def _build_summary(data, include_divisionals=True):
    lines = []
    meta  = data.get('meta', {})
    birth = data.get('birth', {})
    lines.append(f"=== VEDIC ASTROLOGY CHART: {meta.get('name','Unknown')} ===")
    lines.append(f"Extracted: {meta.get('extracted_at','')}\n")
    lines.append("── BIRTH DETAILS ──")
    for k,v in birth.items():
        lines.append(f"  {k:<20} {v}")
    panchang = data.get('panchang', {})
    if panchang:
        lines.append("\n── PANCHANG ──")
        for k,v in panchang.items():
            if isinstance(v, dict):
                parts = [f"{sk}: {sv}" for sk,sv in v.items()]
                lines.append(f"  {k:<20} {', '.join(parts)}")
            else:
                lines.append(f"  {k:<20} {v}")
    planets = data.get('planets', {})
    if planets:
        lines.append("\n── PLANETARY POSITIONS ──")
        for p,v in planets.items():
            if isinstance(v, dict):
                sign = v.get('sign','')
                deg  = v.get('sign_degree','')
                nak  = v.get('nakshatra','')
                nl   = v.get('nakshatra_lord','')
                lines.append(f"  {p:<15} {sign} {deg}, nakshatra {nak} (lord: {nl})")
            else:
                lines.append(f"  {p:<15} {v}")
    karakas = data.get('karakas', {})
    if karakas:
        lines.append("\n── KARAKAS ──")
        for k,v in karakas.items():
            lines.append(f"  {k:<25} {v}")
    dasha = data.get('dasha', {})
    if dasha:
        lines.append("\n── VIMSHOTTARI DASHA ──")
        for md, mv in list(dasha.items())[:3]:
            lines.append(f"  {md} ({mv.get('start','')}–{mv.get('end','')})")
            for ad, av in list(mv.get('antardashas', {}).items())[:5]:
                lines.append(f"    └─ {ad} ({av.get('start','')}–{av.get('end','')})")
    if include_divisionals:
        divs = data.get('divisionals', {})
        for chart_key in ['D9 (Navamsa)', 'D10 (Dasamsa)']:
            if chart_key in divs:
                lines.append(f"\n── {chart_key} POSITIONS ──")
                for p,v in list(divs[chart_key].items())[:12]:
                    if isinstance(v, dict):
                        lines.append(f"  {p:<15} {v.get('sign','')} {v.get('degree','')}")
    return '\n'.join(lines)

TOOLS = [
    {
        'name': 'list_charts',
        'description': 'List all extracted Vedic astrology charts with metadata.',
        'inputSchema': {'type': 'object', 'properties': {}, 'required': []}
    },
    {
        'name': 'get_chart',
        'description': 'Get full chart data for a person. Format: core/dev/llm/raw.',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'name':   {'type': 'string'},
                'format': {'type': 'string', 'enum': ['core','dev','llm','raw'], 'default': 'core'}
            },
            'required': ['name']
        }
    },
    {
        'name': 'get_planets',
        'description': 'Get planetary positions only — sign, degree, nakshatra, house.',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'name':   {'type': 'string'},
                'format': {'type': 'string', 'enum': ['core','dev','llm','raw'], 'default': 'core'}
            },
            'required': ['name']
        }
    },
    {
        'name': 'get_divisional',
        'description': 'Get a single divisional chart (D9, D10, D1 etc).',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'name':   {'type': 'string'},
                'chart':  {'type': 'string', 'description': 'e.g. D9, D10, D1'},
                'format': {'type': 'string', 'enum': ['core','dev','llm','raw'], 'default': 'core'}
            },
            'required': ['name', 'chart']
        }
    },
    {
        'name': 'get_panchang',
        'description': 'Get panchang for a chart — tithi, vara, nakshatra, yoga, karana, kalam.',
        'inputSchema': {
            'type': 'object',
            'properties': {'name': {'type': 'string'}},
            'required': ['name']
        }
    },
    {
        'name': 'get_dasha',
        'description': 'Get Vimshottari Dasha (3 levels) for a chart.',
        'inputSchema': {
            'type': 'object',
            'properties': {'name': {'type': 'string'}},
            'required': ['name']
        }
    },
    {
        'name': 'summarize_chart',
        'description': 'Plain-text LLM-friendly summary of a Vedic astrology chart.',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'name': {'type': 'string'},
                'include_divisionals': {'type': 'boolean', 'default': True}
            },
            'required': ['name']
        }
    },
    {
        'name': 'extract_chart',
        'description': 'Extract a new chart by running JHora (~60s). Requires Wine + JHora.',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'name':  {'type': 'string'},
                'date':  {'type': 'string', 'description': 'YYYY-MM-DD'},
                'time':  {'type': 'string', 'description': 'HH:MM'},
                'lat':   {'type': 'number'},
                'lon':   {'type': 'number'},
                'tz':    {'type': 'number', 'description': 'decimal hours east, e.g. 5.5 for IST'},
                'place': {'type': 'string'}
            },
            'required': ['name','date','time','lat','lon','tz']
        }
    },
    {
        'name': 'interview_advisor',
        'description': (
            'Interactive Vedic astrology interview slot advisor. '
            'Accepts birth details (or an existing chart name), interview slot details '
            '(fixed slots or date range), interview location details (virtual or onsite), '
            'and returns the best slots with full classical analysis. '
            'Use this when the user wants to find or evaluate interview slots and has '
            'not yet provided all required parameters. '
            'Required inputs: natal_chart OR (name + date + time + lat + lon + tz + place for birth), '
            'interview_mode (virtual/onsite), location_lat, location_lon, location_tz, location_place, '
            'and either slots (list of "YYYY-MM-DD HH:MM" strings) or start_date + end_date. '
            'If natal_chart is provided as an already-extracted chart name, skip birth extraction. '
            'If birth details are provided instead, extract the chart first then score slots.'
        ),
        'inputSchema': {
            'type': 'object',
            'properties': {
                'natal_chart':    {'type': 'string', 'description': 'Name of already-extracted natal chart (e.g. Supriya_rect_917). If provided, skips birth extraction.'},
                'birth_name':     {'type': 'string', 'description': 'Name for the chart if extracting fresh from birth details'},
                'birth_date':     {'type': 'string', 'description': 'Birth date YYYY-MM-DD'},
                'birth_time':     {'type': 'string', 'description': 'Birth time HH:MM'},
                'birth_lat':      {'type': 'number', 'description': 'Birth place latitude'},
                'birth_lon':      {'type': 'number', 'description': 'Birth place longitude'},
                'birth_tz':       {'type': 'number', 'description': 'Birth timezone offset e.g. 5.5 for IST'},
                'birth_place':    {'type': 'string', 'description': 'Birth place name'},
                'interview_mode': {'type': 'string', 'enum': ['virtual', 'onsite'], 'description': 'Virtual or onsite interview'},
                'location_lat':   {'type': 'number', 'description': 'Interview/current location latitude'},
                'location_lon':   {'type': 'number', 'description': 'Interview/current location longitude'},
                'location_tz':    {'type': 'number', 'description': 'Interview/current location timezone offset'},
                'location_place': {'type': 'string', 'description': 'Interview/current location name'},
                'slots':          {'type': 'array', 'items': {'type': 'string'}, 'description': 'Fixed slots as list of "YYYY-MM-DD HH:MM" strings'},
                'start_date':     {'type': 'string', 'description': 'Start date YYYY-MM-DD for open range mode'},
                'end_date':       {'type': 'string', 'description': 'End date YYYY-MM-DD for open range mode'},
                'extract':        {'type': 'boolean', 'description': 'Force fresh JHora extraction for slot charts', 'default': False}
            },
            'required': []
        }
    },
    {
        'name': 'get_best_slots',
        'description': (
            'Find the best interview slots in a date range using interview_slots.py. '
            'Scores each 45-min slot by Tara Bala (natal nakshatra), classical panchanga '
            '(Vara, Tithi, Yoga, Karana), 7th house analysis for virtual/onsite mode, '
            'and PM 14.86-88 dasha lord trigger. Returns ranked slots with full reasoning.'
        ),
        'inputSchema': {
            'type': 'object',
            'properties': {
                'natal':   {'type': 'string', 'description': 'Extracted chart name for natal nakshatra lookup'},
                'start':   {'type': 'string', 'description': 'Start date YYYY-MM-DD'},
                'end':     {'type': 'string', 'description': 'End date YYYY-MM-DD'},
                'lat':     {'type': 'number', 'description': 'Latitude of interview location'},
                'lon':     {'type': 'number', 'description': 'Longitude of interview location'},
                'tz':      {'type': 'number', 'description': 'Timezone offset, e.g. 5.5 for IST'},
                'place':   {'type': 'string', 'description': 'Place name'},
                'mode':    {'type': 'string', 'enum': ['virtual', 'onsite'], 'default': 'virtual',
                            'description': 'Interview mode — affects 7th house weighting'},
                'extract': {'type': 'boolean', 'description': 'Force fresh JHora extraction', 'default': False}
            },
            'required': ['natal','start','end','lat','lon','tz','place']
        }
    }
]

def call_tool(name, args):
    if name == 'list_charts':
        charts = _list_charts()
        if not charts: return 'No charts found.'
        return '\n'.join(
            f"• {c['name']} — extracted {c['extracted_at']} ({c['runs']} run(s))"
            for c in charts)

    if name == 'get_chart':
        run_dir = _latest_run_dir(args.get('name',''))
        if not run_dir: raise ValueError(f'No chart found for "{args.get("name")}". Use list_charts.')
        return _load_format(run_dir, args.get('format','core'))

    if name == 'get_planets':
        run_dir = _latest_run_dir(args.get('name',''))
        if not run_dir: raise ValueError(f'No chart found for "{args.get("name")}". Use list_charts.')
        data = _load_format(run_dir, args.get('format','core'))
        return data.get('planets', {})

    if name == 'get_divisional':
        run_dir = _latest_run_dir(args.get('name',''))
        if not run_dir: raise ValueError(f'No chart found.')
        data    = _load_format(run_dir, args.get('format','core'))
        divs    = data.get('divisionals', {})
        chart_key = args.get('chart','D9')
        match = divs.get(chart_key) or next(
            (v for k,v in divs.items() if chart_key.upper() in k.upper()), None)
        if not match: raise ValueError(f'Divisional {chart_key!r} not found.')
        return {chart_key: match}

    if name == 'get_panchang':
        run_dir = _latest_run_dir(args.get('name',''))
        if not run_dir: raise ValueError(f'No chart found.')
        data = _load_format(run_dir, 'core')
        return {'name': data.get('meta',{}).get('name'), 'panchang': data.get('panchang',{})}

    if name == 'get_dasha':
        run_dir = _latest_run_dir(args.get('name',''))
        if not run_dir: raise ValueError(f'No chart found.')
        data = _load_format(run_dir, 'core')
        return {'name': data.get('meta',{}).get('name'), 'dasha': data.get('dasha',{})}

    if name == 'summarize_chart':
        run_dir = _latest_run_dir(args.get('name',''))
        if not run_dir: raise ValueError(f'No chart found.')
        data = _load_format(run_dir, 'core')
        return _build_summary(data, include_divisionals=args.get('include_divisionals', True))

    if name == 'extract_chart':
        params  = {k: str(v) for k, v in args.items()}
        run_dir, err = _run_extraction(params)
        if err: raise RuntimeError(f'Extraction failed: {err}')
        return _load_format(run_dir, 'core')

    if name == 'interview_advisor':
        # Step 1: resolve natal chart — never extract internally
        natal_chart = str(args.get('natal_chart', '')).strip()
        if not natal_chart:
            return (
                'Please provide your natal chart name (e.g. Supriya_rect_917) or your birth details so I can extract it for you.'
            )
        if not _latest_run_dir(natal_chart):
            return f"Chart '{natal_chart}' not found. Please run extract_chart first with your birth details."
        natal_name = natal_chart

        # Step 2: resolve slot mode
        slots      = args.get('slots')
        start_date = str(args.get('start_date', '')).strip()
        end_date   = str(args.get('end_date', '')).strip()
        if slots and isinstance(slots, list) and len(slots) > 0:
            slot_mode = 'fixed'
        elif start_date and end_date:
            slot_mode = 'range'
        else:
            return (
                'Please provide the slots to evaluate. Either:\n'
                '  • slots — a list of "YYYY-MM-DD HH:MM" strings for fixed slots, or\n'
                '  • start_date and end_date (YYYY-MM-DD) to search an open date range.'
            )

        # Step 3: resolve location
        loc_lat   = args.get('location_lat')
        loc_lon   = args.get('location_lon')
        loc_tz    = args.get('location_tz')
        loc_place = str(args.get('location_place', '')).strip()
        if loc_lat is None or loc_lon is None or loc_tz is None or not loc_place:
            return (
                'Please provide the interview location details:\n'
                '  • location_lat, location_lon, location_tz (decimal hours east), location_place\n'
                '  • interview_mode: "virtual" or "onsite" (default: virtual)'
            )

        mode = args.get('interview_mode', 'virtual')

        # Step 4: verify panchanga day charts are pre-extracted (range mode only)
        if slot_mode == 'range':
            d      = _date.fromisoformat(start_date)
            d_end  = _date.fromisoformat(end_date)
            missing = []
            while d <= d_end:
                ds = d.isoformat()
                if not _latest_run_dir(f'panchanga_{ds}'):
                    missing.append(ds)
                d += _timedelta(days=1)
            if missing:
                return (
                    'Missing panchanga charts for: ' + ', '.join(missing) + '.\n'
                    'Please run extract_chart for each with time 09:00 and the interview location coordinates.'
                )

        # Step 5: build and run subprocess — never pass --extract
        cmd = [
            'python3', INTERVIEW_PY,
            '--natal', natal_name,
            '--lat',   str(loc_lat),
            '--lon',   str(loc_lon),
            '--tz',    str(loc_tz),
            '--place', loc_place,
            '--mode',  mode,
        ]
        if slot_mode == 'fixed':
            cmd += ['--slots'] + [str(s) for s in slots]
        else:
            cmd += ['--start', start_date, '--end', end_date]

        result = subprocess.run(cmd, capture_output=True, text=True, cwd=SCRIPTS_DIR)
        if result.returncode != 0:
            raise RuntimeError(f'Interview slot scoring failed: {result.stderr}')

        # Step 6: return stdout + slot_scores.json if present
        output     = result.stdout
        slots_file = os.path.join(SCRIPTS_DIR, 'slot_scores.json')
        if os.path.exists(slots_file):
            with open(slots_file) as f:
                scores = json.load(f)
            return output + '\n' + json.dumps(scores, indent=2)
        return output

    if name == 'get_best_slots':
        cmd = [
            'python3', INTERVIEW_PY,
            '--natal', str(args['natal']),
            '--start', str(args['start']),
            '--end',   str(args['end']),
            '--lat',   str(args['lat']),
            '--lon',   str(args['lon']),
            '--tz',    str(args['tz']),
            '--place', str(args['place']),
            '--mode',  str(args.get('mode', 'virtual')),
        ]
        if args.get('extract', False):
            cmd.append('--extract')
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=SCRIPTS_DIR)
        if result.returncode != 0:
            raise RuntimeError(f'Slot scoring failed: {result.stderr}')
        slots_file = os.path.join(SCRIPTS_DIR, 'slot_scores.json')
        if os.path.exists(slots_file):
            with open(slots_file) as f:
                return json.load(f)
        return result.stdout

    raise ValueError(f'Unknown tool: {name}')


def send(obj):
    line = json.dumps(obj, ensure_ascii=False)
    sys.stdout.write(line + '\n')
    sys.stdout.flush()

def handle(msg):
    method  = msg.get('method','')
    msg_id  = msg.get('id')
    params  = msg.get('params', {})

    if method == 'initialize':
        send({'jsonrpc':'2.0','id':msg_id,'result':{
            'protocolVersion': '2024-11-05',
            'capabilities': {'tools': {}},
            'serverInfo': {'name': 'jhora-mcp', 'version': '1.1.0'}
        }})
    elif method == 'notifications/initialized':
        pass
    elif method == 'tools/list':
        send({'jsonrpc':'2.0','id':msg_id,'result':{'tools': TOOLS}})
    elif method == 'tools/call':
        tool_name = params.get('name','')
        tool_args = params.get('arguments', {})
        try:
            result = call_tool(tool_name, tool_args)
            text = result if isinstance(result, str) else json.dumps(result, indent=2)
            send({'jsonrpc':'2.0','id':msg_id,'result':{
                'content': [{'type':'text','text': text}],
                'isError': False
            }})
        except Exception as e:
            send({'jsonrpc':'2.0','id':msg_id,'result':{
                'content': [{'type':'text','text': str(e)}],
                'isError': True
            }})
    elif msg_id is not None:
        send({'jsonrpc':'2.0','id':msg_id,'error':{
            'code': -32601, 'message': f'Method not found: {method}'
        }})

def main():
    for line in sys.stdin:
        line = line.strip()
        if not line: continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        handle(msg)

if __name__ == '__main__':
    main()
