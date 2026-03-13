import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import pytz
import io
import re

# --- 1. 공항별 시간대(Timezone) 설정 ---
AIRPORT_TZ = {
    'ICN': 'Asia/Seoul', 'GMP': 'Asia/Seoul', 'PUS': 'Asia/Seoul', 'CJU': 'Asia/Seoul',
    'NRT': 'Asia/Tokyo', 'HND': 'Asia/Tokyo', 'KIX': 'Asia/Tokyo', 'NGO': 'Asia/Tokyo', 'FUK': 'Asia/Tokyo', 'CTS': 'Asia/Tokyo',
    'PEK': 'Asia/Shanghai', 'PVG': 'Asia/Shanghai', 'CAN': 'Asia/Shanghai', 'SZX': 'Asia/Shanghai', 'HKG': 'Asia/Hong_Kong',
    'TPE': 'Asia/Taipei', 'MNL': 'Asia/Manila', 'SIN': 'Asia/Singapore', 'KUL': 'Asia/Kuala_Lumpur', 'BKK': 'Asia/Bangkok',
    'SGN': 'Asia/Ho_Chi_Minh', 'HAN': 'Asia/Bangkok', 'DPS': 'Asia/Makassar', 'CGK': 'Asia/Jakarta',
    'GUM': 'Pacific/Guam', 'SYD': 'Australia/Sydney', 'BNE': 'Australia/Brisbane', 'AKL': 'Pacific/Auckland',
    'DEL': 'Asia/Kolkata', 'BOM': 'Asia/Kolkata', 'MLE': 'Indian/Maldives', 'DXB': 'Asia/Dubai', 'IST': 'Europe/Istanbul',
    'LAX': 'America/Los_Angeles', 'SFO': 'America/Los_Angeles', 'SEA': 'America/Los_Angeles', 'LAS': 'America/Los_Angeles', 
    'YVR': 'America/Vancouver', 'ANC': 'America/Anchorage', 'HNL': 'Pacific/Honolulu',
    'JFK': 'America/New_York', 'BOS': 'America/New_York', 'ATL': 'America/New_York', 'IAD': 'America/New_York', 
    'YYZ': 'America/Toronto', 'DTW': 'America/Detroit', 'ORD': 'America/Chicago', 'DFW': 'America/Chicago', 'MIA': 'America/New_York',
    'SCL': 'America/Santiago', 'LHR': 'Europe/London', 'CDG': 'Europe/Paris', 'FRA': 'Europe/Berlin', 'FCO': 'Europe/Rome', 
    'MXP': 'Europe/Rome', 'AMS': 'Europe/Amsterdam', 'ZRH': 'Europe/Zurich', 'VIE': 'Europe/Vienna', 
    'PRG': 'Europe/Prague', 'BUD': 'Europe/Budapest', 'MAD': 'Europe/Madrid', 'BCN': 'Europe/Madrid',
    'LIS': 'Europe/Lisbon', 'ZAG': 'Europe/Zagreb', 'VVO': 'Asia/Vladivostok', 'TAS': 'Asia/Tashkent', 'ALA': 'Asia/Almaty'
}

KOREA_PORTS = ['ICN', 'GMP', 'PUS', 'CJU', 'TAE', 'KWJ', 'RSU', 'USN', 'KUV', 'WJU', 'YNY']
KST = pytz.timezone('Asia/Seoul')
UTC = pytz.utc

PER_DIEM_RATES = {
    "SFO": 4.21, "LAX": 4.01, "LAS": 4.01, "ANC": 3.81, "SEA": 3.81, "ATL": 3.61, "BOS": 3.61, "JFK": 3.61, "ORD": 3.41, "HNL": 3.41,
    "DFW": 3.21, "MIA": 3.21, "LCK": 3.21, "IAD": 3.01, "SCL": 3.19, "YVR": 3.19, "YYZ": 3.00, "ZRH": 4.16, "LHR": 3.86, "FCO": 3.71,
    "FRA": 3.41, "VIE": 3.41, "CDG": 3.26, "AMS": 3.26, "MXP": 3.26, "MAD": 3.26, "BCN": 3.11, "IST": 3.01, "SIN": 2.96, "BKK": 2.80,
    "DEL": 2.50, "BOM": 2.50, "MLE": 2.50, "KUL": 2.32, "SGN": 2.32, "GUM": 3.28, "HKG": 2.35, "TPE": 2.20, "MFM": 2.20, "ULN": 1.95, "DXB": 2.59
}

EURO_CITIES = [
    "LHR", "CDG", "FRA", "FCO", "MXP", "ZRH", "VIE", "PRG", "BUD", "MAD", "BCN", "AMS", "IST", "LIS", "ZAG",
    "VVO", "TAS", "ALA", "SVO", "LED"
]

SIM_KEYWORDS = ["RECPT", "RECPC", "UPRT"]

# --- 헬퍼 함수 ---
def clean_str(val):
    if pd.isna(val): return ""
    s = str(val).strip()
    if s.lower() == 'nan': return ""
    return s

def get_timezone(airport_code):
    tz_name = AIRPORT_TZ.get(clean_str(airport_code), 'Asia/Seoul')
    try: return pytz.timezone(tz_name)
    except: return KST

def get_utc_time(dt_str, airport_code):
    try:
        local_tz = get_timezone(airport_code)
        local_dt = datetime.strptime(str(dt_str), '%Y-%m-%d %H:%M')
        return local_tz.localize(local_dt).astimezone(UTC)
    except: return None

def get_rate_info(city):
    city = clean_str(city)
    currency = "$"
    rate = 2.16
    if city in PER_DIEM_RATES: rate = PER_DIEM_RATES[city]
    else:
        if any(jp in city for jp in ["NRT", "HND", "KIX", "NGO", "FUK", "CTS"]): rate = 2.72
        elif any(cn in city for cn in ["PEK", "PVG", "CAN", "SZX"]): rate = 1.95
    if city in EURO_CITIES: currency = "€"
    return rate, currency

def format_dur(delta):
    total_seconds = int(delta.total_seconds())
    if total_seconds < 0: total_seconds = abs(total_seconds)
    h = total_seconds // 3600
    m = (total_seconds % 3600) // 60
    return f"{h}h {m:02d}m"

def get_smart_date(base_date, input_day):
    # base_date is datetime, input_day is int
    try:
        return base_date.replace(day=input_day, hour=0, minute=0, second=0, microsecond=0)
    except ValueError:
        return base_date

def generate_ics(events):
    ics_lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//KAL Roster//KR",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH"
    ]
    
    dt_now = datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')
    
    for evt in events:
        start_dt = evt['start_dt'].astimezone(UTC).strftime('%Y%m%dT%H%M%SZ')
        end_dt = evt['end_dt'].astimezone(UTC).strftime('%Y%m%dT%H%M%SZ')
        desc = evt['description'].replace('\n', '\\n')
        
        ics_lines.append("BEGIN:VEVENT")
        ics_lines.append(f"DTSTART:{start_dt}")
        ics_lines.append(f"DTEND:{end_dt}")
        ics_lines.append(f"DTSTAMP:{dt_now}")
        ics_lines.append(f"UID:{start_dt}-{evt['subject'].replace(' ', '')}@kalroster")
        ics_lines.append(f"SUMMARY:{evt['subject']}")
        ics_lines.append(f"DESCRIPTION:{desc}")
        ics_lines.append(f"LOCATION:{evt['location']}")
        ics_lines.append("END:VEVENT")
        
    ics_lines.append("END:VCALENDAR")
    return "\r\n".join(ics_lines)

# --- 파싱 로직 ---
def parse_detailed_schedule(text):
    flights_dict = {}
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    
    current_key = None
    i = 0
    while i < len(lines):
        line = lines[i]
        
        # 체크: 비행편명 또는 시뮬레이터명 (예: KE867, DH938, 78RECPC2)
        if re.match(r'^[A-Z0-9]{2,8}$', line) and i + 4 < len(lines):
            flt = line
            dep = lines[i+1]
            std_str = lines[i+2]
            arr = lines[i+3]
            sta_str = lines[i+4]
            # 시뮬레이터는 기종(A/C) 필드가 생략될 수 있으므로, 날짜 패턴이 맞으면 비행편으로 인식
            if re.match(r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$', std_str) and re.match(r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$', sta_str):
                std_utc = get_utc_time(std_str, dep)
                sta_utc = get_utc_time(sta_str, arr)
                
                # A/C 판별 (만약 다음 라인이 CAP/FO 같은 Rank면 A/C가 생략된 것)
                ac = ""
                idx = i + 5
                if idx < len(lines) and lines[idx] not in ['CAP', 'FO', 'FS', 'CS', 'SS', 'PUR', 'INT', 'CC']:
                    ac = lines[idx]
                    i = idx + 1
                else:
                    i = idx
                    
                key = (flt, std_str)
                if key not in flights_dict:
                    flights_dict[key] = {
                        "flt": flt,
                        "dep": dep,
                        "arr": arr,
                        "std_str": std_str,
                        "sta_str": sta_str,
                        "std_utc": std_utc,
                        "sta_utc": sta_utc,
                        "std_kst": std_utc.astimezone(KST) if std_utc else None,
                        "ac": ac,
                        "crews": []
                    }
                current_key = key
                continue
        
        # 비행편 내 크루 파싱 (현재 키가 있을 때만)
        if current_key:
            # Rank 키워드 등장 시 (CAP, FO, FS, CS 등 역할들. 주로 CAP, FO임)
            if line in ['CAP', 'FO', 'FS', 'CS', 'SS', 'PUR', 'INT', 'CC']:
                rank = line
                idx = i + 1
                
                duty = ""
                pic = ""
                crew_id = ""
                
                # Duty 파싱 (FLY, TVL 등이 없는 시뮬레이터 세션 대응)
                if idx < len(lines) and not re.match(r'^\d{6,7}$', lines[idx]) and not re.match(r'^[A-Z]\d{6}$', lines[idx]):
                    duty = lines[idx]
                    idx += 1
                
                # PIC 파싱 (P1, F2 등)
                if idx < len(lines) and re.match(r'^[PF]\d$', lines[idx]):
                    pic = lines[idx]
                    idx += 1
                elif idx < len(lines) and lines[idx] in ['GDTVL', 'TVL']:
                    # 가끔 GDTVL 같은 코드가 나오는 경우 건너뜀
                    idx += 1
                    
                # 사번 (Crew ID) 파싱
                if idx < len(lines) and (re.match(r'^\d{6,7}$', lines[idx]) or re.match(r'^[A-Z]\d{6}$', lines[idx])):
                    crew_id = lines[idx]
                    idx += 1
                    
                name = lines[idx] if idx < len(lines) else ""
                idx += 1
                
                # 비고항목 (Comment/Special Duty Code) 추가 체크 (ex: 787OE, 30MEARLY, FLEET CHNG)
                comment = ""
                if idx < len(lines):
                    next_line = lines[idx]
                    # 다음 줄이 직급(CAP, FO 등)이나 비행명/공항/날짜형식이 아니면 코멘트로 합침
                    if next_line not in ['CAP', 'FO', 'FS', 'CS', 'SS', 'PUR', 'INT', 'CC', 'Flight/Activity'] and not re.match(r'^[A-Z0-9]{2,8}$', next_line) and not re.match(r'^[A-Z]{3}$', next_line) and not re.match(r'^\d{4}-\d{2}-\d{2}', next_line):
                        comment = next_line
                        idx += 1
                        
                info_str = f"{crew_id}, {rank}, {pic}" if pic else f"{crew_id}, {rank}"
                if comment:
                    info_str += f" [{comment}]"

                crew_str = f"{name} ({info_str})"
                if duty == 'TVL':
                    crew_str += " [TVL]"
                    
                if crew_str not in flights_dict[current_key]['crews']:
                    flights_dict[current_key]['crews'].append(crew_str)
                
                i = idx
                continue
                
        i += 1
        
    return sorted(flights_dict.values(), key=lambda x: x['std_utc'] if x['std_utc'] else UTC.localize(datetime.min))

def parse_calendar_schedule(text):
    events = []
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    
    current_day = None
    for line in lines:
        # 달력 밑에 있는 범례 문구 무시하기
        if "Flight (FLY)" in line or "Copyright" in line:
            break
            
        if re.match(r'^\d{2}$', line):
            current_day = int(line)
        elif current_day is not None:
            upper_line = line.upper()
            if 'RESERVE' in upper_line or 'RSV' in upper_line:
                events.append({"type": "RSV", "day": current_day, "text": "Reserve"})
            elif 'STBY' in upper_line:
                events.append({"type": "STBY", "day": current_day, "text": upper_line})
            else:
                # SAFE_MTGMP 09:00 - GMP 16:30 같은 훈련/미팅 추출
                match = re.search(r'([A-Za-z0-9_]+)?[A-Z]{3}\s+(\d{2}:\d{2})\s*-\s*[A-Z]{3}\s+(\d{2}:\d{2})', line)
                if match:
                    subject = match.group(1) if match.group(1) else "Training"
                    start_time = match.group(2)
                    end_time = match.group(3)
                    
                    # 정규 비행편(KE032 등)은 이미 세미 스케줄에서 파싱하므로 달력쪽 훈련 추출에선 제외
                    if not re.match(r'^KE\d+', subject) and not re.match(r'^DH\d+', subject):
                        events.append({
                            "type": "TRG", 
                            "day": current_day, 
                            "text": f"{subject} {start_time}~{end_time}",
                            "subject": subject,
                            "start": start_time,
                            "end": end_time
                        })
                
    return events

def parse_calendar_flights(text):
    flights = []
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    
    current_day = None
    for line in lines:
        if "Flight (FLY)" in line or "Copyright" in line:
            break
            
        if re.match(r'^\d{2}$', line):
            current_day = int(line)
        elif current_day is not None:
            match = re.search(r'^([A-Z0-9]{2,8})([A-Z]{3})\s*(?:\d{2}:\d{2})?\s*-\s*([A-Z]{3})', line)
            if match:
                flt = match.group(1)
                dep = match.group(2)
                arr = match.group(3)
                flights.append({
                    "day": current_day,
                    "flt": flt,
                    "dep": dep,
                    "arr": arr
                })
    return flights


# --- UI ---
st.set_page_config(page_title="KAL Roster to Calendar Ver 2.0", page_icon="✈️", layout="centered")
st.title("✈️ KAL Roster to Calendar Ver 2.0")

with st.expander("📘 새로운 V2 사용법 (100% 모바일 복붙 방식)", expanded=True):
    st.markdown("""
    **더 이상 엑셀 파일이 필요 없습니다! 화면 두 개만 복사해서 붙여넣으세요.**
    
    📱 **모든 기기(아이폰, 갤럭시)에서 완벽히 지원됩니다.**
    
    **1. 마이스케줄 (달력) 복사**
    * 모바일 브라우저에서 '마이스케줄' 화면 전체를 쭉 드래그해서 모두 복사합니다.
    * 아래 **[1. 마이스케줄 화면 복붙]** 칸에 붙여넣습니다. (리저브, 데이오프 날짜을 자동 감지합니다.)

    **2. 크루 로스터 (세부 스케줄) 복사**
    * 달력 화면 메뉴 중 'Crew Roster'를 누르고 'HTML' 포맷으로 띄워진 비행 세부 화면에서, 텍스트 전체를 복사합니다.
    * 아래 **[2. 상세 스케줄 HTML 복붙]** 칸에 붙여넣습니다. (비행시간 및 크루 명단을 감지합니다.)

    **3. 변환하기**
    * [🚀 캘린더 파일 변환하기] 버튼을 누르면 즉시 캘린더 일정이 완성됩니다!
    """)

rank_choice = st.radio(
    "본인 직책 (Per Diem 계산용)", 
    ["FO (부기장)", "CAP (기장)"], 
    index=0, 
    horizontal=True
)
is_cap = True if "CAP" in rank_choice else False

st.markdown("---")
# 텍스트 입력 칸
cal_text = st.text_area("1️⃣ 마이스케줄 달력 화면 복붙 (리저브/스탠바이 파악용)", height=150, placeholder="여기에 달력 텍스트를 붙여넣으세요...")
det_text = st.text_area("2️⃣ 상세 스케줄 HTML 화면 복붙 (비행 및 크루 파악용)", height=250, placeholder="여기에 비행 세부 텍스트를 붙여넣으세요...")

if st.button("🚀 캘린더 파일 변환하기", type="primary"):
    if not cal_text and not det_text:
        st.error("스케줄 텍스트를 하나라도 붙여넣어 주세요!")
        st.stop()
        
    try:
        # 1. 비행 세부 파싱
        sorted_flights = parse_detailed_schedule(det_text) if det_text else []
        
        # 로테이션 묶기
        rots = []
        t_rot = []
        for f in sorted_flights:
            if f['dep'] in ['ICN', 'GMP'] and t_rot:
                 rots.append(t_rot); t_rot = []
            t_rot.append(f)
            if f['arr'] in ['ICN', 'GMP']:
                rots.append(t_rot); t_rot = []
        if t_rot: rots.append(t_rot)

        # 2. 달력 데이터 파싱
        cal_events = parse_calendar_schedule(cal_text) if cal_text else []
        cal_flights = parse_calendar_flights(cal_text) if cal_text else []
        
        # 데이터 일치성 검증 (Cross Check)
        if cal_text and det_text:
            det_flts = set(f['flt'] for f in sorted_flights)
            cal_flts = set(f['flt'] for f in cal_flights)
            
            missing_in_det = cal_flts - det_flts
            missing_in_cal = det_flts - cal_flts
            
            warnings = []
            if missing_in_det:
                warnings.append(f"달력에는 **{', '.join(missing_in_det)}** 비행이 있지만, 상세 스케줄에는 없습니다.")
            if missing_in_cal:
                warnings.append(f"상세 스케줄에는 **{', '.join(missing_in_cal)}** 비행이 있지만, 달력에는 없습니다.")
                
            if warnings:
                st.warning("⚠️ **스케줄 불일치 경고!** 복사하신 두 텍스트의 비행 데이터가 완벽히 일치하지 않습니다. 복사가 중간에 잘렸는지, 빠진 월이 있는지 다시 한번 확인해 주세요.\n\n" + "\n".join([f"- {w}" for w in warnings]))
        
        # 기준 날짜 구하기 (가장 첫 비행 기준, 없으면 현재 시간)
        if sorted_flights and sorted_flights[0]['std_kst']:
            base_date_ref = sorted_flights[0]['std_kst']
        else:
            base_date_ref = datetime.now(KST)
            
        csv_rows = []
        all_ics_events = []
        
        cnt_flt = len(rots)
        cnt_rsv = 0
        cnt_stby = 0
        cnt_trg = 0
        cnt_do = 0

        # 달력 이벤트(리저브, STBY, DO 등) 추가
        flight_days = set([f['std_kst'].day for f in sorted_flights if f['std_kst']])
        det_flts_check = set([f['flt'] for f in sorted_flights])
        
        for cev in cal_events:
            day = cev['day']
            ev_type = cev['type']
            
            # 실제 스케줄(비행)이 있는 날짜에 달력의 ALM이나 DO가 겹치면 무시
            if day in flight_days and ev_type not in ['RSV', 'STBY', 'TRG']:
                continue

            target_date = get_smart_date(base_date_ref, day)
            
            if ev_type == 'RSV':
                start_dt = target_date.replace(hour=0, minute=0, second=0)
                end_dt = start_dt + timedelta(hours=23, minutes=59)
                desc = "Reserve Schedule (All Day)"
                title = "Reserve"
                cnt_rsv += 1
                
            elif ev_type == 'STBY':
                start_dt = target_date.replace(hour=9, minute=0, second=0)
                end_dt = target_date.replace(hour=15, minute=0, second=0) # 임시
                
                # STBY 0900 이런식으로 텍스트가 있다면 추출
                time_match = re.search(r'(\d{4})', cev['text'])
                if time_match:
                    hh = int(time_match.group(1)[:2])
                    mm = int(time_match.group(1)[2:])
                    start_dt = target_date.replace(hour=hh, minute=mm, second=0)
                    end_dt = start_dt + timedelta(hours=6) # 기본 6시간 가정
                    
                desc = "Standby Duty"
                title = "STBY"
                cnt_stby += 1
                
            elif ev_type == 'TRG':
                # 상세 스케줄에 이미 있는 시뮬레이션(예: 78RECPC2)이면 제외 (중복 생성 방지)
                if cev['subject'] in det_flts_check:
                    continue
                    
                hh_s, mm_s = map(int, cev['start'].split(':'))
                hh_e, mm_e = map(int, cev['end'].split(':'))
                
                start_dt = target_date.replace(hour=hh_s, minute=mm_s, second=0)
                end_dt = target_date.replace(hour=hh_e, minute=mm_e, second=0)
                
                if end_dt <= start_dt:
                    end_dt += timedelta(days=1)
                
                desc = f"Training/Meeting: {cev['subject']}"
                title = cev['subject']
                cnt_trg += 1
                
            else:
                # DO, ALM 등 휴일
                start_dt = target_date.replace(hour=0, minute=0, second=0)
                end_dt = start_dt + timedelta(hours=23, minutes=59)
                desc = f"Day Off ({ev_type})"
                title = ev_type
                cnt_do += 1
                
            csv_rows.append({
                "Subject": title,
                "Start Date": start_dt.strftime('%Y-%m-%d'),
                "Start Time": start_dt.strftime('%H:%M'),
                "End Date": end_dt.strftime('%Y-%m-%d'),
                "End Time": end_dt.strftime('%H:%M'),
                "Description": desc,
                "Location": "ICN" if ev_type in ['RSV', 'STBY', 'TRG'] else "Home"
            })
            all_ics_events.append({
                "subject": title,
                "start_dt": start_dt,
                "end_dt": end_dt,
                "description": desc,
                "location": "ICN" if ev_type in ['RSV', 'STBY', 'TRG'] else "Home"
            })

        # 비행 및 시뮬레이터 로테이션 추가
        for r in rots:
            f1, fL = r[0], r[-1]
            is_sim = any(k in f1['flt'].upper() for k in SIM_KEYWORDS)
            
            if is_sim:
                subject = f"{f1['flt']}, {f1['dep']} {f1['std_str'][11:]}~{fL['sta_str'][11:]}"
            else:
                route_path = ",".join([f['arr'] for f in r])
                subject = f"{f1['flt']}, {f1['dep']} {f1['std_str'][11:]} {route_path} {fL['sta_str'][11:]}"
            
            memo = []
            if f1['std_kst']:
                off = timedelta(hours=1, minutes=35) if f1['dep']=='ICN' else timedelta(hours=1, minutes=40)
                show_up_dt = f1['std_kst'] - off
            else:
                show_up_dt = None
            
            total_block_seconds = 0
            for f in r:
                if f['sta_utc'] and f['std_utc']:
                    total_block_seconds += (f['sta_utc'] - f['std_utc']).total_seconds()

            for i, f in enumerate(r):
                memo.append(f"★ {f['dep']}-{f['arr']} ★")
                if i == 0 and not is_sim and show_up_dt:
                    memo.append(f"{f['dep']} Show Up : {show_up_dt.strftime('%Y-%m-%d %H:%M')} (KST)")
                
                blk_dur = "N/A"
                if f['sta_utc'] and f['std_utc']:
                    blk_dur = format_dur(f['sta_utc'] - f['std_utc'])
                
                std_utc_str = f['std_utc'].strftime('%H:%M') if f['std_utc'] else "?"
                sta_utc_str = f['sta_utc'].strftime('%H:%M') if f['sta_utc'] else "?"
                
                memo.append(f"{f['flt']}: {f['std_str']} (UTC {std_utc_str})")
                if f['ac']:
                    memo.append(f"-> {f['sta_str']} (UTC {sta_utc_str}) (A/C: {f['ac']})")
                else:
                    memo.append(f"-> {f['sta_str']} (UTC {sta_utc_str})")
                memo.append(f"Block Time : {blk_dur}")
                
                if i < len(r)-1:
                    next_f = r[i+1]
                    is_dom = (f['dep'] in KOREA_PORTS) and (f['arr'] in KOREA_PORTS)
                    
                    if next_f['std_utc'] and f['sta_utc']:
                        stay_diff = next_f['std_utc'] - f['sta_utc']
                        stay_h = stay_diff.total_seconds() / 3600
                        
                        if is_dom:
                            dom_pay = 26000 if is_cap else 20000
                            memo.append(f"Domestic Stay : {format_dur(stay_diff)} (Allowance : {dom_pay:,} KRW)")
                        else:
                            if stay_h < 4:
                                total_h = total_block_seconds / 3600
                                pd_val = 60 if is_cap and total_h >=5 else (50 if is_cap else (41 if total_h >=5 else 35))
                                memo.append(f"Quick Turn (Per Diem : ${pd_val:.2f})")
                            else:
                                rate, currency = get_rate_info(f['arr'])
                                pd_val = stay_h * rate
                                memo.append(f"Stay Hours : {format_dur(stay_diff)} (Per Diem : {pd_val:.2f} {currency})")
                
                memo.append(f"[{f['flt']} Crew]")
                memo.extend(f['crews'])
                memo.append("")

            str_f1_date = f1['std_str'][:10] if f1['std_str'] else "2000-01-01"
            str_f1_time = f1['std_str'][11:] if f1['std_str'] else "00:00"
            str_fL_date = fL['sta_str'][:10] if fL['sta_str'] else "2000-01-01"
            str_fL_time = fL['sta_str'][11:] if fL['sta_str'] else "23:59"

            csv_rows.append({
                "Subject": subject,
                "Start Date": str_f1_date,
                "Start Time": str_f1_time,
                "End Date": str_fL_date,
                "End Time": str_fL_time,
                "Description": "\n".join(memo),
                "Location": f"{f1['dep']} -> {fL['arr']}"
            })
            
            start_dt_obj = f1['std_kst'] if f1['std_kst'] else UTC.localize(datetime.min)
            if fL['sta_utc'] and f1['std_utc']:
                duration = fL['sta_utc'] - f1['std_utc']
                end_dt_obj = start_dt_obj + duration
            else:
                end_dt_obj = start_dt_obj + timedelta(hours=10)

            all_ics_events.append({
                "subject": subject,
                "start_dt": start_dt_obj,
                "end_dt": end_dt_obj,
                "description": "\n".join(memo),
                "location": f"{f1['dep']} -> {fL['arr']}"
            })

        st.success("✅ 완벽하게 변환되었습니다!")
        st.caption(f"🗓️ 감지된 일정: 비행 로테이션 {cnt_flt}개 | 훈련 {cnt_trg}개 | 리저브 {cnt_rsv}개 | 스탠바이 {cnt_stby}개 | 휴일(DO/ALM) {cnt_do}개")
        
        col_down1, col_down2 = st.columns(2)
        
        res_df = pd.DataFrame(csv_rows)
        csv_buffer = res_df.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig')
        ics_text = generate_ics(all_ics_events)
        
        with col_down1:
            st.download_button(
                label="📁 CSV 파일 다운로드",
                data=csv_buffer,
                file_name="Crew_Calendar.csv",
                mime="text/csv",
                use_container_width=True
            )
            
        with col_down2:
            st.download_button(
                label="📅 아이폰/구글용 캘린더 (iCal)",
                data=ics_text,
                file_name="Crew_Calendar.ics",
                mime="text/calendar",
                type="primary",
                use_container_width=True
            )
            
    except Exception as e:
        import traceback
        st.error(f"오류가 발생했습니다: {e}")
        st.text(traceback.format_exc())
