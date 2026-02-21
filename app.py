import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import pytz
import io
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
st.set_page_config(page_title="KAL Roster to CSV", page_icon="✈️")
st.title("✈️ KAL B787 구글 캘린더 CSV 변환기 (Fix)")

rank = st.radio("직책 선택 (Per Diem 계산용)", ["CAP (기장)", "FO (부기장)"], horizontal=True)
is_cap = True if "CAP" in rank else False

up_file = st.file_uploader("로스터 파일 (CSV, XLSX) 업로드", type=['csv', 'xlsx'])
res_input = st.text_input("리저브 일자만 입력 (예: 01, 05)", help="연월은 자동 계산됩니다.")

if up_file:
    flights = []
    try:
        # 파일 읽기
        if up_file.name.endswith('.csv'):
            df = pd.read_csv(up_file, header=None)
        else:
            df = pd.read_excel(up_file, header=None)
        
        # 'Flight/Activity' 헤더 찾기
        h_idx = -1
        for i, row in df.iterrows():
            if row.astype(str).str.contains('Flight/Activity').any():
                h_idx = i
                break
        
        if h_idx == -1:
            st.error("'Flight/Activity' 행을 찾을 수 없습니다.")
            st.stop()

        # 헤더 적용 (공백 제거)
        df.columns = df.iloc[h_idx].str.strip()
        data = df.iloc[h_idx+1:].reset_index(drop=True)

        curr = None
        for _, row in data.iterrows():
            # 1. 비행 정보 추출
            f_val = str(row.get('Flight/Activity', '')).strip()
            # 'Total' 행이나 nan 값 제외
            if f_val != "" and f_val.lower() != "nan" and not f_val.startswith('Total'):
                if curr: flights.append(curr)
                try:
                    std = KST.localize(datetime.strptime(str(row['STD']), '%Y-%m-%d %H:%M'))
                    sta = KST.localize(datetime.strptime(str(row['STA']), '%Y-%m-%d %H:%M'))
                    curr = {"flt": f_val, "dep": str(row['From']).strip(), "arr": str(row['To']).strip(), "std": std, "sta": sta, "ac": str(row['A/C']).strip(), "crews": []}
                except: continue
            
            # 2. Crew 이름 추출 (강화된 로직)
            c_id = str(row.get('Crew ID', '')).strip()
            
            # 사번이 있는 행만 처리 (유효한 승무원 데이터로 간주)
            if c_id and c_id.lower() != "nan" and c_id.isdigit():
                name = ""
                # 해당 행의 모든 값을 리스트로 가져옴
                row_values = [str(x).strip() for x in row.values]
                
                # 사번 위치 찾기
                if c_id in row_values:
                    id_idx = row_values.index(c_id)
                    # 사번 뒤 5칸까지 뒤져서 "진짜 이름" 찾기
                    for i in range(1, 6):
                        if id_idx + i < len(row_values):
                            candidate = row_values[id_idx + i]
                            # 조건: nan 아니고, 공백 아니고, 숫자만 있는게 아니고(사번중복방지), 길이가 2 이상
                            if (candidate.lower() != "nan" and 
                                candidate != "" and 
                                not candidate.isdigit() and 
                                len(candidate) >= 2):
                                name = candidate
                                break
                
                # 만약 위 로직으로 못 찾았으면 'Name' 컬럼 확인
                if name == "":
                    raw_name = str(row.get('Name', '')).strip()
                    if raw_name.lower() != "nan" and raw_name != "" and not raw_name.isdigit():
                        name = raw_name

                # 최종 저장 (이름이 찾아졌을 경우만)
                if curr and name:
                    r_val = str(row.get('Acting rank', '')).strip()
                    p_val = str(row.get('PIC code', '')).strip()
                    
                    # --- Special Duty Code 완벽 제거 로직 ---
                    sdc_raw = row.get('Special Duty Code', '')
                    if pd.isna(sdc_raw):
                        sdc_str = ""
                    else:
                        sdc = str(sdc_raw).strip()
                        # nan 문자열, 빈 문자열, 점(.) 등을 모두 체크
                        if sdc.lower() == 'nan' or sdc == '' or sdc == '.':
                            sdc_str = ""
                        else:
                            sdc_str = f" [{sdc}]"
                    # --------------------------------------

                    curr['crews'].append(f"{name} ({c_id}, {r_val}, {p_val}){sdc_str}")

        if curr: flights.append(curr)

        # 로테이션 그룹화
        rots = []
        t_rot = []
        for f in flights:
            t_rot.append(f)
            if f['arr'] in ['ICN', 'GMP']:
                rots.append(t_rot); t_rot = []
        if t_rot: rots.append(t_rot)

        # CSV 생성
        csv_rows = []

        # 리저브
        if res_input and flights:
            base_date = flights[0]['std']
            for day_str in res_input.split(','):
                try:
                    day = int(day_str.strip())
                    rd = base_date.replace(day=day, hour=0, minute=0)
                    csv_rows.append({
                        "Subject": "Reserve",
                        "Start Date": rd.strftime('%Y-%m-%d'),
                        "Start Time": "00:00",
                        "End Date": rd.strftime('%Y-%m-%d'),
                        "End Time": "00:10",
                        "Description": "Reserve Schedule",
                        "Location": "ICN"
                    })
                except: pass

        # 비행 스케줄
        for r in rots:
            f1, fL = r[0], r[-1]
            subject = f"{f1['flt']}, {f1['dep']} {f1['std'].strftime('%H:%M')}, {f1['arr']}, {fL['arr']} {fL['sta'].strftime('%H:%M')}"
            
            memo = []
            total_block_time = timedelta()
            for f in r: total_block_time += (f['sta'] - f['std'])

            for i, f in enumerate(r):
                memo.append(f"★ {f['dep']}-{f['arr']} ★")
                if i == 0:
                    off = timedelta(hours=1, minutes=35) if f['dep']=='ICN' else timedelta(hours=1, minutes=40)
                    memo.append(f"{f['dep']} Show Up : {(f['std']-off).strftime('%Y-%m-%d %H:%M')} (KST)")
                
                memo.append(f"{f['flt']}: {f['std'].strftime('%Y-%m-%d %H:%M')} (UTC {f['std'].astimezone(UTC).strftime('%H:%M')}) -> {f['sta'].strftime('%H:%M')} (UTC {f['sta'].astimezone(UTC).strftime('%H:%M')}) (A/C: {f['ac']})")
                memo.append(f"Block Time : {format_dur(f['sta']-f['std'])}")
                
                if i < len(r)-1:
                    stay = r[i+1]['std'] - f['sta']
                    if stay < timedelta(hours=4):
                        total_h = total_block_time.total_seconds()/3600
                        pd_val = 60 if is_cap and total_h >=5 else (50 if is_cap else (41 if total_h >=5 else 35))
                        memo.append(f"Quick Turn (Per Diem : ${pd_val:.2f})")
                    else:
                        rate = get_rate(f['arr'])
                        pd_val = (stay.total_seconds()/3600) * rate
                        memo.append(f"Stay Hours : {format_dur(stay)} (Per Diem : ${pd_val:.2f})")
                
                memo.append(f"\n★ [{f['flt']} Crew] ★")
                memo.extend(f['crews'])
                memo.append("")

            csv_rows.append({
                "Subject": subject,
                "Start Date": f1['std'].strftime('%Y-%m-%d'),
                "Start Time": f1['std'].strftime('%H:%M'),
                "End Date": fL['sta'].strftime('%Y-%m-%d'),
                "End Time": fL['sta'].strftime('%H:%M'),
                "Description": "\n".join(memo),
                "Location": f"{f1['dep']} -> {fL['arr']}"
            })

        # 다운로드 버튼
        res_df = pd.DataFrame(csv_rows)
        csv_buffer = res_df.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig')

        st.download_button(
            label="📅 구글 캘린더 CSV 다운로드",
            data=csv_buffer,
            file_name="Google_Calendar_Import.csv",
            mime="text/csv"
        )
        st.success(f"완료! (총 {len(rots)}개 스케줄)")

    except Exception as e:
        st.error(f"오류가 발생했습니다: {e}")