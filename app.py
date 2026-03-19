import streamlit as st

st.set_page_config(page_title="서비스 이전 안내 | KAL Roster", page_icon="✈️", layout="centered")

st.warning("⚠️ 이 버전은 운영이 종료되었습니다. 아래 새 서비스를 이용해 주세요.")

st.markdown("""
## 📢 서비스 이전 안내

안녕하세요, KAL Roster 서비스를 이용해 주시는 모든 분들께 감사드립니다.

기존에 사용하시던 **Python 기반 Streamlit 버전**은 운영을 종료하고, 완전히 새롭게 개발된 **웹 서비스 버전**으로 이전하였습니다.

새 버전에서는 파일 다운로드 없이 구글 계정 하나로 로그인하면 스케줄을 **Google Calendar에 직접 동기화**할 수 있습니다.

---

### 달라진 점

기존 버전은 CSV/iCal 파일을 다운로드한 뒤 직접 캘린더에 가져오는 방식이었지만, 새 버전은 구글 계정과 직접 연동되어 버튼 하나로 동기화가 완료됩니다. 퍼 디엠 계산, 크루 명단, Show Up 시간 등 기존 기능은 모두 그대로 유지되며, F/O · 기장 전환 토글 및 스케줄 미리보기 기능도 새롭게 추가되었습니다.

---

### 🔗 새 서비스 바로가기

""")

st.link_button("✈️ KAL Roster Hub 바로가기 →", "https://kal-roster-app.vercel.app/", use_container_width=True, type="primary")

st.markdown("""
---

구글 계정으로 로그인하신 후, 기존과 동일하게 마이스케줄 텍스트와 Crew Roster HTML 텍스트를 붙여넣기 하시면 됩니다.

---

### 보안 관련 안내

로그인 시 **"확인되지 않은 앱"** 경고가 뜰 수 있습니다. 구글 공식 심사 전 단계이므로 **[고급] → [이동(안전하지 않음)]** 을 선택하시면 정상 이용 가능합니다. 입력하신 스케줄 데이터는 서버에 저장되지 않습니다.

---

문의: onu0823@gmail.com
""")

st.stop()