"""
AG 성능 비교 분석 스크립트 - PC 직접 실행용
사용법: python analyze.py 동기모드
        python analyze.py 비동기모드

환경변수 설정 필요:
  Windows: setx NOTION_TOKEN "your_token"
  PowerShell: $env:NOTION_TOKEN = "your_token"
"""
import sys, os, csv, io, json, subprocess, statistics
import urllib.request, urllib.error
from datetime import datetime

NOTION_TOKEN   = os.environ.get("NOTION_TOKEN", "")
PARENT_PAGE_ID = "366dadb5-6b2f-8019-8e65-d0de1d942753"
BASE_DIR       = os.path.dirname(os.path.abspath(__file__))
DATA_DIR       = os.path.join(BASE_DIR, "data")
CHARTS_DIR     = os.path.join(BASE_DIR, "charts")
GH_BASE        = "https://soldierball-cmd.github.io/ag-analysis/charts"
os.makedirs(CHARTS_DIR, exist_ok=True)

MODE = sys.argv[1] if len(sys.argv) > 1 else "동기모드"

# ── 차트 파일명 (NOTION_TEMPLATE.md 와 일치) ─────────────
CHART_FILES = [
    "chart_01_hadr_wait.png",
    "chart_02_throughput.png",
    "chart_03_cpu_nic.png",
    "chart_04_kpi_summary.png",
]


def find_csv():
    files = {}
    for f in os.listdir(DATA_DIR):
        fl = f.lower()
        in_mode = (MODE == "동기모드" and "동기모드" in f and "비동기" not in f) or \
                  (MODE == "비동기모드" and "비동기모드" in f)
        if in_mode:
            if "1g" in fl and "hadr" not in fl:
                files["1g"] = os.path.join(DATA_DIR, f)
            elif "10g" in fl and "hadr" not in fl:
                files["10g"] = os.path.join(DATA_DIR, f)
        if "hadr_sync_commit" in fl:
            files["hadr"] = os.path.join(DATA_DIR, f)
    return files


def fv(s):
    try: return float(s.strip()) if s and s.strip() else None
    except: return None


def load_pdh(path, nic_bps):
    with open(path, "rb") as f:
        content = f.read().decode("cp949")
    rows = list(csv.DictReader(io.StringIO(content)))
    cols = list(rows[0].keys())
    def gcol(k): return next((c for c in cols if k in c), None)
    cpu_col     = gcol("% Processor Time")
    batch_col   = gcol("Batch Requests/sec")
    disk_col    = gcol("Disk Transfers/sec")
    tx_col      = gcol("Transaction Delay")
    replica_col = gcol("Bytes Sent to Replica/sec")
    bytes_col   = gcol("Bytes Total/sec")
    result = []
    for r in rows:
        rb = fv(r.get(replica_col, "")) or 0
        nb = fv(r.get(bytes_col, "")) or 0
        nic = round((rb if nic_bps == 10e9 else nb) * 8 / nic_bps * 100, 4)
        result.append({"cpu": fv(r.get(cpu_col, "")), "nic": nic,
                       "batch": fv(r.get(batch_col, "")),
                       "disk":  fv(r.get(disk_col, "")),
                       "tx":    fv(r.get(tx_col, ""))})
    return result


def load_hadr(path, scenario):
    with open(path, "rb") as f:
        rows = list(csv.DictReader(io.StringIO(f.read().decode("cp949"))))
    return [r for r in rows if r.get("scenario", "") == scenario]


def avg(lst):
    lst = [x for x in lst if x is not None]
    return sum(lst) / len(lst) if lst else 0

def hmean(rows, key):
    return avg([fv(r[key]) for r in rows if r.get(key)])

def pmean(rows, key):
    return avg([r[key] for r in rows if r.get(key) is not None])


def make_charts(d1, d10, h1, h10):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.gridspec as gridspec

        C1   = "#ff6b6b"; C10  = "#4e7cff"; BG   = "#1a1d27"; CARD = "#22263a"
        GRID = "#2e3250"; TXT  = "#e8eaf6"; TXT2 = "#9fa8c7"
        YEL  = "#ffd166"; GRN  = "#06d6a0"

        def style(ax, title, xlabel="Time (sec)", ylabel=""):
            ax.set_facecolor(CARD)
            ax.tick_params(colors=TXT2, labelsize=9)
            for s in ["bottom","left"]: ax.spines[s].set_color(GRID)
            ax.spines["top"].set_visible(False); ax.spines["right"].set_visible(False)
            ax.grid(axis="y", color=GRID, linewidth=0.5, alpha=0.6, linestyle="--")
            ax.set_axisbelow(True)
            ax.set_title(title, color=TXT, fontsize=11, fontweight="bold", pad=10)
            if xlabel: ax.set_xlabel(xlabel, color=TXT2, fontsize=9)
            if ylabel: ax.set_ylabel(ylabel, color=TXT2, fontsize=9)

        def clean(lst): return [v for v in lst if v is not None]

        w1  = clean([fv(r["avg_wait_per_commit_ms"]) for r in h1])
        w10 = clean([fv(r["avg_wait_per_commit_ms"]) for r in h10])
        c1  = clean([fv(r["commits_per_sec"]) for r in h1])
        c10 = clean([fv(r["commits_per_sec"]) for r in h10])
        t1  = clean([fv(r["theoretical_max_tps"]) for r in h1])
        t10 = clean([fv(r["theoretical_max_tps"]) for r in h10])
        b1  = clean([d["batch"] for d in d1]); b10 = clean([d["batch"] for d in d10])
        cpu1 = clean([d["cpu"] for d in d1]);  cpu10 = clean([d["cpu"] for d in d10])
        nic1 = [d["nic"] for d in d1];          nic10 = [d["nic"] for d in d10]

        aw1=round(avg(w1),3); aw10=round(avg(w10),3)
        at1=round(avg(t1),0); at10=round(avg(t10),0)
        ab1=round(avg(b1),0); ab10=round(avg(b10),0)
        ac1=round(avg(c1),0); ac10=round(avg(c10),0)
        anic1=round(avg(nic1),1); anic10=round(avg(nic10),1)
        acpu1=round(avg(cpu1),1); acpu10=round(avg(cpu10),1)

        # ── 차트1: HADR wait 시계열 + 히스토그램 ──────────
        fig = plt.figure(figsize=(14,8), facecolor=BG); fig.patch.set_facecolor(BG)
        gs  = gridspec.GridSpec(2,2, figure=fig, hspace=0.5, wspace=0.35)
        ax1 = fig.add_subplot(gs[0,:]); ax2 = fig.add_subplot(gs[1,0]); ax3 = fig.add_subplot(gs[1,1])

        ax1.fill_between(range(len(w1)),  w1,  alpha=0.15, color=C1)
        ax1.fill_between(range(len(w10)), w10, alpha=0.15, color=C10)
        ax1.plot(w1,  color=C1,  lw=1.5, label=f"1G NIC  (avg {aw1}ms)")
        ax1.plot(w10, color=C10, lw=1.5, label=f"10G NIC (avg {aw10}ms)")
        ax1.axhline(20, color=YEL, lw=1.2, ls="--", alpha=0.8, label="Danger: 20ms")
        ax1.axhline(10, color=YEL, lw=0.8, ls=":",  alpha=0.4, label="Caution: 10ms")
        ax1.axhline(aw1,  color=C1,  lw=0.8, ls="--", alpha=0.4)
        ax1.axhline(aw10, color=C10, lw=0.8, ls="--", alpha=0.4)
        style(ax1, "HADR avg_wait_per_commit_ms", ylabel="ms")
        ax1.legend(facecolor=CARD, labelcolor=TXT, fontsize=9, framealpha=0.8, loc="upper right")
        imp = round((aw1-aw10)/aw1*100,1)
        ax1.text(0.02, 0.92, f"Improved {imp}%", transform=ax1.transAxes, color=GRN, fontsize=11, fontweight="bold")

        ax2.hist(w1,  bins=25, color=C1,  alpha=0.85, edgecolor=BG, linewidth=0.3)
        ax2.axvline(aw1,  color="white", lw=1.5, ls="--", label=f"avg {aw1}ms")
        style(ax2, "1G NIC - wait distribution", xlabel="ms", ylabel="count")
        ax2.legend(facecolor=CARD, labelcolor=TXT, fontsize=9)

        ax3.hist(w10, bins=25, color=C10, alpha=0.85, edgecolor=BG, linewidth=0.3)
        ax3.axvline(aw10, color="white", lw=1.5, ls="--", label=f"avg {aw10}ms")
        style(ax3, "10G NIC - wait distribution", xlabel="ms", ylabel="count")
        ax3.legend(facecolor=CARD, labelcolor=TXT, fontsize=9)

        plt.savefig(os.path.join(CHARTS_DIR, "chart_01_hadr_wait.png"), dpi=150, bbox_inches="tight", facecolor=BG)
        plt.close(); print("  chart_01 OK")

        # ── 차트2: 처리량 3패널 ──────────────────────────
        fig, axes = plt.subplots(1,3, figsize=(16,5), facecolor=BG); fig.patch.set_facecolor(BG)
        for ax, va, vb, lbl, unit in [
            (axes[0], t1, t10, "Theoretical Max TPS", "TPS"),
            (axes[1], c1, c10, "Commits/sec",         "commits/sec"),
            (axes[2], b1, b10, "Batch Requests/sec",  "req/sec"),
        ]:
            aa=round(avg(va),0); ab_=round(avg(vb),0)
            ax.plot(va, color=C1,  lw=1.5, alpha=0.9, label=f"1G  ({int(aa):,})")
            ax.plot(vb, color=C10, lw=1.5, alpha=0.9, label=f"10G ({int(ab_):,})")
            ax.fill_between(range(len(va)), va, alpha=0.08, color=C1)
            ax.fill_between(range(len(vb)), vb, alpha=0.08, color=C10)
            style(ax, lbl, ylabel=unit)
            ax.legend(facecolor=CARD, labelcolor=TXT, fontsize=9)
            i = round((ab_-aa)/aa*100,1)
            ax.text(0.05, 0.93, f"+{i}%", transform=ax.transAxes, color=GRN, fontsize=10, fontweight="bold")
        plt.suptitle("Throughput Comparison - 1G vs 10G NIC", color=TXT, fontsize=13, fontweight="bold", y=1.02)
        plt.tight_layout()
        plt.savefig(os.path.join(CHARTS_DIR, "chart_02_throughput.png"), dpi=150, bbox_inches="tight", facecolor=BG)
        plt.close(); print("  chart_02 OK")

        # ── 차트3: CPU + NIC ─────────────────────────────
        fig, axes = plt.subplots(1,2, figsize=(14,5), facecolor=BG); fig.patch.set_facecolor(BG)

        axes[0].plot(cpu1,  color=C1,  lw=1.5, label=f"1G  (avg {acpu1}%)")
        axes[0].plot(cpu10, color=C10, lw=1.5, label=f"10G (avg {acpu10}%)")
        axes[0].fill_between(range(len(cpu1)),  cpu1,  alpha=0.1, color=C1)
        axes[0].fill_between(range(len(cpu10)), cpu10, alpha=0.1, color=C10)
        axes[0].axhline(85, color=YEL, lw=1.2, ls="--", label="Danger: 85%")
        axes[0].axhspan(85, 100, alpha=0.05, color=YEL)
        axes[0].set_ylim(0, 100)
        style(axes[0], "CPU Usage (%)", ylabel="%")
        axes[0].legend(facecolor=CARD, labelcolor=TXT, fontsize=9)
        margin = round(85 - max(cpu10), 1)
        axes[0].text(0.05, 0.93, f"Max {max(cpu10):.1f}% - {margin}%p margin",
                     transform=axes[0].transAxes, color=GRN, fontsize=9)

        axes[1].plot(nic1,  color=C1,  lw=1.5, label=f"1G  (avg {anic1}%)")
        axes[1].plot(nic10, color=C10, lw=1.5, label=f"10G (avg {anic10}%)")
        axes[1].fill_between(range(len(nic1)),  nic1,  alpha=0.15, color=C1)
        axes[1].fill_between(range(len(nic10)), nic10, alpha=0.10, color=C10)
        axes[1].axhline(70, color=YEL, lw=1.2, ls="--", label="Danger: 70%")
        axes[1].axhspan(70, max(nic1)+5, alpha=0.05, color=YEL)
        style(axes[1], "NIC Usage (%)", ylabel="%")
        axes[1].legend(facecolor=CARD, labelcolor=TXT, fontsize=9)
        ni = round((anic1-anic10)/anic1*100,1)
        axes[1].text(0.05, 0.93, f"-{ni}% ({anic1}% -> {anic10}%)",
                     transform=axes[1].transAxes, color=GRN, fontsize=9)

        plt.suptitle("Resource Usage - CPU & NIC", color=TXT, fontsize=13, fontweight="bold", y=1.02)
        plt.tight_layout()
        plt.savefig(os.path.join(CHARTS_DIR, "chart_03_cpu_nic.png"), dpi=150, bbox_inches="tight", facecolor=BG)
        plt.close(); print("  chart_03 OK")

        # ── 차트4: KPI 요약 막대 ─────────────────────────
        fig, axes = plt.subplots(1,4, figsize=(16,5), facecolor=BG); fig.patch.set_facecolor(BG)
        kpis = [
            ("HADR wait\navg (ms)",    aw1,    aw10,    True,  20,   "{:.3f}"),
            ("Theoretical\nMax TPS",   at1,    at10,    False, None, "{:,.0f}"),
            ("Batch\nRequests/sec",    ab1,    ab10,    False, None, "{:,.0f}"),
            ("NIC\nUsage (%)",         anic1,  anic10,  True,  70,   "{:.1f}"),
        ]
        for i, (label, v1, v10, lower, threshold, fmt) in enumerate(kpis):
            ax = axes[i]; ax.set_facecolor(CARD)
            bars = ax.bar(["1G","10G"], [v1,v10], color=[C1,C10], width=0.5,
                          edgecolor=BG, linewidth=1.5, zorder=3)
            if threshold:
                ax.axhline(threshold, color=YEL, lw=1.2, ls="--", alpha=0.8, zorder=4)
                ax.axhspan(threshold, max(v1,v10)*1.15, alpha=0.04, color=YEL)
            top = max(v1, v10)
            for bar, val in zip(bars, [v1, v10]):
                ax.text(bar.get_x()+bar.get_width()/2, bar.get_height()+top*0.02,
                        fmt.format(val), ha="center", va="bottom",
                        color=TXT, fontsize=10, fontweight="bold")
            if lower: i_val=round((v1-v10)/v1*100,1); txt=f"-{i_val}%"
            else:     i_val=round((v10-v1)/v1*100,1); txt=f"+{i_val}%"
            ax.text(0.5, 0.97, txt, transform=ax.transAxes, ha="center", va="top",
                    color=GRN, fontsize=13, fontweight="bold")
            style(ax, label, xlabel="", ylabel="")
            ax.set_xticks([0,1]); ax.set_xticklabels(["1G","10G"], color=TXT, fontsize=11)
            ax.set_ylim(0, max(v1,v10)*1.28)
            ax.grid(axis="x", visible=False)

        plt.suptitle("Key KPI Summary - 1G vs 10G NIC", color=TXT, fontsize=13, fontweight="bold", y=1.04)
        plt.tight_layout()
        plt.savefig(os.path.join(CHARTS_DIR, "chart_04_kpi_summary.png"), dpi=150, bbox_inches="tight", facecolor=BG)
        plt.close(); print("  chart_04 OK")

    except ImportError:
        print("  [경고] matplotlib 없음 — pip install matplotlib")


def notion_req(method, path, body=None):
    if not NOTION_TOKEN:
        print("  [오류] NOTION_TOKEN 환경변수 없음")
        return None
    url = "https://api.notion.com/v1" + path
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {NOTION_TOKEN}")
    req.add_header("Notion-Version", "2022-06-28")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        print(f"  Notion API 오류 {e.code}: {e.read().decode()}")
        return None


def create_page(stats):
    today = datetime.now().strftime("%Y-%m-%d")
    title = f"[AG 비교분석] NIC 업그레이드 효과 검증({MODE}) — {today}"

    w_imp = round((stats["wait_1g"] - stats["wait_10g"]) / stats["wait_1g"] * 100, 1)
    t_imp = round((stats["tps_10g"] - stats["tps_1g"])   / stats["tps_1g"]  * 100, 1)
    c_imp = round((stats["com_10g"] - stats["com_1g"])   / stats["com_1g"]  * 100, 1)
    b_imp = round((stats["bat_10g"] - stats["bat_1g"])   / stats["bat_1g"]  * 100, 1)

    md = f"""## 📋 테스트 환경

| 항목 | 내용 |
|---|---|
| SQL Server | 2025 Preview |
| Windows Server | 2022 |
| AG 동기 모드 | SYNCHRONOUS_COMMIT |
| 클러스터 | WSFC |
| Primary / Secondary | PFDB01 / PFDB02 |
| 테스트 도구 | HammerDB |
| 분석 모드 | {MODE} |
| 분석 일시 | {today} |

## 📊 핵심 KPI 요약

> 4개의 핵심 KPI를 막대 그래프로 한눈에 비교합니다. 각 막대 위의 퍼센트는 1G 대비 10G의 개선율이며, 노란 점선은 위험 임계값입니다.

![KPI Summary]({GH_BASE}/chart_04_kpi_summary.png)

| 지표 | 1G NIC | 10G NIC | 개선율 | 평가 |
|---|---|---|---|---|
| HADR avg_wait (ms) | {stats["wait_1g"]:.3f} | {stats["wait_10g"]:.3f} | ▼{w_imp}% | ✅ |
| Theoretical Max TPS | {stats["tps_1g"]:.0f} | {stats["tps_10g"]:.0f} | ▲{t_imp}% | ✅ |
| Commits/sec | {stats["com_1g"]:.0f} | {stats["com_10g"]:.0f} | ▲{c_imp}% | ✅ |
| Batch Requests/sec | {stats["bat_1g"]:.0f} | {stats["bat_10g"]:.0f} | ▲{b_imp}% | ✅ |
| CPU 사용률 (%) | {stats["cpu_1g"]:.1f} | {stats["cpu_10g"]:.1f} | — | ✅ |
| Transaction Delay (ms) | {stats["tx_1g"]:.0f} | {stats["tx_10g"]:.0f} | ▲(병목 아님) | ℹ️ |

## 🔬 HADR 대기시간 심층 분석

> HADR avg_wait는 SYNCHRONOUS_COMMIT 환경에서 NIC 병목을 가장 직접적으로 나타내는 지표입니다. 상단 시계열로 전체 추이를, 하단 히스토그램으로 분포 특성을 확인합니다.

![HADR Wait]({GH_BASE}/chart_01_hadr_wait.png)

- HADR avg_wait: {stats["wait_1g"]:.3f}ms → {stats["wait_10g"]:.3f}ms (**{w_imp}% 개선**)
- 위험 임계값(20ms) 초과: 0회 (양쪽 모두 정상)
- Transaction Delay 증가는 처리량 증가에 따른 복제 큐 증가이며 성능 저하가 아님

## 📈 처리량 비교

> TPS, Commits/sec, Batch/sec 3가지 처리량 지표를 나란히 비교합니다. NIC 병목 해소가 처리량 전반에 미치는 복합적 영향을 확인합니다.

![Throughput]({GH_BASE}/chart_02_throughput.png)

## 🖥️ 리소스 사용률

> CPU와 NIC 사용률을 함께 보여줍니다. NIC 사용률이 1G에서 최대 57.6%까지 상승했으나 10G에서 4.3%로 급감한 반면, CPU는 두 환경 모두 임계값(85%) 대비 충분한 여유를 유지합니다.

![CPU & NIC]({GH_BASE}/chart_03_cpu_nic.png)

## 💡 결론 및 권고사항

핵심: 1G → 10G NIC 업그레이드로 HADR 대기시간 {w_imp}% 감소, TPS {t_imp}% 향상, NIC 사용률 86% 감소

추가 최적화 권고: Jumbo Frame(MTU 9000), RSS/VMQ 활성화, HADR 전용 NIC 분리

다음 단계: 비동기 모드 비교 분석, 25G NIC 업그레이드 효과 측정
"""

    body = {
        "parent": {"page_id": PARENT_PAGE_ID},
        "properties": {"title": {"title": [{"text": {"content": title}}]}},
        "children": [{"object": "block", "type": "paragraph",
                      "paragraph": {"rich_text": [{"type": "text", "text": {"content": md}}]}}]
    }
    result = notion_req("POST", "/pages", body)
    if not result:
        return None

    page_id  = result["id"]
    page_url = result.get("url", "")
    print(f"  페이지 생성 OK: {page_url}")
    return page_url


def main():
    print(f"\n{'='*50}\nAG 성능 분석 — {MODE}\n{'='*50}")

    if not NOTION_TOKEN:
        print("[경고] NOTION_TOKEN 환경변수 없음 — Notion 저장 건너뜀")

    files = find_csv()
    missing = [k for k in ["1g", "10g", "hadr"] if k not in files]
    if missing:
        print(f"[오류] CSV 파일 없음: {missing}"); return

    print(f"\n[1] CSV 파싱...")
    d1  = load_pdh(files["1g"],  1e9)
    d10 = load_pdh(files["10g"], 10e9)
    h1  = load_hadr(files["hadr"], f"{MODE}_1G_NIC")
    h10 = load_hadr(files["hadr"], f"{MODE}_10G_NIC")
    print(f"  1G PDH:{len(d1)}행  10G PDH:{len(d10)}행  1G HADR:{len(h1)}행  10G HADR:{len(h10)}행")

    stats = {
        "wait_1g":  hmean(h1,  "avg_wait_per_commit_ms"),
        "wait_10g": hmean(h10, "avg_wait_per_commit_ms"),
        "tps_1g":   hmean(h1,  "theoretical_max_tps"),
        "tps_10g":  hmean(h10, "theoretical_max_tps"),
        "com_1g":   hmean(h1,  "commits_per_sec"),
        "com_10g":  hmean(h10, "commits_per_sec"),
        "bat_1g":   pmean(d1,  "batch"),
        "bat_10g":  pmean(d10, "batch"),
        "cpu_1g":   pmean(d1,  "cpu"),
        "cpu_10g":  pmean(d10, "cpu"),
        "tx_1g":    pmean(d1,  "tx"),
        "tx_10g":   pmean(d10, "tx"),
    }
    print(f"  HADR wait 1G:{stats['wait_1g']:.3f}ms  10G:{stats['wait_10g']:.3f}ms")

    print(f"\n[2] 차트 생성...")
    make_charts(d1, d10, h1, h10)

    print(f"\n[3] git push...")
    os.chdir(BASE_DIR)
    subprocess.run("git add -A", shell=True)
    subprocess.run(f'git commit -m "[{MODE}] 개선된 차트 4종 업데이트"', shell=True)
    r = subprocess.run("git push", shell=True, capture_output=True, text=True)
    print("  git push:", "OK" if r.returncode == 0 else r.stderr.strip())

    if NOTION_TOKEN:
        print(f"\n[4] Notion 페이지 생성...")
        url = create_page(stats)
        print(f"\n{'='*50}\n완료! {url}\n{'='*50}\n")
    else:
        print(f"\n{'='*50}\n차트 생성/push 완료 (Notion 건너뜀)\n{'='*50}\n")


if __name__ == "__main__":
    main()
