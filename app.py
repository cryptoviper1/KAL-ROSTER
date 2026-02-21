import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import pytz
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

def get_rate(city):
    city = clean_str(city)
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
st.title("✈️ KAL B787 로스터 CSV 변환기 (v2.1 Fix)")

rank = st.radio("직책 선택 (Per Diem 계산용)", ["CAP (기장)", "FO (부기장)"], horizontal=True)
is_cap = True if "CAP" in rank else False

up_file = st.file_uploader("로스터 파일 (CSV, XLSX) 업로드", type=['csv', 'xlsx'])

# 리저브 입력란 및 상태 표시
c1, c2 = st.columns([3, 1])
with c1:
    res_input = st.text_input("리저브 일자 입력 (예: 01, 05)", help="입력하면 자동으로 아래에 확인 메시지가 뜹니다.")
with c2:
    st.write("") # 여백
    st.write("") 
    if res_input:
        st.success("✅ 리저브 입력됨")
    else:
        st.info("대기 중...")

if up_file:
    # 비행 정보를 (편명, STD)를 키(Key)로 하는 딕셔너리에 저장
    # 이렇게 하면 페이지가 넘어가서 똑같은 편명이 또 나와도 같은 방에 몰아넣을 수 있음
    flight_dict = {} 
    current_key = None # 현재 작업 중인 비행의 키 (편명, STD)

    try:
        if up_file.name.endswith('.csv'):
            df = pd.read_csv(up_file, header=None)
        else:
            df = pd.read_excel(up_file, header=None)
        
        # 헤더 찾기
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
            
            # 중간 헤더 무시
            if f_val == 'Flight/Activity' or 'page' in f_val.lower():
                continue

            # 1. 비행 정보 식별 (편명이 있으면 새로운 키 생성 or 기존 키 찾기)
            if f_val and not f_val.startswith('Total'):
                try:
                    # STD를 파싱해서 고유 키로 사용 (문자열 그대로 쓰면 오타/공백 이슈 있을 수 있으므로 객체화)
                    std_dt = KST.localize(datetime.strptime(str(row['STD']), '%Y-%m-%d %H:%M'))
                    sta_dt = KST.localize(datetime.strptime(str(row['STA']), '%Y-%m-%d %H:%M'))
                    
                    # Key 생성: (편명, 출발시간)
                    key = (f_val, std_dt)
                    
                    # 이 비행이 처음 나온 거라면 방을 새로 만듦
                    if key not in flight_dict:
                        flight_dict[key] = {
                            "flt": f_val,
                            "dep": clean_str(row.get('From')),
                            "arr": clean_str(row.get('To')),
                            "std": std_dt,
                            "sta": sta_dt,
                            "ac": clean_str(row.get('A/C')),
                            "crews": [] # 크루 리스트 초기화
                        }
                    
                    # 현재 작업 중인 방(Key)을 이걸로 설정 (다음 줄부터 나오는 크루는 여기로 들어감)
                    current_key = key
                    
                except: 
                    # 날짜 파싱 실패 시, 이전 비행의 크루 정보일 수 있으므로 pass하고 아래 크루 로직으로 감
                    pass
            
            # 2. Crew 정보 추출 (현재 설정된 current_key 방에 집어넣기)
            # 비행 정보 행에도 크루가 있을 수 있고, 그 아래 행에도 있을 수 있음.
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
                        
                        # 중복 방지: 이미 명단에 있는 사람이면 넣지 않음 (페이지 넘길 때 헤더 반복 등으로 인해)
                        if crew_str not in flight_dict[current_key]['crews']:
                            flight_dict[current_key]['crews'].append(crew_str)

        # 3. 딕셔너리를 리스트로 변환 및 시간 정렬
        sorted_flights = sorted(flight_dict.values(), key=lambda x: x['std'])

        # 4. 로테이션 묶기
        rots = []
        t_rot = []
        
        for f in sorted_flights:
            if f['dep'] in ['ICN', 'GMP'] and t_rot:
                 rots.append(t_rot)
                 t_rot = []
            
            t_rot.append(f)
            
            if f['arr'] in ['ICN', 'GMP']:
                rots.append(t_rot)
                t_rot = []
                
        if t_rot: rots.append(t_rot)

        # 5. CSV 생성
        csv_rows = []

        # [리저브 처리] 24시간 설정 (00:00 ~ 23:59)
        if res_input and sorted_flights:
            base_date = sorted_flights[0]['std']
            dates_added = 0
            for day_str in res_input.split(','):
                try:
                    day = int(day_str.strip())
                    # 해당 일의 00:00 시작
                    start_dt = base_date.replace(day=day, hour=0, minute=0, second=0)
                    # 해당 일의 23:59:59 종료 (하루 종일)
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
                    dates_added += 1
                except: pass
            
            if dates_added > 0:
                st.info(f"📆 리저브 일정 {dates_added}개가 포함되었습니다.")

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

        # 다운로드
        res_df = pd.DataFrame(csv_rows)
        csv_buffer = res_df.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig')

        st.download_button(
            label="📅 구글 캘린더 CSV 다운로드",
            data=csv_buffer,
            file_name="Google_Calendar_Import.csv",
            mime="text/csv"
        )
        st.success(f"변환 완료! (총 {len(rots)}개 스케줄)")

    except Exception as e:
        st.error(f"오류가 발생했습니다: {e}")