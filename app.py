import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import pytz
import io

# --- 1. 공항별 시간대(Timezone) 설정 (B787 주요 취항지) ---
# 이곳에 없는 공항은 기본 KST로 계산되지만, 주요 도시는 다 넣었습니다.
AIRPORT_TZ = {
    # 한국/일본/동아시아 (UTC+9)
    'ICN': 'Asia/Seoul', 'GMP': 'Asia/Seoul', 'PUS': 'Asia/Seoul', 'CJU': 'Asia/Seoul',
    'NRT': 'Asia/Tokyo', 'HND': 'Asia/Tokyo', 'KIX': 'Asia/Tokyo', 'NGO': 'Asia/Tokyo', 'FUK': 'Asia/Tokyo', 'CTS': 'Asia/Tokyo',
    
    # 중국/동남아/대양주
    'PEK': 'Asia/Shanghai', 'PVG': 'Asia/Shanghai', 'CAN': 'Asia/Shanghai', 'SZX': 'Asia/Shanghai', 'HKG': 'Asia/Hong_Kong',
    'TPE': 'Asia/Taipei', 'MNL': 'Asia/Manila', 'SIN': 'Asia/Singapore', 'KUL': 'Asia/Kuala_Lumpur', 'BKK': 'Asia/Bangkok',
    'SGN': 'Asia/Ho_Chi_Minh', 'HAN': 'Asia/Bangkok', 'DPS': 'Asia/Makassar', 'CGK': 'Asia/Jakarta',
    'GUM': 'Pacific/Guam', 'SYD': 'Australia/Sydney', 'BNE': 'Australia/Brisbane', 'AKL': 'Pacific/Auckland',
    'DEL': 'Asia/Kolkata', 'BOM': 'Asia/Kolkata', 'MLE': 'Indian/Maldives', 'DXB': 'Asia/Dubai', 'IST': 'Europe/Istanbul',

    # 미주 (Summer Time 자동 적용됨)
    'LAX': 'America/Los_Angeles', 'SFO': 'America/Los_Angeles', 'SEA': 'America/Los_Angeles', 'LAS': 'America/Los_Angeles', 
    'YVR': 'America/Vancouver', 'ANC': 'America/Anchorage', 'HNL': 'Pacific/Honolulu',
    'JFK': 'America/New_York', 'BOS': 'America/New_York', 'ATL': 'America/New_York', 'IAD': 'America/New_York', 
    'YYZ': 'America/Toronto', 'DTW': 'America/Detroit', 'ORD': 'America/Chicago', 'DFW': 'America/Chicago', 'MIA': 'America/New_York',
    'SCL': 'America/Santiago',

    # 유럽
    'LHR': 'Europe/London', 'CDG': 'Europe/Paris', 'FRA': 'Europe/Berlin', 'FCO': 'Europe/Rome', 
    'MXP': 'Europe/Rome', 'AMS': 'Europe/Amsterdam', 'ZRH': 'Europe/Zurich', 'VIE': 'Europe/Vienna', 
    'PRG': 'Europe/Prague', 'BUD': 'Europe/Budapest', 'MAD': 'Europe/Madrid', 'BCN': 'Europe/Madrid',
    'LIS': 'Europe/Lisbon'
}

KST = pytz.timezone('Asia/Seoul')
UTC = pytz.utc

PER_DIEM_RATES = {
    "SFO": 4.21, "LAX": 4.01, "LAS": 4.01, "ANC": 3.81, "SEA": 3.81, "ATL": 3.61, "BOS": 3.61, "JFK": 3.61, "ORD": 3.41, "HNL": 3.41,
    "DFW": 3.21, "MIA": 3.21, "LCK": 3.21, "IAD": 3.01, "SCL": 3.19, "YVR": 3.19, "YYZ": 3.00, "ZRH": 4.16, "LHR": 3.86, "FCO": 3.71,
    "FRA": 3.41, "VIE": 3.41, "CDG": 3.26, "AMS": 3.26, "MXP": 3.26, "MAD": 3.26, "BCN": 3.11, "IST": 3.01, "SIN": 2.96, "BKK": 2.80,
    "DEL": 2.50, "BOM": 2.50, "MLE": 2.50, "KUL": 2.32, "SGN": 2.32, "GUM": 3.28, "HKG": 2.35, "TPE": 2.20, "MFM": 2.20, "ULN": 1.95, "DXB": 2.59
}

# --- 헬퍼 함수 ---
def clean_str(val):
    if pd.isna(val): return ""
    s = str(val).strip()
    if s.lower() == 'nan': return ""
    return s

def is_valid_name(text):
    if not text: return False
    if text.replace('.', '').isdigit(): return False
    if text.upper() in ['P1', 'P2', 'F1', 'F2', 'CAP', 'FO', 'DUTY', 'STD', 'STA', 'NAME', 'CREW ID']: return False
    if len(text) < 2: return False
    return True

def get_timezone(airport_code):
    """공항 코드로 Timezone 객체 반환"""
    tz_name = AIRPORT_TZ.get(clean_str(airport_code), 'Asia/Seoul') # 기본값 KST
    try:
        return pytz.timezone(tz_name)
    except:
        return KST

def get_utc_time(dt_str, airport_code):
    """현지 시간 문자열과 공항 코드를 받아 UTC datetime 반환"""
    try:
        local_tz = get_timezone(airport_code)
        local_dt = datetime.strptime(str(dt_str), '%Y-%m-%d %H:%M')
        # 현지 시간으로 인식 (localize)
        local_aware = local_tz.localize(local_dt)
        # UTC로 변환
        return local_aware.astimezone(UTC)
    except:
        return None

def get_rate(city):
    city = clean_str(city)
    if city in PER_DIEM_RATES: return PER_DIEM_RATES[city]
    if any(jp in city for jp in ["NRT", "HND", "KIX", "NGO", "FUK", "CTS"]): return 2.72
    if any(cn in city for cn in ["PEK", "PVG", "CAN", "SZX"]): return 1.95
    return 2.16

def format_dur(delta):
    total_seconds = int(delta.total_seconds())
    if total_seconds < 0: # 음수 방지 (혹시 모를 에러 대비)
        total_seconds = abs(total_seconds)
    h = total_seconds // 3600
    m = (total_seconds % 3600) // 60
    return f"{h}h {m:02d}m"

# --- UI ---
st.set_page_config(page_title="KAL Roster to CSV", page_icon="✈️")
st.title("✈️ KAL B787 로스터 CSV 변환기 (v2.2)")

rank = st.radio("직책 선택 (Per Diem 계산용)", ["CAP (기장)", "FO (부기장)"], horizontal=True)
is_cap = True if "CAP" in rank else False

up_file = st.file_uploader("로스터 파일 (CSV, XLSX) 업로드", type=['csv', 'xlsx'])

c1, c2 = st.columns([3, 1])
with c1:
    res_input = st.text_input("리저브 일자 입력 (예: 01, 05)", help="입력하면 자동으로 아래에 확인 메시지가 뜹니다.")
with c2:
    st.write("") 
    st.write("") 
    if res_input:
        st.success("✅ 입력 확인")

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

        for _, row in data.iterrows():
            f_val = clean_str(row.get('Flight/Activity', ''))
            
            if f_val == 'Flight/Activity' or 'page' in f_val.lower():
                continue

            if f_val and not f_val.startswith('Total'):
                try:
                    # 키 생성용 (문자열 그대로)
                    std_str = str(row['STD'])
                    if len(std_str) < 10: continue 
                    
                    # 시차 계산을 위한 UTC 변환
                    dep_port = clean_str(row.get('From'))
                    arr_port = clean_str(row.get('To'))
                    
                    # 1. UTC 기준 시간 계산 (Block Time용)
                    std_utc = get_utc_time(row['STD'], dep_port)
                    sta_utc = get_utc_time(row['STA'], arr_port)
                    
                    # 2. 캘린더 표시용 KST 시간 (로컬 -> UTC -> KST)
                    # (기존 코드는 엑셀 시간을 KST로 바로 박았지만, 정확하게 하려면 로컬 시간을 KST로 변환해야 함)
                    # 하지만 승무원 캘린더는 보통 '현지 출발시간'을 제목에 적고 싶어하므로
                    # 엑셀에 적힌 시간을 그대로 datetime 객체로 만듦 (Timezone Aware로)
                    
                    # 여기서는 '키' 구분을 위해 엑셀 값 그대로 사용
                    std_local_naive = datetime.strptime(str(row['STD']), '%Y-%m-%d %H:%M')
                    
                    key = (f_val, std_str) # 편명 + 출발시간(문자열)을 키로 사용
                    
                    if key not in flight_dict:
                        flight_dict[key] = {
                            "flt": f_val,
                            "dep": dep_port,
                            "arr": arr_port,
                            "std_str": str(row['STD']), # 표시용
                            "sta_str": str(row['STA']), # 표시용
                            "std_utc": std_utc, # 계산용 (UTC)
                            "sta_utc": sta_utc, # 계산용 (UTC)
                            "std_kst": std_utc.astimezone(KST), # Show-up 계산용
                            "ac": clean_str(row.get('A/C')),
                            "crews": []
                        }
                    
                    current_key = key
                    
                except: 
                    pass
            
            # Crew 정보 추출
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
                        p_val = clean_str(row.get('PIC code'))
                        sdc = clean_str(row.get('Special Duty Code'))
                        info_parts = [x for x in [c_id, r_val, p_val] if x]
                        info_str = ", ".join(info_parts)
                        sdc_str = f" [{sdc}]" if sdc else ""
                        crew_str = f"{name} ({info_str}){sdc_str}"
                        if crew_str not in flight_dict[current_key]['crews']:
                            flight_dict[current_key]['crews'].append(crew_str)

        sorted_flights = sorted(flight_dict.values(), key=lambda x: x['std_utc'])

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

        # CSV 생성
        csv_rows = []

        # 리저브
        if res_input and sorted_flights:
            base_date = sorted_flights[0]['std_kst']
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
                except: pass

        for r in rots:
            f1, fL = r[0], r[-1]
            # 구글 캘린더 제목: 현지 시간 기준 표시 (엑셀 원본 사용)
            subject = f"{f1['flt']}, {f1['dep']} {f1['std_str'][11:]}, {f1['arr']}, {fL['arr']} {fL['sta_str'][11:]}"
            
            memo = []
            
            # Show Up 계산 (KST 기준)
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
                
                # Block Time 계산 (UTC 차이)
                blk_dur = "N/A"
                if f['sta_utc'] and f['std_utc']:
                    diff = f['sta_utc'] - f['std_utc']
                    blk_dur = format_dur(diff)
                
                # 메모 시간 표기: 현지시간(엑셀값) (UTC 시간)
                std_utc_str = f['std_utc'].strftime('%H:%M') if f['std_utc'] else "?"
                sta_utc_str = f['sta_utc'].strftime('%H:%M') if f['sta_utc'] else "?"
                
                memo.append(f"{f['flt']}: {f['std_str']} (UTC {std_utc_str}) -> {f['sta_str'][11:]} (UTC {sta_utc_str}) (A/C: {f['ac']})")
                memo.append(f"Block Time : {blk_dur}")
                
                # Stay & Per Diem
                if i < len(r)-1:
                    next_f = r[i+1]
                    if next_f['std_utc'] and f['sta_utc']:
                        stay_diff = next_f['std_utc'] - f['sta_utc']
                        stay_h = stay_diff.total_seconds() / 3600
                        
                        # 퀵턴/체류비
                        if stay_h < 4:
                            # 총 비행시간(UTC 기준 합계)
                            total_h = total_block_seconds / 3600
                            pd_val = 60 if is_cap and total_h >=5 else (50 if is_cap else (41 if total_h >=5 else 35))
                            memo.append(f"Quick Turn (Per Diem : ${pd_val:.2f})")
                        else:
                            rate = get_rate(f['arr'])
                            pd_val = stay_h * rate
                            memo.append(f"Stay Hours : {format_dur(stay_diff)} (Per Diem : ${pd_val:.2f})")
                
                memo.append(f"\n★ [{f['flt']} Crew] ★")
                memo.extend(f['crews'])
                memo.append("")

            # CSV 날짜는 엑셀에 적힌 날짜(현지시간) 기준 -> 구글 캘린더가 알아서 해당 일자 스케줄로 잡음
            # 단, 시간은 정확히 입력
            csv_rows.append({
                "Subject": subject,
                "Start Date": f1['std_str'][:10],
                "Start Time": f1['std_str'][11:],
                "End Date": fL['sta_str'][:10],
                "End Time": fL['sta_str'][11:],
                "Description": "\n".join(memo),
                "Location": f"{f1['dep']} -> {fL['arr']}"
            })

        # 다운로드
        res_df = pd.DataFrame(csv_rows)
        csv_buffer = res_df.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig')

        st.success("✅ 변환 파일 다운로드 준비 완료!")
        st.download_button(
            label="변환 파일 다운로드 완료 (Click)",
            data=csv_buffer,
            file_name="Google_Calendar_Import.csv",
            mime="text/csv"
        )

    except Exception as e:
        st.error(f"오류가 발생했습니다: {e}")