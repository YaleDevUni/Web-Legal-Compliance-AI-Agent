# Technical Issues & Fixes — Web Legal Compliance AI Agent

포트폴리오용 기술 난제 해결 기록. 각 섹션은 **문제 → 원인 분석 → 해결 방법** 순으로 작성됩니다.

---

## 1. Qdrant ReadTimeout (RAG 파이프라인)

**증상**
URL 분석 요청 시 Qdrant 벡터 검색에서 `ReadTimeout` 발생. 분석 자체가 불가능해짐.

**원인**
`httpx` 기본 타임아웃(5초)이 대용량 벡터 검색 응답 시간보다 짧음.

**해결**
```python
# Before
QdrantClient(url=str(settings.qdrant_url))

# After
QdrantClient(url=str(settings.qdrant_url), timeout=30)
```

---

## 2. RAG 컨텍스트 손실 — Parent Chunk 문제

**증상**
개인정보보호법 제23조 ②항만 검색 히트 시 ①항(핵심 규정)이 LLM에 전달되지 않아, 위반 여부를 잘못 판단.

**원인**
의미 기반 청킹(Semantic Chunking) 도입 후 단락 단위로 벡터화. 검색 결과가 특정 단락만 반환되면 같은 조문의 다른 단락은 LLM 컨텍스트에서 누락됨.

**해결 — Parent Chunk Strategy**

청킹 시 각 청크 메타데이터에 원문 전체(`full_content`)를 저장:

```python
metadata = {
    "article_id": article.article_id,
    ...
    "full_content": article.content,  # 조문 전체 원문
}
```

RAG 컨텍스트 구성 시 `full_content` 우선 사용:

```python
full_text = meta.get("full_content") or "\n\n".join(data["texts"])
```

어떤 단락이 검색되더라도 해당 조문 전체가 LLM에 전달됨.

---

## 3. LLM 분류 오류 — "없음" → COMPLIANT 역설

**증상**
LLM이 `description`에 "동의 절차 없음", "개인정보 처리방침 미비"라고 쓰면서 `status`를 `compliant`로 분류. 논리 모순이지만 프롬프트가 이를 허용.

**원인**
기존 프롬프트의 규칙 1이 "추측이나 가능성은 compliant"로 광범위하게 정의되어, LLM이 명백한 위반도 안전하게 compliant로 처리.

**해결 — 3-way 명시적 분류 기준 + 논리 모순 경고**

```
violation: 법령이 요구하는 필수 요소가 HTML/코드에 존재하지 않거나, 금지된 행위가 명확히 있는 경우
compliant: 법령이 요구하는 요소가 HTML/코드에 실제로 존재하는 경우
unverifiable: 서버사이드에서만 확인 가능한 항목

⚠️ 핵심 규칙: description에 '~없음', '~미비'라고 쓰면서 compliant로 분류하는 것은
논리 모순입니다. 없다고 판단했다면 반드시 violation으로 분류하세요.
```

---

## 4. 에이전트 순차 실행 → 병렬 실행 전환

**증상**
개인정보·보안·서비스 에이전트가 순차 실행되어 전체 분석에 60~90초 소요.

**원인**
초기 구현에서 `for law_name in required_laws: agent.analyze()` 단순 루프 사용.

**해결 — ThreadPoolExecutor**

```python
with ThreadPoolExecutor(max_workers=len(agents_to_run)) as executor:
    futures = {
        executor.submit(agent.analyze, code_text, search_query): law_name
        for law_name, agent in agents_to_run.items()
    }
    for future in as_completed(futures):
        reports = future.result()
```

가장 느린 에이전트 시간만큼만 소요. 3개 에이전트 기준 약 3배 속도 개선.

---

## 5. Redis Pub/Sub Race Condition — 메시지 유실

**증상**
Job Queue 패턴 도입 후 프론트엔드가 SSE를 구독해도 결과가 0개로 표시됨.
Worker 로그에서는 분석 완료가 확인됨.

**원인**
Redis Pub/Sub의 fire-and-forget 특성. Worker가 먼저 `PUBLISH`를 완료한 후 SSE 구독자가 연결되면 메시지가 이미 사라져 있음.

```
[Worker]  분석 완료 → PUBLISH result:{job_id}  (구독자 없음 → 유실)
[SSE]     GET /events  SUBSCRIBE result:{job_id}  (이미 늦음)
```

**해결 — Redis Streams 결과 보존**

Pub/Sub 대신 `XADD`로 결과 스트림에 저장. SSE는 `XREAD id=0`으로 처음부터 읽음.

```python
# Worker: 결과를 스트림에 영구 저장 (TTL=10분)
rc.xadd(f"result:{job_id}", {"_event": "report", "data": json.dumps(report)})
rc.expire(f"result:{job_id}", 600)

# SSE: 처음부터 읽기 — 늦게 연결해도 유실 없음
rc.xread({result_key: "0"}, count=50, block=500)
```

Worker가 먼저 끝나도 결과가 스트림에 남아 있어 SSE가 나중에 연결해도 전부 수신 가능.

---

## 6. Redis bytes/str 키 불일치

**증상**
Race condition 수정 후에도 SSE에서 결과가 표시되지 않음. `XRANGE`로 확인하면 결과 스트림에 데이터가 정상 존재.

**원인**
API Redis 클라이언트가 `decode_responses=False`로 초기화되어 XREAD 결과의 필드 키가 bytes(`b"_event"`)로 반환됨. SSE 파서가 문자열 키(`"_event"`)로 조회하여 항상 `None` 반환.

```python
fields.get("_event", "report")   # b"_event" != "_event" → 항상 "report" 반환
fields["data"]                   # KeyError (실제 키는 b"data") → try/except로 skip
```

**해결**

```python
# Before
redis_lib.from_url(settings.redis_url, decode_responses=False)

# After
redis_lib.from_url(settings.redis_url, decode_responses=True)
```

Worker는 이미 `decode_responses=True`를 사용 중이었으므로 API와 통일.

---

## 7. Hybrid Search 메타데이터 손실

**증상**
BM25 + Vector RRF 검색 결과에서 `law_name`, `sha256` 등 메타데이터가 누락되어 Citation 생성 불가.

**원인**
BM25 결과를 벡터 결과와 병합하는 RRF 로직에서 BM25 측 메타데이터를 누락하고 점수만 병합.

**해결**
RRF 병합 시 각 소스의 payload를 우선순위에 따라 병합:

```python
merged_payload = {**bm25_payload, **vector_payload}  # vector 우선
```

---

## 8. Streamlit → FastAPI + React/Vite 마이그레이션

**동기**
Streamlit은 단일 스레드 동기 모델로 다수 사용자 동시 요청을 처리할 수 없음. 사용자가 분석 중이면 다른 사용자의 요청이 블로킹됨.

**변경 아키텍처**

```
Before:  사용자 → Streamlit(단일 스레드) → 직접 Orchestrator 실행 → 결과 표시

After:   사용자 → React/Vite → POST /api/analyze → job_id 즉시 반환
                                Redis Stream (stream:jobs) enqueue
                                Worker (비동기) consume → 분석 실행
                                GET /api/analyze/{id}/events (SSE) → 결과 스트리밍
```

**핵심 설계 결정**
- `src/` 비즈니스 로직은 완전 재사용 (Orchestrator, RAG, 에이전트 코드 변경 없음)
- Worker가 `Orchestrator.stream` 인터페이스를 통해 에이전트 완료마다 즉시 결과 publish
- `decode_responses=True` 통일로 Worker-API 간 Redis 직렬화 일관성 확보

---

## 9. ComplianceStatus 대소문자 불일치 (프론트엔드 버그)

**증상**
API가 보고서 5개를 반환하지만 프론트엔드 메트릭 카드가 모두 0으로 표시됨.

**원인**
Python Pydantic enum `model_dump(mode="json")`이 enum 값 자체를 직렬화:

```python
class ComplianceStatus(str, Enum):
    VIOLATION = "violation"   # → JSON: "violation" (소문자)
```

TypeScript 타입과 필터는 대문자로 정의:

```typescript
type ComplianceStatus = 'COMPLIANT' | 'VIOLATION' | 'UNVERIFIABLE'  // 불일치
reports.filter(r => r.status === 'VIOLATION')  // 항상 빈 배열
```

**해결**
TypeScript 타입, 필터, `STATUS_CONFIG` 키를 모두 소문자로 통일:

```typescript
type ComplianceStatus = 'compliant' | 'violation' | 'unverifiable'
```
