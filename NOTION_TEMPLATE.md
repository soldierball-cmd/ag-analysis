# Notion 페이지 작성 템플릿 — 범용 성능 비교 분석

## 기본 정보
- 상위 페이지 ID: 366dadb5-6b2f-8019-8e65-d0de1d942753
- Charts Base URL: https://soldierball-cmd.github.io/ag-analysis/charts
- 차트 파일명 4종 고정:
  - chart_01_main.png      (시나리오 자동 전환: HADR wait 또는 Batch/sec)
  - chart_02_throughput.png
  - chart_03_cpu_nic.png
  - chart_04_kpi_summary.png

---

## 페이지 제목 형식
[분석] {테스트 제목} — {YYYY-MM-DD}
예) [분석] AG 동기모드 NIC 1G vs 10G 성능 비교 — 2026-05-22

---

## 페이지 본문 구조

### 섹션 1: 테스트 정보
```markdown
## 📋 테스트 정보

| 항목 | 내용 |
|---|---|
| 테스트 제목 | {title} |
| 테스트 목적 | {purpose} |
| 비교 대상 A | {label_a} |
| 비교 대상 B | {label_b} |
| 분석 시나리오 | {scenario_type} |
| 분석 방법 | 전체 구간 + 안정구간(10%~90%) 통계 분석 |
| 분석 일시 | {YYYY-MM-DD} |
| 추가 파일 | {extra_files 또는 없음} |
```

---

### 섹션 2: 핵심 KPI 요약
```markdown
## 📊 핵심 KPI 요약

> **왜 이 차트를 넣었나?**
> {시나리오에 따라 Claude가 작성 — 예: "4개의 핵심 지표를 막대 그래프로 한눈에 비교합니다.
> 각 막대 위 퍼센트는 A 대비 B의 개선율이며, 노란 점선은 위험 임계값입니다."}
>
> **차트 읽는 법:**
> {시나리오에 따라 Claude가 작성 — 예: "막대가 높을수록 처리량이 많고, 낮을수록
> 대기시간이 짧습니다. 개선율이 클수록 효과가 큰 항목입니다."}

![KPI Summary](https://soldierball-cmd.github.io/ag-analysis/charts/chart_04_kpi_summary.png)

| 지표 | A ({label_a}) | B ({label_b}) | 개선율 | 평가 |
|---|---|---|---|---|
| {지표1} — 평균 | {val_a} | {val_b} | {imp}% | {emoji} |
| {지표2} — P95  | {val_a} | {val_b} | {imp}% | {emoji} |
| ... | ... | ... | ... | ... |
```

※ 지표 목록은 시나리오에 따라 Claude가 자동 선정
※ 개선율 계산: 낮을수록 좋은 지표(wait, latency) → ▼, 높을수록 좋은 지표(TPS) → ▲

---

### 섹션 3: 시나리오별 주요 차트 (차트1)
```markdown
## {시나리오별 제목 — 예: 🔬 HADR 대기시간 심층 분석}

> **왜 이 차트를 넣었나?**
> {Claude가 시나리오에 맞게 작성}
>
> **차트 읽는 법:**
> {Claude가 시나리오에 맞게 작성}

![Chart 01](https://soldierball-cmd.github.io/ag-analysis/charts/chart_01_main.png)

| 구분 | A ({label_a}) | B ({label_b}) | 의미 |
|---|---|---|---|
| 평균 | {avg_a} | {avg_b} | {interpretation} |
| P95  | {p95_a} | {p95_b} | 부하 집중 시 안정성 |
| 표준편차 | {stdev_a} | {stdev_b} | 변동성 비교 |
| 최대값 | {max_a} | {max_b} | 최악 순간 비교 |

> **해석:** {Claude가 데이터 기반으로 작성}
```

---

### 섹션 4: 처리량 비교 (차트2)
```markdown
## 📈 처리량 비교

> **왜 이 차트를 넣었나?**
> {Claude가 시나리오에 맞게 작성}
>
> **차트 읽는 법:**
> {Claude가 시나리오에 맞게 작성}

![Throughput](https://soldierball-cmd.github.io/ag-analysis/charts/chart_02_throughput.png)

| 구분 | A ({label_a}) | B ({label_b}) | 개선율 |
|---|---|---|---|
| {지표1} 평균 | {val_a} | {val_b} | {imp}% |
| {지표1} 최솟값 | {min_a} | {min_b} | B 최솟값 > A 여부 |
| {지표1} 표준편차 | {stdev_a} | {stdev_b} | 변동성 비교 |

> **해석:** {Claude가 데이터 기반으로 작성}
```

---

### 섹션 5: 리소스 사용률 (차트3)
```markdown
## 🖥️ 리소스 사용률 분석

> **왜 이 차트를 넣었나?**
> {Claude가 시나리오에 맞게 작성 — 처리량 증가 시 리소스 여유 확인 목적}
>
> **차트 읽는 법:**
> {Claude가 시나리오에 맞게 작성 — 노란 점선이 위험 임계값}

![CPU & NIC](https://soldierball-cmd.github.io/ag-analysis/charts/chart_03_cpu_nic.png)

| 리소스 | 임계값 | A 최대 | B 최대 | A 여유 | B 여유 | 상태 |
|---|---|---|---|---|---|---|
| CPU | 85% | {cpu_a_max}% | {cpu_b_max}% | {margin_a}%p | {margin_b}%p | ✅/⚠️/🔴 |
| NIC 사용률 | 70% | {nic_a_max}% | {nic_b_max}% | {margin_a}%p | {margin_b}%p | ✅/⚠️/🔴 |
| {기타 리소스} | {threshold} | {val_a} | {val_b} | {margin} | {margin} | ✅/⚠️/🔴 |

> **해석:** {Claude가 데이터 기반으로 작성}
```

---

### 섹션 6: 심층 분석 (시나리오별 추가 항목)
```markdown
## 🔍 심층 분석

{시나리오에 따라 Claude가 추가 항목 구성}

예시 — NIC 비교 시:
### Transaction Delay 해석
> ⚠️ TX Delay 증가는 성능 저하가 아닙니다.
> 처리량 증가에 따른 복제 큐 증가이며, HADR wait 감소가 이를 증명합니다.

예시 — DMV 데이터 있을 시:
### Wait Stats 비교 (dm_os_wait_stats)
| wait_type | A 누적 | B 누적 | 변화 |

예시 — 이미지 파일 있을 시:
### 서버 스펙 / 환경 정보
{이미지에서 확인된 정보 텍스트로 정리}
```

---

### 섹션 7: 결론 및 권고사항
```markdown
## 💡 결론 및 권고사항

### 핵심 요약
{Claude가 실측값 기반으로 작성 — 수치 포함 필수}
예) "A 대비 B에서 {지표1} {X}% 개선, {지표2} {Y}% 향상 확인"

### 리소스 임계값 최종 확인
| 리소스 | 임계값 | A 상태 | B 상태 |
|---|---|---|---|
| {지표} | {threshold} | ✅/⚠️/🔴 | ✅/⚠️/🔴 |

### 추가 최적화 권고
{시나리오에 맞는 권고사항 — Claude가 작성}
예) NIC 비교: Jumbo Frame, RSS/VMQ, HADR 전용 NIC 분리
예) Disk 비교: RAID 구성 최적화, IO 스케줄러 설정
예) 버전 비교: 신기능 활성화 검토, 호환성 확인

### 다음 단계 테스트 권고
{시나리오에 맞는 후속 테스트 — Claude가 작성}
```

---

## Claude 작성 원칙 (반드시 준수)

1. **시나리오 자동 판단**: 파일명 + 제목으로 어떤 분석인지 스스로 파악
2. **callout(>) 블록 필수**: 모든 차트 앞에 "왜 이 차트인지" + "읽는 법" 설명
3. **통계는 실측 기반**: avg/P95/max/stdev 모두 계산, 추정값 사용 금지
4. **전체 + 안정구간 분리**: 워밍업 10% 제외한 안정구간 별도 분석
5. **인사이트 도출**: 단순 수치 나열이 아닌 의미 해석 포함
6. **TX Delay 처리**: NIC/복제 관련 시나리오에서는 병목 아님 반드시 명시
7. **차트 base64 금지**: 컨텍스트에 올리지 말고 GitHub Pages URL 사용
8. **새 페이지 생성**: 기존 페이지 수정 금지, 매번 새로 생성
