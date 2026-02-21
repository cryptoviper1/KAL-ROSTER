import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import pytz
from icalendar import Calendar, Event
import io
import pdfplumber

# --- 기본 설정 ---
KST = pytz.timezone('Asia/Seoul')
UTC = pytz.utc

# Per Diem 단가표
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
st.title("✈️ KAL B787 로스터 변환기 (v1.1)")

up_file = st.file_uploader("파일 업로드 (PDF, XLSX, CSV)", type=['pdf', 'xlsx', 'csv'])
res_input = st.text_input("리저브 날짜 (예: 2026-03-01, 2026-03-02)")

if up_file:
    flights = []
    try:
        if up_file.name.endswith('.csv'):
            df = pd.read_csv(up_file, header=None)
        elif up_file.name.endswith('.xlsx'):
            df = pd.read_excel(up_file, header=None)
        else:
            # PDF 처리 로직 (생략 - 필요시 추가 가능)
            st.warning("PDF 분석 기능은 현재 준비 중입니다. 엑셀이나 CSV를 사용해 주세요.")
            st.stop()

        # 1. 헤더 행 찾기 (공백 제거 후 'Flight/Activity' 포함된 행 검색)
        h_idx = -1
        for i, row in df.iterrows():
            if row.astype(str).str.contains('Flight/Activity').any():
                h_idx = i
                break
        
        if h_idx == -1:
            st.error("파일에서 'Flight/Activity' 열을 찾을 수 없습니다. 올바른 로스터 파일인지 확인해주세요.")
            st.stop()

        # 2. 데이터 정리
        df.columns = df.iloc[h_idx].str.strip() # 컬럼명 공백 제거
        data = df.iloc[h_idx+1:].reset_index(drop=True)

        curr = None
        for _, row in data.iterrows():
            f_val = str(row.get('Flight/Activity', '')).strip()
            
            # 새로운 비행 편명 발견 시
            if f_val != "" and f_val != "nan" and not f_val.startswith('Total'):
                if curr: flights.append(curr)
                try:
                    std = KST.localize(datetime.strptime(str(row['STD']), '%Y-%m-%d %H:%M'))
                    sta = KST.localize(datetime.strptime(str(row['STA']), '%Y-%m-%d %H:%M'))
                    curr = {
                        "flt": f_val, "dep": str(row['From']).strip(), "arr": str(row['To']).strip(),
                        "std": std, "sta": sta, "ac": str(row['A/C']).strip(), "crews": []
                    }
                except: continue
            
            # 승무원 정보 추가 (Name이 있는 행)
            # 파일 분석 결과 Name이 간혹 옆 칸으로 밀릴 수 있어 여러 칸 확인
            name = str(row.get('Name', '')).strip()
            if name == "nan" or name == "":
                # Name 컬럼이 비어있으면 옆 칸들에서 이름 탐색
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

        # 3. 로테이션 및 ICS 생성 로직 (동일)
        # [이하 기존과 동일한 로테이션 묶기 및 캘린더 생성 코드...]
        rots = []
        t_rot = []
        for f in flights:
            t_rot.append(f)
            if f['arr'] in ['ICN', 'GMP']:
                rots.append(t_rot); t_rot = []

        if not rots and flights: rots = [flights] # 로테이션이 안 닫히면 전체를 하나로

        cal = Calendar()
        # 리저브
        if res_input:
            for d in res_input.split(','):
                try:
                    dt = KST.localize(datetime.strptime(d.strip(), '%Y-%m-%d'))
                    e = Event(); e.add('summary', 'Reserve')
                    e.add('dtstart', dt); e.add('dtend', dt + timedelta(minutes=10))
                    cal.add_component(e)
                except: pass

        for r in rots:
            f1, fL = r[0], r[-1]
            summary = f"{f1['flt']}, {f1['dep']} {f1['std'].strftime('%H:%M')}, {f1['arr']}, {fL['arr']} {fL['sta'].strftime('%H:%M')}"
            ev = Event(); ev.add('summary', summary); ev.add('dtstart', f1['std']); ev.add('dtend', fL['sta'])
            
            memo = []
            for i, f in enumerate(r):
                memo.append(f"★ {f['dep']}-{f['arr']} ★")
                if i == 0:
                    off = timedelta(hours=1, minutes=35) if f['dep']=='ICN' else timedelta(hours=1, minutes=40)
                    memo.append(f"{f['dep']} Show Up : {(f['std']-off).strftime