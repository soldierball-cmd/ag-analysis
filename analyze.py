"""
AG 성능 비교 분석 스크립트 — PC 직접 실행용

사용법:
  # 모드 기반 (기존 방식 — 동일 모드 내 1G/10G 비교)
  python analyze.py 동기모드
  python analyze.py 비동기모드

  # 파일 직접 지정 (범용 — 어떤 조합이든 가능)
  python analyze.py --a 동기모드_1G_NIC.csv --b 비동기모드_1G_NIC.csv
  python analyze.py --a 동기모드_1G_NIC.csv --b 비동기모드_1G_NIC.csv --hadr hadr_sync_commit_monitor.csv
  python analyze.py --a data/A.csv --b data/B.csv  (경로 직접 지정도 가능)

환경변수:
  Windows PowerShell: $env:NOTION_TOKEN = "ntn_xxx..."
  영구 설정:          setx NOTION_TOKEN "ntn_xxx..."

차트 저장 구조:
  charts/{YYYYMMDD_HHMMSS}_{A파일명}_vs_{B파일명}/
    has_hadr=True:  chart_01_hadr_wait.png / chart_02_tps_commits_batch.png
    has_hadr=False: chart_01_batch_timeseries.png / chart_02_batch_cpu_disk.png
    공통:           chart_03_cpu_nic.png / chart_04_kpi_summary.png
"""
import sys, os, csv, io, json, subprocess, mimetypes
import urllib.request, urllib.error
from datetime import datetime

NOTION_TOKEN   = os.environ.get("NOTION_TOKEN", "")
PARENT_PAGE_ID = "366dadb5-6b2f-8019-8e65-d0de1d942753"
BASE_DIR       = os.path.dirname(os.path.abspath(__file__))
DATA_DIR       = os.path.join(BASE_DIR, "data")
GH_BASE_ROOT   = "https://soldierball-cmd.github.io/ag-analysis/charts"
TIMESTAMP      = datetime.now().strftime("%Y%m%d_%H%M%S")

SUBDIR     = None
CHARTS_DIR = None
GH_BASE    = None


# ═══════════════════════════════════════════════════════════
#  인수 파싱
# ═══════════════════════════════════════════════════════════
def parse_args():
    """
    반환: (mode_label, path_a, path_b, path_hadr, nic_bps_a, nic_bps_b)
    """
    args = sys.argv[1:]

    # --a / --b 직접 지정 모드
    if "--a" in args and "--b" in args:
        ia = args.index("--a"); ib = args.index("--b")
        fa = args[ia + 1]; fb = args[ib + 1]
        # 상대 경로이면 data/ 폴더 기준으로 처리
        if not os.path.isabs(fa) and not os.path.exists(fa):
            fa = os.path.join(DATA_DIR, fa)
        if not os.path.isabs(fb) and not os.path.exists(fb):
            fb = os.path.join(DATA_DIR, fb)

        # --hadr 지정 여부
        path_hadr = None
        if "--hadr" in args:
            ih = args.index("--hadr")
            ph = args[ih + 1]
            if not os.path.isabs(ph) and not os.path.exists(ph):
                ph = os.path.join(DATA_DIR, ph)
            path_hadr = ph
        else:
            # hadr CSV 자동 탐색
            for f in os.listdir(DATA_DIR):
                if "hadr_sync_commit" in f.lower():
                    path_hadr = os.path.join(DATA_DIR, f)
                    break

        # NIC 대역폭: 파일명에서 자동 판별
        def detect_bps(name):
            nl = name.lower()
            if "10g" in nl: return 10e9
            if "25g" in nl: return 25e9
            return 1e9  # 기본 1G

        bps_a = detect_bps(os.path.basename(fa))
        bps_b = detect_bps(os.path.basename(fb))

        # 모드 레이블: 파일명 조합
        label_a = os.path.splitext(os.path.basename(fa))[0]
        label_b = os.path.splitext(os.path.basename(fb))[0]
        mode_label = f"{label_a}_vs_{label_b}"
        return mode_label, fa, fb, path_hadr, bps_a, bps_b

    # 기존 모드 기반 방식
    mode = args[0] if args else "동기모드"
    path_a = path_b = path_hadr = None
    for f in os.listdir(DATA_DIR):
        fl = f.lower()
        in_mode = (
            (mode == "동기모드"   and "동기모드"   in f and "비동기" not in f) or
            (mode == "비동기모드" and "비동기모드" in f)
        )
        if in_mode:
            if   "1g"  in fl and "hadr" not in fl: path_a = os.path.join(DATA_DIR, f)
            elif "10g" in fl and "hadr" not in fl: path_b = os.path.join(DATA_DIR, f)
        if "hadr_sync_commit" in fl:
            path_hadr = os.path.join(DATA_DIR, f)

    bps_a = 1e9; bps_b = 10e9
    return mode, path_a, path_b, path_hadr, bps_a, bps_b


# ═══════════════════════════════════════════════════════════
#  유틸
# ═══════════════════════════════════════════════════════════
def fv(s):
    try:    return float(s.strip()) if s and s.strip() else None
    except: return None

def clean(lst): return [v for v in lst if v is not None]

def avg(lst):
    lst = clean(lst)
    return sum(lst) / len(lst) if lst else 0

def pct(a, b, lower_is_better=False):
    if a == 0: return "N/A"
    val   = round((a - b) / a * 100, 1) if lower_is_better else round((b - a) / a * 100, 1)
    arrow = "▼" if lower_is_better else "▲"
    if lower_is_better:
        return f"{arrow}{abs(val)}%" if b < a else f"▲{abs(val)}% (악화)"
    else:
        return f"{arrow}{abs(val)}%" if b > a else f"▼{abs(val)}% (감소)"

def make_subdir(label_a, label_b):
    safe = lambda s: s.replace(" ", "_").replace("/", "_").replace("\\", "_")
    return f"{TIMESTAMP}_{safe(label_a)}_vs_{safe(label_b)}"

def find_spec_img():
    for f in os.listdir(DATA_DIR):
        if ("스펙" in f or "spec" in f.lower()) and \
           os.path.splitext(f)[1].lower() in (".png", ".jpg", ".jpeg", ".webp"):
            return os.path.join(DATA_DIR, f)
    return None


# ═══════════════════════════════════════════════════════════
#  PDH / HADR 로드
# ═══════════════════════════════════════════════════════════
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
        rb  = fv(r.get(replica_col, "")) or 0
        nb  = fv(r.get(bytes_col,   "")) or 0
        # NIC 사용률: replica 트래픽이 있으면 우선, 없으면 total 사용
        raw = rb if rb > 0 else nb
        nic = round(raw * 8 / nic_bps * 100, 4)
        result.append({
            "cpu":   fv(r.get(cpu_col,   "")),
            "nic":   nic,
            "batch": fv(r.get(batch_col, "")),
            "disk":  fv(r.get(disk_col,  "")),
            "tx":    fv(r.get(tx_col,    "")),
        })
    return result

def load_hadr_for(path, label_a, label_b):
    """HADR CSV에서 A/B 레이블로 데이터 필터링 (유연한 매칭)"""
    if not path or not os.path.exists(path):
        return [], []
    with open(path, "rb") as f:
        rows = list(csv.DictReader(io.StringIO(f.read().decode("cp949"))))
    scenarios = [r.get("scenario", "").strip() for r in rows]

    def best_match(label, scenarios):
        # 정확히 일치하는 것 우선
        exact = [r for r in rows if r.get("scenario","").strip() == label]
        if exact: return exact
        # 1G/10G 키워드 포함 여부로 fallback
        la = label.lower()
        return [r for r in rows if all(k in r.get("scenario","").lower() for k in
                [x for x in ["1g","10g","동기","비동기"] if x in la])]

    ha = best_match(label_a, scenarios)
    hb = best_match(label_b, scenarios)
    print(f"  HADR 매칭: A({label_a})={len(ha)}행, B({label_b})={len(hb)}행")
    return ha, hb


# ═══════════════════════════════════════════════════════════
#  차트 생성
# ═══════════════════════════════════════════════════════════
def make_charts(da, db, ha, hb, has_hadr, label_a, label_b):
    global CHARTS_DIR, GH_BASE
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.gridspec as gridspec

        CA   = "#ff6b6b"; CB   = "#4e7cff"
        BG   = "#1a1d27"; CARD = "#22263a"
        GRID = "#2e3250"; TXT  = "#e8eaf6"; TXT2 = "#9fa8c7"
        YEL  = "#ffd166"; GRN  = "#06d6a0"

        def style(ax, title, xlabel="Time (sec)", ylabel=""):
            ax.set_facecolor(CARD)
            ax.tick_params(colors=TXT2, labelsize=9)
            for s in ["bottom", "left"]: ax.spines[s].set_color(GRID)
            ax.spines["top"].set_visible(False); ax.spines["right"].set_visible(False)
            ax.grid(axis="y", color=GRID, lw=0.5, alpha=0.6, ls="--")
            ax.set_axisbelow(True)
            ax.set_title(title, color=TXT, fontsize=11, fontweight="bold", pad=10)
            if xlabel: ax.set_xlabel(xlabel, color=TXT2, fontsize=9)
            if ylabel: ax.set_ylabel(ylabel, color=TXT2, fontsize=9)

        def save(fname):
            path = os.path.join(CHARTS_DIR, fname)
            plt.savefig(path, dpi=150, bbox_inches="tight", facecolor=BG)
            plt.close()
            print(f"  {fname} OK")

        # PDH 데이터
        ba   = clean([d["batch"] for d in da]); bb  = clean([d["batch"] for d in db])
        cpua = clean([d["cpu"]   for d in da]); cpub= clean([d["cpu"]   for d in db])
        nica = [d["nic"] for d in da];          nicb= [d["nic"] for d in db]
        dska = clean([d["disk"]  for d in da]); dskb= clean([d["disk"]  for d in db])

        aba   = round(avg(ba),   0); abb   = round(avg(bb),   0)
        acpua = round(avg(cpua), 1); acpub = round(avg(cpub), 1)
        anica = round(avg(nica), 1); anicb = round(avg(nicb), 1)
        adska = round(avg(dska), 0); adskb = round(avg(dskb), 0)

        # HADR 데이터
        if has_hadr:
            wa  = clean([fv(r["avg_wait_per_commit_ms"]) for r in ha])
            wb  = clean([fv(r["avg_wait_per_commit_ms"]) for r in hb])
            ca  = clean([fv(r["commits_per_sec"])        for r in ha])
            cb  = clean([fv(r["commits_per_sec"])        for r in hb])
            ta  = clean([fv(r["theoretical_max_tps"])    for r in ha])
            tb  = clean([fv(r["theoretical_max_tps"])    for r in hb])
            awa = round(avg(wa),3); awb = round(avg(wb),3)
            ata = round(avg(ta),0); atb = round(avg(tb),0)
            aca = round(avg(ca),0); acb = round(avg(cb),0)

        # 짧은 레이블 (차트 범례용)
        short_a = label_a.replace("_NIC","").replace("모드","")[-12:]
        short_b = label_b.replace("_NIC","").replace("모드","")[-12:]

        # ── 차트 01 ─────────────────────────────────────
        fig = plt.figure(figsize=(14, 8), facecolor=BG)
        fig.patch.set_facecolor(BG)
        gs  = gridspec.GridSpec(2, 2, figure=fig, hspace=0.5, wspace=0.35)
        ax1 = fig.add_subplot(gs[0, :])
        ax2 = fig.add_subplot(gs[1, 0])
        ax3 = fig.add_subplot(gs[1, 1])

        if has_hadr:
            vs_a, vs_b  = wa, wb
            avg_a, avg_b= awa, awb
            unit = "ms"
            ttl  = f"HADR avg_wait_per_commit_ms  [{short_a} vs {short_b}]"
            d_a  = f"{short_a} — wait dist"
            d_b  = f"{short_b} — wait dist"
            imp  = f"Diff {round((awa-awb)/awa*100,1)}%" if awa else "N/A"
            ax1.axhline(20, color=YEL, lw=1.2, ls="--", alpha=0.8, label="Danger: 20ms")
            fname01 = "chart_01_hadr_wait.png"
        else:
            vs_a, vs_b  = ba, bb
            avg_a, avg_b= aba, abb
            unit = "req/sec"
            ttl  = f"Batch Requests/sec  [{short_a} vs {short_b}]"
            d_a  = f"{short_a} — Batch dist"
            d_b  = f"{short_b} — Batch dist"
            diff = round((abb-aba)/aba*100,1) if aba else 0
            imp  = f"Diff {diff:+.1f}%"
            fname01 = "chart_01_batch_timeseries.png"

        ax1.fill_between(range(len(vs_a)), vs_a, alpha=0.15, color=CA)
        ax1.fill_between(range(len(vs_b)), vs_b, alpha=0.15, color=CB)
        ax1.plot(vs_a, color=CA, lw=1.5, label=f"{short_a} (avg {avg_a})")
        ax1.plot(vs_b, color=CB, lw=1.5, label=f"{short_b} (avg {avg_b})")
        ax1.axhline(avg_a, color=CA, lw=0.8, ls="--", alpha=0.4)
        ax1.axhline(avg_b, color=CB, lw=0.8, ls="--", alpha=0.4)
        style(ax1, ttl, ylabel=unit)
        ax1.legend(facecolor=CARD, labelcolor=TXT, fontsize=9, framealpha=0.8, loc="upper right")
        ax1.text(0.02, 0.92, imp, transform=ax1.transAxes, color=GRN, fontsize=10, fontweight="bold")

        ax2.hist(vs_a, bins=25, color=CA, alpha=0.85, edgecolor=BG, lw=0.3)
        ax2.axvline(avg_a, color="white", lw=1.5, ls="--", label=f"avg {avg_a}")
        style(ax2, d_a, xlabel=unit, ylabel="count")
        ax2.legend(facecolor=CARD, labelcolor=TXT, fontsize=9)

        ax3.hist(vs_b, bins=25, color=CB, alpha=0.85, edgecolor=BG, lw=0.3)
        ax3.axvline(avg_b, color="white", lw=1.5, ls="--", label=f"avg {avg_b}")
        style(ax3, d_b, xlabel=unit, ylabel="count")
        ax3.legend(facecolor=CARD, labelcolor=TXT, fontsize=9)
        save(fname01)

        # ── 차트 02 ─────────────────────────────────────
        fig, axes = plt.subplots(1, 3, figsize=(16, 5), facecolor=BG)
        fig.patch.set_facecolor(BG)

        if has_hadr:
            panels = [
                (axes[0], ta, tb, "Theoretical Max TPS", "TPS"),
                (axes[1], ca, cb, "Commits/sec",         "commits/sec"),
                (axes[2], ba, bb, "Batch Requests/sec",  "req/sec"),
            ]
            sup2   = f"Throughput — {short_a} vs {short_b}"
            fname02= "chart_02_tps_commits_batch.png"
        else:
            panels = [
                (axes[0], ba,   bb,   "Batch Requests/sec", "req/sec"),
                (axes[1], cpua, cpub, "CPU Usage (%)",      "%"),
                (axes[2], dska, dskb, "Disk IOPS",          "IOPS"),
            ]
            sup2   = f"Performance — {short_a} vs {short_b}"
            fname02= "chart_02_batch_cpu_disk.png"

        for ax, va, vb, lbl, unit in panels:
            aa_ = round(avg(va),0); ab_ = round(avg(vb),0)
            ax.plot(va, color=CA, lw=1.5, alpha=0.9, label=f"{short_a} ({int(aa_):,})")
            ax.plot(vb, color=CB, lw=1.5, alpha=0.9, label=f"{short_b} ({int(ab_):,})")
            ax.fill_between(range(len(va)), va, alpha=0.08, color=CA)
            ax.fill_between(range(len(vb)), vb, alpha=0.08, color=CB)
            style(ax, lbl, ylabel=unit)
            ax.legend(facecolor=CARD, labelcolor=TXT, fontsize=9)
            i = round((ab_-aa_)/aa_*100,1) if aa_ else 0
            ax.text(0.05, 0.93, f"{i:+.1f}%" if aa_ else "N/A",
                    transform=ax.transAxes, color=GRN, fontsize=10, fontweight="bold")

        plt.suptitle(sup2, color=TXT, fontsize=13, fontweight="bold", y=1.02)
        plt.tight_layout()
        save(fname02)

        # ── 차트 03 — CPU + NIC ──────────────────────────
        fig, axes = plt.subplots(1, 2, figsize=(14, 5), facecolor=BG)
        fig.patch.set_facecolor(BG)

        axes[0].plot(cpua, color=CA, lw=1.5, label=f"{short_a} (avg {acpua}%)")
        axes[0].plot(cpub, color=CB, lw=1.5, label=f"{short_b} (avg {acpub}%)")
        axes[0].fill_between(range(len(cpua)), cpua, alpha=0.1, color=CA)
        axes[0].fill_between(range(len(cpub)), cpub, alpha=0.1, color=CB)
        axes[0].axhline(85, color=YEL, lw=1.2, ls="--", label="Danger: 85%")
        axes[0].axhspan(85, 100, alpha=0.05, color=YEL)
        axes[0].set_ylim(0, 100)
        style(axes[0], "CPU Usage (%)", ylabel="%")
        axes[0].legend(facecolor=CARD, labelcolor=TXT, fontsize=9)
        mx = max(cpub) if cpub else 0
        axes[0].text(0.05, 0.93, f"B Max {mx:.1f}%  ({round(85-mx,1)}%p margin)",
                     transform=axes[0].transAxes, color=GRN, fontsize=9)

        axes[1].plot(nica, color=CA, lw=1.5, label=f"{short_a} (avg {anica}%)")
        axes[1].plot(nicb, color=CB, lw=1.5, label=f"{short_b} (avg {anicb}%)")
        axes[1].fill_between(range(len(nica)), nica, alpha=0.15, color=CA)
        axes[1].fill_between(range(len(nicb)), nicb, alpha=0.10, color=CB)
        axes[1].axhline(70, color=YEL, lw=1.2, ls="--", label="Danger: 70%")
        if nica: axes[1].axhspan(70, max(nica)+5, alpha=0.05, color=YEL)
        style(axes[1], "NIC Usage (%)", ylabel="%")
        axes[1].legend(facecolor=CARD, labelcolor=TXT, fontsize=9)
        axes[1].text(0.05, 0.93, f"A:{anica}% B:{anicb}%",
                     transform=axes[1].transAxes, color=GRN, fontsize=9)

        plt.suptitle(f"Resource — {short_a} vs {short_b}", color=TXT, fontsize=13, fontweight="bold", y=1.02)
        plt.tight_layout()
        save("chart_03_cpu_nic.png")

        # ── 차트 04 — KPI 막대 ──────────────────────────
        fig, axes = plt.subplots(1, 4, figsize=(16, 5), facecolor=BG)
        fig.patch.set_facecolor(BG)

        if has_hadr:
            kpis = [
                ("HADR wait\navg (ms)",  awa,   awb,   True,  20,   "{:.3f}"),
                ("Theoretical\nMax TPS", ata,   atb,   False, None, "{:,.0f}"),
                ("Batch\nReq/sec",       aba,   abb,   False, None, "{:,.0f}"),
                ("NIC\nUsage (%)",       anica, anicb, True,  70,   "{:.1f}"),
            ]
        else:
            kpis = [
                ("Batch\nReq/sec",       aba,   abb,   False, None, "{:,.0f}"),
                ("CPU\nUsage (%)",       acpua, acpub, False, 85,   "{:.1f}"),
                ("Disk\nIOPS",           adska, adskb, False, None, "{:,.0f}"),
                ("NIC\nUsage (%)",       anica, anicb, True,  70,   "{:.1f}"),
            ]

        for idx, (lbl, va, vb, lower, thr, fmt) in enumerate(kpis):
            ax = axes[idx]; ax.set_facecolor(CARD)
            bars = ax.bar([short_a[-8:], short_b[-8:]], [va, vb], color=[CA, CB],
                          width=0.5, edgecolor=BG, lw=1.5, zorder=3)
            top = max(va, vb) if max(va, vb) > 0 else 1
            if thr:
                ax.axhline(thr, color=YEL, lw=1.2, ls="--", alpha=0.8, zorder=4)
                if top*1.15 > thr: ax.axhspan(thr, top*1.15, alpha=0.04, color=YEL)
            for bar, val in zip(bars, [va, vb]):
                ax.text(bar.get_x()+bar.get_width()/2, bar.get_height()+top*0.02,
                        fmt.format(val), ha="center", va="bottom", color=TXT, fontsize=10, fontweight="bold")
            iv = round((va-vb)/va*100,1) if lower and va else round((vb-va)/va*100,1) if va else 0
            ax.text(0.5, 0.97, f"{'-' if lower else '+'}{abs(iv)}%" if va else "N/A",
                    transform=ax.transAxes, ha="center", va="top", color=GRN, fontsize=13, fontweight="bold")
            ax.set_title(lbl, color=TXT, fontsize=11, fontweight="bold", pad=10)
            ax.tick_params(colors=TXT2, labelsize=8)
            for s in ["bottom","left"]: ax.spines[s].set_color(GRID)
            ax.spines["top"].set_visible(False); ax.spines["right"].set_visible(False)
            ax.grid(axis="y", color=GRID, lw=0.5, alpha=0.6, ls="--")
            ax.set_ylim(0, top*1.28); ax.grid(axis="x", visible=False)

        plt.suptitle(f"Key KPI — {short_a} vs {short_b}", color=TXT, fontsize=13, fontweight="bold", y=1.04)
        plt.tight_layout()
        save("chart_04_kpi_summary.png")

        return {"f01": fname01, "f02": fname02,
                "f03": "chart_03_cpu_nic.png", "f04": "chart_04_kpi_summary.png"}

    except ImportError:
        print("  [경고] matplotlib 없음 — pip install matplotlib")
    except Exception as e:
        import traceback; traceback.print_exc()
        print(f"  [오류] 차트 생성 실패: {e}")
    return {}


# ═══════════════════════════════════════════════════════════
#  Notion API (토큰 있을 때만)
# ═══════════════════════════════════════════════════════════
def notion_req(method, path, body=None):
    if not NOTION_TOKEN: return None
    url  = "https://api.notion.com/v1" + path
    data = json.dumps(body).encode() if body else None
    req  = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization",  f"Bearer {NOTION_TOKEN}")
    req.add_header("Notion-Version", "2022-06-28")
    req.add_header("Content-Type",   "application/json")
    try:
        with urllib.request.urlopen(req) as r: return json.loads(r.read())
    except urllib.error.HTTPError as e:
        print(f"  Notion API 오류 {e.code}: {e.read().decode()[:300]}"); return None


# ═══════════════════════════════════════════════════════════
#  메인
# ═══════════════════════════════════════════════════════════
def main():
    global SUBDIR, CHARTS_DIR, GH_BASE

    mode_label, path_a, path_b, path_hadr, bps_a, bps_b = parse_args()

    print(f"\n{'='*55}\nAG 성능 분석\n  A: {path_a}\n  B: {path_b}\n{'='*55}")

    if not path_a or not os.path.exists(path_a):
        print(f"[오류] A 파일 없음: {path_a}"); return
    if not path_b or not os.path.exists(path_b):
        print(f"[오류] B 파일 없음: {path_b}"); return

    label_a = os.path.splitext(os.path.basename(path_a))[0]
    label_b = os.path.splitext(os.path.basename(path_b))[0]

    SUBDIR     = make_subdir(label_a, label_b)
    CHARTS_DIR = os.path.join(BASE_DIR, "charts", SUBDIR)
    GH_BASE    = f"{GH_BASE_ROOT}/{SUBDIR}"
    os.makedirs(CHARTS_DIR, exist_ok=True)
    print(f"  차트 폴더: charts/{SUBDIR}/")

    print(f"\n[1] CSV 파싱...")
    da = load_pdh(path_a, bps_a)
    db = load_pdh(path_b, bps_b)
    print(f"  A:{len(da)}행  B:{len(db)}행")

    # HADR 로드
    ha, hb = load_hadr_for(path_hadr, label_a, label_b)

    # has_hadr 판별
    wa = clean([fv(r["avg_wait_per_commit_ms"]) for r in ha])
    wb = clean([fv(r["avg_wait_per_commit_ms"]) for r in hb])
    awa = round(avg(wa),3); awb = round(avg(wb),3)
    has_hadr = len(wa)>0 and len(wb)>0 and (awa>0 or awb>0)
    print(f"  HADR wait A:{awa}ms B:{awb}ms  has_hadr={has_hadr}")

    # PDH 통계
    nica  = [d["nic"] for d in da]; nicb  = [d["nic"] for d in db]
    cpua  = clean([d["cpu"]   for d in da]); cpub  = clean([d["cpu"]   for d in db])
    ba_l  = clean([d["batch"] for d in da]); bb_l  = clean([d["batch"] for d in db])
    t_a   = clean([fv(r["theoretical_max_tps"]) for r in ha])
    t_b   = clean([fv(r["theoretical_max_tps"]) for r in hb])
    c_a   = clean([fv(r["commits_per_sec"])     for r in ha])
    c_b   = clean([fv(r["commits_per_sec"])     for r in hb])

    stats = {
        "wait_1g": awa, "wait_10g": awb,
        "tps_1g":  round(avg(t_a),0), "tps_10g":  round(avg(t_b),0),
        "com_1g":  round(avg(c_a),0), "com_10g":  round(avg(c_b),0),
        "bat_1g":  round(avg(ba_l),0),"bat_10g":  round(avg(bb_l),0),
        "cpu_1g":  round(avg(cpua),1),"cpu_10g":  round(avg(cpub),1),
        "cpu_1g_max":  round(max(cpua) if cpua else 0,1),
        "cpu_10g_max": round(max(cpub) if cpub else 0,1),
        "nic_1g":  round(avg(nica),1),"nic_10g":  round(avg(nicb),1),
        "nic_1g_max":  round(max(nica) if nica else 0,1),
        "nic_10g_max": round(max(nicb) if nicb else 0,1),
    }

    print(f"\n[2] 차트 생성...")
    chart_files = make_charts(da, db, ha, hb, has_hadr, label_a, label_b) or {}

    print(f"\n[3] git push...")
    os.chdir(BASE_DIR)
    subprocess.run("git add -A", shell=True)
    subprocess.run(f'git commit -m "[분석] {SUBDIR}"', shell=True)
    r = subprocess.run("git push", shell=True, capture_output=True, text=True)
    print("  git push:", "OK" if r.returncode == 0 else r.stderr.strip())

    # latest.json 저장
    latest = {
        "subdir":      SUBDIR,
        "mode":        mode_label,
        "timestamp":   TIMESTAMP,
        "gh_base":     GH_BASE,
        "has_hadr":    has_hadr,
        "chart_files": chart_files,
        "stats":       stats,
        "scenario":    {"label_a": label_a, "label_b": label_b}
    }
    with open(os.path.join(BASE_DIR, "charts", "latest.json"), "w", encoding="utf-8") as f:
        json.dump(latest, f, ensure_ascii=False, indent=2)
    print(f"  latest.json 저장 OK")

    print(f"\n{'='*55}\n차트 완료! Notion 페이지 생성은 Claude MCP에서 진행하세요.\nlatest.json 위치: {BASE_DIR}\\charts\\latest.json\n{'='*55}\n")


if __name__ == "__main__":
    main()
