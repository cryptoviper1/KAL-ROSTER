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
    """지저분한 데이터(nan, 공백) 청소"""
    if pd.isna(val): return ""
    s = str(val).strip()
    if s.lower() == 'nan': return ""
    return s

def is_valid_name(text):
    """이름인지 검증 (P1, P2, 숫자 등 제외)"""
    if not text: return False
    if text.replace('.', '').isdigit(): return False
    if text.upper() in ['P1', 'P2', 'F1', 'F2', 'CAP', 'FO']: return False
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
st.title("✈️ KAL B787 로스터 CSV 변환기 (Final Fix)")

rank = st.radio("직책 선택 (Per Diem 계산용)", ["CAP (기장)", "FO (부기장)"], horizontal=True)
is_cap = True if "CAP" in rank else False

up_file = st.file_uploader("로스터 파일 (CSV, XLSX) 업로드", type=['csv', 'xlsx'])
res_input = st.text_input("리저브 일자만 입력 (예: 01, 05)", help="연월은 자동 계산됩니다.")

if up_file:
    raw_flights = []
    try:
        # 파일 읽기
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

        # 헤더 적용
        df.columns = df.iloc[h_idx].apply(clean_str)
        data = df.iloc[h_idx+1:].reset_index(drop=True)

        curr = None
        for _, row in data.iterrows():
            # 1. 비행 정보 추출
            f_val = clean_str(row.get('Flight/Activity', ''))
            
            if f_val and not f_val.startswith('Total'):
                # 이전 비행 저장
                if curr: raw_flights.append(curr)
                
                try:
                    std = KST.localize(datetime.strptime(str(row['STD']), '%Y-%m-%d %H:%M'))
                    sta = KST.localize(datetime.strptime(str(row['STA']), '%Y-%m-%d %H:%M'))
                    curr = {
                        "flt": f_val, 
                        "dep": clean_str(row.get('From')), 
                        "arr": clean_str(row.get('To')), 
                        "std": std, "sta": sta, 
                        "ac": clean_str(row.get('A/C')), 
                        "crews": []
                    }
                except: continue
            
            # 2. Crew 정보 추출 (스마트 검색)
            c_id = clean_str(row.get('Crew ID'))
            
            if c_id and c_id.isdigit():
                name = ""
                raw_name = clean_str(row.get('Name'))
                
                if is_valid_name(raw_name):
                    name = raw_name
                else:
                    # 이름 찾기 (옆칸 뒤지기)
                    row_vals = [clean_str(x) for x in row.values]
                    if c_id in row_vals:
                        idx = row_vals.index(c_id)
                        for i in range(1, 6):
                            if idx + i < len(row_vals):
                                candidate = row_vals[idx + i]
                                if is_valid_name(candidate):
                                    name = candidate
                                    break
                
                if curr and name:
                    r_val = clean_str(row.get('Acting rank'))
                    p_val = clean_str(row.get('PIC code'))
                    sdc = clean_str(row.get('Special Duty Code'))
                    
                    # --- 이름 포맷팅 개선 (콤마 제거) ---
                    # 정보가 있는 것만 리스트에 담아서 join
                    info_parts = [x for x in [c_id, r_val, p_val] if x]
                    info_str = ", ".join(info_parts)
                    
                    sdc_str = f" [{sdc}]" if sdc else ""
                    curr['crews'].append(f"{name} ({info_str}){sdc_str}")

        if curr: raw_flights.append(curr)

        # 3. 비행 데이터 정제 (중복 제거 & 시간 정렬)
        # 시간순 정렬 (순서 꼬임 방지)
        raw_flights.sort(key=lambda x: x['std'])
        
        unique_flights = []
        if raw_flights:
            unique_flights.append(raw_flights[0])
            for i in range(1, len(raw_flights)):
                prev = unique_flights[-1]
                curr = raw_flights[i]
                # 편명과 출발시간이 같으면 중복으로 간주하고 스킵
                if not (prev['flt'] == curr['flt'] and prev['std'] == curr['std']):
                    unique_flights.append(curr)

        # 4. 로테이션 묶기 (ICN/GMP 기준)
        rots = []
        t_rot = []
        
        for f in unique_flights:
            # 안전장치: 인천/김포 출발인데 이미 진행 중인 로테이션이 있으면?
            # (단, 이전 비행이 인천/김포 도착이 아니었을 경우에만 끊어줌)
            if f['dep'] in ['ICN', 'GMP'] and t_rot:
                # 이전 로테이션 강제 종료 (비엔나 분리 방지용)
                # 단, 연결편(환승)일 수도 있으니 시간 차이가 큼(24시간 이상)을 체크할 수도 있지만
                # 보통 인천 출발이면 새 스케줄입니다.
                rots.append(t_rot)
                t_rot = []
            
            t_rot.append(f)
            
            if f['arr'] in ['ICN', 'GMP']:
                rots.append(t_rot)
                t_rot = []
                
        if t_rot: rots.append(t_rot) # 마지막 잔여 스케줄

        # 5. CSV 생성
        csv_rows = []

        # 리저브
        if res_input and unique_flights:
            base_date = unique_flights[0]['std']
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

        # 비행
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