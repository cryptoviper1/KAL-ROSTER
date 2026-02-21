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
st.title("✈️ KAL B787 로스터 변환기 (v1.2)")

up_file = st.file_uploader("로스터 CSV 파일을 업로드하세요", type=['csv'])
res_input = st.text_input("리저브 날짜 (예: 2026-03-01, 2026-03-02)")

if up_file:
    flights = []
    try:
        df = pd.read_csv(up_file, header=None)
        
        # 1. 헤더 찾기
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
            
            # Crew 정보 수집
            name = str(row.get('Name', '')).strip()
            if (name == "nan" or name == "") and curr:
                for col in df.columns[11:15]:
                    val = str(row.get(col, '')).strip()
                    if val != "nan" and val != "" and len(val) > 2:
                        name = val
                        break
            
            if curr and name != "nan" and name != "":
                c_id = str(row.get('Crew ID', '')).strip()
                rank = str(row.get('Acting rank', '')).strip()
                pic = str(row.get('PIC code', '')).strip()
                sdc = str(row.get('Special Duty Code', '')).strip()
                sdc_str = f" [{sdc}]" if sdc != "nan" and sdc != "" else ""
                curr['crews'].append(f"{name} ({c_id}, {rank}, {pic}){sdc_str}")

        if curr: flights.append(curr)

        # 2. 로테이션 묶기
        rots = []
        t_rot = []
        for f in flights:
            t_rot.append(f)
            if f['arr'] in ['ICN', 'GMP']:
                rots.append(t_rot)
                t_rot = []
        if t_rot: rots.append(t_rot)

        # 3. ICS 생성
        cal = Calendar()
        cal.add('prodid', '-//KAL B787//')
        cal.add('version', '2.0')

        # 리저브
        if res_input:
            for d in res_input.split(','):
                try:
                    rd = KST.localize(datetime.strptime(d.strip(), '%Y-%m-%d'))
                    e = Event()
                    e.add('summary', 'Reserve')
                    e.add('dtstart', rd)
                    e.add('dtend', rd + timedelta(minutes=10))
                    cal.add_component(e)
                except: pass

        # 비행 일정
        for r in rots:
            f1, fL = r[0], r[-1]
            ev = Event()
            ev.add('summary', f"{f1['flt']}, {f1['dep']} {f1['std'].strftime('%H:%M')}, {f1['arr']}, {fL['arr']} {fL['sta'].strftime('%H:%M')}")
            ev.add('dtstart', f1['std'])
            ev.add('dtend', fL['sta'])
            
            memo = []
            for i, f in enumerate(r):
                memo.append(f"★ {f['dep']}-{f['arr']} ★")
                if i == 0:
                    off = timedelta(hours=1, minutes=35) if f['dep']=='ICN' else timedelta(hours=1, minutes=40)
                    showup_time = (f['std'] - off).strftime('%Y-%m-%d %H:%M')
                    memo.append(f"{f['dep']} Show Up : {showup_time} (KST)")
                
                memo.append(f"{f['flt']}: {f['std'].strftime('%Y-%m-%d %H:%M')} (UTC {f['std'].astimezone(UTC).strftime('%H:%M')}) -> {f['sta'].strftime('%H:%M')} (UTC {f['sta'].astimezone(UTC).strftime('%H:%M')}) (A/C: {f['ac']})")
                memo.append(f"Block Time : {format_dur(f['sta']-f['std'])}")
                
                if i < len(r)-1:
                    stay = r[i+1]['std'] - f['sta']
                    pd = (stay.total_seconds()/3600) * get_rate(f['arr'])
                    memo.append(f"Stay Hours : {format_dur(stay)} (Per Diem : ${pd:.2f})")
                
                memo.append(f"\n★ [{f['flt']} Crew] ★")
                memo.extend(f['crews'])
                memo.append("")

            ev.add('description', "\n".join(memo))
            cal.add_component(ev)

        st.download_button("📅 캘린더 파일 다운로드", cal.to_ical(), "My_Schedule.ics", "text/calendar")
        st.success("분석이 완료되었습니다!")

    except Exception as e:
        st.error(f"오류가 발생했습니다: {e}")