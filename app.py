import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import pytz
from icalendar import Calendar, Event
import io

# --- 기본 설정 ---
KST = pytz.timezone('Asia/Seoul')
UTC = pytz.utc

PER_DIEM_RATES = {
    "SFO": 4.21, "LAX": 4.01, "LAS": 4.01, "ANC": 3.81, "SEA": 3.81, "ATL": 3.61, "BOS": 3.61, "JFK": 3.61, "ORD": 3.41, "HNL": 3.41,
    "DFW": 3.21, "MIA": 3.21, "LCK": 3.21, "IAD": 3.01, "SCL": 3.19, "YVR": 3.19, "YYZ": 3.00, "ZRH": 4.16, "LHR": 3.86, "FCO": 3.71,
    "FRA": 3.41, "VIE": 3.41, "CDG": 3.26, "AMS": 3.26, "MXP": 3.26, "MAD": 3.26, "BCN": 3.11, "IST": 3.01, "SIN": 2.96, "BKK": 2.80,
    "DEL": 2.50, "BOM": 2.50, "MLE": 2.50, "KUL": 2.32, "SGN": 2.32, "GUM": 3.28, "HKG": 2.35, "TPE": 2.20, "MFM": 2.20, "ULN": 1.95, "DXB": 2.59
}

def get_rate(city):
    city = str(city).strip()
    if city in PER_DIEM_RATES: return PER_DIEM_RATES[city]
    if any(jp in city for jp in ["NRT", "HND", "KIX", "NGO", "FUK", "CTS"]): return 2.72
    if any(cn in city for cn in ["PEK", "PVG", "CAN", "SZX"]): return 1.95
    return 2.16

def format_dur(delta):
    h = int(delta.total_seconds() // 3600)
    m = int((delta.total_seconds() % 3600) // 60)
    return f"{h}h {m:02d}m"

# --- UI ---
st.set_page_config(page_title="KAL Roster Converter", page_icon="✈️")
st.title("✈️ KAL B787 로스터 변환기 (v1.3)")

# 1. 직책 선택 추가
rank = st.radio("나의 직책을 선택하세요 (Per Diem 계산용)", ["CAP (기장)", "FO (부기장)"], horizontal=True)
is_cap = True if "CAP" in rank else False

# 2. 파일 업로드 (xlsx 추가)
up_file = st.file_uploader("로스터 파일 (CSV 또는 XLSX)을 업로드하세요", type=['csv', 'xlsx'])

# 3. 리저브 일자만 입력
res_input = st.text_input("리저브 일자만 입력 (예: 01, 05, 12)", help="연월은 로스터 파일에서 자동으로 계산합니다.")

if up_file:
    flights = []
    try:
        # 파일 타입에 따른 읽기 방식
        if up_file.name.endswith('.csv'):
            df = pd.read_csv(up_file, header=None)
        else:
            df = pd.read_excel(up_file, header=None)
        
        # 헤더 행 찾기
        h_idx = -1
        for i, row in df.iterrows():
            if row.astype(str).str.contains('Flight/Activity').any():
                h_idx = i
                break
        
        if h_idx == -1:
            st.error("'Flight/Activity' 행을 찾을 수 없습니다.")
            st.stop()

        df.columns = df.iloc[h_idx].str.strip()
        data = df.iloc[h_idx+1:].reset_index(drop=True)

        curr = None
        for _, row in data.iterrows():
            f_val = str(row.get('Flight/Activity', '')).strip()
            if f_val != "" and f_val != "nan" and not f_val.startswith('Total'):
                if curr: flights.append(curr)
                try:
                    std = KST.localize(datetime.strptime(str(row['STD']), '%Y-%m-%d %H:%M'))
                    sta = KST.localize(datetime.strptime(str(row['STA']), '%Y-%m-%d %H:%M'))
                    curr = {"flt": f_val, "dep": str(row['From']).strip(), "arr": str(row['To']).strip(), "std": std, "sta": sta, "ac": str(row['A/C']).strip(), "crews": []}
                except: continue
            
            # Crew 정보
            name = str(row.get('Name', '')).strip()
            if (name == "nan" or name == "") and curr:
                for col in df.columns[11:15]:
                    val = str(row.get(col, '')).strip()
                    if val != "nan" and val != "" and len(val) > 2:
                        name = val
                        break
            if curr and name != "nan" and name != "":
                c_id = str(row.get('Crew ID', '')).strip()
                r_val = str(row.get('Acting rank', '')).strip()
                p_val = str(row.get('PIC code', '')).strip()
                sdc = str(row.get('Special Duty Code', '')).strip()
                sdc_str = f" [{sdc}]" if sdc != "nan" and sdc != "" else ""
                curr['crews'].append(f"{name} ({c_id}, {r_val}, {p_val}){sdc_str}")
        if curr: flights.append(curr)

        # 로테이션 묶기
        rots = []
        t_rot = []
        for f in flights:
            t_rot.append(f)
            if f['arr'] in ['ICN', 'GMP']:
                rots.append(t_rot)
                t_rot = []
        if t_rot: rots.append(t_rot)

        # ICS 생성
        cal = Calendar()
        cal.add('prodid', '-//KAL B787//')
        cal.add('version', '2.0')

        # 리저브 처리 (일자만 입력받아 연월 자동 적용)
        if res_input and flights:
            base_date = flights[0]['std'] # 첫 비행 기준 연/월
            for day_str in res_input.split(','):
                try:
                    day = int(day_str.strip())
                    rd = base_date.replace(day=day, hour=0, minute=0)
                    e = Event()
                    e.add('summary', 'Reserve')
                    e.add('dtstart', rd)
                    e.add('dtend', rd + timedelta(minutes=10))
                    cal.add_component(e)
                except: pass

        # 비행 일정 및 Per Diem 계산
        for r in rots:
            f1, fL = r[0], r[-1]
            summary = f"{f1['flt']}, {f1['dep']} {f1['std'].strftime('%H:%M')}, {f1['arr']}, {fL['arr']} {fL['sta'].strftime('%H:%M')}"
            ev = Event(); ev.add('summary', summary); ev.add('dtstart', f1['std']); ev.add('dtend', fL['sta'])
            
            memo = []
            total_block_time = timedelta()
            for f in r: total_block_time += (f['sta'] - f['std'])

            for i, f in enumerate(r):
                memo.append(f"★ {f['dep']}-{f['arr']} ★")
                if i == 0:
                    off = timedelta(hours=1, minutes=35) if f['dep']=='ICN' else timedelta(hours=1, minutes=40)
                    memo.append(f"{f['dep']} Show Up : {(f['std'] - off).strftime('%Y-%m-%d %H:%M')} (KST)")
                
                memo.append(f"{f['flt']}: {f['std'].strftime('%Y-%m-%d %H:%M')} (UTC {f['std'].astimezone(UTC).strftime('%H:%M')}) -> {f['sta'].strftime('%H:%M')} (UTC {f['sta'].astimezone(UTC).strftime('%H:%M')}) (A/C: {f['ac']})")
                memo.append(f"Block Time : {format_dur(f['sta']-f['std'])}")
                
                if i < len(r)-1:
                    stay = r[i+1]['std'] - f['sta']
                    # 퀵턴 수당 로직
                    if stay < timedelta(hours=4): # 4시간 미만 체류 시 퀵턴
                        total_h = total_block_time.total_seconds()/3600
                        if is_cap: pd = 60 if total_h >= 5 else 50
                        else: pd = 41 if total_h >= 5 else 35
                        memo.append(f"Quick Turn (Per Diem : ${pd:.2f})")
                    else:
                        rate = get_rate(f['arr'])
                        pd = (stay.total_seconds()/3600) * rate
                        memo.append(f"Stay Hours : {format_dur(stay)} (Per Diem : ${pd:.2f})")
                
                memo.append(f"\n★ [{f['flt']} Crew] ★")
                memo.extend(f['crews'])
                memo.append("")

            ev.add('description', "\n".join(memo))
            cal.add_component(ev)

        st.download_button("📅 캘린더 파일 다운로드", cal.to_ical(), "My_Schedule.ics", "text/calendar")
        st.success("업그레이드된 분석이 완료되었습니다!")

    except Exception as e:
        st.error(f"오류가 발생했습니다: {e}")