# ISSUE TODO

## [BUG-1] Citation SHA/날짜가 가짜 기본값으로 출력됨

**증상**: `📚 전자상거래법 제13조 · sha:00000000 · 2024-01-01 · 원문 링크`

**원인**:
- `src/agents/_base_agent.py`의 `_make_citation()`이 `ArticleDB.get_info(article_id)`로 DB 조회
- LLM이 생성한 article_id (예: `PA_15`, `EC_13`)가 실제 `article_hashes` 테이블에 없으면
  `sha256 = "0" * 64`, `updated_at = datetime(2024, 1, 1)` 기본값 사용
- DB에 article_id가 없는 이유: LLM이 임의로 article_id를 생성하고, 에이전트 프롬프트에
  DB에 존재하는 실제 article_id 형식이 안내되어 있지 않음

**수정 계획**:
- `ArticleDB`에 `find_by_law(law_name, article_number) -> dict | None` 메서드 추가
- `_make_citation()`에서 article_id DB 조회 실패 시 law_name + article_number로 fallback 검색
- 그래도 없으면 sha256 "N/A" 표시 대신 실제 content SHA 계산 또는 명시적 "미등록" 표기

**관련 파일**:
- `src/agents/_base_agent.py:18-39` (`_make_citation`)
- `src/integrity/db.py` (`ArticleDB`)
- `tests/integrity/test_db.py`
- `tests/agents/test_base_agent.py` (신규)

---

## [BUG-2] code_snippet 파싱 버그 (pipe split off-by-one)

**증상**: LLM이 code_snippet을 포함한 응답을 반환해도 `recommendation` 필드가 비어 있을 수 있음

**원인**:
- `_parse_llm_response()`에서 `content.split("|")`로 무제한 분리
- description 또는 다른 필드에 `|`가 포함되면 parts 인덱스가 밀림
- 예: `violation|설명|부분|개인정보 보호법|제15조|PA_15|problematic_code` → parts가 7개이지만
  앞 필드 중 하나에 `|`가 있으면 code_snippet이 엉뚱한 값이 됨

**수정 계획**:
- `content.split("|", maxsplit=5)` 사용 → 마지막 필드(code_snippet)에 `|` 허용
- `parts[6]` 체크 로직 제거, 항상 `parts[5]` 사용

**관련 파일**:
- `src/agents/_base_agent.py:44-48` (`_parse_llm_response`)
- `tests/agents/test_base_agent.py` (신규)

---

## [NEW-1] 소스코드 위치 표시 기능 미구현

**배경**: 현재 LLM이 위반으로 판단한 code_snippet은 `recommendation` 필드에 저장되어 UI에서
"문제 코드"로 표시되나, 원본 입력 코드에서 **몇 번째 줄인지 위치 정보가 없음**.

**요구사항**:
- 분석 결과에서 문제 코드 스니펫의 **라인 번호(시작/끝)** 표시
- 원본 코드 내에서 code_snippet을 찾아 위치 매핑
- UI에서 `라인 12-14:` 형식으로 표시

**구현 계획** (TDD):
1. `ComplianceReport`에 `source_location: SourceLocation | None = None` 필드 추가
2. `SourceLocation(BaseModel)`: `line_start: int`, `line_end: int`, `snippet: str`
3. `BaseAgent.analyze()`에서 code_snippet을 원본 코드에서 찾아 라인 번호 계산
4. `app.py` UI에서 라인 번호 포함 렌더링

**관련 파일**:
- `src/core/models.py` (SourceLocation, ComplianceReport 수정)
- `src/agents/_base_agent.py` (BaseAgent.analyze 수정)
- `app.py` (UI 렌더링)
- `tests/core/test_models.py`
- `tests/agents/test_base_agent.py` (신규)

---

## 진행 상태

- [x] BUG-1: ArticleDB.find_by_law() + _make_citation fallback (TDD) — `src/integrity/db.py`, `src/agents/_base_agent.py`
- [x] BUG-2: code_snippet maxsplit=5 파싱 수정 — `src/agents/_base_agent.py`
- [x] NEW-1: SourceLocation 모델 + BaseAgent 위치 매핑 + UI 표시 (TDD) — `src/core/models.py`, `src/agents/_base_agent.py`, `app.py`
