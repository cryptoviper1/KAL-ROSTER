import streamlit as st

st.set_page_config(page_title="서비스 이전 안내 | KAL Roster", page_icon="✈️", layout="centered")

st.warning("⚠️ 이 버전은 운영이 종료되었습니다. 새로운 서비스로 이전되었습니다.")

st.markdown("""
## ✈️ KAL Roster — 새 버전으로 이전했습니다

안녕하세요. 기존 Python 기반 서비스는 운영을 종료하고,  
완전히 새롭게 개발된 웹 서비스 버전으로 이전하였습니다.

---

### 무엇이 달라졌나요?

| 항목 | 기존 버전 | 새 버전 |
|------|----------|--------|
| 로그인 | 불필요 | 구글 계정 1회 로그인 |
| 캘린더 등록 | CSV / iCal 직접 가져오기 | **Google Calendar 자동 동기화** |
| 퍼 디엠 계산 | ✅ | ✅ (합의서 최신 기준 반영) |
| 크루 명단 / Show Up 시간 | ✅ | ✅ |
| F/O · 기장 전환 | ❌ | ✅ |
| 스케줄 미리보기 | ❌ | ✅ |

---

### 🔗 새 서비스 바로가기
""")

st.link_button("✈️ kalroster.com 바로가기 →", "https://kalroster.com", use_container_width=True, type="primary")

st.markdown("""
---

**사용 방법은 기존과 동일합니다.**  
구글 계정으로 로그인 후, 마이스케줄 텍스트와 Crew Roster HTML 텍스트를 붙여넣기 하시면 됩니다.

---

> 💡 **로그인 시 "확인되지 않은 앱" 경고가 뜨는 경우**  
> 구글 공식 심사 진행 중입니다. **[고급] → [kalroster.com으로 이동(안전하지 않음)]** 을 클릭하시면 정상 이용 가능합니다.  
> 입력하신 스케줄 데이터는 서버에 저장되지 않습니다.

---

문의: onu0823@gmail.com
""")

st.stop()
