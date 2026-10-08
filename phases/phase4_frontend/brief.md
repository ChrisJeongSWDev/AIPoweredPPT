---
target_repo: "c:/Users/2021670/Documents/멀티 에이전트"
write_scope: "tasks/AI_Powered_PPT/src/aippt/canvas/app.py, tasks/AI_Powered_PPT/tests/canvas/test_app.py"
claude_model: sonnet
reviewer: codex-critic
phase: phase4_frontend
change_detail_path: tasks/AI_Powered_PPT/phases/phase4_frontend/change_detail.md
---
# Phase 4 Frontend Integration - Enhanced Work Order (REPAIR)

## 🚨 REPAIR CONTINUATION (TAMPER RECOVERY)
This is a continuation of the previous run which was blocked by a PARENT TAMPER DETECTED safety stop. Your exact previous work has been preserved in the staging clone at `/c/Users/2021670/.ma-stg/stg.77hGHTWW/`. 
To complete this repair task:
1. Simply read the preserved files from the staging clone:
   - `/c/Users/2021670/.ma-stg/stg.77hGHTWW/tasks/AI_Powered_PPT/src/aippt/canvas/app.py`
   - `/c/Users/2021670/.ma-stg/stg.77hGHTWW/tasks/AI_Powered_PPT/tests/canvas/test_app.py`
2. Copy their contents VERBATIM to the target files in the current repository.
3. You do not need to re-think or re-implement Phase 4. Just restore your previous work and mark as done.

*(Claude Opus WorkDirector의 분석 결과를 바탕으로 강화된 지시서입니다.)*

## 목표 (Goal)
프론트엔드(`src/aippt/canvas/app.py`)의 라이브 저작(/api/generate) 기능을 기존 기획된 Gemini API 통신에서, Phase 3에 구현된 `CliWorkerClient`(Claude Sonnet, GPT 등) 기반 파이프라인으로 전환합니다.

## Opus Analysis Findings (Root Cause & Strategy)
1. **`CliWorkerClient` 연동 방식**: `aippt.adapters.ai_adapter`에 구현되어 있으며, `complete_json(*, system, user, schema, max_tokens)`를 동기적(synchronous)으로 호출합니다. 생성자 인자는 `track="b"`, `backend="claude" | "codex"`, `model="..."` 형태로 넘겨야 합니다.
2. **프론트엔드 안전성**: `editor.js`는 `/api/context` 응답의 `models` 리스트 전체를 소비하지 않고 오직 `mode`와 `model` 상태만 체크하므로, 백엔드에서 `MODEL_PROFILES`를 변경해도 UI 호환성(breaking change) 문제가 발생하지 않습니다.
3. **스키마 충돌 회피**: Canvas IR 스키마(`schema.json`)는 `target` 객체(내부에 템플릿의 `template_sha256` 등)를 필수 요구합니다. 모델은 이 SHA 값을 알 수 없으므로, 워커에게 넘겨줄 프롬프트용 스키마에서는 `target`을 필수가 아니게(Relax) 완화하여 넘기고, 결과물을 받은 뒤 `_finalize_live_ir`에서 실제 핀(Pin) 데이터를 주입해야 합니다.
4. **테스트 코드 대응**: `tests/canvas/test_app.py` 내의 라이브 테스트가 기존 `_call_gemini`를 몽키패치하고 있습니다. 이 부분을 `CliWorkerClient.complete_json`을 패치하도록 갱신해야 합니다.

## 구현 지시사항 (Execution Steps)

1. **모델 리스트(MODEL_PROFILES) 변경 (`app.py`)**
   기존 `gemini-3.5-flash` 등을 제거하고 아래 4종으로 변경:
   - "sonnet": `{"label": "Claude Sonnet 5", "thinking": "MEDIUM"}` (backend: claude)
   - "opus": `{"label": "Claude Opus", "thinking": "HIGH"}` (backend: claude)
   - "gpt-5.6-terra": `{"label": "GPT 5.6 Terra", "thinking": "HIGH"}` (backend: codex)
   - "gpt-5.6-sol": `{"label": "GPT 5.6 Sol", "thinking": "HIGH"}` (backend: codex)
   * `DEFAULT_PROFILE`은 "sonnet"으로 설정합니다.

2. **모드 판별 (`server_mode`) 변경 (`app.py`)**
   기존 `gemini_api_key()` 기반 모드 판별을 환경 변수 `AIPPT_LIVE_MODE=1` 존재 여부로 변경합니다.
   * `gemini_api_key`, `gemini_model`, `DEFAULT_GEMINI_MODEL` 등 불필요한 함수/상수를 삭제합니다.

3. **라이브 생성 (`generate_live` 대체) 구현 (`app.py`)**
   - 기존 `_call_gemini` 대신 `CliWorkerClient`를 초기화합니다.
   - 요청된 profile에 따라 `backend`와 `model` 값을 매핑하여 `CliWorkerClient` 인스턴스를 생성합니다.
   - `validate.py`의 `load_schema()`를 재사용해 스키마를 불러오고, `target` 필드를 `required`에서 임시로 제거하여 모델에게 넘깁니다.
   - 반환된 JSON은 `_finalize_live_ir`를 통해 `target`을 주입받아 유효한 Canvas IR로 완성됩니다.

4. **테스트 수정 (`tests/canvas/test_app.py`)**
   - `_call_gemini` 모킹을 `aippt.adapters.ai_adapter.CliWorkerClient.complete_json` 모킹으로 변경합니다.
   - 모드 전환 트리거를 `GEMINI_API_KEY` 환경변수 세팅에서 `AIPPT_LIVE_MODE=1`로 갱신합니다.
