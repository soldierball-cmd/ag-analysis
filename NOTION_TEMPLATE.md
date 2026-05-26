# Notion 페이지 작성 템플릿 (AG 성능 비교 분석)

## 기본 정보
- 상위 페이지 ID: 366dadb5-6b2f-8019-8e65-d0de1d942753
- Notion PAT: 환경변수 NOTION_TOKEN 사용 (코드에 직접 입력 금지)
- GitHub Charts URL: https://soldierball-cmd.github.io/ag-analysis/charts/
- 차트 파일명: chart_01_hadr_wait.png / chart_02_throughput.png / chart_03_batch.png / chart_04_cpu_nic.png

## 페이지 제목 형식
[AG 비교분석] {테스트 제목} — {YYYY-MM-DD}

## 페이지 아이콘
📊

---

## 통계 계산 기준 (반드시 준수)
- 전체 구간 통계: avg, min, max, P95, stdev
- 안정구간 통계: 워밍업 10% + 쿨다운 10% 제외 (전체의 10%~90% 구간)
- 개선율 계산:
  - 낮을수록 좋은 지표(wait, NIC): (A값 - B값) / A값 × 100
  - 높을수록 좋은 지표(TPS 등): (B값 - A값) / A값 × 100

---

## 페이지 본문 구조 (풍부한 버전)

### 섹션 1: 테스트 정보

## 📋 테스트 정보

| 항목 | 내용 |
|---|---|
| 테스트 제목 | {title} |
| 테스트 목적 | {purpose} |
| SQL Server | {sql_ver} |
| Windows Server | {win_ver} |
| AG 모드 | {ag_mode} |
| 클러스터 | {cluster} |
| Primary / Secondary | {primary} / {secondary} |
| 테스트 도구 | {tool} |
| 분석 방법 | 전체 구간 + 안정구간(워밍업 10% 제외) 통계 분석 |
| 분석 일시 | {YYYY-MM-DD} |

---

### 섹션 2: 핵심 지표 비교 (안정구간 평균)

## 📊 핵심 지표 비교 (안정구간 평균)

| 지표 | A ({label_a}) | B ({label_b}) | 개선율 | 평가 |
|---|---|---|---|---|
| HADR avg_wait — 평균 (ms) | {wait_a_avg} | {wait_b_avg} | ▼{w_imp}% | ✅ |
| HADR avg_wait — P95 (ms) | {wait_a_p95} | {wait_b_p95} | ▼{w_p95_imp}% | ✅ |
| HADR avg_wait — 최대 (ms) | {wait_a_max} | {wait_b_max} | ▼{w_max_imp}% | ✅ |
| Theoretical Max TPS — 평균 | {tps_a_avg} | {tps_b_avg} | ▲{t_imp}% | ✅ |
| Theoretical Max TPS — P95 | {tps_a_p95} | {tps_b_p95} | ▲{t_p95_imp}% | ✅ |
| Commits/sec — 평균 | {com_a_avg} | {com_b_avg} | ▲{c_imp}% | ✅ |
| Batch Requests/sec — 평균 | {bat_a_avg} | {bat_b_avg} | ▲{b_imp}% | ✅ |
| CPU 사용률 — 평균 (%) | {cpu_a_avg} | {cpu_b_avg} | — | ✅ |
| CPU 사용률 — P95 (%) | {cpu_a_p95} | {cpu_b_p95} | — | ✅ |
| NIC 사용률 — 평균 (%) | {nic_a_avg} | {nic_b_avg} | ▼{nic_imp}% | ✅ |
| NIC 사용률 — 최대 (%) | {nic_a_max} | {nic_b_max} | ▼{nic_max_imp}% | ✅ |
| Disk IOPS — 평균 | {disk_a_avg} | {disk_b_avg} | ▲{d_imp}% | ✅ |
| Transaction Delay — 평균 (ms) | {tx_a_avg} | {tx_b_avg} | ▲(병목 아님) | ℹ️ |
| Transaction Delay — P95 (ms) | {tx_a_p95} | {tx_b_p95} | ▲(병목 아님) | ℹ️ |

---

### 섹션 3: 심층 분석

## 🔬 심층 분석

### 1. HADR 대기시간 안정성 분석

| 구분 | A ({label_a}) | B ({label_b}) | 의미 |
|---|---|---|---|
| 평균 wait | {wait_a_avg}ms | {wait_b_avg}ms | B가 {w_imp}% 더 낮은 대기시간 |
| P95 wait | {wait_a_p95}ms | {wait_b_p95}ms | 부하 집중 시에도 B가 안정적 |
| 표준편차 | {wait_a_stdev} | {wait_b_stdev} | B의 변동성이 더 낮음 |
| 최대값 | {wait_a_max}ms | {wait_b_max}ms | B에서 최악의 순간도 더 낮음 |
| 위험임계값(20ms) 초과 | {over_20ms_a}초 | {over_20ms_b}초 | — |

> **해석**: {hadr_interpretation}

### 2. 처리량 분석

| 구분 | A ({label_a}) | B ({label_b}) | 비고 |
|---|---|---|---|
| TPS 평균 | {tps_a_avg} | {tps_b_avg} | ▲{t_imp}% |
| TPS 표준편차 | {tps_a_stdev} | {tps_b_stdev} | 변동성 비교 |
| TPS 최솟값 | {tps_a_min} | {tps_b_min} | B 최솟값도 A 최솟값 상회 여부 |
| Batch/sec 평균 | {bat_a_avg} | {bat_b_avg} | ▲{b_imp}% |
| Batch/sec 표준편차 | {bat_a_stdev} | {bat_b_stdev} | 변동성 비교 |

> **해석**: {throughput_interpretation}

### 3. NIC 병목 해소 분석

| 구분 | A ({label_a}) | B ({label_b}) |
|---|---|---|
| NIC 사용률 평균 | {nic_a_avg}% | {nic_b_avg}% |
| NIC 사용률 최대 | {nic_a_max}% | {nic_b_max}% |
| NIC 사용률 표준편차 | {nic_a_stdev}% | {nic_b_stdev}% |
| 임계값(70%) 여유 | {nic_a_margin}%p | {nic_b_margin}%p |

> **해석**: {nic_interpretation}

### 4. CPU 리소스 분석

| 구분 | A ({label_a}) | B ({label_b}) |
|---|---|---|
| CPU 평균 | {cpu_a_avg}% | {cpu_b_avg}% |
| CPU P95 | {cpu_a_p95}% | {cpu_b_p95}% |
| CPU 최대 | {cpu_a_max}% | {cpu_b_max}% |
| 임계값(85%) 여유 | {cpu_a_margin}%p | {cpu_b_margin}%p |

> **해석**: {cpu_interpretation}

### 5. Transaction Delay 해석

| 구분 | A ({label_a}) | B ({label_b}) | 해석 |
|---|---|---|---|
| TX Delay 평균 | {tx_a_avg}ms | {tx_b_avg}ms | 처리량 증가에 비례한 정상 상승 |
| TX Delay P95 | {tx_a_p95}ms | {tx_b_p95}ms | 병목 지표 아님 |
| TX Delay 최대 | {tx_a_max}ms | {tx_b_max}ms | 복제 큐 증가 반영 |

> ⚠️ **주의**: Transaction Delay 증가는 성능 저하가 아닙니다. 처리량이 증가하면서 복제 큐가 늘어난 것으로, HADR wait이 오히려 감소한 점이 이를 증명합니다.

---

### 섹션 4: 리소스 임계값 요약

## ✅ 리소스 임계값 요약

| 리소스 | 임계값 | A 최대 | B 최대 | A 상태 | B 상태 |
|---|---|---|---|---|---|
| HADR wait | 20ms | {wait_a_max}ms | {wait_b_max}ms | ✅ 정상 | ✅ 정상 |
| NIC 사용률 | 70% | {nic_a_max}% | {nic_b_max}% | {nic_a_status} | {nic_b_status} |
| CPU | 85% | {cpu_a_max}% | {cpu_b_max}% | ✅ 정상 | ✅ 정상 |

---

### 섹션 5: 차트 이미지

## 📈 차트

![HADR Wait](https://soldierball-cmd.github.io/ag-analysis/charts/chart_01_hadr_wait.png)

![Throughput](https://soldierball-cmd.github.io/ag-analysis/charts/chart_02_throughput.png)

![Batch Requests/sec](https://soldierball-cmd.github.io/ag-analysis/charts/chart_03_batch.png)

![CPU & NIC Usage](https://soldierball-cmd.github.io/ag-analysis/charts/chart_04_cpu_nic.png)

---

### 섹션 6: 결론 및 권고사항

## 💡 결론 및 권고사항

### 핵심 요약
{conclusion_summary}

### 추가 최적화 권고

| 항목 | 내용 | 기대 효과 |
|---|---|---|
| Jumbo Frame (MTU 9000) | 대용량 패킷 처리 효율화 | 네트워크 오버헤드 감소 |
| RSS/VMQ 활성화 | NIC 멀티코어 분산 처리 | NIC 처리 효율 향상 |
| HADR 전용 NIC 분리 | 복제 트래픽 격리 | 일반 트래픽과 간섭 제거 |

### 다음 단계 테스트 권고
- 비동기 모드 비교 분석 (현재 데이터 준비됨)
- 25G NIC 업그레이드 효과 측정
- 부하 증가 테스트: 현재 대비 2x, 3x 부하에서 NIC 병목 재현 가능성 확인

---

## Claude가 직접 Notion 작성 시 절차

1. CSV 파싱 (bash_tool Python):
   - PDH CSV: CP949 인코딩
     컬럼: % Processor Time, Batch Requests/sec, Disk Transfers/sec,
           Transaction Delay, Bytes Sent to Replica/sec
   - HADR CSV: scenario 컬럼으로 필터
     컬럼: avg_wait_per_commit_ms, commits_per_sec, theoretical_max_tps
   - NIC 사용률 = Bytes Sent to Replica/sec × 8 / NIC대역폭(bps) × 100

2. 통계 계산 (전체 + 안정구간):
   - 전체: avg, min, max, P95, stdev
   - 안정구간: rows[int(n*0.1):int(n*0.9)] 슬라이싱
   - statistics 모듈 사용

3. 인사이트 도출:
   - HADR wait 변동성(stdev) 비교
   - TPS 최솟값 비교 (B 최솟값 > A 최솟값 여부)
   - NIC 임계값 여유 계산
   - Transaction Delay 증가 = 병목 아님 명시

4. Notion MCP로 새 페이지 생성:
   - notion-create-pages 사용
   - parent: page_id = 366dadb5-6b2f-8019-8e65-d0de1d942753
   - 위 본문 구조 그대로 작성

5. 주의사항:
   - 차트 base64를 컨텍스트에 올리지 말 것 (컨텍스트 폭발)
   - 차트는 GitHub Pages URL로 삽입
   - NOTION_TOKEN 코드 직접 입력 금지
