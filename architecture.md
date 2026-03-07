# Web Legal Compliance AI Agent
## Architecture & Design Document

> 웹사이트 소스코드(abs path) · URL · 자연어 질문을 입력하면  
> 관련 법규 준수 여부를 멀티 에이전트로 분석하고  
> 조항 인용(Citation + SHA-256)과 함께 보완 사항을 실시간 스트리밍으로 안내하는 시스템

---

## 1. 전체 아키텍처

```
┌──────────────────────────────────────────────────────────────────┐
│  00  INPUT HANDLER                                               │
│  abs path · URL(BS4) · 자연어 질문 · tiktoken Token Splitter    │
└─────────────────────────┬────────────────────────────────────────┘
                           │ 파싱 텍스트 + 메타데이터
                           ↓
┌──────────────────────────────────────────────────────────────────┐
│  01  LAW KNOWLEDGE BASE  (사전 구축 / 증분 업데이트)             │
│  law.go.kr 수집 → SHA-256 체크 → 청킹 → 임베딩 → Qdrant       │
└─────────────────────────┬────────────────────────────────────────┘
                           │ Hybrid Retrieval
                           ↓
┌──────────────────────────────────────────────────────────────────┐
│  02  RETRIEVAL LAYER                                             │
│  Redis Semantic Cache → BM25 + Qdrant Vector → RRF → Top-K     │
└─────────────────────────┬────────────────────────────────────────┘
                           │ Top-K Chunks + Metadata
                           ↓
┌──────────────────────────────────────────────────────────────────┐
│  03  MULTI-AGENT REASONING  (LangChain)                          │
│                                                                  │
│  Orchestrator                                                    │
│  ├── Privacy Agent   → 개인정보보호법 · 정보통신망법 · 위치정보법 │
│  ├── Security Agent  → 안전성 확보 조치 기준 · 정보통신망법      │
│  └── Service Agent   → 전자상거래법 · 청소년보호법 · 신용정보법  │
│                ↓                                                 │
│       Citation Assembler  [법령명 제N조 · sha:xxxx · 날짜]       │
└─────────────────────────┬────────────────────────────────────────┘
                           │ Redis Stream (XADD)
                           ↓
┌──────────────────────────────────────────────────────────────────┐
│  04  RESPONSE LAYER                                              │
│  Redis Stream Consumer → Streamlit st.write_stream              │
│  ✅ 준수 항목  ⚠️ 보완 항목  📚 Citation + SHA 카드             │
└──────────────────────────────────────────────────────────────────┘
```

---

## 2. 레이어별 상세

### 00. Input Handler

| 모드 | 처리 방식 | 비고 |
|------|-----------|------|
| **파일 (abs path)** | 경로로 직접 로드, 확장자별 파서 분기 | .py .html .js .css 지원 |
| **URL** | requests + BeautifulSoup4로 정적 파싱 | JS/CSS/meta 태그 포함 |
| **자연어 질문** | 그대로 Query로 전달 | 코드 없이 법규만 질의 |

**Token Splitter 로직**

```
입력 텍스트
    ↓ tiktoken.count_tokens()
한도 이내? ──Yes──→ 단일 청크로 처리
    │ No
    ↓
RecursiveCharacterTextSplitter
  chunk_size    = model_ctx_limit × 0.7
  chunk_overlap = 200 tokens
    ↓
청크 N개 → 병렬 분석 후 결과 병합
```

---

### 01. Law Knowledge Base

**수집 대상**

| 법규 | 소스 | 담당 Agent | 핵심 체크 포인트 |
|------|------|-----------|-----------------|
| 개인정보 보호법 | law.go.kr API | Privacy | 수집·동의, 제3자 제공, 민감정보, 파기 |
| 정보통신망법 | law.go.kr API | Privacy + Security | 보안 조치, 접속 로그, 광고 동의 |
| 위치정보법 | law.go.kr API | Privacy | GPS·Wi-Fi 수집, 방통위 신고 |
| 안전성 확보 조치 기준 | 개인정보보호위 고시 | Security | 암호화, 접근 권한, 취약점 점검 |
| 전자상거래법 | law.go.kr API | Service | 사업자 표시, 환불 정책, 결제 보존 5년 |
| 청소년보호법 | law.go.kr API | Service | 연령 인증, 유해매체 표시 |
| 신용정보법 | law.go.kr API | Service | 금융정보 처리, 허가 요건 |

**SHA-256 무결성 관리**

```
법령 수집 (조항 단위)
    ↓
SHA-256(조항 본문) 계산
    ↓
SQLite 비교
  ┌────────────┬───────────┬───────────┬────────────┐
  │ article_id │ hash_curr │ hash_prev │ updated_at │
  └────────────┴───────────┴───────────┴────────────┘
    ↓
hash_curr ≠ hash_prev
  ──Yes──→ 해당 조항만 재임베딩  (증분 업데이트)
  ──No───→ 스킵

Citation 포맷: [개인정보보호법 제17조 · sha:a3f2c1… · 2024-03-15]
```

---

### 02. Retrieval Layer

```
사용자 쿼리
    ↓
Redis Semantic Cache 조회
  cosine ≥ 0.95 ──캐시 히트──→ 즉시 반환
    │ 미스
    ↓
Query Rewriter  (HyDE / Multi-Query 확장)
    ↓
    ├── BM25 Sparse   : 조항 번호 · 법률 용어 정확 매칭
    └── Qdrant Dense  : 의미 기반 유사도 검색
    ↓
RRF (Reciprocal Rank Fusion)
    ↓
Dynamic Top-K
  코드 분석 (복잡) → K = 8
  단순 질문        → K = 3
    ↓
Top-K Chunks + { article_id, sha, url, law_name, updated_at }
```

---

### 03. Multi-Agent Reasoning

```
Orchestrator Agent  (LangChain AgentExecutor)
│
│  입력 유형 판별 → 분석 범주 결정 → Sub-Agent 병렬 분배
│
├── Privacy Agent  ────────────────────────────────────────────────
│     체크 항목:  개인정보 수집 동의 코드 존재 여부
│                처리방침 페이지 게시 여부
│                민감정보·위치정보 처리 여부
│                보유기간·파기 로직 존재 여부
│                마케팅 동의 분리 여부
│     참조 법규:  개인정보보호법 · 정보통신망법 · 위치정보법
│
├── Security Agent ────────────────────────────────────────────────
│     체크 항목:  비밀번호 평문 저장 패턴 탐지
│                HTTPS 강제 리다이렉트 여부
│                SQL Injection 취약 패턴
│                접근 로그 보관 코드
│                암호화 알고리즘 적정성
│     참조 법규:  정보통신망법 보안 조항 · 안전성 확보 조치 기준
│
└── Service Agent  ────────────────────────────────────────────────
      체크 항목:  결제 기능 감지 시 전자상거래법 적용
                사업자 정보 표시 여부
                환불 정책 페이지 존재
                청소년 연령 인증 여부
                금융정보 처리 시 신용정보법
      참조 법규:  전자상거래법 · 청소년보호법 · 신용정보법

                      ↓ 병렬 결과 수집

Citation Assembler
  → 중복 조항 제거
  → SHA + 원문 URL + 개정일 부착
  → ✅ / ⚠️ 분류 후 구조화
```

**출력 포맷**

```
✅ 준수 항목
  • 개인정보 처리방침 하단 게시 확인
    [개인정보보호법 제30조 · sha:a3f2… · 2024-01-01] → law.go.kr/…

⚠️ 보완 필요
  • 비밀번호 평문 저장 감지 (users.password 컬럼)
    [안전성 확보 조치 기준 제7조 · sha:b12d… · 2023-09-15]
    권고: bcrypt / argon2 해싱 적용

📚 참조 조항 테이블
  법령명 | 조항 | SHA(앞 8자) | 시행일 | 원문 URL
```

---

### 04. Response Layer

```
Citation Assembler 결과
    ↓
Redis Stream  XADD legal-stream *  (에이전트별 채널, 순서 보장)
    ↓
Stream Consumer  XREAD COUNT 1 BLOCK 0
    ↓
Streamlit  st.write_stream()
  ├── 실시간 스트리밍 응답 패널
  ├── Citation 카드  (SHA + 원문 링크)
  └── 🔔 개정 감지 뱃지  (hash_prev ≠ hash_curr 시)
```

---

## 3. 기술 스택

| 레이어 | 기술 | 선택 이유 |
|--------|------|-----------|
| **LLM** | GPT-4o-mini | Tool Use 안정, 저비용, 스트리밍 |
| **Embedding** | text-embedding-3-small | 비용 대비 성능, 다국어 |
| **Vector DB** | Qdrant (Docker) | payload 필터 강력, 프로덕션 근접 |
| **Metadata / SHA** | SQLite | 해시 이력 저장, 서버 불필요 |
| **Cache + Stream** | Redis 7 (Docker) | Semantic Cache + Stream 이중 역할 |
| **RAG / Agent** | LangChain | AgentExecutor · Tool · RunnableParallel |
| **Sparse Search** | rank-bm25 | 조항 번호 정확 매칭 |
| **웹 파싱** | requests + BeautifulSoup4 | URL 정적 파싱 |
| **Token 계산** | tiktoken | 모델 한도 초과 감지 |
| **법령 수집** | law.go.kr Open API | 조항 단위 구조화 수집 |
| **UI** | Streamlit | st.write_stream SSE 대응 |
| **패키지 관리** | uv | lock 파일 기반 재현 가능 빌드 |
| **컨테이너** | Docker Compose | 전체 스택 단일 명령 기동 |

**pyproject.toml 의존성**

```toml
dependencies = [
    # LLM / Embedding
    "openai>=1.35",
    "langchain>=0.2",
    "langchain-openai>=0.1",
    "langchain-community>=0.2",
    "langchain-text-splitters>=0.2",

    # Vector DB
    "qdrant-client>=1.9",
    "langchain-qdrant>=0.1",

    # Cache + Stream
    "redis>=5.0",

    # 법령 수집 / 파싱
    "requests>=2.32",
    "beautifulsoup4>=4.12",
    "lxml>=5.2",

    # Token / Sparse Search
    "tiktoken>=0.7",
    "rank-bm25>=0.2",

    # UI
    "streamlit>=1.36",

    # Utilities
    "python-dotenv>=1.0",
    "pydantic>=2.7",
    "loguru>=0.7",
    "tqdm>=4.66",
]
```

---

## 4. 폴더 구조

```
legal-compliance-agent/
│
├── Dockerfile                  # uv 멀티스테이지 빌드
├── docker-compose.yml          # app + Qdrant + Redis
├── .dockerignore
├── pyproject.toml
├── uv.lock                     # 재현 가능한 빌드 (자동 생성)
├── .env.example
├── .gitignore
│
├── scripts/
│   └── setup_index.py          # 법령 수집 + SHA 체크 + Qdrant 색인
│                               # CMD 첫 번째 단계로 자동 실행
│
├── src/
│   ├── collector/              # law.go.kr 수집 · 파싱
│   │   ├── law_api.py
│   │   ├── parser.py
│   │   └── scheduler.py        # APScheduler 주기 재수집
│   │
│   ├── integrity/              # SHA-256 무결성
│   │   ├── hasher.py
│   │   └── db.py               # SQLite CRUD
│   │
│   ├── embedder/               # 청킹 + Qdrant 색인
│   │   ├── chunker.py
│   │   └── indexer.py          # upsert (증분)
│   │
│   ├── input/                  # 사용자 입력 처리
│   │   ├── file_loader.py      # abs path
│   │   ├── url_parser.py       # BS4
│   │   └── token_splitter.py   # tiktoken
│   │
│   ├── retrieval/              # 하이브리드 검색
│   │   ├── query_rewriter.py
│   │   ├── bm25.py
│   │   ├── vector.py           # Qdrant
│   │   ├── rrf.py
│   │   ├── dynamic_topk.py
│   │   └── cache.py            # Redis Semantic Cache
│   │
│   ├── agents/                 # 멀티 에이전트
│   │   ├── orchestrator.py
│   │   ├── privacy_agent.py
│   │   ├── security_agent.py
│   │   ├── service_agent.py
│   │   └── citation.py
│   │
│   ├── streaming/              # Redis Stream
│   │   └── redis_stream.py     # XADD / XREAD
│   │
│   └── core/                   # 공통
│       ├── config.py
│       ├── models.py           # Pydantic: LawArticle · Citation · Report
│       └── logger.py
│
├── data/                       # volume mount → 컨테이너 재시작 후 유지
│   ├── sqlite/articles.db
│   └── raw/articles.json
│
└── app.py                      # Streamlit 진입점
```

---

## 5. Docker 구성

**Dockerfile (uv 멀티스테이지)**

```dockerfile
# Stage 1: builder
FROM python:3.12-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

WORKDIR /app
COPY pyproject.toml uv.lock ./

# 의존성만 먼저 설치 → pyproject 변경 없으면 레이어 캐시 재사용
RUN uv sync --frozen --no-install-project --no-dev

# Stage 2: runtime
FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/
COPY --from=builder /app/.venv /app/.venv

WORKDIR /app
COPY . .

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app/src"
EXPOSE 8501

# 법령 색인 구축 후 앱 실행 (SHA 비교로 재시작 시 중복 없음)
CMD ["sh", "-c", "python scripts/setup_index.py && streamlit run app.py --server.address=0.0.0.0"]
```

**docker-compose.yml**

```yaml
services:

  qdrant:
    image: qdrant/qdrant:latest
    ports: ["6333:6333"]
    volumes:
      - qdrant_data:/qdrant/storage

  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]
    volumes:
      - redis_data:/data

  app:
    build: .
    ports: ["8501:8501"]
    env_file: .env
    volumes:
      - ./data:/app/data          # SQLite + raw JSON 영속
      - ./src:/app/src            # 개발 중 코드 반영
    depends_on:
      - qdrant
      - redis

volumes:
  qdrant_data:
  redis_data:
```

**실행**

```bash
cp .env.example .env        # OPENAI_API_KEY 입력

docker-compose up --build   # 최초 (빌드 + 색인 + 앱)
docker-compose up           # 이후 재시작
```

---

## 6. 핵심 기술 포인트 (포트폴리오 차별화)

| 기술 | 해결한 문제 | 구현 방식 |
|------|------------|-----------|
| **SHA-256 Integrity** | 법령 개정 반영 누락 | 조항 해시 비교 → 변경분만 재임베딩, 이력 보관 |
| **Dynamic Top-K** | 검색 품질 vs 비용 | 입력 복잡도(코드/질문)에 따라 K=3~8 자동 조정 |
| **RRF Fusion** | 단일 검색 한계 | BM25(조항 번호 정확 검색) + Vector(의미 검색) 결합 |
| **Redis Semantic Cache** | API 비용 · 응답 지연 | 유사 쿼리 cosine ≥ 0.95 → 캐시 히트, TTL=1h |
| **Redis Stream** | 멀티 에이전트 결과 순서 보장 | XADD per agent → XREAD → st.write_stream |
| **Token Splitter** | 대용량 코드 파일 처리 | tiktoken 계산 → 오버랩 청킹 → 결과 병합 |
| **Citation + SHA** | 응답 신뢰도 확보 | 모든 인용에 해시·날짜 부착, 개정 시 🔔 뱃지 |
| **Multi-Agent** | 법규 도메인 분리 | Privacy·Security·Service 병렬 전문화 |
| **uv in Docker** | 재현 가능한 빌드 | lock 파일 기반 멀티스테이지, 레이어 캐시 최적화 |
