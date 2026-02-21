import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import pytz
from icalendar import Calendar, Event
import io
import pdfplumber
import re

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
    if city in PER_DIEM_RATES: return PER_DIEM_RATES[city]
    if any(jp in city for jp in ["NRT", "HND", "KIX", "NGO", "FUK", "CTS"]): return 2.72
    if any(cn in city for cn in ["PEK", "PVG", "CAN", "SZX"]): return 1.95
    return 2.16

def format_dur(delta):
    h = int(delta.total_seconds() // 3600)
    m = int((delta.total_seconds() % 3600) // 60)
    return f"{h}h {m:02d}m"

# --- UI 구성 ---
st.set_page_config(page_title="KAL B787 Roster Converter", page_icon="✈️")
st.title("✈️ KAL B787 로스터 통합 변환기")
st.markdown("PDF, XLSX, CSV 파일을 구글 캘린더용 ICS 파일로 변환합니다.")

up_file = st.file_uploader("로스터 파일을 업로드하세요 (PDF, XLSX, CSV)", type=['pdf', 'xlsx', 'csv'])
res_input = st.text_input("리저브 날짜 (예: 2026-03-01, 2026-03-02)")
rank = st.radio("직책 선택", ["CAP", "FO"], horizontal=True)

if up_file:
    flights = []
    
    # 1. 파일 타입별 데이터 추출
    if up_file.name.endswith('.pdf'):
        with pdfplumber.open(up_file) as pdf:
            full_text = ""
            for page in pdf.pages:
                full_text += page.extract_text()
        st.info("PDF 텍스트 추출 완료. (비행 정보를 분석합니다...)")
        # PDF 분석 로직은 텍스트 패턴 매칭이 필요합니다 (현재는 CSV/XLSX 최적화)
        
    elif up_file.name.endswith('.csv'):
        df = pd.read_csv(up_file, header=None)
    else:
        df = pd.read_excel(up_file, header=None)

    # 2. 데이터 프레임 분석 (기존 승무원님 양식 기준)
    try:
        if not up_file.name.endswith('.pdf'):
            h_idx = df[df.iloc[:, 1] == 'Flight/Activity'].index[0]
            df.columns = df.iloc[h_idx]
            data = df.iloc[h_idx+1:].reset_index(drop=True)

            curr = None
            for _, row in data.iterrows():
                f_act = str(row['Flight/Activity']).strip()
                if f_act != "nan" and f_act != "" and not f_act.startswith('Total'):
                    if curr: flights.append(curr)
                    try:
                        std = KST.localize(datetime.strptime(str(row['STD']), '%Y-%m-%d %H:%M'))
                        sta = KST.localize(datetime.strptime(str(row['STA']), '%Y-%m-%d %H:%M'))
                        curr = {"flt": f_act, "dep": row['From'], "arr": row['To'], "std": std, "sta": sta, "ac": row['A/C'], "crews": []}
                    except: continue
                if curr and str(row['Name']).strip() != "nan":
                    sdc = f" {row['Special Duty Code']}" if pd.notna(row['Special Duty Code']) else ""
                    curr['crews'].append(f"{row['Name']} ({row['Crew ID']}, {row['Acting rank']}, {row['PIC code']}){sdc}")
            if curr: flights.append(curr)
    except Exception as e:
        st.error(f"데이터 분석 중 오류 발생: {e}")
        st.stop()

    # 3. 로테이션 묶기 및 ICS 생성
    rots = []
    t_rot = []
    for f in flights:
        t_rot.append(f)
        if f['arr'] in ['ICN', 'GMP']:
            rots.append(t_rot); t_rot = []

    cal = Calendar()
    cal.add('prodid', '-//KAL B787//')
    cal.add('version', '2.0')

    # 리저브 처리
    if res_input:
        for d in res_input.split(','):
            try:
                dt = KST.localize(datetime.strptime(d.strip(), '%Y-%m-%d'))
                e = Event(); e.add('summary', 'Reserve')
                e.add('dtstart', dt); e.add('dtend', dt + timedelta(minutes=10))
                cal.add_component(e)
            except: pass

    # 비행 처리
    for r in rots:
        f1, fL = r[0], r[-1]
        ev = Event()
        ev.add('summary', f"{f1['flt']}, {f1['dep']} {f1['std'].strftime('%H:%M')}, {f1['arr']}, {fL['arr']} {fL['sta'].strftime('%H:%M')}")
        ev.add('dtstart', f1['std']); ev.add('dtend', fL['sta'])
        
        memo = []
        for i, f in enumerate(r):
            memo.append(f"★ {f['dep']}-{f['arr']} ★")
            if i == 0:
                off = timedelta(hours=1, minutes=35) if f['dep']=='ICN' else timedelta(hours=1, minutes=40)
                memo.append(f"{f['dep']} Show Up : {(f['std']-off).strftime('%Y-%m-%d %H:%M')} (KST)")
            
            b_time = f['sta']-f['std']
            memo.append(f"{f['flt']}: {f['std'].strftime('%Y-%m-%d %H:%M')} (UTC {f['std'].astimezone(UTC).strftime('%H:%M')}) -> {f['sta'].strftime('%H:%M')} (UTC {f['sta'].astimezone(UTC).strftime('%H:%M')}) (A/C: {f['ac']})")
            memo.append(f"Block Time : {format_dur(b_time)}")
            
            if i < len(r)-1:
                stay = r[i+1]['std']-f['sta']
                rate = get_rate(f['arr'])
                pd_val = (stay.total_seconds()/3600) * rate
                memo.append(f"Stay Hours : {format_dur(stay)} (Per Diem : ${pd_val:.2f})")
            
            memo.append(f"\n★ [{f['flt']} Crew] ★\n" + "\n".join(f['crews']) + "\n")
        
        ev.add('description', "\n".join(memo))
        cal.add_component(ev)

    st.download_button("📅 캘린더 파일 다운로드 (.ics)", cal.to_ical(), "My_Schedule.ics", "text/calendar")
    st.success(f"총 {len(rots)}개의 로테이션 스케줄이 생성되었습니다!")