# 부동산 법령 AI — 개발 로드맵 (TDD 기반)

> 도메인: **부동산법** (주택법·공인중개사법·건축법 등)
> 핵심: 법령 Open API 수집 → 조문 단위 청킹 → RAG Reasoning Agent → 대화형 UI (좌: 채팅 / 우: 인용 패널)

---

## 방향 전환 요약

| 제거 | 유지 | 신규 |
|------|------|------|
| URL/파일 입력 & 웹 분석 | core models · config · logger | 부동산 법령 도메인 정의 |
| PrivacyAgent · SecurityAgent · ServiceAgent | embedder (chunker · indexer) | 판례 API 수집 파이프라인 |
| Orchestrator (웹 분석용) | retrieval (BM25 · vector · hybrid · RRF) | 법령 관계 그래프 (NetworkX) |
| parse-url / parse-file 엔드포인트 | Redis Stream · Qdrant · SQLite | LegalReasoningAgent |
| URL 캐시 | FastAPI 기본 구조 | 대화 세션 (conversation memory) |
| 웹 보안 테스트 전체 | integrity (SHA-256) | /api/chat 엔드포인트 + SSE |

---

## Phase 0 — 프로젝트 정리 (Cleanup)

> 웹 분석 기능 제거, 도메인 모델 재정의

### 0-1. 도메인 모델 재정의 (`src/core/models.py`)
- [x] `LawArticle` — 유지 (필드 정리)
- [x] `Citation` — 유지 (판례 출처 필드 추가: `case_number`, `court`, `decision_date`)
- [x] `ComplianceReport` → **`LegalAnswer`** 로 교체
- [x] `CaseArticle` (판례 전용 모델) 신규 추가
- [ ] TDD: `tests/core/test_models.py` 업데이트

### 0-2. 제거 대상 파일 목록 정리 후 삭제
- [x] `api/routers/parse.py`
- [x] `src/input/url_parser.py`
- [x] `src/input/file_loader.py`
- [x] `src/input/token_splitter.py`
- [x] `src/agents/privacy_agent.py`
- [x] `src/agents/security_agent.py`
- [x] `src/agents/service_agent.py`
- [x] `src/agents/orchestrator.py`
- [x] `src/cache/url_cache.py`

### 0-3. 테스트 정리
- [x] 웹 분석 관련 테스트 삭제
  - `tests/input/` 전체
  - `tests/agents/test_orchestrator.py`, `test_privacy_agent.py`, `test_security_agent.py`, `test_service_agent.py`
  - `tests/cache/test_url_cache.py`
  - `tests/api/test_analyze_queue.py`
- [ ] 신규 구조에 맞게 `conftest.py` 재정비

---

## Phase 1 — 법령 데이터 파이프라인

> law.go.kr Open API → 법령목록 → 법령본문 → 조문 파싱 → 청킹 → Qdrant

### 1-1. 부동산 도메인 법령 정의 (`src/collector/domain.py`)
- [x] TDD: `tests/collector/test_domain.py` — 법령명 목록 존재 확인

### 1-2. 법령목록 API (`src/collector/law_list_api.py`)
- [x] `GET /DRF/lawSearch.do` — OC, target=law, type=JSON, query=법령명
- [x] 반환: `[{"법령ID": "...", "법령명": "...", "시행일": "..."}]`
- [x] 페이지네이션 처리 (display=100, page=1,2,…)
- [x] TDD: `tests/collector/test_law_list_api.py`

### 1-3. 법령본문 API (`src/collector/law_content_api.py`)
- [x] `GET /DRF/lawService.do` — OC, target=law, type=JSON, ID=법령ID
- [x] 반환: 조문 목록 파싱 → `list[LawArticle]`
- [x] 조문 계층 보존: 조(條) → 항(項) → 호(號) → 목(目)
- [x] TDD: `tests/collector/test_law_content_api.py`

### 1-4. 판례 API (`src/collector/case_api.py`)
- [x] 법원 판례정보 Open API (`/DRF/lawSearch.do?target=prec`)
- [x] 부동산 키워드 목록으로 판례 수집:
  ```
  ["전세사기", "임대차", "매매계약", "분양", "재개발",
   "공인중개사", "하자담보", "명도소송", "유치권", "저당권",
   "전세권", "임차권등기명령", "계약갱신청구권"]
  ```
- [x] `CaseArticle` 모델로 파싱 (사건번호, 법원명, 선고일, 판시사항, 판결요지, 참조조문)
- [x] TDD: `tests/collector/test_case_api.py`

### 1-5. 수집 스케줄러 업데이트 (`src/collector/scheduler.py`)
- [x] 법령본문 + 판례 통합 스케줄러 (`LegalDataCollector`)
- [x] 변경된 조문만 증분 색인 (SHA-256 비교)
- [x] TDD: `tests/collector/test_scheduler.py`

---

## Phase 2 — 청킹 & 임베딩 파이프라인

> 조문 단위 시맨틱 청킹 → 법령·판례 통합 Qdrant 컬렉션

### 2-1. 조문 단위 청커 개선 (`src/embedder/chunker.py`)
- [x] 현행 단락 기반 → **조/항/호 계층 기반** 청킹으로 교체
- [x] 판례 청크 추가 (`chunk_case`)
- [x] TDD: `tests/embedder/test_chunker.py` 업데이트

### 2-2. Qdrant 컬렉션 분리 (`src/embedder/indexer.py`)
- [x] `laws` 컬렉션 — 법령 조문
- [x] `cases` 컬렉션 — 판례
- [x] `recreate_collection(collection_name)` — 컬렉션별 재생성
- [x] TDD: `tests/embedder/test_indexer.py` 업데이트

### 2-3. 색인 스크립트 업데이트 (`scripts/setup_index.py`)
- [x] 법령목록 → 법령본문 → 청킹 → 색인 전체 파이프라인
- [x] 판례 수집 → 청킹 → 색인
- [x] `--reset` 플래그: 컬렉션 초기화 후 재색인
- [x] `--laws-only` / `--cases-only` 플래그

---

## Phase 3 — 법령 관계 그래프

> 조문 간 참조 관계 파싱 → NetworkX 그래프 → Multi-hop 검색

### 3-1. 참조 파서 (`src/graph/reference_parser.py`)
- [x] 조문 내 참조 패턴 추출:
  ```
  "제X조", "제X조제Y항", "동법 제X조", "「주택법」 제X조"
  ```
- [x] → `list[tuple[str, str]]` (source_article_id, target_article_id)
- [x] TDD: `tests/graph/test_reference_parser.py`

### 3-2. 법령 그래프 (`src/graph/law_graph.py`)
- [x] NetworkX DiGraph 구성
- [x] `add_article(article_id, metadata)` — 노드 추가
- [x] `add_reference(src, dst)` — 엣지 추가
- [x] `get_related(article_id, depth=2)` — BFS로 연관 조문 ID 반환
- [x] 그래프 저장/로드: `data/graph/law_graph.pkl`
- [x] TDD: `tests/graph/test_law_graph.py`

### 3-3. 그래프 빌드 스크립트 (`scripts/build_graph.py`)
- [x] SQLite에서 전체 조문 로드 → 참조 파싱 → 그래프 저장

---

## Phase 4 — RAG + Reasoning Agent

> HybridRetriever 재사용 + LegalReasoningAgent + 대화 메모리

### 4-1. 검색 레이어 조정 (`src/retrieval/`)
- [x] `HybridRetriever` — `collection_name` 파라미터 추가 (laws/cases 선택)
- [x] `QueryRewriter` — 부동산 법률 도메인 프롬프트로 교체 (진행 필요 시 Agent 구현 시 함께 처리)
- [x] `GraphExpander` 신규: 검색 결과 article_id → 그래프에서 연관 조문 추가
- [x] TDD: `tests/retrieval/test_graph_expander.py`

### 4-2. LegalReasoningAgent (`src/agents/legal_agent.py`)
- [x] 기존 `BaseAgent` 기반 재설계 (Redesign for real estate domain)
- [x] 동작 흐름 구현: Retrieval -> Graph Expansion -> LLM Reasoning
- [x] 시스템 프롬프트: 법률 보조 역할, 조문 원문 인용 필수, 면책 고지
- [x] TDD: `tests/agents/test_legal_agent.py`

### 4-3. 대화 세션 (`src/session/conversation.py`)
- [x] `ConversationSession` — `session_id`, `history: list[dict]`, `context_window=10`
- [x] Redis 기반 세션 저장 (TTL: 3600s)
- [x] TDD: `tests/session/test_conversation.py`

---

## Phase 5 — FastAPI 재설계

> /api/chat (SSE 스트리밍) + 세션 관리 엔드포인트

### 5-1. 채팅 엔드포인트 (`src/api/routers/chat.py`)
- [x] `POST /api/chat` -> SSE 스트리밍 (content, citations, done)
- [x] `GET /api/sessions/{session_id}/history` — 대화 내역 반환
- [x] `DELETE /api/sessions/{session_id}` — 세션 삭제

### 5-2. 법령 검색 엔드포인트 (`src/api/routers/search.py`)
- [x] `GET /api/search?q=질문&type=law|case` — 직접 검색
- [x] `GET /api/articles/{article_id}` — 단일 조문 상세 조회

### 5-3. main.py 정리
- [x] chat/search 라우터 등록
- [x] LegalReasoningAgent + warm-up

---

## Phase 6 — React UI 재설계

> 좌: 대화창 / 우: Citation 패널 (법령 원문 + 판례)

### 6-1. 레이아웃 구성
- [x] `ChatPanel` (좌) — 질문 입력 + SSE 스트리밍 응답
- [x] `CitationPanel` (우) — 응답과 연동된 인용 카드
- [x] 모바일 대응 및 반응형 레이아웃 기초

### 6-2. 상태 관리
- [x] SSE 스트리밍 → `useChat` 훅 (토큰 단위 스트리밍 구현)
- [x] 세션 ID 로컬스토리지 유지
- [x] React Query (TanStack Query) 도입

---

## 우선순위 실행 계획

```
[즉시] Phase 0  → 정리·삭제 (TDD 그린 유지하며 제거)
[1주]  Phase 1  → 법령목록 + 법령본문 + 판례 API (TDD)
[1주]  Phase 2  → 조문 청킹 개선 + Qdrant 저장
[1주]  Phase 3  → 법령 관계 그래프
[1주]  Phase 4  → LegalReasoningAgent + 세션
[1주]  Phase 5  → FastAPI /api/chat
[1주]  Phase 6  → React UI
```

---

## 기술 스택 (변경 후)

| 항목 | 기술 |
|------|------|
| LLM | GPT-4o-mini (openai>=1.35) |
| Embedding | text-embedding-3-small |
| Vector DB | Qdrant — `laws` + `cases` 컬렉션 |
| 법령 관계 | NetworkX (DiGraph) |
| 대화 메모리 | LangChain ConversationBufferWindowMemory + Redis |
| 검색 | BM25 + Vector + RRF (HybridRetriever) |
| API | FastAPI + SSE |
| Frontend | React + Vite |
| 인프라 | Docker Compose (qdrant · redis · api · worker · frontend) |

---

---

## Phase 7 — 성능 최적화 (스케일링)

> SQLite WAL + 시맨틱 캐시 + Redis Stream LLM 큐잉 + Uvicorn 멀티워커

### 7-1. SQLite WAL 모드 (`src/integrity/db.py`)
- [x] TDD: `tests/integrity/test_db_wal.py` — WAL 모드 활성화 확인
- [x] `ArticleDB.__init__`에 `PRAGMA journal_mode=WAL` 추가

### 7-2. 시맨틱 응답 캐시 (`src/cache/semantic_cache.py`)
- [x] TDD: `tests/cache/test_semantic_cache.py`
  - 캐시 miss → None 반환
  - 캐시 set 후 유사 질문 get → 응답 반환 (threshold 이상)
  - 낮은 유사도 질문 → None 반환
- [x] `SemanticCache` 클래스: OpenAI 임베딩 + Qdrant `query_cache` 컬렉션
- [x] `get(question)` / `set(question, response)` 구현

### 7-3. Redis Stream LLM 큐 (`src/streaming/llm_queue.py`)
- [x] TDD: `tests/streaming/test_llm_queue.py`
  - `enqueue` → job_id 반환
  - `dequeue` → job dict 반환
  - `publish_chunk` → `consume_response` 로 청크 수신
  - Consumer Group 재생성 시 오류 없음 (BUSYGROUP 무시)
- [x] `LLMJobQueue`: XADD / XREADGROUP / XACK / XREAD 기반 구현

### 7-4. LLM 워커 (`src/worker/llm_worker.py`)
- [x] TDD: `tests/worker/test_llm_worker.py`
  - `_process` — agent mock으로 청크 발행 검증
  - 오류 발생 시 `error` 청크 발행 + XACK 확인
- [x] `LLMWorker`: 백그라운드 asyncio 태스크
- [x] Citation 객체 → dict 직렬화 처리

### 7-5. 통합 연결
- [x] `api/dependencies.py` — `get_llm_queue`, `get_semantic_cache`, `get_llm_worker` 추가
- [x] `api/routers/chat.py` — 캐시 확인 → 큐 enqueue → 응답 스트리밍
- [x] `api/main.py` — lifespan에서 worker 백그라운드 태스크 시작
- [x] `src/core/config.py` — `llm_concurrency`, `cache_similarity_threshold` 설정 추가
- [x] `scripts/entrypoint.sh` — `uvicorn --workers $(nproc)` 적용

---

*Last updated: 2026-03-09*
