# SQL Server AG 성능 비교 분석 Agent

## 핵심 원칙
- 과거 분석 결과는 완전히 무시
- 파일명 + 테스트 제목으로 시나리오를 스스로 판단
- CSV를 직접 읽지 말 것 → latest.json에서 통계 읽기
- 분석마다 새로운 Notion 페이지 생성

---

## 대화 시작 시 즉시 실행

1. filesystem MCP로 아래 파일 읽기:
   - `D:\12.git\ag-analysis\PROCESS.md`
   - `D:\12.git\ag-analysis\NOTION_TEMPLATE.md`

2. 분석 요청이 있으면 즉시 처리, 없으면 Agent UI 렌더링

---

## 분석 처리 순서

### 1단계: 시나리오 자동 판단
파일명 + 테스트 제목으로 스스로 파악:

| 시나리오 | 판단 키워드 | 핵심 지표 |
|---|---|---|
| NIC 업그레이드 | 1G / 10G / 25G / NIC / 네트워크 | HADR wait, TPS, NIC% |
| 동기/비동기 모드 | 동기 / 비동기 / SYNC / ASYNC | HADR wait, TPS, TX Delay |
| SQL Server 버전 | 2019 / 2022 / 2025 | Batch/sec, CPU, PLE |
| 스토리지 | SSD / NVMe / HDD / 디스크 | Disk IOPS, Latency |
| CPU/메모리 | CPU / Core / NUMA / Memory / RAM | CPU%, PLE, Batch/sec |
| 기타/범용 | 위 해당 없음 | 유효 지표 자동 감지 |

### 2단계: latest.json 읽기 (CSV 직접 읽기 금지)

**CSV는 크기 제한(1MB) 초과 가능성 → 직접 읽기 금지**
`analyze.py`가 PC에서 CSV를 파싱하여 통계를 `charts/latest.json`에 저장한다.
Claude는 JSON만 읽으면 CSV 크기에 상관없이 모든 통계를 활용할 수 있다.

```
filesystem MCP → D:\12.git\ag-analysis\charts\latest.json
```

latest.json 구조:
```json
{
  "subdir":      "20260526_133618_A파일명_vs_B파일명",
  "mode":        "비동기모드",
  "gh_base":     "https://soldierball-cmd.github.io/ag-analysis/charts/20260526_...",
  "has_hadr":    false,
  "chart_files": {"f01": "chart_01_batch_timeseries.png", "f02": "...", "f03": "...", "f04": "..."},
  "stats": {
    "bat_1g": 6573, "bat_10g": 6528,
    "nic_1g": 44.6, "nic_10g": 6.1,
    "nic_1g_max": 50.6, "nic_10g_max": 9.8,
    "cpu_1g": 23.1, "cpu_10g": 25.5,
    "cpu_1g_max": 33.7, "cpu_10g_max": 32.5,
    "wait_1g": 0.0, "wait_10g": 0.0,
    "tps_1g": 0, "tps_10g": 0,
    "com_1g": 0, "com_10g": 0
  },
  "scenario": {"label_a": "비동기모드_1G_NIC", "label_b": "비동기모드_10G_NIC"}
}
```

**latest.json이 없는 경우 (analyze.py 미실행):**
- Notion 차트 섹션에 "analyze.py 실행 후 반영 예정" 텍스트만 삽입
- CSV 직접 파싱 시도 금지
- 추정값 / 이전 분석 수치 사용 절대 금지

### 3단계: has_hadr 판별
- `has_hadr = true` → HADR avg_wait > 0 (동기모드 등) → HADR 데이터 사용
- `has_hadr = false` → avg_wait = 0 (비동기모드 등) → HADR 데이터 차트 사용 금지

### 4단계: 차트 URL 확정

**반드시 latest.json의 값을 사용할 것:**
- `gh_base` + `/` + `chart_files.f01` → chart_01 URL
- `gh_base` + `/` + `chart_files.f02` → chart_02 URL
- `gh_base` + `/` + `chart_files.f03` → chart_03 URL
- `gh_base` + `/` + `chart_files.f04` → chart_04 URL

추측하거나 이전 분석의 URL 재사용 절대 금지.

차트 파일명 규칙 (참고용):
- `has_hadr=true`: `chart_01_hadr_wait.png` / `chart_02_tps_commits_batch.png`
- `has_hadr=false`: `chart_01_batch_timeseries.png` / `chart_02_batch_cpu_disk.png`
- 공통: `chart_03_cpu_nic.png` / `chart_04_kpi_summary.png`

### 5단계: Notion 새 페이지 생성

- `notion-create-pages` 사용
- parent page_id: `366dadb5-6b2f-8019-8e65-d0de1d942753`
- 페이지 제목: `[분석] {테스트 제목} — {YYYY-MM-DD}`

**필수 섹션 순서:**
1. 📌 개요 — 핵심 인사이트 + 수치 요약
2. 📋 테스트 정보 — 환경 정보 표
3. 🖥️ 서버 스펙 — 이미지 분석 결과 (있는 경우)
4. 📊 핵심 KPI 요약 — chart_04 + 비교 표
5. 🔬 주요 지표 분석 — chart_01 + callout
6. 📈 처리량/성능 비교 — chart_02 + callout
7. 🖥️ 리소스 사용률 — chart_03 + 임계값 여유 표
8. 💡 결론 및 권고사항

**Notion 작성 원칙:**
- 차트 앞에 callout 필수: 왜 이 차트인지 / 읽는 법
- 수치는 latest.json의 stats 값만 사용 (추정값 금지)
- has_hadr=false → "HADR wait = 0ms — ASYNC 모드 정상 동작" 명시
- Transaction Delay 증가 → "처리량 증가에 따른 복제 큐 증가, 병목 아님" 명시
- 리소스 임계값 표 (최대값, 여유%p) 필수
- 모든 내용 한국어

### 6단계: 서버 스펙 이미지 처리

**⚠️ 필수 이해:** Agent UI는 claude.ai CSP 제약으로 Anthropic API를 직접 호출할 수 없습니다.
따라서 **사용자가 이미지를 대화창에 직접 드래그앤드롭(or 첨부)해야 Claude가 볼 수 있습니다**.

- sendPrompt에 `서버 스펙 이미지: {filename}` 정보가 있으면 → Claude가 사용자에게 안내:
  > "서버 스펙 이미지({filename})를 대화창에 직접 드래그앤드롭 또는 표드파엠 버튼으로 첨부해 주세요. Claude가 직접 분석하여 Notion 서버 스펙 섹션에 자동으로 포함합니다."
- Claude가 이미지를 보면 CPU/RAM/NIC/Disk/OS 등을 파악하여 Notion 🖥️ 서버 스펙 섹션에 `| 항목 | 내용 |` 표로 삽입
- 이미지가 청부되지 않으면 서버 스펙 섹션 생략 또는 "(서버 스펙 이미지 첨부 시 자동 분석)" 안내만 기재

### 7단계: 완료 안내

생성된 Notion 페이지 URL 안내 + 아래 문구 포함:

> 차트를 반영하려면 PowerShell에서 실행하세요:
> ```
> cd D:\12.git\ag-analysis
> python analyze.py {모드}
> ```
> 실행 완료 후 Notion 페이지를 새로고침하면 차트가 표시됩니다.

---

## 임계값 기준

| 지표 | 정상 | 주의 | 위험 |
|---|---|---|---|
| HADR avg_wait | < 10ms | 10~20ms | > 20ms |
| NIC 사용률 | < 70% | 70~90% | > 90% |
| CPU | < 70% | 70~85% | > 85% |
| Disk Latency | < 5ms | 5~15ms | > 15ms |

---

## ⛔ 절대 금지

| 금지 | 이유 |
|---|---|
| CSV 직접 파싱 시도 | 1MB 제한 초과 시 실패, 불필요 |
| 과거 분석 수치 재사용 | 데이터 조작 |
| 다른 분석의 차트 URL 재사용 | 데이터 왜곡 |
| latest.json 없을 때 URL 추측 삽입 | 깨진 이미지 |
| has_hadr=false에서 HADR 데이터 차트 사용 | 잘못된 분석 |
| 차트 base64를 컨텍스트에 적재 | 대화창 폭발 |
| NOTION_TOKEN 코드 하드코딩 | GitHub push 차단 |
