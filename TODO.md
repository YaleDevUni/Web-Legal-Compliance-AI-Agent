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
- [ ] 법원 판례정보 Open API (`/DRF/lawSearch.do?target=prec`)
- [ ] 부동산 키워드 목록으로 판례 수집:
  ```
  ["전세사기", "임대차", "매매계약", "분양", "재개발",
   "공인중개사", "하자담보", "명도소송", "유치권", "저당권",
   "전세권", "임차권등기명령", "계약갱신청구권"]
  ```
- [ ] `CaseArticle` 모델로 파싱 (사건번호, 법원명, 선고일, 판시사항, 판결요지, 참조조문)
- [ ] TDD: `tests/collector/test_case_api.py`
  - `test_fetch_cases_by_keyword()`
  - `test_parse_case_to_model()`
  - `test_reference_articles_extracted()` — 판례 내 참조조문 파싱

### 1-5. 수집 스케줄러 업데이트 (`src/collector/scheduler.py`)
- [ ] 법령본문 + 판례 통합 스케줄러
- [ ] 변경된 조문만 증분 색인 (SHA-256 비교)

---

## Phase 2 — 청킹 & 임베딩 파이프라인

> 조문 단위 시맨틱 청킹 → 법령·판례 통합 Qdrant 컬렉션

### 2-1. 조문 단위 청커 개선 (`src/embedder/chunker.py`)
- [ ] 현행 단락 기반 → **조/항/호 계층 기반** 청킹으로 교체
- [ ] 각 청크 메타데이터:
  ```python
  {
    "article_id": "주택법_제49조",
    "law_name": "주택법",
    "article_number": "제49조",
    "paragraph": "①",        # 항 번호 (없으면 "")
    "subparagraph": "1.",     # 호 번호 (없으면 "")
    "full_content": "...",    # 조문 전체 원문 (Parent Chunk)
    "sha256": "...",
    "doc_type": "law",        # "law" | "case"
  }
  ```
- [ ] 판례 청크 추가 (`doc_type="case"`)
- [ ] TDD: `tests/embedder/test_chunker.py` 전면 업데이트

### 2-2. Qdrant 컬렉션 분리 (`src/embedder/indexer.py`)
- [ ] `laws` 컬렉션 — 법령 조문
- [ ] `cases` 컬렉션 — 판례
- [ ] `recreate_collection(collection_name)` — 컬렉션별 재생성
- [ ] TDD: `tests/embedder/test_indexer.py` 업데이트

### 2-3. 색인 스크립트 업데이트 (`scripts/setup_index.py`)
- [ ] 법령목록 → 법령본문 → 청킹 → 색인 전체 파이프라인
- [ ] 판례 수집 → 청킹 → 색인
- [ ] `--reset` 플래그: 컬렉션 초기화 후 재색인
- [ ] `--laws-only` / `--cases-only` 플래그

---

## Phase 3 — 법령 관계 그래프

> 조문 간 참조 관계 파싱 → NetworkX 그래프 → Multi-hop 검색

### 3-1. 참조 파서 (`src/graph/reference_parser.py`)
- [ ] 조문 내 참조 패턴 추출:
  ```
  "제X조", "제X조제Y항", "동법 제X조", "「주택법」 제X조"
  ```
- [ ] → `list[tuple[str, str]]` (source_article_id, target_article_id)
- [ ] TDD: `tests/graph/test_reference_parser.py`
  - `test_extract_intra_law_reference()` — 동일 법령 내 참조
  - `test_extract_cross_law_reference()` — 타 법령 참조
  - `test_no_reference_returns_empty()`

### 3-2. 법령 그래프 (`src/graph/law_graph.py`)
- [ ] NetworkX DiGraph 구성
- [ ] `add_article(article_id, metadata)` — 노드 추가
- [ ] `add_reference(src, dst)` — 엣지 추가
- [ ] `get_related(article_id, depth=2)` — BFS로 연관 조문 ID 반환
- [ ] 그래프 저장/로드: `data/graph/law_graph.pkl`
- [ ] TDD: `tests/graph/test_law_graph.py`
  - `test_related_articles_within_depth()`
  - `test_circular_reference_safe()`
  - `test_serialize_deserialize()`

### 3-3. 그래프 빌드 스크립트 (`scripts/build_graph.py`)
- [ ] SQLite에서 전체 조문 로드 → 참조 파싱 → 그래프 저장

---

## Phase 4 — RAG + Reasoning Agent

> HybridRetriever 재사용 + LegalReasoningAgent + 대화 메모리

### 4-1. 검색 레이어 조정 (`src/retrieval/`)
- [ ] `HybridRetriever` — `collection_name` 파라미터 추가 (laws/cases 선택)
- [ ] `QueryRewriter` — 부동산 법률 도메인 프롬프트로 교체
- [ ] `GraphExpander` 신규: 검색 결과 article_id → 그래프에서 연관 조문 추가
- [ ] TDD: `tests/retrieval/test_graph_expander.py`

### 4-2. LegalReasoningAgent (`src/agents/legal_agent.py`)
- [ ] 기존 `BaseAgent` 기반 재설계
- [ ] 동작 흐름:
  ```
  질문 → QueryRewriter → HybridRetriever(laws + cases)
       → GraphExpander (연관 조문 확장)
       → LLM (법령 원문 + 판례 컨텍스트 기반 reasoning)
       → LegalAnswer (answer + citations + related_articles)
  ```
- [ ] 시스템 프롬프트: 법률 보조 역할, 조문 원문 인용 필수, 면책 고지
- [ ] TDD: `tests/agents/test_legal_agent.py`
  - `test_returns_legal_answer_with_citations()`
  - `test_graph_expansion_includes_related_articles()`
  - `test_case_law_included_when_relevant()`

### 4-3. 대화 세션 (`src/session/conversation.py`)
- [ ] `ConversationSession` — `session_id`, `history: list[dict]`, `context_window=10`
- [ ] Redis 기반 세션 저장 (TTL: 3600s)
- [ ] LangChain `ConversationBufferWindowMemory` 연동
- [ ] TDD: `tests/session/test_conversation.py`
  - `test_session_create_and_load()`
  - `test_history_truncated_at_context_window()`
  - `test_session_expires_after_ttl()`

---

## Phase 5 — FastAPI 재설계

> /api/chat (SSE 스트리밍) + 세션 관리 엔드포인트

### 5-1. 채팅 엔드포인트 (`src/api/routers/chat.py`)
- [ ] `POST /api/chat`
  ```json
  { "question": "전세보증금 반환 기한은?", "session_id": "uuid" }
  ```
  → SSE 스트리밍: `answer` 토큰 + 최종 `citations` JSON
- [ ] `GET /api/sessions/{session_id}/history` — 대화 내역 반환
- [ ] `DELETE /api/sessions/{session_id}` — 세션 삭제
- [ ] TDD: `tests/api/test_chat.py`
  - `test_chat_returns_sse_stream()`
  - `test_citations_included_in_final_event()`
  - `test_session_history_persisted()`

### 5-2. 법령 검색 엔드포인트 (`src/api/routers/search.py`)
- [ ] `GET /api/search?q=질문&type=law|case` — 직접 검색 (채팅 없이)
- [ ] `GET /api/articles/{article_id}` — 단일 조문 상세 조회 + 연관 조문

### 5-3. main.py 정리
- [ ] parse 라우터 제거, chat/search 라우터 등록
- [ ] LegalReasoningAgent + LawGraph 워밍업

---

## Phase 6 — React UI 재설계

> 좌: 대화창 / 우: Citation 패널 (법령 원문 + 판례)

### 6-1. 레이아웃 구성
- [ ] `ChatPanel` (좌) — 질문 입력 + SSE 스트리밍 응답
- [ ] `CitationPanel` (우) — 응답과 연동된 인용 카드
  - 법령 카드: 법령명 · 조항번호 · 원문 · SHA-256
  - 판례 카드: 사건번호 · 법원 · 선고일 · 판결요지
- [ ] 인용 번호 클릭 시 우측 패널 해당 카드로 스크롤

### 6-2. 상태 관리
- [ ] SSE 스트리밍 → `useEventSource` 훅
- [ ] 세션 ID 로컬스토리지 유지
- [ ] 대화 내역 무한 스크롤

### 6-3. 법령 관계 시각화 (선택)
- [ ] D3.js / Cytoscape.js — 연관 조문 그래프 미니맵

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

*Last updated: 2026-03-08*
