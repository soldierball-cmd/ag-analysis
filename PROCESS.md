# SQL Server 성능 비교 분석 — 범용 프로세스 가이드

## 목적
Claude가 어떤 성능 비교 분석 요청이든 **파일명 + 테스트 제목만으로**
스스로 시나리오를 판단하고 Notion 리포트를 자동 생성하기 위한 범용 프레임워크.

과거 분석 결과나 특정 시나리오 값은 무시하고,
**항상 업로드된 CSV 데이터만 기반으로 분석**한다.

---

## 기본 환경 정보
| 항목 | 내용 |
|---|---|
| GitHub Pages | https://soldierball-cmd.github.io/ag-analysis/ |
| 로컬 저장소 | D:\12.git\ag-analysis\ |
| Notion 상위 페이지 ID | 366dadb5-6b2f-8019-8e65-d0de1d942753 |
| Charts Base URL | https://soldierball-cmd.github.io/ag-analysis/charts |

---

## Claude 분석 시작 시 필수 절차

### Step 1: 시나리오 자동 판단
테스트 제목 + 파일명만 보고 스스로 파악:
- A군 vs B군이 무엇인가?
- 핵심 비교 지표가 무엇인가?
- HADR CSV가 있는가? → has_hadr 판별
- 추가 파일(이미지, DMV 등)이 있는가?

### Step 2: CSV 파싱 및 통계 계산
업로드된 CSV만 사용. 과거 수치 절대 사용 금지.

### Step 3: has_hadr 판별 (차트 분기의 핵심)
HADR CSV의 avg_wait_per_commit_ms 평균 확인:
- `has_hadr = True` → avg_wait > 0 (동기모드 등)
- `has_hadr = False` → avg_wait = 0 또는 HADR 데이터 없음 (비동기모드 등)

**has_hadr=False이면 HADR 데이터를 차트/분석에 절대 사용하지 않음**

### Step 4: Notion 새 페이지 생성
- notion-create-pages MCP 사용
- parent page_id: `366dadb5-6b2f-8019-8e65-d0de1d942753`
- 매번 새 페이지 생성 (기존 페이지 수정 금지)
- 실측 CSV 데이터 기반 수치만 사용 (추정값 절대 금지)

---

## 시나리오 자동 판단 기준

파일명 + 테스트 제목으로 Claude가 스스로 판단:

| 시나리오 | 판단 키워드 | 핵심 지표 |
|---|---|---|
| NIC 업그레이드 | 1G / 10G / 25G / NIC / 네트워크 | HADR wait, TPS, NIC 사용률 |
| 동기/비동기 모드 | 동기 / 비동기 / SYNC / ASYNC | HADR wait, TPS, TX Delay |
| SQL Server 버전 | 2019 / 2022 / 2025 / 버전 | Batch/sec, CPU, PLE |
| 스토리지/Disk | SSD / NVMe / HDD / 디스크 | Disk IOPS, Disk Latency |
| CPU/메모리 | CPU / Core / NUMA / Memory / RAM | CPU%, PLE, Batch/sec |
| 기타/범용 | 위 해당 없음 | 유효 지표 자동 감지 |

---

## CSV 파싱 규칙

### PDH 성능모니터 CSV (CP949 인코딩)
컬럼명이 `\\서버명\\카운터경로` 형식 → 키워드로 자동 탐색:
- `% Processor Time` → CPU
- `Batch Requests/sec` → 처리량
- `Transaction Delay` → TX 지연
- `Bytes Sent to Replica/sec` → 복제 전송 (NIC 계산용)
- `Bytes Total/sec` → 전체 NIC 트래픽
- `Disk Transfers/sec` → Disk IOPS
- `Avg. Disk sec/Transfer` → Disk 지연 (×1000 = ms)
- `Available MBytes` → 가용 메모리
- `Page Life Expectancy` → PLE

### NIC 사용률 계산
파일명에서 NIC 대역폭 자동 판단 (1G=1e9 / 10G=10e9 / 25G=25e9):
```
NIC% = Bytes Sent to Replica/sec × 8 / NIC대역폭 × 100
```

### HADR CSV
- `scenario` 컬럼으로 A/B군 필터
- 컬럼: `avg_wait_per_commit_ms` / `commits_per_sec` / `theoretical_max_tps`

---

## 통계 계산 기준

전체 구간 + 안정구간(앞 10% / 뒤 10% 제외) 모두 계산:
- avg / min / max / P95 / stdev

---

## 임계값 기준
| 지표 | 정상 | 주의 | 위험 |
|---|---|---|---|
| HADR avg_wait | < 10ms | 10~20ms | > 20ms |
| NIC 사용률 | < 70% | 70~90% | > 90% |
| CPU 사용률 | < 70% | 70~85% | > 85% |
| Disk Latency | < 5ms | 5~15ms | > 15ms |
| PLE | > 300 | 100~300 | < 100 |

---

## 차트 저장 구조

```
charts/{YYYYMMDD_HHMMSS}_{A파일명}_vs_{B파일명}/
  has_hadr=True:  chart_01_hadr_wait.png / chart_02_tps_commits_batch.png
  has_hadr=False: chart_01_batch_timeseries.png / chart_02_batch_cpu_disk.png
  공통:           chart_03_cpu_nic.png / chart_04_kpi_summary.png
```

- 분석마다 고유 폴더 → 덮어쓰기 없음, 다중 사용자 지원
- Notion URL: `https://soldierball-cmd.github.io/ag-analysis/charts/{SUBDIR}/{파일명}`
- Notion 페이지 생성 시 SUBDIR 포함한 정확한 URL 사용

---

## Notion 페이지 작성 원칙

1. **📌 개요 섹션 필수** — 시나리오별 핵심 인사이트를 첫 번째로 서술
2. 차트 앞에 callout 필수: 왜 이 차트인지 / 읽는 법
3. 수치는 업로드된 CSV 실측 기반만 (추정값 사용 금지)
4. has_hadr=False: "HADR wait = 0ms — ASYNC 모드 정상 동작" 명시
5. Transaction Delay 증가 = 병목 아님 (복제 시나리오 시 명시)
6. 리소스 임계값 표 (최대값, 여유%p) 필수
7. 서버 스펙 이미지 분석 결과 → 🖥️ 서버 스펙 섹션에 표로 포함
8. 모든 내용 한국어로 작성

---

## 서버 스펙 이미지 처리

- Agent UI가 Anthropic API로 이미지를 자동 분석 → 텍스트 추출
- 추출된 텍스트가 sendPrompt의 [서버 스펙 분석 결과] 섹션으로 전달
- Claude는 해당 내용을 Notion 페이지 🖥️ 서버 스펙 섹션에 표로 삽입
- base64 이미지 원본을 Claude 컨텍스트에 올리지 말 것

---

## ⛔ 절대 금지
| 금지 사항 | 이유 |
|---|---|
| 과거 분석 수치를 현재 분석에 사용 | 데이터 조작 |
| 다른 분석의 차트 URL 재사용 | 데이터 왜곡 |
| has_hadr=False에서 HADR 데이터 차트 사용 | 잘못된 분석 |
| 차트 base64를 컨텍스트에 적재 | 대화창 폭발 |
| NOTION_TOKEN 코드 하드코딩 | GitHub push 차단 |
| Claude 서버 → GitHub Pages curl | 403 반환 |
| Claude 서버 → api.notion.com 직접 호출 | 허용목록 미포함 |

---

## 분석 워크플로우 (사용자 안내용)

```
① Agent UI에서 CSV + 이미지 업로드 → 분석 시작
   → Claude가 통계 분석 + Notion 페이지 생성

② PowerShell에서 실행 (차트 생성)
   cd D:\12.git\ag-analysis
   python analyze.py {모드}

③ Notion 페이지 새로고침 → 차트 이미지 표시
```
