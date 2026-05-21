# Notion 페이지 작성 템플릿 (AG 성능 비교 분석)

## 기본 정보
- 상위 페이지 ID: 366dadb5-6b2f-8019-8e65-d0de1d942753
- Notion PAT: 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
- GitHub Charts URL: https://soldierball-cmd.github.io/ag-analysis/charts/
- 차트 파일명: chart_01_hadr_wait.png / chart_02_throughput.png / chart_03_batch.png / chart_04_cpu_nic.png

## 페이지 제목 형식
[AG 비교분석] NIC 업그레이드 효과 검증({모드}) — {YYYY-MM-DD}
예) [AG 비교분석] NIC 업그레이드 효과 검증(동기모드) — 2026-05-21

## 페이지 아이콘
📊

---

## 페이지 본문 구조

### 섹션 1: 테스트 환경

## 📋 테스트 환경

| 항목 | 내용 |
|---|---|
| SQL Server | 2025 Preview |
| Windows Server | 2022 |
| AG 동기 모드 | SYNCHRONOUS_COMMIT |
| 클러스터 | WSFC |
| Primary / Secondary | PFDB01 / PFDB02 |
| 테스트 도구 | HammerDB |
| 분석 모드 | {모드} |
| 분석 일시 | {YYYY-MM-DD} |

---

### 섹션 2: 성능 지표 비교표
※ 값은 CSV 실측 평균값 사용. 개선율 계산식:
- 낮을수록 좋은 지표(wait): (1G값 - 10G값) / 1G값 × 100
- 높을수록 좋은 지표(TPS 등): (10G값 - 1G값) / 1G값 × 100

## 📊 1G vs 10G 성능 지표 비교

| 지표 | 1G NIC | 10G NIC | 개선율 | 평가 |
|---|---|---|---|---|
| HADR avg_wait (ms) | {wait_1g:.3f} | {wait_10g:.3f} | ▼{w_imp}% | ✅ |
| Theoretical Max TPS | {tps_1g:.0f} | {tps_10g:.0f} | ▲{t_imp}% | ✅ |
| Commits/sec | {commits_1g:.0f} | {commits_10g:.0f} | ▲{c_imp}% | ✅ |
| Batch Requests/sec | {batch_1g:.0f} | {batch_10g:.0f} | ▲{b_imp}% | ✅ |
| CPU 사용률 (%) | {cpu_1g:.1f} | {cpu_10g:.1f} | — | ✅ |
| Transaction Delay (ms) | {tx_1g:.0f} | {tx_10g:.0f} | ▲(병목 아님) | ℹ️ |

---

### 섹션 3: NIC 병목 분석
※ HADR 위험 임계값 = 20ms. Transaction Delay 증가는 병목이 아님을 반드시 명시.

## 🔍 NIC 병목 분석

10G NIC 업그레이드는 SYNCHRONOUS_COMMIT 환경에서 유의미한 성능 개선 효과를 보였습니다.

- **HADR avg_wait**: {wait_1g}ms → {wait_10g}ms (**{w_imp}% 개선**, 위험임계값 20ms 대비 정상)
- **TPS**: {tps_1g} → {tps_10g} (**{t_imp}% 향상**)
- **Transaction Delay 증가({tx_1g}ms → {tx_10g}ms)** 는 처리량 2배 증가에 따른 복제 큐 증가이며, 성능 저하가 아님
- 1G 환경에서 NIC 포화가 HADR_SYNC_COMMIT 대기 증가의 주요 원인이었으며, 10G 전환 후 NIC 사용률 5% 미만으로 해소됨

---

### 섹션 4: 기타 리소스 정상 확인

## ✅ 기타 리소스 정상 확인

- **CPU**: {cpu_1g}% → {cpu_10g}% (임계값 85% 대비 충분한 여유, 처리량 증가에 따른 정상 상승)
- **NIC**: 10G 전환 후 5% 미만 (임계값 70% 대비 충분한 여유)
- **Disk**: 정상 범위
- 병목은 NIC에 집중되어 있었으며, 10G 업그레이드로 완전히 해소됨

---

### 섹션 5: 차트 이미지
※ git push 완료 후 GitHub Pages URL로 삽입. 이미지 블록 4개.

## 📈 차트

![HADR Wait](https://soldierball-cmd.github.io/ag-analysis/charts/chart_01_hadr_wait.png)

![Throughput](https://soldierball-cmd.github.io/ag-analysis/charts/chart_02_throughput.png)

![Batch Requests/sec](https://soldierball-cmd.github.io/ag-analysis/charts/chart_03_batch.png)

![CPU & NIC Usage](https://soldierball-cmd.github.io/ag-analysis/charts/chart_04_cpu_nic.png)

---

### 섹션 6: 결론 및 권고사항

## 💡 결론 및 권고사항

**핵심 요약**: 1G → 10G NIC 업그레이드로 HADR 대기시간 {w_imp}% 감소, TPS {t_imp}% 향상

**추가 최적화 권고**:
- Jumbo Frame(MTU 9000) 설정
- RSS/VMQ 활성화
- HADR 전용 NIC 분리

**다음 단계 테스트 권고**:
- 비동기 모드 비교 분석
- 25G NIC 업그레이드 효과 측정

---

## Claude가 직접 Notion 작성 시 절차

1. CSV 파일 위치 확인: D:\12.git\ag-analysis\data\
   - 동기모드_1G_NIC.csv / 동기모드_10G_NIC.csv
   - 비동기모드_1G_NIC.csv / 비동기모드_10G_NIC.csv
   - hadr_sync_commit_monitor.csv

2. 파일 읽기: filesystem MCP로 읽거나, 사용자가 업로드한 파일 사용

3. 통계 계산 (bash_tool Python):
   - PDH CSV: CP949 인코딩, 컬럼에서 "% Processor Time", "Batch Requests/sec",
     "Disk Transfers/sec", "Transaction Delay", "Bytes Sent to Replica/sec" 추출
   - HADR CSV: scenario 컬럼으로 필터 (동기모드_1G_NIC / 동기모드_10G_NIC)
     avg_wait_per_commit_ms, commits_per_sec, theoretical_max_tps 사용
   - NIC 사용률 = Bytes Sent to Replica/sec × 8 / NIC대역폭(bps) × 100
     1G = 1,000,000,000bps / 10G = 10,000,000,000bps

4. Notion MCP로 새 페이지 생성:
   - notion-create-pages 사용
   - parent: page_id = 366dadb5-6b2f-8019-8e65-d0de1d942753
   - 위 본문 구조 그대로 작성 ({변수} 자리에 실측값 대입)

5. 주의사항:
   - Claude 서버에서 차트 생성 후 base64로 컨텍스트에 올리면 안 됨 (컨텍스트 폭발)
   - 차트는 PC에서 analyze.py 실행 후 git push → GitHub Pages URL 사용
   - analyze.py 실행: python analyze.py 동기모드
