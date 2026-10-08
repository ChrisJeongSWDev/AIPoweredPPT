---
write_scope: none
read_refs:
  - "c:/Users/2021670/Documents/멀티 에이전트/tasks/AI_Powered_PPT/src/aippt/canvas/static/index.html"
  - "c:/Users/2021670/Documents/멀티 에이전트/tasks/AI_Powered_PPT/src/aippt/canvas/static/style.css"
---
# Task
You are Codex Critic (acting as a Reviewer / Director). 
The user has provided a checklist of UI changes they want. Some have been implemented, some might be missing, and some might be poorly aligned in the current CSS/HTML. 

# User's Request / Checklist
- 디자인 전면 개편: 이전의 투명한 글래스모피즘 효과 대신, 배경을 깔끔한 흰색(Solid White)으로 변경하고 테두리와 그림자로 세련된 느낌만 살린 단일 컨테이너(Single Container) 형태.
- 배치 및 아이콘 변경: 프롬프트 입력창 좌측 하단에 + 아이콘과 함께 Gemini 모델 선택 드롭다운을 배치, 우측 하단에는 보내기(Submit) 역할을 하는 둥근 화살표(➔) 버튼 적용 (Antigravity 창과 동일한 감각).
- Paste Gem JSON 위치: 좌측 툴바의 "JSON & Data" 섹션 내 버튼들 바로 아래로 이동.
- Save / Load Template 버튼 한 줄 배치: Save와 Load 버튼이 한 줄(1열)에 나란히 배치. (Wait, later they say "Save 100%, Load 100%" - clarify this!).
- JSON Textbox 뷰어 버튼 강조: "View & Copy JSON 📝" 버튼을 파란색 배경으로 크고 눈에 띄게 강조.
- JSON & Data 그룹 정렬:
  - View & Copy JSON: 상단 전체 너비(100%) 다크 버튼으로 배치.
  - [ Download JSON ] [ Load JSON ]: 아래에 50:50 나란히 배치되는 2컬럼 레이아웃.
- Export Deck (슬라이드 추출) 그룹 정렬:
  - [ Export PPT ] [ Download HTML ]: 50:50 2컬럼 다크 프리미엄 스타일로 정렬.
- Server Templates (서버 템플릿) 그룹 정렬:
  - Name 입력창: 라벨과 입력창 세로형(Stacked) 100% 수평 정렬.
  - Save Template 버튼: 100% 수평 정렬.
  - Templates 드롭다운: 100% 수평 정렬.
  - Load Template 버튼: 드롭다운 바로 아래 100% 수평 정렬. (User requested Save/Load 1 row earlier, but here requests 100% stacked for Server Templates. Follow the 100% stacked layout for the Server Templates group).
- UI 버튼 공통 디테일 최적화 (style.css):
  - 모던한 슬레이트 블루/다크톤(#1e293b) 컬러 팔레트 적용.
  - 호버(Hover) 시 부드러운 전환 효과(Transition) 및 라운딩 둥근 모서리(5px) 통일.
  - 폰트 두께, 여백(Padding), 인풋/버튼간 높이 비율 균형 조정.

# Instructions
1. Review the CURRENT state of `index.html` and `style.css` (specifically the sidebar buttons, `#ai` composer, etc.).
2. Write a detailed CRITIQUE identifying what is currently wrong, missing, or misaligned with the user's checklist.
3. Provide a clear, concrete WORK ORDER (Action Plan) for the Claude Sonnet worker to fix these issues. Focus purely on CSS layout (flexbox grids, widths) and HTML class structure.
