import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import pytz
import io

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

def is_valid_name(text):
    if not text: return False
    if text.replace('.', '').isdigit(): return False
    if text.upper() in ['P1', 'P2', 'F1', 'F2', 'CAP', 'FO', 'DUTY', 'STD', 'STA', 'NAME', 'CREW ID', 'SPECIAL DUTY CODE', 'TVL', 'FLY', 'INT']: return False
    if len(text) < 2: return False
    return True

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

def parse_time_input(t_str):
    t_str = str(t_str).strip()
    if ':' in t_str:
        try:
            h, m = map(int, t_str.split(':'))
            return h, m
        except: return None
    elif len(t_str) == 4 and t_str.isdigit():
        try:
            h = int(t_str[:2])
            m = int(t_str[2:])
            return h, m
        except: return None
    elif len(t_str) == 3 and t_str.isdigit():
        try:
            h = int(t_str[:1])
            m = int(t_str[1:])
            return h, m
        except: return None
    return None

def get_smart_date(base_date, input_day):
    try:
        input_day = int(input_day)
        target_date = base_date.replace(day=input_day, hour=0, minute=0, second=0)
        return target_date
    except:
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


# --- UI ---
st.set_page_config(page_title="KAL Roster to CSV Ver 1.3", page_icon="✈️")
st.title("✈️ KAL Roster to CSV Ver 1.3")

# 사용법 배너
with st.expander("📘 사용법 읽어보기 (Click)"):
    st.markdown("""
    **1. 스케줄 파일 준비 (iFlight CWP)**
    * iFlight(CWP) 웹사이트에서 **월간 스케줄표**를 **엑셀(Excel)**로 다운로드하세요.
    * *주의: 모바일 앱(App)에서는 안 됩니다. PC나 모바일 웹 브라우저를 이용하세요.*

    **2. 파일 업로드**
    * 아래 **[Browse files]** 버튼을 눌러 다운받은 파일을 올리세요.

    **3. 근무 입력 (선택)**
    * **직책:** 기장/부기장 선택 (체류비 계산용)
    * **리저브:** 날짜만 입력 (예: `01`, `05`)
    * **스탠바이:** 날짜와 시간 입력 (예: `05`일 `0900` ~ `1500`)

    **4. 캘린더에 넣기**
    * 📱 **모바일:** **[📅 iCal 다운로드]** -> 파일 실행 -> **'모두 추가'** (저장할 캘린더 계정 확인!)
    * 💻 **PC:** **[📁 CSV 다운로드]** -> 구글 캘린더 웹사이트 -> 설정 -> 가져오기
    """)

rank = st.radio(
    "직책 선택 (Per Diem 계산용)", 
    ["FO (부기장)", "CAP (기장)"], 
    index=0, 
    horizontal=True
)
is_cap = True if "CAP" in rank else False

up_file = st.file_uploader("로스터 파일 (CSV, XLSX) 업로드", type=['csv', 'xlsx'])

# --- 1. 리저브 입력 ---
c1, c2 = st.columns([3, 1], vertical_alignment="bottom")
with c1:
    res_input = st.text_input("리저브(Reserve) 날짜 (예: 28, 01, 02)", help="해당 월의 날짜를 입력하세요.")
with c2:
    if res_input: st.success("✅ 입력됨")
    else: st.info("⬅️ 엔터")

# --- 2. 스탠바이 입력 ---
st.markdown("---")
st.write("**스탠바이(STBY) 입력** (예: 0900 또는 09:00)")

stby_data = [] 

# STBY Row 1
c_s1_1, c_s1_2, c_s1_3, c_s1_4 = st.columns([1, 1.5, 1.5, 1.5], vertical_alignment="bottom")
with c_s1_1: d1 = st.text_input("일(Day)", key="d1", placeholder="05")
with c_s1_2: s1 = st.text_input("시작", key="s1", placeholder="0900")
with c_s1_3: e1 = st.text_input("종료", key="e1", placeholder="1500")
with c_s1_4:
    if d1 and s1 and e1: st.success("✅ 완료")
    else: st.info("⬅️ 엔터")
if d1 and s1 and e1: stby_data.append((d1, s1, e1))

# STBY Row 2
c_s2_1, c_s2_2, c_s2_3, c_s2_4 = st.columns([1, 1.5, 1.5, 1.5], vertical_alignment="bottom")
with c_s2_1: d2 = st.text_input("일(Day)2", key="d2", placeholder="12", label_visibility="hidden")
with c_s2_2: s2 = st.text_input("시작2", key="s2", placeholder="1400", label_visibility="hidden")
with c_s2_3: e2 = st.text_input("종료2", key="e2", placeholder="2000", label_visibility="hidden")
with c_s2_4:
    if d2 and s2 and e2: st.success("✅ 완료")
    elif d2 or s2 or e2: st.info("⬅️ 엔터")
if d2 and s2 and e2: stby_data.append((d2, s2, e2))

# STBY Row 3
c_s3_1, c_s3_2, c_s3_3, c_s3_4 = st.columns([1, 1.5, 1.5, 1.5], vertical_alignment="bottom")
with c_s3_1: d3 = st.text_input("일(Day)3", key="d3", placeholder="20", label_visibility="hidden")
with c_s3_2: s3 = st.text_input("시작3", key="s3", placeholder="2200", label_visibility="hidden")
with c_s3_3: e3 = st.text_input("종료3", key="e3", placeholder="0200", label_visibility="hidden")
with c_s3_4:
    if d3 and s3 and e3: st.success("✅ 완료")
    elif d3 or s3 or e3: st.info("⬅️ 엔터")
if d3 and s3 and e3: stby_data.append((d3, s3, e3))


if up_file:
    flight_dict = {} 
    current_key = None 

    try:
        if up_file.name.endswith('.csv'):
            df = pd.read_csv(up_file, header=None)
        else:
            df = pd.read_excel(up_file, header=None)
        
        h_idx = -1
        for i, row in df.iterrows():
            if row.astype(str).str.contains('Flight/Activity').any():
                h_idx = i
                break
        
        if h_idx == -1:
            st.error("'Flight/Activity' 행을 찾을 수 없습니다.")
            st.stop()

        df.columns = df.iloc[h_idx].apply(clean_str)
        data = df.iloc[h_idx+1:].reset_index(drop=True)
        
        sdc_col_name = None
        for col in df.columns:
            if "special" in str(col).lower() and "duty" in str(col).lower():
                sdc_col_name = col
                break
        
        duty_col_name = None
        for col in df.columns:
            if str(col).strip().lower() == "duty":
                duty_col_name = col
                break
        
        int_col_name = None
        for col in df.columns:
            if str(col).strip().upper() == "INT":
                int_col_name = col
                break

        for _, row in data.iterrows():
            f_val = clean_str(row.get('Flight/Activity', ''))
            
            if f_val == 'Flight/Activity' or 'page' in f_val.lower():
                continue

            if f_val and not f_val.startswith('Total'):
                try:
                    std_str = str(row['STD'])
                    if len(std_str) < 10: continue 
                    
                    dep_port = clean_str(row.get('From'))
                    arr_port = clean_str(row.get('To'))
                    
                    std_utc = get_utc_time(row['STD'], dep_port)
                    sta_utc = get_utc_time(row['STA'], arr_port)
                    
                    key = (f_val, std_str) 
                    
                    if key not in flight_dict:
                        flight_dict[key] = {
                            "flt": f_val,
                            "dep": dep_port,
                            "arr": arr_port,
                            "std_str": str(row['STD']),
                            "sta_str": str(row['STA']),
                            "std_utc": std_utc,
                            "sta_utc": sta_utc,
                            "std_kst": std_utc.astimezone(KST),
                            "ac": clean_str(row.get('A/C')),
                            "crews": []
                        }
                    current_key = key
                except: pass
            
            # Crew 및 Instructor 추출
            if current_key:
                c_id = clean_str(row.get('Crew ID'))
                r_val = clean_str(row.get('Acting rank'))
                is_instructor_row = (r_val == 'INT')
                
                if int_col_name:
                    int_val = clean_str(row.get(int_col_name))
                    if is_valid_name(int_val):
                         crew_str = f"{int_val} (INT)"
                         if crew_str not in flight_dict[current_key]['crews']:
                            flight_dict[current_key]['crews'].append(crew_str)

                if (c_id and c_id.isdigit()) or is_instructor_row:
                    name = ""
                    raw_name = clean_str(row.get('Name'))
                    if is_valid_name(raw_name):
                        name = raw_name
                    else:
                        row_vals = [clean_str(x) for x in row.values]
                        if c_id in row_vals:
                            idx = row_vals.index(c_id)
                            for i in range(1, 6):
                                if idx + i < len(row_vals):
                                    candidate = row_vals[idx + i]
                                    if is_valid_name(candidate):
                                        name = candidate
                                        break
                    if name:
                        duty_val = ""
                        if duty_col_name: duty_val = clean_str(row.get(duty_col_name))
                        
                        if duty_val.upper() == "TVL": p_val = "Ex"
                        else: p_val = clean_str(row.get('PIC code'))
                        
                        sdc = ""
                        if sdc_col_name: sdc = clean_str(row.get(sdc_col_name))
                        if not sdc:
                            last_val = clean_str(row.iloc[-1])
                            if last_val and len(last_val) < 20 and not last_val.isdigit() and last_val != name:
                                sdc = last_val

                        info_parts = [x for x in [c_id, r_val, p_val] if x]
                        info_str = ", ".join(info_parts)
                        sdc_str = f" [{sdc}]" if sdc else ""
                        
                        crew_str = f"{name} ({info_str}){sdc_str}"
                        if crew_str not in flight_dict[current_key]['crews']:
                            flight_dict[current_key]['crews'].append(crew_str)

        sorted_flights = sorted(flight_dict.values(), key=lambda x: x['std_utc'])

        rots = []
        t_rot = []
        for f in sorted_flights:
            if f['dep'] in ['ICN', 'GMP'] and t_rot:
                 rots.append(t_rot); t_rot = []
            t_rot.append(f)
            if f['arr'] in ['ICN', 'GMP']:
                rots.append(t_rot); t_rot = []
        if t_rot: rots.append(t_rot)

        all_events = []
        csv_rows = []
        
        if sorted_flights:
            base_date_ref = sorted_flights[0]['std_kst']
        else:
            base_date_ref = datetime.now(KST)
        
        # 1. 리저브
        res_cnt = 0
        if res_input:
            for day_str in res_input.split(','):
                try:
                    day = int(day_str.strip())
                    start_dt = base_date_ref.replace(day=day, hour=0, minute=0, second=0)
                    end_dt = start_dt + timedelta(hours=23, minutes=59)
                    
                    csv_rows.append({
                        "Subject": "Reserve",
                        "Start Date": start_dt.strftime('%Y-%m-%d'),
                        "Start Time": "00:00",
                        "End Date": end_dt.strftime('%Y-%m-%d'),
                        "End Time": "23:59",
                        "Description": "Reserve Schedule (All Day)",
                        "Location": "ICN"
                    })
                    all_events.append({
                        "subject": "Reserve",
                        "start_dt": start_dt,
                        "end_dt": end_dt,
                        "description": "Reserve Schedule (All Day)",
                        "location": "ICN"
                    })
                    res_cnt += 1
                except: pass

        # 2. 스탠바이
        stby_cnt = 0
        if stby_data:
            for s_day, s_start, s_end in stby_data:
                try:
                    day = int(s_day.strip())
                    sh, sm = parse_time_input(s_start)
                    eh, em = parse_time_input(s_end)
                    if sh is not None and eh is not None:
                        start_dt = base_date_ref.replace(day=day, hour=sh, minute=sm, second=0)
                        end_dt = base_date_ref.replace(day=day, hour=eh, minute=em, second=0)
                        
                        if end_dt < start_dt: 
                            end_dt += timedelta(days=1)
                        
                        csv_rows.append({
                            "Subject": "STBY",
                            "Start Date": start_dt.strftime('%Y-%m-%d'),
                            "Start Time": start_dt.strftime('%H:%M'),
                            "End Date": end_dt.strftime('%Y-%m-%d'),
                            "End Time": end_dt.strftime('%H:%M'),
                            "Description": "Standby Duty",
                            "Location": "ICN"
                        })
                        all_events.append({
                            "subject": "STBY",
                            "start_dt": start_dt,
                            "end_dt": end_dt,
                            "description": "Standby Duty",
                            "location": "ICN"
                        })
                        stby_cnt += 1
                except: pass

        # 3. 비행 및 시뮬레이터
        for r in rots:
            f1, fL = r[0], r[-1]
            is_sim = any(k in f1['flt'].upper() for k in SIM_KEYWORDS)
            
            if is_sim:
                subject = f"{f1['flt']}, {f1['dep']} {f1['std_str'][11:]}~{fL['sta_str'][11:]}"
            else:
                route_path = ",".join([f['arr'] for f in r])
                subject = f"{f1['flt']}, {f1['dep']} {f1['std_str'][11:]} {route_path} {fL['sta_str'][11:]}"
            
            memo = []
            off = timedelta(hours=1, minutes=35) if f1['dep']=='ICN' else timedelta(hours=1, minutes=40)
            show_up_dt = f1['std_kst'] - off
            
            total_block_seconds = 0
            for f in r:
                if f['sta_utc'] and f['std_utc']:
                    total_block_seconds += (f['sta_utc'] - f['std_utc']).total_seconds()

            for i, f in enumerate(r):
                memo.append(f"★ {f['dep']}-{f['arr']} ★")
                if i == 0 and not is_sim:
                    memo.append(f"{f['dep']} Show Up : {show_up_dt.strftime('%Y-%m-%d %H:%M')} (KST)")
                
                blk_dur = "N/A"
                if f['sta_utc'] and f['std_utc']:
                    blk_dur = format_dur(f['sta_utc'] - f['std_utc'])
                
                std_utc_str = f['std_utc'].strftime('%H:%M') if f['std_utc'] else "?"
                sta_utc_str = f['sta_utc'].strftime('%H:%M') if f['sta_utc'] else "?"
                
                memo.append(f"{f['flt']}: {f['std_str']} (UTC {std_utc_str})")
                memo.append(f"-> {f['sta_str']} (UTC {sta_utc_str}) (A/C: {f['ac']})")
                memo.append(f"Block Time : {blk_dur}")
                
                if i < len(r)-1:
                    next_f = r[i+1]
                    if next_f['std_utc'] and f['sta_utc']:
                        stay_diff = next_f['std_utc'] - f['sta_utc']
                        stay_h = stay_diff.total_seconds() / 3600
                        if stay_h < 4:
                            total_h = total_block_seconds / 3600
                            pd_val = 60 if is_cap and total_h >=5 else (50 if is_cap else (41 if total_h >=5 else 35))
                            memo.append(f"Quick Turn (Per Diem : ${pd_val:.2f})")
                        else:
                            rate, currency = get_rate_info(f['arr'])
                            pd_val = stay_h * rate
                            memo.append(f"Stay Hours : {format_dur(stay_diff)} (Per Diem : {pd_val:.2f} {currency})")
                
                # [수정] 크루 헤더에서 별표 제거
                memo.append(f"\n[{f['flt']} Crew]")
                memo.extend(f['crews'])
                memo.append("")

            # CSV용 데이터
            csv_rows.append({
                "Subject": subject,
                "Start Date": f1['std_str'][:10],
                "Start Time": f1['std_str'][11:],
                "End Date": fL['sta_str'][:10],
                "End Time": fL['sta_str'][11:],
                "Description": "\n".join(memo),
                "Location": f"{f1['dep']} -> {fL['arr']}"
            })
            
            # ICS용 데이터
            start_dt_obj = f1['std_kst']
            if fL['sta_utc'] and f1['std_utc']:
                duration = fL['sta_utc'] - f1['std_utc']
                end_dt_obj = start_dt_obj + duration
            else:
                end_dt_obj = start_dt_obj + timedelta(hours=10)

            all_events.append({
                "subject": subject,
                "start_dt": start_dt_obj,
                "end_dt": end_dt_obj,
                "description": "\n".join(memo),
                "location": f"{f1['dep']} -> {fL['arr']}"
            })

        st.success("✅ 변환 완료!")
        st.caption(f"상세: 비행 {len(rots)}개, 리저브 {res_cnt}개, 스탠바이 {stby_cnt}개 포함됨")
        
        col_down1, col_down2 = st.columns(2)
        
        # 1. CSV
        res_df = pd.DataFrame(csv_rows)
        csv_buffer = res_df.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig')
        
        with col_down1:
            st.download_button(
                label="📁 CSV 다운로드 (PC)",
                data=csv_buffer,
                file_name="Google_Calendar.csv",
                mime="text/csv"
            )

        # 2. ICS
        ics_text = generate_ics(all_events)
        with col_down2:
            st.download_button(
                label="📅 iCal 다운로드 (모바일)",
                data=ics_text,
                file_name="Roster.ics",
                mime="text/calendar"
            )

    except Exception as e:
        st.error(f"오류가 발생했습니다: {e}")