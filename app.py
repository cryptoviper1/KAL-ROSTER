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

# --- 헬퍼 함수 ---
def clean_str(val):
    if pd.isna(val): return ""
    s = str(val).strip()
    if s.lower() == 'nan': return ""
    return s

def is_valid_name(text):
    if not text: return False
    if text.replace('.', '').isdigit(): return False
    if text.upper() in ['P1', 'P2', 'F1', 'F2', 'CAP', 'FO', 'DUTY', 'STD', 'STA', 'NAME', 'CREW ID', 'SPECIAL DUTY CODE', 'TVL', 'FLY']: return False
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

# [NEW] 스마트 시간 파싱 함수 (0900 -> 9, 0 / 09:00 -> 9, 0)
def parse_time_input(t_str):
    t_str = str(t_str).strip()
    # 1. 콜론이 있는 경우 (09:00)
    if ':' in t_str:
        try:
            h, m = map(int, t_str.split(':'))
            return h, m
        except: return None
    # 2. 4자리 숫자인 경우 (0900)
    elif len(t_str) == 4 and t_str.isdigit():
        try:
            h = int(t_str[:2])
            m = int(t_str[2:])
            return h, m
        except: return None
    # 3. 3자리 숫자인 경우 (900 -> 09:00)
    elif len(t_str) == 3 and t_str.isdigit():
        try:
            h = int(t_str[:1])
            m = int(t_str[1:])
            return h, m
        except: return None
    
    return None

# --- UI ---
st.set_page_config(page_title="KAL Roster to CSV", page_icon="✈️")
st.title("✈️ KAL B787 로스터 CSV 변환기 (v3.5)")

rank = st.radio(
    "직책 선택 (Per Diem 계산용)", 
    ["FO (부기장)", "CAP (기장)"], 
    index=0, 
    horizontal=True
)
is_cap = True if "CAP" in rank else False

up_file = st.file_uploader("로스터 파일 (CSV, XLSX) 업로드", type=['csv', 'xlsx'])

# --- 1. 리저브 입력 ---
c1, c2 = st.columns([3, 1])
with c1:
    res_input = st.text_input("리저브(Reserve) 날짜 (예: 01, 05)", help="입력 시 24시간 근무로 설정됩니다.")
with c2:
    st.write("") 
    st.write("") 
    if res_input: st.success("✅ 입력됨")
    else: st.info("⬅️ 엔터")

# --- 2. 스탠바이 입력 (스마트 입력 지원) ---
st.markdown("---")
st.write("**스탠바이(STBY) 입력** (예: 0900 또는 09:00)")

stby_data = [] 

# STBY Row 1
c_s1_1, c_s1_2, c_s1_3, c_s1_4 = st.columns([1, 1.5, 1.5, 1.5])
with c_s1_1: d1 = st.text_input("일(Day)", key="d1", placeholder="05")
with c_s1_2: s1 = st.text_input("시작", key="s1", placeholder="0900")
with c_s1_3: e1 = st.text_input("종료", key="e1", placeholder="1500")
with c_s1_4:
    st.write("")
    st.write("")
    if d1 and s1 and e1: st.success("✅ 완료")
    else: st.info("⬅️ 엔터")
if d1 and s1 and e1: stby_data.append((d1, s1, e1))

# STBY Row 2
c_s2_1, c_s2_2, c_s2_3, c_s2_4 = st.columns([1, 1.5, 1.5, 1.5])
with c_s2_1: d2 = st.text_input("일(Day)2", key="d2", placeholder="12", label_visibility="collapsed")
with c_s2_2: s2 = st.text_input("시작2", key="s2", placeholder="1400", label_visibility="collapsed")
with c_s2_3: e2 = st.text_input("종료2", key="e2", placeholder="2000", label_visibility="collapsed")
with c_s2_4:
    if d2 and s2 and e2: st.success("✅ 완료")
    elif d2 or s2 or e2: st.info("⬅️ 엔터")
if d2 and s2 and e2: stby_data.append((d2, s2, e2))

# STBY Row 3
c_s3_1, c_s3_2, c_s3_3, c_s3_4 = st.columns([1, 1.5, 1.5, 1.5])
with c_s3_1: d3 = st.text_input("일(Day)3", key="d3", placeholder="20", label_visibility="collapsed")
with c_s3_2: s3 = st.text_input("시작3", key="s3", placeholder="2200", label_visibility="collapsed")
with c_s3_3: e3 = st.text_input("종료3", key="e3", placeholder="0200", label_visibility="collapsed")
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
            
            if current_key:
                c_id = clean_str(row.get('Crew ID'))
                if c_id and c_id.isdigit():
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
                        r_val = clean_str(row.get('Acting rank'))
                        
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

        csv_rows = []
        base_date = sorted_flights[0]['std_kst'] if sorted_flights else datetime.now(KST)

        # [1] 리저브 처리
        res_cnt = 0
        if res_input:
            for day_str in res_input.split(','):
                try:
                    day = int(day_str.strip())
                    start_dt = base_date.replace(day=day, hour=0, minute=0, second=0)
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
                    res_cnt += 1
                except: pass

        # [2] 스탠바이 처리 (스마트 파싱 적용)
        stby_cnt = 0
        if stby_data:
            for s_day, s_start, s_end in stby_data:
                try:
                    day = int(s_day.strip())
                    # 스마트 파싱 함수 호출
                    sh, sm = parse_time_input(s_start)
                    eh, em = parse_time_input(s_end)
                    
                    if sh is not None and eh is not None:
                        start_dt = base_date.replace(day=day, hour=sh, minute=sm, second=0)
                        end_dt = base_date.replace(day=day, hour=eh, minute=em, second=0)
                        
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
                        stby_cnt += 1
                except: pass

        # [3] 비행 스케줄 처리
        for r in rots:
            f1, fL = r[0], r[-1]
            subject = f"{f1['flt']}, {f1['dep']} {f1['std_str'][11:]}, {f1['arr']}, {fL['arr']} {fL['sta_str'][11:]}"
            
            memo = []
            off = timedelta(hours=1, minutes=35) if f1['dep']=='ICN' else timedelta(hours=1, minutes=40)
            show_up_dt = f1['std_kst'] - off
            
            total_block_seconds = 0
            for f in r:
                if f['sta_utc'] and f['std_utc']:
                    total_block_seconds += (f['sta_utc'] - f['std_utc']).total_seconds()

            for i, f in enumerate(r):
                memo.append(f"★ {f['dep']}-{f['arr']} ★")
                if i == 0:
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
                
                memo.append(f"\n★ [{f['flt']} Crew] ★")
                memo.extend(f['crews'])
                memo.append("")

            csv_rows.append({
                "Subject": subject,
                "Start Date": f1['std_str'][:10],
                "Start Time": f1['std_str'][11:],
                "End Date": fL['sta_str'][:10],
                "End Time": fL['sta_str'][11:],
                "Description": "\n".join(memo),
                "Location": f"{f1['dep']} -> {fL['arr']}"
            })

        res_df = pd.DataFrame(csv_rows)
        csv_buffer = res_df.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig')

        st.info("🟦 변환 완료! 아래 버튼을 눌러 다운로드를 시작하세요.")
        st.caption(f"상세: 비행 {len(rots)}개, 리저브 {res_cnt}개, 스탠바이 {stby_cnt}개 포함됨")
        
        if st.download_button(
            label="변환된 파일 다운로드",
            data=csv_buffer,
            file_name="Google_Calendar_Import.csv",
            mime="text/csv"
        ):
            st.success("✅ 다운로드 완료! (파일을 확인하세요)")

    except Exception as e:
        st.error(f"오류가 발생했습니다: {e}")