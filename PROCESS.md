# AG 성능 비교 분석 프로세스 가이드

## 프로젝트 개요
- **목표**: SQL Server AG 환경에서 NIC 업그레이드(1G→10G) 효과를 CSV 데이터로 분석하고 Notion에 자동 저장
- **GitHub Pages**: https://soldierball-cmd.github.io/ag-analysis/
- **Notion 상위 페이지 ID**: 366dadb5-6b2f-8019-8e65-d0de1d942753
- **로컬 저장소**: D:\12.git\ag-analysis\

---

## 테스트 환경
| 항목 | 내용 |
|---|---|
| SQL Server | 2025 Preview |
| Windows Server | 2022 |
| AG 모드 | SYNCHRONOUS_COMMIT |
| 클러스터 | WSFC |
| Primary | PFDB01 |
| Secondary | PFDB02 |
| 부하 도구 | HammerDB |

---

## 전체 프로세스 (사용자 기준)

### STEP 1: CSV 파일 준비
CSV 파일을 `D:\12.git\ag-analysis\data\` 폴더에 복사

| 파일명 | 설명 |
|---|---|
| 동기모드_1G_NIC.csv | PDH 성능모니터 1G 결과 |
| 동기모드_10G_NIC.csv | PDH 성능모니터 10G 결과 |
| 비동기모드_1G_NIC.csv | PDH 성능모니터 1G 결과 (비동기) |
| 비동기모드_10G_NIC.csv | PDH 성능모니터 10G 결과 (비동기) |
| hadr_sync_commit_monitor.csv | HADR 대기시간 모니터링 결과 |

### STEP 2: 분석 실행 (PowerShell)
```powershell
cd D:\12.git\ag-analysis
python analyze.py 동기모드
# 또는
python analyze.py 비동기모드
```

**자동으로 처리되는 것:**
1. CSV 파싱 + 통계 계산
2. 차트 4개 생성 → `charts\` 폴더 저장
3. git push → GitHub Pages 배포
4. Notion 새 페이지 자동 생성 (차트 이미지 포함)

### STEP 3: 결과 확인
- PowerShell 출력에서 Notion 페이지 URL 확인
- Notion에서 페이지 및 차트 이미지 정상 표시 확인

---

## Claude가 직접 개입하는 경우

분석 결과가 이상하거나 수동으로 Notion을 작성해야 할 때:

### Claude 직접 Notion 작성 절차

1. **NOTION_TEMPLATE.md 읽기**
   - filesystem MCP로 `D:\12.git\ag-analysis\NOTION_TEMPLATE.md` 읽기

2. **CSV 파싱** (bash_tool Python)
   - PDH CSV: CP949 인코딩
   - 주요 컬럼: `% Processor Time`, `Batch Requests/sec`, `Transaction Delay`,
     `Bytes Sent to Replica/sec`
   - HADR CSV: `scenario` 컬럼으로 필터
     - 동기모드_1G_NIC / 동기모드_10G_NIC
     - 컬럼: `avg_wait_per_commit_ms`, `commits_per_sec`, `theoretical_max_tps`
   - NIC 사용률 = Bytes Sent to Replica/sec × 8 / NIC대역폭(bps) × 100
     - 1G = 1,000,000,000 bps
     - 10G = 10,000,000,000 bps

3. **통계 계산만** (차트 생성 금지 — 컨텍스트 폭발)
   - bash_tool에서 숫자만 계산 후 출력

4. **Notion MCP로 새 페이지 생성**
   - `notion-create-pages` 사용
   - parent page_id: `366dadb5-6b2f-8019-8e65-d0de1d942753`
   - NOTION_TEMPLATE.md 구조 그대로 작성

5. **차트는 GitHub Pages URL로 삽입**
   - https://soldierball-cmd.github.io/ag-analysis/charts/chart_01_hadr_wait.png
   - https://soldierball-cmd.github.io/ag-analysis/charts/chart_02_throughput.png
   - https://soldierball-cmd.github.io/ag-analysis/charts/chart_03_batch.png
   - https://soldierball-cmd.github.io/ag-analysis/charts/chart_04_cpu_nic.png

---

## 핵심 제약사항 (반드시 준수)

| 제약 | 이유 |
|---|---|
| NOTION_TOKEN 코드 하드코딩 금지 | GitHub push 차단됨 |
| Claude 서버에서 차트 base64 컨텍스트 적재 금지 | 대화창 컨텍스트 폭발 |
| Claude 서버에서 curl로 GitHub Pages 확인 불가 | 403 반환 (서버 네트워크 정책) |
| api.notion.com Claude 서버에서 직접 호출 불가 | Host not in allowlist |

---

## 파일 구조
```
D:\12.git\ag-analysis\
├── analyze.py          ← 핵심 자동화 스크립트
├── NOTION_TEMPLATE.md  ← Claude 직접 작성 시 참고 템플릿
├── PROCESS.md          ← 이 파일 (전체 프로세스 가이드)
├── index.html          ← GitHub Pages 메인
├── data\               ← CSV 원본 파일
│   ├── 동기모드_1G_NIC.csv
│   ├── 동기모드_10G_NIC.csv
│   ├── 비동기모드_1G_NIC.csv
│   ├── 비동기모드_10G_NIC.csv
│   └── hadr_sync_commit_monitor.csv
└── charts\             ← 생성된 차트 PNG
    ├── chart_01_hadr_wait.png
    ├── chart_02_throughput.png
    ├── chart_03_batch.png
    └── chart_04_cpu_nic.png
```

---

## 실측 결과 (동기모드 기준)

| 지표 | 1G NIC | 10G NIC | 개선율 |
|---|---|---|---|
| HADR avg_wait (ms) | 0.721 | 0.348 | ▼51.8% |
| Theoretical Max TPS | 1,389 | 2,891 | ▲108.1% |
| Commits/sec | 22,873 | 40,463 | ▲76.9% |
| Batch Requests/sec | 1,597 | 3,603 | ▲125.6% |
| CPU 사용률 (%) | 8.2 | 18.3 | — |
| Transaction Delay (ms) | 446 | 1,172 | ▲(병목 아님) |

**핵심 해석:**
- Transaction Delay 증가는 처리량 2배 증가에 따른 복제 큐 증가 — 성능 저하 아님
- HADR 위험 임계값 20ms 대비 모두 정상 (0.721ms / 0.348ms)
- NIC 병목이 HADR_SYNC_COMMIT 대기 증가의 주요 원인이었으며 10G 전환 후 해소

---

## 환경변수 설정 (최초 1회)
```powershell
setx NOTION_TOKEN "your_notion_token_here"
# 설정 후 PowerShell 새 창 열기
```
