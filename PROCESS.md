# SQL Server 성능 비교 분석 — 범용 프로세스 가이드

## 목적
이 가이드는 Claude가 어떤 성능 비교 분석이든 CSV 파일과 테스트 제목만으로
자동으로 분석하고 Notion 리포트를 생성하기 위한 범용 프레임워크입니다.
AG 동기모드 1G vs 10G NIC 비교는 템플릿 케이스이며, 실제로는 어떤 비교 분석에도 적용됩니다.

---

## 기본 환경 정보
| 항목 | 내용 |
|---|---|
| GitHub Pages | https://soldierball-cmd.github.io/ag-analysis/ |
| GitHub 계정 | soldierball-cmd |
| 로컬 저장소 | D:\12.git\ag-analysis\ |
| Notion 상위 페이지 ID | 366dadb5-6b2f-8019-8e65-d0de1d942753 |
| Notion PAT | 환경변수 NOTION_TOKEN (코드 직접 입력 금지) |
| Charts Base URL | https://soldierball-cmd.github.io/ag-analysis/charts |

---

## Claude 분석 시작 시 필수 절차

새 대화에서 분석 요청이 오면 반드시 아래 순서로 처리:

### Step 1: 파일명과 제목으로 시나리오 자동 판단
사용자가 제공한 **테스트 제목**과 **파일명**을 보고 아래를 스스로 파악:
- 무엇 vs 무엇을 비교하는가? (A군 / B군)
- 어떤 지표가 핵심인가? (NIC 비교라면 NIC/HADR 중심, CPU 비교라면 CPU 중심 등)
- HADR CSV가 있는가? (있으면 wait 분석 포함, 없으면 PDH 지표만)
- 추가 파일(이미지, DMV 등)이 있는가?

### Step 2: 파일 읽기
```
filesystem MCP → D:\12.git\ag-analysis\PROCESS.md (이 파일)
filesystem MCP → D:\12.git\ag-analysis\NOTION_TEMPLATE.md
```

### Step 3: CSV 파싱 및 통계 계산 (bash_tool)
→ 아래 "CSV 파싱 규칙" 참조

### Step 4: 시나리오별 핵심 지표 선정
→ 아래 "시나리오 판단 기준" 참조

### Step 5: Notion 새 페이지 생성
→ NOTION_TEMPLATE.md 구조 + 시나리오별 핵심 지표 강조

---

## CSV 파싱 규칙

### PDH 성능모니터 CSV
- 인코딩: **CP949**
- 컬럼명이 `\\서버명\\카운터경로` 형식 → 키워드로 자동 탐색

```python
def gcol(cols, keyword):
    return next((c for c in cols if keyword in c), None)

# 탐색할 키워드 목록
cpu_col     = gcol(cols, '% Processor Time')
batch_col   = gcol(cols, 'Batch Requests/sec')
tx_col      = gcol(cols, 'Transaction Delay')
replica_col = gcol(cols, 'Bytes Sent to Replica/sec')
bytes_col   = gcol(cols, 'Bytes Total/sec')
disk_col    = gcol(cols, 'Disk Transfers/sec')
disk_lat    = gcol(cols, 'Avg. Disk sec/Transfer')
mem_col     = gcol(cols, 'Available MBytes')
ple_col     = gcol(cols, 'Page Life Expectancy')
```

### NIC 사용률 계산
```python
# 파일명 또는 제목에서 NIC 대역폭 자동 판단
# "10G" 포함 → 10,000,000,000 bps
# "1G" 포함 → 1,000,000,000 bps
# "25G" 포함 → 25,000,000,000 bps
nic_pct = bytes_sent_to_replica * 8 / nic_bps * 100  # 10G 환경
nic_pct = bytes_total * 8 / nic_bps * 100              # 1G 환경
```

### HADR 모니터링 CSV
- `scenario` 컬럼으로 필터링
- 컬럼: `avg_wait_per_commit_ms`, `commits_per_sec`, `theoretical_max_tps`
- 파일명/scenario 값에서 A군/B군 자동 판별

### DMV CSV (선택)
- `dm_os_wait_stats` 형태: wait_type / waiting_tasks_count / wait_time_ms
- `dm_hadr_database_replica_states` 형태: log_send_queue_size / redo_queue_size

---

## 통계 계산 기준 (항상 적용)

```python
import statistics

def calc_stats(vals):
    vals = [v for v in vals if v is not None]
    if not vals: return {}
    return {
        'avg':   round(statistics.mean(vals), 3),
        'min':   round(min(vals), 3),
        'max':   round(max(vals), 3),
        'p95':   round(sorted(vals)[int(len(vals)*0.95)], 3),
        'stdev': round(statistics.stdev(vals) if len(vals) > 1 else 0, 3),
    }

# 안정구간: 워밍업(앞 10%) + 쿨다운(뒤 10%) 제외
def stable(rows):
    n = len(rows)
    return rows[int(n*0.1) : int(n*0.9)]
```

---

## 시나리오 판단 기준

Claude는 파일명과 테스트 제목을 보고 아래 기준으로 시나리오를 자동 판단한다.

### 시나리오 A: NIC 업그레이드 비교
**판단 기준:** 파일명에 "1G", "10G", "25G", "NIC", "네트워크" 포함
**핵심 지표:** HADR avg_wait, TPS, NIC 사용률, Batch/sec
**차트 구성:** 차트1(HADR wait 시계열+분포) / 차트2(처리량 3패널) / 차트3(CPU+NIC) / 차트4(KPI 막대)
**강조 포인트:** NIC 포화 여부, HADR wait 감소, Transaction Delay는 병목 아님 명시

### 시나리오 B: 동기/비동기 모드 비교
**판단 기준:** 파일명에 "동기", "비동기", "SYNC", "ASYNC" 포함
**핵심 지표:** HADR avg_wait, TPS, Commits/sec, Transaction Delay
**차트 구성:** 차트1(HADR wait 비교) / 차트2(처리량) / 차트3(CPU+NIC) / 차트4(KPI)
**강조 포인트:** 동기/비동기 간 대기시간 트레이드오프 분석

### 시나리오 C: SQL Server 버전 비교
**판단 기준:** 파일명에 버전명(2019, 2022, 2025 등) 포함
**핵심 지표:** Batch/sec, CPU, Memory(PLE), Disk IOPS
**차트 구성:** 차트1(처리량) / 차트2(CPU+Memory) / 차트3(Disk) / 차트4(KPI)
**강조 포인트:** 버전별 성능 차이, 리소스 효율 비교

### 시나리오 D: 스토리지/Disk 비교
**판단 기준:** 파일명에 "SSD", "NVMe", "HDD", "디스크", "Disk" 포함
**핵심 지표:** Disk IOPS, Disk Latency(ms), PLE, Batch/sec
**차트 구성:** 차트1(Disk IOPS) / 차트2(Disk Latency) / 차트3(PLE+Memory) / 차트4(KPI)
**강조 포인트:** I/O 병목 여부, 스토리지 유형별 지연 차이

### 시나리오 E: CPU/메모리 설정 비교
**판단 기준:** 파일명에 "CPU", "Core", "NUMA", "Memory", "RAM" 포함
**핵심 지표:** CPU 사용률, PLE, Batch/sec, 컨텍스트 스위치
**차트 구성:** 차트1(CPU) / 차트2(Memory/PLE) / 차트3(처리량) / 차트4(KPI)
**강조 포인트:** CPU 병목 여부, 메모리 압박 여부

### 시나리오 F: 기타/범용
**판단 기준:** 위 시나리오에 해당하지 않는 경우
**핵심 지표:** 파일에 있는 모든 유효 지표 자동 감지
**차트 구성:** 데이터에 따라 Claude가 가장 의미있는 4개 차트 자동 선정
**강조 포인트:** 테스트 제목과 목적에 맞게 Claude가 인사이트 도출

---

## 임계값 기준 (공통)
| 지표 | 정상 | 주의 | 위험 |
|---|---|---|---|
| HADR avg_wait | < 10ms | 10~20ms | > 20ms |
| NIC 사용률 | < 70% | 70~90% | > 90% |
| CPU 사용률 | < 70% | 70~85% | > 85% |
| Disk Latency | < 5ms | 5~15ms | > 15ms |
| PLE | > 300 | 100~300 | < 100 |
| Memory 사용률 | < 80% | 80~90% | > 90% |

---

## 차트 구성 원칙 (4종 고정)

차트 파일명은 항상 아래 4개 고정 (Notion URL과 일치):
- `chart_01_hadr_wait.png`
- `chart_02_throughput.png`
- `chart_03_cpu_nic.png`
- `chart_04_kpi_summary.png`

시나리오에 따라 차트 내용은 달라지지만 파일명은 동일하게 유지.

**공통 스타일:**
```python
BG   = "#1a1d27"  # 전체 배경
CARD = "#22263a"  # 플롯 배경
C_A  = "#ff6b6b"  # A군 (레드)
C_B  = "#4e7cff"  # B군 (블루)
GRN  = "#06d6a0"  # 개선율 강조
YEL  = "#ffd166"  # 위험임계값
TXT  = "#e8eaf6"  # 텍스트
TXT2 = "#9fa8c7"  # 보조 텍스트
```

**⚠️ 절대 금지: 차트를 base64로 컨텍스트에 올리는 것 → 대화창 폭발**

---

## Notion 페이지 생성 규칙

- `notion-create-pages` MCP 사용
- parent page_id: `366dadb5-6b2f-8019-8e65-d0de1d942753`
- 매번 **새 페이지** 생성 (기존 페이지 수정 금지)
- NOTION_TEMPLATE.md 구조 기반으로 작성
- 차트는 GitHub Pages URL로 삽입 (git push 완료 후 표시됨)

---

## ⛔ 절대 금지 (차트 삽입 관련)

Notion 페이지에 차트 이미지를 삽입할 때:
1. **반드시 해당 분석 요청의 실제 CSV 데이터로 생성된 차트만 삽입**
2. GitHub Pages에 해당 분석의 차트가 존재하는지 확인 불가한 경우
   → 차트 URL을 추측하거나 다른 분석의 차트를 재사용하지 말 것
   → 사용자에게 아래와 같이 안내할 것:
   "차트는 PC에서 analyze.py 실행 후 git push가 완료되면 Notion에 추가하겠습니다."
3. 기존에 GitHub Pages에 올라가 있는 다른 분석의 차트를 현재 분석에 재사용하는 것은
   **데이터 왜곡** → 어떤 이유로도 절대 금지
4. 차트가 없는 상태에서 Notion 페이지를 먼저 생성하는 것은 허용
   → 차트 섹션에 "차트는 git push 완료 후 추가 예정" 텍스트 삽입

---

## 핵심 제약사항
| 제약 | 이유 |
|---|---|
| NOTION_TOKEN 코드 하드코딩 금지 | GitHub push 차단됨 |
| 차트 base64 컨텍스트 적재 금지 | 대화창 컨텍스트 폭발 |
| Claude 서버 → GitHub Pages curl 불가 | 403 반환 (브라우저는 정상) |
| Claude 서버 → api.notion.com 직접 호출 불가 | Host not in allowlist |
| 다른 분석의 차트 URL 재사용 금지 | 데이터 왜곡 |

---

## 참고: 템플릿 케이스 실측 결과 (AG 동기모드 1G vs 10G)
| 지표 | 1G NIC | 10G NIC | 개선율 |
|---|---|---|---|
| HADR avg_wait (ms) | 0.361 | 0.175 | ▼51.5% |
| Theoretical Max TPS | 1,388 | 2,883 | ▲107.7% |
| Batch Requests/sec | 1,753 | 3,676 | ▲109.7% |
| NIC 사용률 (%) | 32.0 | 4.3 | ▼86.7% |
| CPU 사용률 (%) | 8.9 | 18.6 | — |
| Transaction Delay (ms) | 483 | 1,206 | ▲(병목 아님) |
