# Phase 4: 실전 Gemini API 연동 및 Web Gem 워크플로우 통합

Phase 4의 핵심 목표는 더미(Mock) 모드를 넘어서 **실제 Gemini 모델과 연동**하고, 사용자가 요청한 **두 가지 방식(자체 API 호출, Web Gem 복사/붙여넣기)**을 모두 우아하게 지원하는 것입니다.

## 1. 구현 방향 (Proposed Changes)

### A. 자체 챗 (Direct API) 방식 
백엔드(`app.py`)의 `/api/generate`를 수정하여, 실제 Google Gemini API를 호출합니다.
- `google-genai` 라이브러리를 사용합니다 (`requirements.txt` 추가).
- 환경 변수 `GEMINI_API_KEY`가 있으면 실제 API(`gemini-2.5-flash` 등)를 호출하고, `Gemini_Web_Prompt.md`의 내용을 System Instruction으로 주입하여 JSON 응답을 받아옵니다.
- 만약 API Key가 없으면 기존처럼 더미(Mock) 데이터를 반환하도록 Fallback 처리하여 로컬 개발 환경이 깨지지 않게 보호합니다.
- 프론트엔드는 `/api/context`를 통해 현재 서버가 API 모드인지 Mock 모드인지 인지하고, UI의 뱃지(`mock` -> `live`)를 변경합니다.

### B. Web Gem 연동 (Paste JSON) 방식
Gemini Web(또는 ChatGPT 등)에서 생성된 JSON 텍스트를 파일로 저장하지 않고 즉시 에디터에 적용할 수 있는 기능을 추가합니다.
- **UI 추가**: "Paste Gem JSON" (또는 "클립보드에서 불러오기") 버튼을 추가합니다.
- **로직**: `navigator.clipboard.readText()`를 통해 클립보드의 텍스트를 읽은 후 JSON 파싱, 곧바로 기존의 철통 보안 게이트인 `loadIR()`로 넘깁니다. 실패 시 적절한 경고(toast/banner)를 표시합니다.

## 2. 작업 대상 파일 (Write Scope)
- `src/aippt/canvas/app.py`: Gemini API 연동 및 `/api/context` 상태 추가
- `src/aippt/canvas/static/index.html`: 클립보드 붙여넣기 버튼 및 상태 뱃지 추가
- `src/aippt/canvas/static/editor.js`: 클립보드 읽기 및 `/api/context` 연동 로직
- `requirements.txt`: `google-genai` 패키지 추가
- `tests/canvas/test_app.py`: API 모드 활성화 시나리오에 대한 Mocking 테스트 추가

## 3. 검증 계획 (Verification Plan)
- **API 미설정 시**: 기존처럼 1.5초 후 Mock 데이터가 정상적으로 나타나고 테스트가 통과하는지 확인.
- **클립보드 붙여넣기**: 잘못된 텍스트 붙여넣기 시 에러 배너 표시, 올바른 JSON 붙여넣기 시 성공적으로 렌더링되는지 수동 검증.
