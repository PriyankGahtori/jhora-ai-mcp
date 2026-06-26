#!/usr/bin/env bash
# jhora_panchanga.sh — Extract panchanga for a specific date/time/location

set -euo pipefail

SCRIPTS_DIR="$(cd "$(dirname "$0")" && pwd)"
OUT_DIR="${JHORA_OUT_DIR:-$SCRIPTS_DIR/jhora_data}"
WINE_PREFIX="${WINE_PREFIX:-$HOME/Library/Application Support/CrossOver/Bottles/Jagannatha Hora Vedic Astrology Software}"
WINE_TEMP="${WINE_PREFIX}/drive_c/windows/temp"
AHK_EXE="${AHK_EXE:-${WINE_PREFIX}/drive_c/Program Files/AutoHotkey/AutoHotkey.exe}"
WINE_BIN="/Applications/CrossOver.app/Contents/SharedSupport/CrossOver/CrossOver-Hosted Application/wine"
AHK_SCRIPT="C:\\windows\\temp\\extract_param.ahk"
PARSER="$SCRIPTS_DIR/jhora_parse.py"

NAME="" DATE="" TIME="" LAT="" LON="" TZ="" PLACE="Unknown"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --name)  NAME="$2";  shift 2 ;;
    --date)  DATE="$2";  shift 2 ;;
    --time)  TIME="$2";  shift 2 ;;
    --lat)   LAT="$2";   shift 2 ;;
    --lon)   LON="$2";   shift 2 ;;
    --tz)    TZ="$2";    shift 2 ;;
    --place) PLACE="$2"; shift 2 ;;
    *) echo "Unknown arg: $1"; exit 1 ;;
  esac
done

if [[ -z "$NAME" || -z "$DATE" || -z "$TIME" || -z "$LAT" || -z "$LON" || -z "$TZ" ]]; then
  echo "ERROR: --name --date --time --lat --lon --tz all required"
  exit 1
fi

YEAR=$(echo "$DATE" | cut -d- -f1)
MONTH=$(echo "$DATE" | cut -d- -f2 | sed 's/^0//')
DAY=$(echo "$DATE"   | cut -d- -f3 | sed 's/^0//')

HOUR=$(echo "$TIME" | cut -d: -f1 | sed 's/^0//')
MIN=$(echo  "$TIME" | cut -d: -f2 | sed 's/^0*//')
[[ -z "$MIN" ]] && MIN=0
TIME_DMMFF=$(python3 -c "print(f'{int(\"$HOUR\") + int(\"$MIN\")/100:.6f}')")

TZ_SIGN=$(python3 -c "v=float('$TZ'); print('-' if v>=0 else '')")
TZ_ABS=$(python3 -c "v=abs(float('$TZ')); h=int(v); m=round((v-h)*60); print(f'{h}.{m:02d}0000')")
TZ_VAL="${TZ_SIGN}${TZ_ABS}"

LAT_DMMFF=$(python3 -c "
v=abs(float('$LAT')); d=int(v); m=(v-d)*60; sign='' if float('$LAT')>=0 else '-'
print(f'{sign}{d}.{int(m):02d}{round((m-int(m))*60):02d}00')
")

LON_DMMFF=$(python3 -c "
v=abs(float('$LON')); d=int(v); m=(v-d)*60; sign='-' if float('$LON')>=0 else ''
print(f'{sign}{d}.{int(m):02d}{round((m-int(m))*60):02d}00')
")

JHD_CONTENT="${MONTH}
${DAY}
${YEAR}
${TIME_DMMFF}
${TZ_VAL}
${LON_DMMFF}
${LAT_DMMFF}
0.000000
${TZ_VAL}
${TZ_VAL}
0
0
${NAME}
${PLACE}
1
1013.250000
20.000000
0"

if [[ ! -f "$WINE_TEMP/extract_param.ahk" ]] || \
   ! cmp -s "$SCRIPTS_DIR/extract_param.ahk" "$WINE_TEMP/extract_param.ahk"; then
  cp "$SCRIPTS_DIR/extract_param.ahk" "$WINE_TEMP/extract_param.ahk"
fi

echo "$JHD_CONTENT" > "$WINE_TEMP/${NAME}.jhd"
WIN_JHD="C:\\windows\\temp\\${NAME}.jhd"

echo "Extracting panchanga for $NAME ($DATE $TIME)..."
CX_BOTTLE="Jagannatha Hora Vedic Astrology Software" \
WINEPREFIX="$WINE_PREFIX" \
"$WINE_BIN" "$AHK_EXE" "$AHK_SCRIPT" "$WIN_JHD" 2>/dev/null

python3 "$PARSER" "$OUT_DIR"
echo "Done: $OUT_DIR/$NAME/"
