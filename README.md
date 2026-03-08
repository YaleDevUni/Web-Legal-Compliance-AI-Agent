# 부동산 법률 AI 상담사

> 대한민국 부동산 법령 및 판례를 기반으로 실시간 법률 상담을 제공하는 RAG(Retrieval-Augmented Generation) 시스템

[![Python](https://img.shields.io/badge/Python-3.12-blue)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-green)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18-blue)](https://react.dev)
[![Qdrant](https://img.shields.io/badge/Qdrant-Vector_DB-red)](https://qdrant.tech)
[![License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)

---

## 목차

1. [프로젝트 개요](#1-프로젝트-개요)
2. [시스템 아키텍처](#2-시스템-아키텍처)
3. [데이터 모델 (ERD)](#3-데이터-모델-erd)
4. [RAG 파이프라인](#4-rag-파이프라인)
5. [기술적 난제와 해결 방법](#5-기술적-난제와-해결-방법)
6. [성능 최적화](#6-성능-최적화)
7. [프로젝트 구조](#7-프로젝트-구조)
8. [기술 스택](#8-기술-스택)
9. [설치 및 실행](#9-설치-및-실행)
10. [API 문서](#10-api-문서)
11. [개발 가이드 (TDD)](#11-개발-가이드-tdd)
12. [AI 협업 개발 방법론](#12-ai-협업-개발-방법론)

---

## 1. 프로젝트 개요

### 목적

한국 부동산 법률은 **주택임대차보호법**, **공인중개사법**, **건축법** 등 10개 이상의 법령이 서로 교차 참조하며 복잡하게 얽혀 있습니다. 일반인이 관련 법조문을 직접 검색하고 해석하는 것은 매우 어렵습니다.

이 시스템은 다음 문제를 해결합니다.

| 문제 | 해결 방안 |
|------|-----------|
| 법령 간 복잡한 교차 참조 | NetworkX 법령 관계 그래프 + BFS 확장 검색 |
| 키워드 검색의 한계 | BM25 + Vector 하이브리드 검색 + RRF 병합 |
| 답변 근거 불투명 | 조문 원문 인용(Citation) 강제화 + SHA-256 무결성 검증 |
| 대화 문맥 유실 | Redis 기반 슬라이딩 윈도우 세션 관리 |
| LLM 응답 지연 | 시맨틱 캐시 + Redis Stream 큐잉 + 멀티워커 |

### 주요 기능

- **실시간 SSE 스트리밍** — 토큰 단위로 답변을 스트리밍하여 체감 응답 시간 최소화
- **조문 원문 인용** — 답변의 모든 법적 근거에 법령명·조항번호·원문·링크 제공
- **법령 관계 그래프 시각화** — 인용된 조문과 관련 조문 간 참조 관계를 Force-Graph로 렌더링
- **판례 통합 검색** — 법령 조문과 관련 대법원 판례를 동시에 검색하여 실무적 해석 제공
- **대화 세션 유지** — 이전 질문 문맥을 기억하여 follow-up 질문 처리

---

## 2. 시스템 아키텍처

### 전체 구성

```
┌─────────────────────────────────────────────────────────────┐
│                         Client                              │
│                  React + Vite (port 5173)                   │
│   ChatPanel │ CitationPanel │ LawGraphView (Force-Graph)    │
└─────────────────────────┬───────────────────────────────────┘
                          │ SSE Streaming / REST
┌─────────────────────────▼───────────────────────────────────┐
│                   FastAPI (port 8000)                        │
│        8 Uvicorn Workers  │  /api/chat  │  /api/search       │
│                           │                                  │
│  ┌─────────────┐  ┌───────▼───────┐  ┌──────────────────┐   │
│  │ Semantic    │  │  LLM Job      │  │  Session Manager  │   │
│  │ Cache       │  │  Queue        │  │  (Redis List)     │   │
│  │ (Qdrant)    │  │  (Redis       │  │                   │   │
│  └─────────────┘  │   Stream)     │  └──────────────────┘   │
│                   └───────┬───────┘                          │
└───────────────────────────┼──────────────────────────────────┘
                            │ XREADGROUP (Consumer Group)
┌───────────────────────────▼──────────────────────────────────┐
│                    LLM Worker (per process)                   │
│                                                              │
│   ┌───────────────────────────────────────────────────┐      │
│   │              LegalReasoningAgent                  │      │
│   │                                                   │      │
│   │  1. HybridRetriever ──────► BM25 + Vector (RRF)  │      │
│   │       laws / cases                                │      │
│   │                                                   │      │
│   │  2. GraphExpander ────────► LawGraph (NetworkX)   │      │
│   │       BFS depth=1                                 │      │
│   │                                                   │      │
│   │  3. ChatOpenAI.astream() → SSE chunks             │      │
│   └───────────────────────────────────────────────────┘      │
└──────────────────────────────────────────────────────────────┘
                            │
         ┌──────────────────┼──────────────────┐
         │                  │                  │
    ┌────▼────┐        ┌────▼────┐       ┌────▼────┐
    │ Qdrant  │        │  Redis  │       │ SQLite  │
    │ Vector  │        │  7      │       │ WAL     │
    │ DB      │        │         │       │         │
    │ laws    │        │ session │       │ article │
    │ cases   │        │ stream  │       │ hashes  │
    │ q_cache │        │         │       │         │
    └─────────┘        └─────────┘       └─────────┘
```

### 요청 처리 흐름 (캐시 Miss)

```
Client
  │
  │ POST /api/chat {"question": "전세 보증금 반환 방법"}
  ▼
chat.py (SSE event_generator)
  │
  ├─ [1] SemanticCache.get()  ──miss──►  [2] LLMJobQueue.enqueue()
  │                                              │
  │                                              │ XADD stream:llm_jobs
  │                                              ▼
  │                                       Redis Stream
  │                                              │
  │                                              │ XREADGROUP (Consumer Group)
  │                                              ▼
  │                                       LLMWorker._process()
  │                                              │
  │                                    ┌─────────┴──────────┐
  │                                    │                    │
  │                              law_retriever         case_retriever
  │                              (BM25+Vector)         (BM25+Vector)
  │                                    │                    │
  │                                    └────────┬───────────┘
  │                                             │
  │                                      GraphExpander.expand()
  │                                      (BFS depth=1)
  │                                             │
  │                                      ChatOpenAI.astream()
  │                                             │
  │                              XADD stream:response:{job_id}
  │                                             │
  ◄──── SSE chunk 전달 ◄─── queue.consume_response()
  │
  ├─ [3] session.add_message()  (Redis)
  └─ [4] SemanticCache.set()    (Qdrant)
```

### 요청 처리 흐름 (캐시 Hit)

```
Client
  │
  │ POST /api/chat (동일/유사 질문)
  ▼
SemanticCache.get()
  │
  │ embed(question) → Qdrant query_points(score_threshold=0.92)
  │
  ├─ HIT: 캐시 응답 즉시 스트리밍 (~0.8초, OpenAI 호출 없음)
  └─ MISS: LLM 큐 경로 (~20초)
```

---

## 3. 데이터 모델 (ERD)

```
┌──────────────────────────────────────┐
│              LawArticle              │
├──────────────────────────────────────┤
│ PK  article_id       : str           │
│     law_name         : str           │
│     article_number   : str           │
│     content          : str           │
│     sha256           : str (64 hex)  │
│     url              : AnyHttpUrl    │
│     updated_at       : datetime      │
└──────────────────┬───────────────────┘
                   │ 1:N
                   ▼
┌──────────────────────────────────────┐
│               Citation               │
├──────────────────────────────────────┤
│     article_id       : str           │
│     law_name         : str           │
│     article_number   : str           │
│     sha256           : str           │
│     url              : AnyHttpUrl    │
│     updated_at       : datetime      │
│     article_content  : str (optional)│
│  ── 판례 전용 필드 ──────────────────  │
│     case_number      : str | None    │
│     court            : str | None    │
│     decision_date    : datetime|None │
└──────────────────────────────────────┘

┌──────────────────────────────────────┐
│             CaseArticle              │
├──────────────────────────────────────┤
│ PK  case_id          : str           │
│     case_number      : str           │
│     case_name        : str           │
│     court            : str           │
│     decision_date    : datetime      │
│     decision_type    : str           │
│     ruling_summary   : str           │  판시사항
│     ruling_text      : str           │  판결요지
│     referenced_articles: list[str]   │──► LawArticle.article_id
│     url              : AnyHttpUrl    │
│     sha256           : str           │
└──────────────────────────────────────┘

┌──────────────────────────────────────┐
│              LegalAnswer             │
├──────────────────────────────────────┤
│     question         : str           │
│     answer           : str           │
│     citations        : list[Citation]│
│     related_articles : list[str]     │──► LawArticle.article_id
│     session_id       : str           │
└──────────────────────────────────────┘

  SQLite: article_hashes (무결성 추적)
┌──────────────────────────────────────┐
│           article_hashes             │
├──────────────────────────────────────┤
│ PK  article_id  TEXT                 │
│     law_name    TEXT                 │
│     article_number TEXT              │
│     content     TEXT                 │
│     sha256      TEXT NOT NULL        │
│     updated_at  TEXT NOT NULL        │
└──────────────────────────────────────┘

  Qdrant: 벡터 컬렉션 구조
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│     laws        │  │     cases       │  │  query_cache    │
├─────────────────┤  ├─────────────────┤  ├─────────────────┤
│ id: UUID5       │  │ id: UUID5       │  │ id: MD5 hash    │
│ vector: 1536d   │  │ vector: 1536d   │  │ vector: 1536d   │
│ payload:        │  │ payload:        │  │ payload:        │
│  article_id     │  │  case_id        │  │  question       │
│  law_name       │  │  case_number    │  │  response{}     │
│  article_number │  │  court          │  │                 │
│  full_content   │  │  section        │  │ COSINE distance │
│  sha256, url    │  │  doc_type:case  │  │ threshold: 0.92 │
│  doc_type: law  │  │                 │  │                 │
└─────────────────┘  └─────────────────┘  └─────────────────┘
```

---

## 4. RAG 파이프라인

### 4-1. 법령 데이터 수집

```
law.go.kr Open API
    │
    ├── /DRF/lawSearch.do?target=law    ──► 법령 목록 (11개 부동산 법령)
    │         페이지네이션: display=100
    │
    ├── /DRF/lawService.do?ID={법령ID}  ──► 조문 본문 파싱
    │         조(條) → 항(項) → 호(號) → 목(目) 계층 보존
    │
    └── /DRF/lawSearch.do?target=prec  ──► 판례 (13개 키워드)
              전세사기 | 임대차 | 매매계약 | 공인중개사 | ...
```

### 4-2. 청킹 전략

**법령 조문 청킹** (계층 구조 보존)

```
원본 조문:
"제3조(대항력 등)
① 임차인이 주택의 인도와 주민등록을 마친 때에는..."
"② 임차주택의 양수인..."

→ 청크 1: "주택임대차보호법 제3조 대항력 등\n① 임차인이..."
   메타: {paragraph: "①", full_content: 전체 조문}

→ 청크 2: "주택임대차보호법 제3조 대항력 등\n② 임차주택의..."
   메타: {paragraph: "②", full_content: 전체 조문}
```

> `full_content` 필드에 전체 조문을 보존함으로써, 검색 시 청크 단위로 분할되더라도 LLM에게는 완전한 조문 원문을 제공합니다.

**판례 청킹** (섹션 분리)

```
판시사항: "임차인이 우선변제권을 취득하기 위한 요건..."
판결요지: "주택임대차보호법 제3조의2에 의한 우선변제권은..."

→ 청크 1: "[2023다12345 판시사항]\n임차인이 우선변제권을..."
   메타: {section: "summary", case_number: "2023다12345"}

→ 청크 2: "[2023다12345 판결요지]\n주택임대차보호법..."
   메타: {section: "ruling", case_number: "2023다12345"}
```

### 4-3. 하이브리드 검색 (BM25 + Vector + RRF)

```python
# 검색 흐름
query = "전세 계약 만료 후 보증금 반환"

# Step 1: BM25 희소 검색 (키워드 정확도)
bm25_scores = BM25Okapi(corpus).get_scores(query.split())
bm25_top_k  = argsort(bm25_scores)[:top_k]  # 순위 목록 1

# Step 2: Vector 밀집 검색 (의미 유사도)
embedding   = openai.embed(query)  # 1536차원
vector_top_k = qdrant.query_points(
    collection="laws",
    query=embedding,
    score_threshold=None
)[:top_k]  # 순위 목록 2

# Step 3: RRF 병합 (Reciprocal Rank Fusion)
# k=60 하이퍼파라미터: 낮은 순위 문서도 소량 기여
for doc in union(bm25_top_k, vector_top_k):
    rrf_score[doc] = Σ 1 / (60 + rank_i)
```

**RRF를 선택한 이유**: 두 검색 결과의 점수 스케일이 다릅니다(BM25는 절대 점수, 코사인 유사도는 0-1). 단순 가중 합산이 아닌 **순위(rank) 기반 병합**은 스케일 정규화 없이도 안정적으로 동작합니다.

### 4-4. 법령 관계 그래프 확장

```
초기 검색 결과:
  [주택임대차보호법 제3조, 민법 제621조]

                    ▼ GraphExpander.expand(depth=1)

LawGraph (NetworkX DiGraph):
  주택임대차보호법 제3조 ──참조──► 주민등록법 제6조
                          ──참조──► 민법 제213조
  민법 제621조            ──참조──► 민법 제618조

최종 컨텍스트:
  [주택임대차보호법 제3조, 민법 제621조,   ← 직접 검색
   주민등록법 제6조, 민법 제213조,         ← 그래프 확장
   민법 제618조]                           ← 그래프 확장
```

그래프 확장을 통해 **직접 검색되지 않은 연관 조문**까지 LLM 컨텍스트에 포함시켜, 법령 간 종속관계를 고려한 답변을 생성합니다.

### 4-5. LLM 추론 및 인용 생성

```
System Prompt
  + [법령 컨텍스트] 법령 1~N (full_content)
  + [판례 컨텍스트] 판례 1~M (ruling_text)
  + [대화 이력] 최근 6개 메시지 (sliding window)
  + [사용자 질문]
          │
          ▼
  ChatOpenAI(gpt-4o-mini, temperature=0).astream()
          │
  규칙: "주택임대차보호법 제3조[1]에 따르면..."
        인용 마커 [n] 필수 포함
          │
          ▼
  SSE 청크 스트리밍 → 프론트엔드 실시간 렌더링
```

### 4-6. LangChain 사용 범위

이 프로젝트는 LangChain을 **일부 레이어에서만** 선택적으로 활용합니다.

**실제로 사용하는 컴포넌트**

| 컴포넌트 | 패키지 | 사용 위치 | 역할 |
|---------|--------|-----------|------|
| `ChatOpenAI` | `langchain-openai` | `legal_agent.py`<br>`_base_agent.py`<br>`query_rewriter.py` | LLM 호출 · `.astream()` 스트리밍 |
| `OpenAIEmbeddings` | `langchain-openai` | `vector.py`<br>`indexer.py` | `.embed_query()` · `.embed_documents()` |
| `HumanMessage`<br>`AIMessage`<br>`SystemMessage` | `langchain-core` | `legal_agent.py`<br>`query_rewriter.py` | 대화 메시지 타입 표준화 |

**의도적으로 사용하지 않는 것**

| LangChain 기능 | 미사용 이유 |
|----------------|-------------|
| `AgentExecutor` / `Chain` | RAG 파이프라인을 직접 구현하여 법령 도메인에 맞게 세밀하게 제어 |
| `LCEL` (LangChain Expression Language) | SSE 스트리밍과 Redis 큐를 직접 연결하는 커스텀 흐름 필요 |
| `langchain-qdrant` (VectorStore) | Qdrant 클라이언트를 직접 사용하여 `query_points()` · `scroll()` 세밀 제어 |
| `ConversationBufferWindowMemory` | Redis List 기반 직접 구현으로 세션 TTL · 직렬화 완전 제어 |

> **설계 원칙**: LangChain의 고수준 추상화는 범용성을 위해 도메인별 최적화를 희생합니다. 법령 계층 청킹, 판례/법령 컬렉션 분리, Redis 큐 연동 등은 직접 구현이 더 적합했습니다. LangChain은 OpenAI API의 인터페이스 레이어로만 활용합니다.

---

## 5. 기술적 난제와 해결 방법

### 난제 1. 법령 인용 번호의 일관성 유지

**문제**: LLM이 답변에서 `[1]`, `[2]` 같은 인용 번호를 생성하지만, 새로운 메시지마다 번호가 초기화됩니다. 이전 메시지에서 `[1]`로 인용된 조문이 다음 메시지에서 `[1]`로 다른 조문을 가리킬 수 있습니다.

**해결**: **글로벌 인용 레지스트리** 패턴

```typescript
// 세션 전체에 걸쳐 citations 배열을 누적 관리
const [citations, setCitations] = useState<Citation[]>([]);

// 새 메시지의 로컬 인용 번호를 글로벌 인덱스로 변환
const globalIdx = citations.findIndex(c => c.article_id === citation.article_id);
const displayNum = globalIdx !== -1 ? globalIdx + 1 : localIdx;
```

같은 조문은 세션 전체에서 항상 동일한 번호로 표시됩니다.

---

### 난제 2. 스트리밍 + 큐잉의 양립

**문제**: SSE는 연결을 유지하며 실시간으로 데이터를 전송해야 하지만, Redis Stream 큐는 비동기 처리를 위해 연결을 분리합니다. 두 패턴을 어떻게 동시에 사용할 수 있을까요?

**해결**: **응답 스트림(per-job Redis Stream)**

```
SSE 엔드포인트            Redis Stream                  LLM Worker
      │                       │                              │
      │── enqueue(job_id)  ──►│ stream:llm_jobs              │
      │                       │◄── XREADGROUP ────────────── │
      │                       │                              │
      │◄── XREAD(block) ───── │ stream:response:{job_id}     │
      │  (3초 블로킹 대기)       │◄─── XADD chunk ─────────────│
      │                       │◄─── XADD chunk ───────────── │
      │──► SSE forward ──►    │◄─── XADD done ────────────── │
```

SSE 엔드포인트는 `queue.consume_response(job_id)`로 job별 Redis Stream을 구독하고, Worker가 청크를 발행하는 즉시 클라이언트에 전달합니다. 커넥션 분리와 실시간 스트리밍이 동시에 달성됩니다.

---

### 난제 3. 멀티 워커 환경에서의 LLM Worker

**문제**: `--workers 8` 옵션으로 8개의 uvicorn 프로세스가 실행되면, 각 프로세스가 독립적인 asyncio 루프를 갖습니다. Consumer Group에서 같은 job을 중복 처리하는 문제가 발생할 수 있습니다.

**해결**: **PID 기반 Consumer 이름**

```python
self._name = f"worker-{os.getpid()}"

# 각 워커 프로세스가 고유한 consumer 이름으로 XREADGROUP 호출
await r.xreadgroup(CONSUMER_GROUP, "worker-15", {QUEUE_KEY: ">"}, ...)
await r.xreadgroup(CONSUMER_GROUP, "worker-16", {QUEUE_KEY: ">"}, ...)
```

Redis Consumer Group은 하나의 메시지를 오직 하나의 consumer에게만 전달합니다. PID로 이름을 차별화함으로써, 8개 워커가 병렬로 큐를 처리하되 중복 처리를 방지합니다.

---

### 난제 4. 법령 무결성 검증과 증분 색인

**문제**: law.go.kr API는 법령 개정 시 전체 데이터를 다시 반환합니다. 수만 개의 조문을 매번 재색인하면 비효율적입니다.

**해결**: **SHA-256 기반 변경 감지**

```python
# 수집된 조문의 SHA-256을 SQLite에 저장
changed = article_db.upsert(article_id, sha256=new_hash, ...)

# 변경된 조문만 Qdrant 재색인
if changed:
    indexer.upsert_laws([article], changed_ids={article.article_id})
```

SQLite `article_hashes` 테이블이 이전 버전의 해시를 저장하고, 동일 해시면 색인을 건너뜁니다. `article_history` 테이블로 개정 이력도 추적합니다.

---

### 난제 5. 벡터 검색 + 키워드 검색의 스케일 차이

**문제**: BM25는 전체 코퍼스를 메모리에 로드해야 합니다. Qdrant에서 수만 개의 청크를 매번 로드하면 시작 시간이 길어집니다.

**해결**: **초기화 시 배치 로드 + LRU 캐시 싱글턴**

```python
def _load_corpus(self):
    offset = None
    while True:
        result = self._qdrant.scroll(
            collection_name=self._collection,
            limit=1000,
            offset=offset,
            with_payload=True
        )
        points, next_offset = result
        # BM25 코퍼스 구축
        if not next_offset:
            break
        offset = next_offset

@lru_cache(maxsize=1)
def get_law_retriever() -> HybridRetriever:
    ...  # FastAPI 시작 시 1회만 초기화
```

서버 시작 시 warm-up으로 BM25 인덱스를 구축하고, `lru_cache`로 프로세스 재사용합니다.

---

## 6. 성능 최적화

### 6-1. 시맨틱 응답 캐시

동일하거나 의미적으로 유사한 질문에 대해 OpenAI API를 재호출하지 않습니다.

```
질문 임베딩(1536d) → Qdrant query_cache 컬렉션 검색
  │
  ├── 코사인 유사도 ≥ 0.92 → 캐시 히트 (응답 즉시 반환)
  └── 코사인 유사도 < 0.92 → 캐시 미스 (LLM 호출)
```

| 시나리오 | 응답 시간 | OpenAI 비용 |
|----------|-----------|-------------|
| 캐시 미스 (LLM 호출) | ~20초 | ~$0.001/req |
| 캐시 히트 | **~0.8초** | **$0** |
| 개선율 | **25배 빠름** | **100% 절감** |

임계값 `0.92`는 "전세 보증금 반환 방법"과 "전세 계약 만료 후 보증금을 못 받으면"처럼 표현은 다르지만 의도가 같은 질문을 동일하게 처리합니다.

### 6-2. Redis Stream LLM 큐잉

```
동시 사용자 급증 → OpenAI Rate Limit(RPM/TPM) 초과 방지

Without 큐잉:
  100 req/s → 100개 동시 OpenAI API 호출 → 429 Rate Limit

With 큐잉:
  100 req/s → Redis Stream 버퍼링 → 최대 llm_concurrency(=3)개 동시 처리
            → 나머지 대기열 순차 처리
```

### 6-3. SQLite WAL 모드

```python
self._conn.execute("PRAGMA journal_mode=WAL")
```

WAL(Write-Ahead Logging) 모드는 읽기와 쓰기가 서로를 차단하지 않습니다.

| 모드 | 동시 읽기 | 읽기-쓰기 동시 |
|------|-----------|----------------|
| Journal (기본) | 가능 | ❌ (쓰기 중 읽기 블록) |
| WAL | 가능 | ✅ |

스케줄러가 법령을 색인하면서 쓰기를 수행하는 동안, API 서버의 읽기 쿼리가 블로킹되지 않습니다.

### 6-4. Uvicorn 멀티워커

```bash
# CPU 코어 수 × 1 개의 워커 프로세스
WORKERS=${UVICORN_WORKERS:-$(nproc)}
exec uvicorn api.main:app --workers "${WORKERS}"
```

각 워커는 독립적인 Python 프로세스로 GIL 우회. I/O 바운드 작업(네트워크, DB)에서 선형적 처리량 향상.

### 6-5. UUID5 기반 결정론적 청크 ID

```python
chunk_id = uuid.uuid5(uuid.NAMESPACE_URL, chunk_text)
```

동일한 텍스트는 항상 동일한 UUID를 생성합니다. Qdrant `upsert`가 중복 삽입을 자동으로 처리하여, 재색인 시 기존 벡터를 덮어쓰기만 하고 중복 포인트가 생기지 않습니다.

---

## 7. 프로젝트 구조

```
.
├── api/
│   ├── main.py                  # FastAPI 진입점 + lifespan (Worker 시작)
│   ├── dependencies.py          # 싱글턴 의존성 (lru_cache)
│   └── routers/
│       ├── chat.py              # POST /api/chat (SSE)
│       └── search.py            # GET /api/search, /api/articles/{id}
│
├── src/
│   ├── core/
│   │   ├── models.py            # Pydantic 모델 (LawArticle, Citation, ...)
│   │   ├── config.py            # pydantic-settings (환경변수)
│   │   └── logger.py            # loguru 설정
│   │
│   ├── agents/
│   │   └── legal_agent.py       # LegalReasoningAgent (검색→확장→LLM→스트리밍)
│   │
│   ├── collector/
│   │   ├── domain.py            # 부동산 법령 목록 (11개) + 판례 키워드 (13개)
│   │   ├── law_list_api.py      # 법령 목록 수집
│   │   ├── law_content_api.py   # 법령 본문 수집
│   │   ├── case_api.py          # 판례 수집
│   │   └── scheduler.py         # 증분 색인 스케줄러
│   │
│   ├── embedder/
│   │   ├── chunker.py           # chunk_article(), chunk_case()
│   │   └── indexer.py           # ArticleIndexer (OpenAI embed → Qdrant)
│   │
│   ├── retrieval/
│   │   ├── hybrid.py            # HybridRetriever (BM25 + Vector + RRF)
│   │   └── graph_expander.py    # GraphExpander (BFS 관련 조문 추가)
│   │
│   ├── graph/
│   │   ├── law_graph.py         # LawGraph (NetworkX DiGraph)
│   │   └── reference_parser.py  # 조문 내 참조 패턴 파싱
│   │
│   ├── session/
│   │   └── conversation.py      # ConversationSession + SessionManager (Redis)
│   │
│   ├── integrity/
│   │   ├── db.py                # ArticleDB (SQLite WAL + SHA-256)
│   │   └── hasher.py            # SHA-256 해시 유틸리티
│   │
│   ├── cache/
│   │   └── semantic_cache.py    # SemanticCache (OpenAI embed + Qdrant)
│   │
│   ├── streaming/
│   │   └── llm_queue.py         # LLMJobQueue (Redis Stream Consumer Group)
│   │
│   └── worker/
│       └── llm_worker.py        # LLMWorker (asyncio background task)
│
├── frontend/
│   └── src/
│       ├── App.tsx              # 메인 레이아웃
│       └── components/
│           ├── ChatPanel.tsx    # 채팅 + 인용 마커 렌더링
│           ├── CitationPanel.tsx# 법령/판례 인용 카드
│           └── LawGraphView.tsx # Force-Graph 시각화
│
├── scripts/
│   ├── setup_index.py           # 전체 색인 파이프라인
│   ├── build_graph.py           # 법령 관계 그래프 빌드
│   └── entrypoint.sh            # Docker 진입점
│
├── tests/                       # pytest TDD (모듈별 분리)
│   ├── integrity/
│   ├── cache/
│   ├── streaming/
│   ├── worker/
│   ├── retrieval/
│   ├── agents/
│   └── ...
│
├── data/
│   ├── sqlite/articles.db       # SHA-256 메타데이터
│   ├── graph/law_graph.pkl      # NetworkX 직렬화
│   └── raw/                     # 수집된 원본 데이터
│
├── docker-compose.yml
├── Dockerfile.api
├── pyproject.toml
└── .env.example
```

---

## 8. 기술 스택

| 분류 | 기술 | 버전 | 역할 |
|------|------|------|------|
| **LLM** | GPT-4o-mini | - | 법령 추론 및 답변 생성 |
| **Embedding** | text-embedding-3-small | - | 벡터 검색 + 시맨틱 캐시 |
| **Vector DB** | Qdrant | latest | laws / cases / query_cache |
| **Graph** | NetworkX | ≥3.6 | 법령 참조 관계 DiGraph |
| **Sparse Search** | rank-bm25 | ≥0.2 | BM25Okapi 키워드 검색 |
| **Cache/Stream** | Redis | 7-alpine | 세션·큐·시맨틱캐시 |
| **Metadata DB** | SQLite (WAL) | built-in | SHA-256 무결성 검증 |
| **API Framework** | FastAPI | ≥0.111 | SSE 스트리밍 REST API |
| **ASGI Server** | Uvicorn | ≥0.30 | 멀티워커 비동기 서버 |
| **LLM 추상화** | langchain-openai | ≥0.1 | `ChatOpenAI` (LLM) · `OpenAIEmbeddings` (임베딩) |
| **메시지 타입** | langchain-core | ≥0.2 | `HumanMessage` · `AIMessage` · `SystemMessage` |
| **Frontend** | React + Vite | 18 | SPA |
| **Graph UI** | react-force-graph-2d | - | 법령 관계 물리 시뮬레이션 |
| **Markdown** | react-markdown + remark-gfm | - | 답변 렌더링 |
| **Data Collection** | requests + BeautifulSoup4 | - | law.go.kr API 파싱 |
| **Config** | pydantic-settings | ≥2.3 | 환경변수 관리 |
| **Logging** | loguru | ≥0.7 | 구조화 로깅 |
| **Package Manager** | uv | - | Python 패키지 관리 |
| **Container** | Docker Compose | - | 서비스 오케스트레이션 |

---

## 9. 설치 및 실행

### 사전 요구사항

- Docker & Docker Compose
- law.go.kr Open API 키 ([신청](https://open.law.go.kr/LSO/main.do))
- OpenAI API 키

### 빠른 시작

```bash
# 1. 저장소 클론
git clone https://github.com/your-username/web-legal-compliance-ai-agent
cd web-legal-compliance-ai-agent

# 2. 환경변수 설정
cp .env.example .env
# .env 파일에 아래 값 입력:
#   OPENAI_API_KEY=sk-...
#   LAW_API_KEY=...

# 3. 전체 서비스 실행 (최초 실행 시 법령 색인 자동 수행)
docker compose up -d

# 4. 브라우저 접속
open http://localhost:5173
```

### 초기 색인만 별도 실행

```bash
# 법령 + 판례 수집 및 색인
docker compose run --rm api python scripts/setup_index.py --reset

# 법령 관계 그래프 빌드
docker compose run --rm api python scripts/build_graph.py
```

### 워커 수 조정

```bash
# 환경변수로 워커 수 조정 (기본: nproc)
UVICORN_WORKERS=4 docker compose up -d api
```

### 로컬 개발 환경

```bash
# Python 의존성 설치
uv sync --extra dev

# Redis, Qdrant는 Docker로 실행
docker compose up -d redis qdrant

# API 서버 실행
uv run uvicorn api.main:app --reload --port 8000

# 테스트 실행
uv run pytest tests/ -v
```

---

## 10. API 문서

### `POST /api/chat`

SSE 스트리밍으로 법률 질문에 답변합니다.

**Request**
```json
{
  "question": "전세 계약 만료 후 보증금을 돌려받지 못하면 어떻게 해야 하나요?",
  "session_id": "optional-session-id"
}
```

**SSE Events**

| Event | Payload | 설명 |
|-------|---------|------|
| `citations` | `{citations, related_articles, session_id}` | 검색된 법령/판례 (스트리밍 시작 전) |
| `content` | `{text}` | 답변 토큰 스트림 |
| `citations` | `{citations, related_articles, full_answer, session_id}` | 최종 인용 + 전체 답변 |
| `done` | `{session_id, cached?}` | 스트리밍 완료 (`cached: true`이면 캐시 히트) |
| `error` | `{message}` | 오류 발생 |

**Example Response Stream**
```
event: citations
data: {"citations": [...], "related_articles": ["001697_3", ...], "session_id": "abc"}

event: content
data: {"text": "주택임대차보호법 제3조[1]에 따르면"}

event: content
data: {"text": " 임차인은 임차주택의 인도와 주민등록을..."}

...

event: done
data: {"session_id": "abc"}
```

---

### `GET /api/search`

법령 또는 판례를 직접 검색합니다.

**Query Parameters**

| 파라미터 | 타입 | 기본값 | 설명 |
|----------|------|--------|------|
| `q` | string | 필수 | 검색 질문 |
| `type` | `law` \| `case` | `law` | 검색 대상 |
| `top_k` | integer | 5 | 반환 개수 |

---

### `GET /api/articles/{article_id}`

단일 조문의 상세 정보를 조회합니다.

---

### `GET /api/sessions/{session_id}/history`

세션의 대화 이력을 반환합니다.

---

### `DELETE /api/sessions/{session_id}`

세션을 삭제합니다.

---

### `GET /health`

서비스 상태를 확인합니다.

```json
{"status": "ok"}
```

---

## 11. 개발 가이드 (TDD)

이 프로젝트는 **Red → Green → Refactor** 사이클을 따릅니다.

```bash
# 실패하는 테스트 먼저 작성 (Red)
# 구현 후 테스트 통과 (Green)
# 리팩터링 (Refactor, 테스트 유지)

uv run pytest tests/ -v                          # 전체 테스트
uv run pytest tests/cache/ -v                    # 특정 모듈
uv run pytest tests/ --tb=short -q              # 요약 출력
```

### 테스트 커버리지 현황

| 모듈 | 테스트 파일 | 테스트 수 |
|------|-------------|-----------|
| `integrity.db` | `test_db.py`, `test_db_wal.py` | 8 |
| `cache.semantic_cache` | `test_semantic_cache.py` | 7 |
| `streaming.llm_queue` | `test_llm_queue.py` | 10 |
| `worker.llm_worker` | `test_llm_worker.py` | 5 |
| `collector.*` | `test_domain.py`, `test_law_*.py` | 15+ |
| `graph.*` | `test_law_graph.py`, `test_reference_parser.py` | 10+ |
| `retrieval.*` | `test_hybrid.py`, `test_graph_expander.py` | 10+ |
| `agents.*` | `test_legal_agent.py` | 5+ |

### 환경변수 레퍼런스

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `OPENAI_API_KEY` | 필수 | OpenAI API 키 |
| `LAW_API_KEY` | 필수 | law.go.kr API 키 |
| `QDRANT_URL` | `http://localhost:6333` | Qdrant 접속 URL |
| `REDIS_URL` | `redis://localhost:6379` | Redis 접속 URL |
| `LLM_CONCURRENCY` | `3` | 동시 LLM 처리 최대 수 |
| `CACHE_SIMILARITY_THRESHOLD` | `0.92` | 시맨틱 캐시 유사도 임계값 |
| `UVICORN_WORKERS` | `$(nproc)` | uvicorn 워커 수 |
| `ENV` | `dev` | 실행 환경 |
| `LOG_LEVEL` | `INFO` | 로그 레벨 |

---

## 12. AI 협업 개발 방법론

이 프로젝트는 처음부터 끝까지 **Claude Code (VSCode 익스텐션)** 를 개발 파트너로 활용하여 구축되었습니다. 단순히 코드 생성 도구로 사용한 것이 아니라, 설계·구현·테스트·디버깅·문서화의 전 사이클에 걸쳐 협업하는 방식으로 진행했습니다.

---

### 12-1. TODO.md 기반 Phase 계획 관리

프로젝트를 **페이즈 단위로 분할**하고, 각 페이즈 시작 전 `TODO.md`에 구체적인 작업 목록을 먼저 정의했습니다. 구현은 그 이후에 진행했습니다.

```
TODO.md 구조 예시:

## Phase 1 — 법령 데이터 파이프라인
### 1-2. 법령목록 API
- [ ] TDD: tests/collector/test_law_list_api.py
- [ ] GET /DRF/lawSearch.do 호출 구현
- [ ] 페이지네이션 처리 (display=100, page=1,2,...)

→ 구현 완료 후:
- [x] TDD: tests/collector/test_law_list_api.py
- [x] GET /DRF/lawSearch.do 호출 구현
```

**페이즈 목록**

| Phase | 내용 |
|-------|------|
| Phase 0 | 웹 분석 기능 제거, 부동산 법률 도메인으로 재정의 |
| Phase 1 | law.go.kr API 수집 파이프라인 (법령 + 판례) |
| Phase 2 | 조문 청킹 + Qdrant 벡터 색인 |
| Phase 3 | 법령 관계 그래프 (NetworkX) |
| Phase 4 | LegalReasoningAgent + 대화 세션 |
| Phase 5 | FastAPI /api/chat SSE 엔드포인트 |
| Phase 6 | React UI (ChatPanel · CitationPanel · LawGraphView) |
| Phase 7 | 성능 최적화 (WAL · 시맨틱 캐시 · Redis Stream 큐잉 · 멀티워커) |

각 페이즈가 완료된 후에야 다음 페이즈의 TODO를 확정지었습니다. 이전 결과물이 다음 설계에 영향을 주기 때문입니다.

---

### 12-2. TDD — 테스트를 코드보다 먼저 작성

모든 모듈을 **Red → Green → Refactor** 사이클로 개발했습니다.

**실제 진행 흐름 (Phase 7 예시)**

```
1. [Red]   tests/cache/test_semantic_cache.py 작성
           → 아직 SemanticCache 없음 → 7 errors

2. [Green] src/cache/semantic_cache.py 구현
           → 7 passed

3. [Red]   tests/streaming/test_llm_queue.py 작성
           → 아직 LLMJobQueue 없음 → 10 errors

4. [Green] src/streaming/llm_queue.py 구현
           → 10 passed

5. [Red]   tests/worker/test_llm_worker.py 작성
           → 아직 LLMWorker 없음 → 5 errors

6. [Green] src/worker/llm_worker.py 구현
           → 5 passed

7. 통합 연결 (chat.py, main.py, dependencies.py)

8. Docker 빌드 → 실제 요청 → 로그 확인
```

이 방식의 핵심은 **구현체가 없는 상태에서 테스트를 먼저 작성**함으로써 인터페이스와 동작 명세가 코드보다 먼저 확정된다는 점입니다. Claude에게 "이 테스트를 통과하는 코드를 작성해"라고 지시하면, 이미 명세가 테스트에 담겨 있어 불필요한 주석이나 문서 없이도 정확한 구현이 가능했습니다.

**Mock 전략**

외부 의존성(OpenAI, Qdrant, Redis)은 `unittest.mock`으로 모두 격리했습니다. 실제 서버 없이 CI 환경에서 전체 테스트를 실행할 수 있습니다.

```python
# 예: SemanticCache 테스트 — OpenAI/Qdrant 호출 없이 격리
@pytest.fixture
def cache(mock_qdrant):
    with patch("cache.semantic_cache.AsyncOpenAI"):
        c = SemanticCache("test-key", mock_qdrant, threshold=0.92)
    return c, mock_qdrant
```

---

### 12-3. Claude Code를 활용한 시스템 설계 협업

코드 작성 이전에 **시스템 엔지니어링 관점의 설계 질문**을 Claude에게 던지고 응답을 바탕으로 아키텍처를 결정했습니다.

**병목 분석 → 최적화 방향 결정**

> "사용자가 늘어나면 어디서 병목이 생기고 어떻게 해결할 것인가?"

Claude는 이 질문에 대해 현재 스택(OpenAI API, SQLite, NetworkX, BM25, SSE)을 기반으로 구체적인 병목 지점과 우선순위를 분석했고, 이것이 Phase 7 최적화 작업의 설계 근거가 되었습니다.

| 질문 유형 | 활용 방식 |
|-----------|-----------|
| "이 구조에서 병목이 어디?" | 성능 최적화 우선순위 결정 |
| "Redis Stream으로 LLM 큐잉하면 어때?" | 아키텍처 트레이드오프 검토 |
| "LangChain을 얼마나 써야 해?" | 의존성 범위 결정 |
| "GraphExpander와 LawGraph의 차이?" | 설계 명확화 |

---

### 12-4. 실제 환경 검증 — Docker 로그 기반 디버깅

코드 작성 후 바로 Docker 컨테이너를 빌드하고, **실제 요청을 보내 로그로 검증**하는 방식을 사용했습니다. 단순히 테스트가 통과하는 것에 그치지 않고, 실제 운영 환경에서의 동작을 확인했습니다.

```bash
# 빌드 → 요청 → 로그 검증 사이클
docker compose build api && docker compose up -d api

# 캐시 miss 경로 검증
curl -N -X POST http://localhost:8000/api/chat \
  -d '{"question": "전세 계약 만료 후 보증금 반환 방법"}'

# 로그에서 실제 처리 흐름 확인
docker compose logs api --tail=20
# → INFO | LLM Worker [worker-16] 시작됨
# → INFO | 비동기 질문 수신: 전세 계약 만료 후...
# → INFO | 그래프 확장: 10개의 연관 조문을 추가로 불러옵니다.

# 캐시 hit 검증 (동일 질문 재전송)
# → INFO | 캐시 히트: 전세 계약 만료 후 보증금을...
# → done: {"cached": true}  ← 0.8초 응답
```

이 과정에서 `qdrant-client` 버전 업그레이드로 인해 `search()` API가 `query_points()`로 변경된 것을 실제 로그로 발견하고 즉시 수정했습니다. TDD 테스트만으로는 잡을 수 없는 런타임 통합 오류를 실환경 검증으로 포착한 사례입니다.

---

### 12-5. Claude Code 활용 원칙

이 프로젝트를 통해 정립한 AI 협업 원칙입니다.

**효과적이었던 것**

- **테스트 명세 → 구현 순서 유지**: Claude에게 먼저 테스트를 작성하게 하고, 그 테스트를 통과하는 구현을 요청하면 인터페이스가 흔들리지 않음
- **페이즈 단위 컨텍스트 제공**: 전체 코드베이스를 한 번에 던지지 않고, 현재 페이즈에 관련된 파일만 읽게 하여 집중도 유지
- **설계 결정의 근거 확보**: "왜 이 방식인가"를 Claude와 대화하며 결정하면, 나중에 README에 기술적 근거로 그대로 활용 가능
- **실환경 검증을 마지막으로**: 테스트 통과 후 반드시 Docker 환경에서 실제 요청으로 검증

**주의했던 것**

- 테스트 없이 구현부터 작성하는 것을 의도적으로 방지 (Red 단계 강제)
- Claude가 생성한 코드도 반드시 로컬에서 실행하여 검증 후 커밋
- 페이즈 간 의존성이 생기면 TODO.md를 먼저 업데이트하고 진행

---

## 면책 고지

이 시스템이 제공하는 정보는 **참고용**이며 법적 효력을 갖지 않습니다. 실제 법적 분쟁 또는 계약 체결 시에는 반드시 공인된 법률 전문가의 자문을 받으시기 바랍니다.

---

*이 프로젝트는 법률 정보 접근성 향상을 목적으로 개발되었습니다.*

*Developed with [Claude Code](https://claude.ai/claude-code) — Anthropic의 AI 개발 도구*
