# Web Legal Compliance AI Agent — TDD 구현 TODO

> **TDD 사이클**: Red (실패 테스트 작성) → Green (최소 구현) → Refactor
> 체크박스: `- [x]` 완료 / `- [ ]` 미완료
> 각 모듈은 **테스트 파일 먼저** 작성 후 구현합니다.
> **테스트 주석 기준**: 모듈 docstring에 테스트 전략 설명, 각 테스트 함수에 1줄 docstring 필수

---

## 0. 프로젝트 초기 설정

- [x] 폴더 구조 생성 (`src/`, `scripts/`, `data/`, `tests/`)
- [x] `pyproject.toml` 작성 (의존성 + pytest, pytest-asyncio, pytest-mock 포함)
- [x] `uv sync` 실행 및 `uv.lock` 생성
- [x] `.env.example` 작성 (`OPENAI_API_KEY`, `QDRANT_URL`, `REDIS_URL`, `LAW_API_KEY`)
- [x] `.gitignore` 작성
- [x] `tests/conftest.py` 작성 (공통 픽스처: mock LLM, mock Qdrant, mock Redis)
- [x] 전체 테스트 파일 주석 보강 (모듈 docstring 테스트 전략 + 각 테스트 함수 1줄 docstring)

---

## 1. 핵심 공통 모듈 (`src/core/`)

### 1-1. models.py
- [x] **[Red]** `tests/core/test_models.py` 작성
  - [x] `LawArticle` 필드 검증 테스트 (article_id, law_name, content, sha256, url, updated_at)
  - [x] `Citation` 포맷 검증 테스트
  - [x] `ComplianceReport` 준수/위반 분류 테스트
- [x] **[Green]** `src/core/models.py` 구현 (Pydantic BaseModel)
- [x] **[Refactor]** 유효성 검사 validator 추가

### 1-2. config.py
- [x] **[Red]** `tests/core/test_config.py` 작성
  - [x] 환경변수 누락 시 예외 발생 테스트
  - [x] 기본값 설정 테스트
- [x] **[Green]** `src/core/config.py` 구현 (pydantic BaseSettings)
- [x] **[Refactor]** 환경별 설정 분리 (dev / prod)

### 1-3. logger.py
- [x] **[Green]** `src/core/logger.py` 구현 (loguru, 테스트 불필요)

---

## 2. SHA-256 무결성 관리 (`src/integrity/`)

### 2-1. hasher.py
- [x] **[Red]** `tests/integrity/test_hasher.py` 작성
  - [x] 동일 텍스트 → 동일 해시 테스트
  - [x] 다른 텍스트 → 다른 해시 테스트
  - [x] 빈 문자열 해시 테스트
- [x] **[Green]** `src/integrity/hasher.py` 구현 (hashlib.sha256)
- [x] **[Refactor]** 인코딩 처리 통일

### 2-2. db.py
- [x] **[Red]** `tests/integrity/test_db.py` 작성 (SQLite in-memory)
  - [x] 테이블 생성 테스트
  - [x] 신규 조항 INSERT 테스트
  - [x] 해시 변경 감지 테스트 (hash_curr ≠ hash_prev → True 반환)
  - [x] 해시 동일 시 스킵 테스트 (→ False 반환)
  - [x] 이력 조회 테스트
- [x] **[Green]** `src/integrity/db.py` 구현 (SQLite CRUD)
- [x] **[Refactor]** 트랜잭션 처리 및 예외 핸들링

---

## 3. 법령 수집 (`src/collector/`)

### 3-1. parser.py
- [x] **[Red]** `tests/collector/test_parser.py` 작성
  - [x] 정상 XML 응답 → `LawArticle` 리스트 변환 테스트
  - [x] 필드 누락 응답 처리 테스트
  - [x] 빈 응답 처리 테스트
- [x] **[Green]** `src/collector/parser.py` 구현
- [x] **[Refactor]** 파싱 오류 로깅 추가

### 3-2. law_api.py
- [x] **[Red]** `tests/collector/test_law_api.py` 작성 (requests mock)
  - [x] API 정상 호출 테스트 (7개 법령 각각)
  - [x] 네트워크 오류 재시도 테스트
  - [x] API 키 누락 시 예외 테스트
- [x] **[Green]** `src/collector/law_api.py` 구현 (law.go.kr Open API)
  - [x] 개인정보보호법, 정보통신망법, 위치정보법
  - [x] 안전성 확보 조치 기준
  - [x] 전자상거래법, 청소년보호법, 신용정보법
- [x] **[Refactor]** rate limit 처리, 지수 백오프 재시도

### 3-3. scheduler.py
- [x] **[Red]** `tests/collector/test_scheduler.py` 작성 (APScheduler mock)
  - [x] 스케줄 등록 테스트
  - [x] 수집 → SHA 비교 → 재임베딩 흐름 테스트
- [x] **[Green]** `src/collector/scheduler.py` 구현
- [x] **[Refactor]** 스케줄 주기 config화

---

## 4. 임베딩 & 색인 (`src/embedder/`)

### 4-1. chunker.py
- [x] **[Red]** `tests/embedder/test_chunker.py` 작성
  - [x] chunk_size 이하 텍스트 → 단일 청크 테스트
  - [x] chunk_size 초과 텍스트 → 복수 청크 + overlap 테스트
  - [x] 메타데이터 보존 테스트 (article_id, sha 등)
- [x] **[Green]** `src/embedder/chunker.py` 구현 (RecursiveCharacterTextSplitter)
- [x] **[Refactor]** 법령 조항 구분자 우선 분할

### 4-2. indexer.py
- [x] **[Red]** `tests/embedder/test_indexer.py` 작성 (Qdrant mock)
  - [x] 신규 조항 upsert 테스트
  - [x] 변경된 조항만 재임베딩 테스트
  - [x] 변경 없는 조항 스킵 테스트
  - [x] 컬렉션 없으면 자동 생성 테스트
- [x] **[Green]** `src/embedder/indexer.py` 구현 (qdrant-client)
- [x] **[Refactor]** 배치 upsert로 성능 최적화

---

## 5. 입력 처리 (`src/input/`)

### 5-1. file_loader.py
- [x] **[Red]** `tests/input/test_file_loader.py` 작성 (tmp_path 픽스처)
  - [x] `.py` 파일 로드 테스트
  - [x] `.html` 파일 로드 테스트
  - [x] `.js` / `.css` 파일 로드 테스트
  - [x] 존재하지 않는 경로 예외 테스트
  - [x] 미지원 확장자 예외 테스트
- [x] **[Green]** `src/input/file_loader.py` 구현
- [x] **[Refactor]** 확장자별 인코딩 처리

### 5-2. url_parser.py
- [x] **[Red]** `tests/input/test_url_parser.py` 작성 (responses mock)
  - [x] HTML 파싱 + JS/CSS/meta 태그 추출 테스트
  - [x] 잘못된 URL 예외 테스트
  - [x] 타임아웃 처리 테스트
- [x] **[Green]** `src/input/url_parser.py` 구현 (requests + BeautifulSoup4)
- [x] **[Refactor]** 상대 경로 → 절대 URL 변환

### 5-3. token_splitter.py
- [x] **[Red]** `tests/input/test_token_splitter.py` 작성
  - [x] 한도 이내 텍스트 → 단일 청크 반환 테스트
  - [x] 한도 초과 텍스트 → 복수 청크 반환 테스트
  - [x] chunk_size = ctx_limit × 0.7 검증 테스트
  - [x] overlap = 200 토큰 검증 테스트
- [x] **[Green]** `src/input/token_splitter.py` 구현 (tiktoken)
- [x] **[Refactor]** 모델별 ctx_limit 매핑 테이블

---

## 6. 검색 레이어 (`src/retrieval/`)

### 6-1. cache.py
- [x] **[Red]** `tests/retrieval/test_cache.py` 작성 (Redis mock)
  - [x] cosine ≥ 0.95 → 캐시 히트 반환 테스트
  - [x] cosine < 0.95 → 캐시 미스 테스트
  - [x] TTL 1시간 설정 검증 테스트
  - [x] 캐시 저장 테스트
- [x] **[Green]** `src/retrieval/cache.py` 구현 (redis-py)
- [x] **[Refactor]** 직렬화 방식 통일 (JSON)

### 6-2. bm25.py
- [x] **[Red]** `tests/retrieval/test_bm25.py` 작성
  - [x] 조항 번호 정확 매칭 테스트 (e.g. "제17조")
  - [x] 법률 용어 매칭 테스트
  - [x] 빈 코퍼스 예외 테스트
- [x] **[Green]** `src/retrieval/bm25.py` 구현 (rank-bm25)
- [x] **[Refactor]** 형태소 분석기 연동 (선택)

### 6-3. vector.py
- [x] **[Red]** `tests/retrieval/test_vector.py` 작성 (Qdrant mock)
  - [x] 쿼리 임베딩 생성 테스트
  - [x] Qdrant 검색 결과 반환 테스트
  - [x] payload 필터 적용 테스트
- [x] **[Green]** `src/retrieval/vector.py` 구현 (text-embedding-3-small + qdrant-client)
- [x] **[Refactor]** 배치 임베딩 처리

### 6-4. rrf.py
- [x] **[Red]** `tests/retrieval/test_rrf.py` 작성
  - [x] BM25 + Vector 결과 융합 점수 계산 테스트
  - [x] 중복 문서 통합 테스트
  - [x] 결과 내림차순 정렬 테스트
- [x] **[Green]** `src/retrieval/rrf.py` 구현 (Reciprocal Rank Fusion)
- [x] **[Refactor]** k 파라미터 config화

### 6-5. dynamic_topk.py
- [x] **[Red]** `tests/retrieval/test_dynamic_topk.py` 작성
  - [x] threshold 이상 스코어 개수 클램핑 테스트
  - [x] 빈 스코어 → min_k 반환 테스트
  - [x] max_k 초과 클램핑 테스트
- [x] **[Green]** `src/retrieval/dynamic_topk.py` 구현
- [x] **[Refactor]** 복잡도 판별 기준 고도화

### 6-6. query_rewriter.py
- [x] **[Red]** `tests/retrieval/test_query_rewriter.py` 작성 (LLM mock)
  - [x] LLM 재작성 쿼리 반환 테스트
  - [x] Multi-Query 확장 테스트 (N개 쿼리 반환)
  - [x] 빈 쿼리 ValueError 테스트
  - [x] 빈 LLM 응답 fallback 테스트
- [x] **[Green]** `src/retrieval/query_rewriter.py` 구현
- [x] **[Refactor]** 프롬프트 템플릿 분리

---

## 7. 멀티 에이전트 (`src/agents/`)

### 7-1. citation.py
- [x] **[Red]** `tests/agents/test_citation.py` 작성
  - [x] 중복 조항 제거 테스트
  - [x] SHA + URL + 개정일 부착 테스트
  - [x] 출력 포맷 검증 테스트
- [x] **[Green]** `src/agents/citation.py` 구현 (Citation Assembler)
- [x] **[Refactor]** article_id 기준 중복 제거

### 7-2. privacy_agent.py
- [x] **[Red]** `tests/agents/test_privacy_agent.py` 작성 (LLM mock)
  - [x] 동의 코드 존재 시 준수 판정 테스트
  - [x] 민감정보 처리 코드 감지 테스트
  - [x] Citation 반환 테스트
- [x] **[Green]** `src/agents/privacy_agent.py` 구현
- [x] **[Refactor]** BaseAgent 공통 로직 분리

### 7-3. security_agent.py
- [x] **[Red]** `tests/agents/test_security_agent.py` 작성 (LLM mock)
  - [x] 평문 비밀번호 패턴 탐지 테스트
  - [x] HTTP → HTTPS 리다이렉트 미적용 탐지 테스트
  - [x] Citation 반환 테스트
- [x] **[Green]** `src/agents/security_agent.py` 구현
- [x] **[Refactor]** BaseAgent 공통 로직 분리

### 7-4. service_agent.py
- [x] **[Red]** `tests/agents/test_service_agent.py` 작성 (LLM mock)
  - [x] 결제 코드 감지 → 전자상거래법 적용 테스트
  - [x] 사업자 정보 미표시 탐지 테스트
  - [x] Citation 반환 테스트
- [x] **[Green]** `src/agents/service_agent.py` 구현
- [x] **[Refactor]** BaseAgent 공통 로직 분리

### 7-5. orchestrator.py
- [x] **[Red]** `tests/agents/test_orchestrator.py` 작성 (Sub-Agent mock)
  - [x] 3개 에이전트 모두 호출 테스트
  - [x] 병렬 결과 병합 테스트
  - [x] 빈 입력 → 빈 리스트 반환 테스트
- [x] **[Green]** `src/agents/orchestrator.py` 구현
- [x] **[Refactor]** 3 에이전트 순차 호출 병합

---

## 8. 스트리밍 레이어 (`src/streaming/`)

- [x] **[Red]** `tests/streaming/test_redis_stream.py` 작성 (Redis mock)
  - [x] XADD 호출 및 메시지 포맷 테스트
  - [x] XREAD 결과 역직렬화 테스트
  - [x] 에이전트별 채널 분리(stream:{channel}) 테스트
- [x] **[Green]** `src/streaming/redis_stream.py` 구현
- [x] **[Refactor]** JSON 직렬화/역직렬화 통일

---

## 9. 스크립트 (`scripts/`)

- [x] **[Red]** `tests/test_setup_index.py` 작성 (전체 파이프라인 mock)
  - [x] 수집 → SHA 비교 → 임베딩 전체 흐름 테스트
  - [x] 변경 없는 조항 스킵 테스트
- [x] **[Green]** `scripts/setup_index.py` 구현
- [x] **[Refactor]** changed_ids 집합 반환으로 선택적 색인

### 9-2. load_html_laws.py
- [x] **[Green]** `scripts/load_html_laws.py` 구현
  - [x] `data/laws/*.html` 전체 로드 → parse_law_html → setup_index 파이프라인
  - [x] 파일명 → law_id_prefix 매핑 테이블
  - [x] 파싱 결과 요약 출력 (법령별 조문 수, 총계)

---

## 10. 통합 테스트 (`tests/integration/`)

- [ ] `tests/integration/test_e2e_file.py` — 파일 입력 E2E
  - [ ] 의도적 위반 코드 → 위반 항목 탐지 확인
  - [ ] 준수 코드 → 준수 판정 확인
- [ ] `tests/integration/test_e2e_url.py` — URL 입력 E2E
- [ ] `tests/integration/test_cache_hit.py` — Semantic Cache 히트/미스
- [ ] `tests/integration/test_stream_order.py` — Redis Stream 순서 보장
- [ ] `tests/integration/test_citation_integrity.py` — Citation SHA 정합성

---

## 11. Streamlit UI (`app.py`)

- [x] 입력 폼 (파일 업로드 / URL / 코드 직접 입력 탭)
- [x] 분석 실행 버튼
- [x] 준수 항목(✅) / 보완 항목(⚠️) 구분 출력
- [x] Citation 카드 (SHA 앞 8자 + 원문 링크)
- [x] 위반 항목 권고사항 표시

---

## 12. 인프라 (`Docker`)

- [x] `Dockerfile` 작성 (uv 멀티스테이지 빌드)
- [x] `docker-compose.yml` 작성 (qdrant + redis + app)
- [x] `.dockerignore` 작성
- [ ] `docker compose up --build` 정상 기동 확인

---

## 진행 현황 요약

| 모듈 | 테스트 작성 | 구현 | 리팩터 |
|------|------------|------|--------|
| 프로젝트 초기 설정 | - | **완료** | - |
| core/models | **완료** | **완료** | **완료** |
| core/config | **완료** | **완료** | **완료** |
| integrity/hasher | **완료** | **완료** | **완료** |
| integrity/db | **완료** | **완료** | **완료** |
| collector/parser | **완료** | **완료** | **완료** |
| collector/law_api | **완료** | **완료** | **완료** |
| collector/scheduler | **완료** | **완료** | **완료** |
| embedder/chunker | **완료** | **완료** | **완료** |
| embedder/indexer | **완료** | **완료** | **완료** |
| input/file_loader | **완료** | **완료** | **완료** |
| input/url_parser | **완료** | **완료** | **완료** |
| input/token_splitter | **완료** | **완료** | **완료** |
| retrieval/cache | **완료** | **완료** | **완료** |
| retrieval/bm25 | **완료** | **완료** | **완료** |
| retrieval/vector | **완료** | **완료** | **완료** |
| retrieval/rrf | **완료** | **완료** | **완료** |
| retrieval/dynamic_topk | **완료** | **완료** | **완료** |
| retrieval/query_rewriter | **완료** | **완료** | **완료** |
| agents/citation | **완료** | **완료** | **완료** |
| agents/privacy | **완료** | **완료** | **완료** |
| agents/security | **완료** | **완료** | **완료** |
| agents/service | **완료** | **완료** | **완료** |
| agents/orchestrator | **완료** | **완료** | **완료** |
| streaming/redis_stream | **완료** | **완료** | **완료** |
| scripts/setup_index | **완료** | **완료** | **완료** |
| 통합 테스트 | 미완료 | - | - |
| Streamlit UI | - | **완료** | - |
| Docker 인프라 | - | **완료** | - |
