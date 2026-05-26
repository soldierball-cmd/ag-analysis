"""
AG 성능 비교 분석 스크립트 — PC 직접 실행용
사용법: python analyze.py 동기모드
        python analyze.py 비동기모드

환경변수 설정:
  Windows PowerShell: $env:NOTION_TOKEN = "ntn_xxx..."
  영구 설정:          setx NOTION_TOKEN "ntn_xxx..."  (새 터미널 필요)
"""
import sys, os, csv, io, json, subprocess, base64, mimetypes
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
    """나누기 0 방지 개선율 → 문자열 반환"""
    if a == 0: return "N/A"
    val = round((a - b) / a * 100, 1) if lower_is_better else round((b - a) / a * 100, 1)
    arrow = "▼" if lower_is_better else "▲"
    if lower_is_better:
        return f"{arrow}{abs(val)}%" if b < a else f"▲{abs(val)}% (악화)"
    else:
        return f"{arrow}{abs(val)}%" if b > a else f"▼{abs(val)}% (감소)"


# ═══════════════════════════════════════════════════════════
#  CSV 파일 탐색
# ═══════════════════════════════════════════════════════════
def find_csv():
    files = {}
    for f in os.listdir(DATA_DIR):
        fl = f.lower()
        in_mode = (
            (MODE == "동기모드"   and "동기모드"   in f and "비동기" not in f) or
            (MODE == "비동기모드" and "비동기모드" in f)
        )
        if in_mode:
            if "1g"  in fl and "hadr" not in fl: files["pdh_1g"]  = os.path.join(DATA_DIR, f)
            elif "10g" in fl and "hadr" not in fl: files["pdh_10g"] = os.path.join(DATA_DIR, f)
        if "hadr_sync_commit" in fl:
            files["hadr"] = os.path.join(DATA_DIR, f)
    # 서버 스펙 이미지 탐색
    for f in os.listdir(DATA_DIR):
        if "스펙" in f or "spec" in f.lower():
            ext = os.path.splitext(f)[1].lower()
            if ext in (".png", ".jpg", ".jpeg", ".webp"):
                files["spec_img"] = os.path.join(DATA_DIR, f)
    return files


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
        nic = round((rb if nic_bps == 10e9 else nb) * 8 / nic_bps * 100, 4)
        result.append({
            "cpu":   fv(r.get(cpu_col,   "")),
            "nic":   nic,
            "batch": fv(r.get(batch_col, "")),
            "disk":  fv(r.get(disk_col,  "")),
            "tx":    fv(r.get(tx_col,    "")),
        })
    return result

def load_hadr(path, scenario):
    with open(path, "rb") as f:
        rows = list(csv.DictReader(io.StringIO(f.read().decode("cp949"))))
    return [r for r in rows if r.get("scenario", "") == scenario]


# ═══════════════════════════════════════════════════════════
#  차트 생성
#  ┌────────────────────────────────────────────────────────┐
#  │  has_hadr=True  (동기모드 등, HADR wait > 0)           │
#  │   chart_01: HADR wait 시계열 + 분포                    │
#  │   chart_02: TPS / Commits/sec / Batch/sec              │
#  │   chart_04: HADR wait / TPS / Batch / NIC              │
#  ├────────────────────────────────────────────────────────┤
#  │  has_hadr=False (비동기모드 등, HADR wait = 0)         │
#  │   chart_01: Batch/sec 시계열 + 분포  ← PDH 데이터만   │
#  │   chart_02: Batch / CPU / Disk       ← PDH 데이터만   │
#  │   chart_04: Batch / CPU / Disk / NIC ← PDH 데이터만   │
#  ├────────────────────────────────────────────────────────┤
#  │  chart_03: CPU + NIC 사용률  — 항상 PDH 데이터        │
#  └────────────────────────────────────────────────────────┘
# ═══════════════════════════════════════════════════════════
def make_charts(d1, d10, h1, h10, has_hadr):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.gridspec as gridspec

        C1   = "#ff6b6b"; C10  = "#4e7cff"
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

        # ── PDH 데이터 ──────────────────────────────────
        b1   = clean([d["batch"] for d in d1]);  b10  = clean([d["batch"] for d in d10])
        cpu1 = clean([d["cpu"]   for d in d1]);  cpu10= clean([d["cpu"]   for d in d10])
        nic1 = [d["nic"] for d in d1];           nic10= [d["nic"] for d in d10]
        dsk1 = clean([d["disk"]  for d in d1]);  dsk10= clean([d["disk"]  for d in d10])

        ab1  = round(avg(b1),   0); ab10  = round(avg(b10),   0)
        acpu1= round(avg(cpu1), 1); acpu10= round(avg(cpu10), 1)
        anic1= round(avg(nic1), 1); anic10= round(avg(nic10), 1)

        # ── HADR 데이터 (has_hadr=True일 때만 사용) ─────
        if has_hadr:
            w1  = clean([fv(r["avg_wait_per_commit_ms"]) for r in h1])
            w10 = clean([fv(r["avg_wait_per_commit_ms"]) for r in h10])
            c1  = clean([fv(r["commits_per_sec"])        for r in h1])
            c10 = clean([fv(r["commits_per_sec"])        for r in h10])
            t1  = clean([fv(r["theoretical_max_tps"])    for r in h1])
            t10 = clean([fv(r["theoretical_max_tps"])    for r in h10])
            aw1 = round(avg(w1),3); aw10= round(avg(w10),3)
            at1 = round(avg(t1),0); at10= round(avg(t10),0)
            ac1 = round(avg(c1),0); ac10= round(avg(c10),0)

        # ════════════════════════════════════════════════
        # 차트 01 — 핵심 지표 시계열 + 분포
        # ════════════════════════════════════════════════
        fig = plt.figure(figsize=(14, 8), facecolor=BG)
        fig.patch.set_facecolor(BG)
        gs  = gridspec.GridSpec(2, 2, figure=fig, hspace=0.5, wspace=0.35)
        ax1 = fig.add_subplot(gs[0, :]); ax2 = fig.add_subplot(gs[1, 0]); ax3 = fig.add_subplot(gs[1, 1])

        if has_hadr:
            v1s, v10s   = w1, w10
            avg1, avg10 = aw1, aw10
            unit        = "ms"
            t1_lbl      = f"1G NIC  (avg {aw1}ms)"
            t10_lbl     = f"10G NIC (avg {aw10}ms)"
            c1_ttl      = "HADR avg_wait_per_commit_ms"
            d1_ttl      = "1G — wait distribution"
            d10_ttl     = "10G — wait distribution"
            imp_txt     = f"Improved {round((aw1-aw10)/aw1*100,1)}%" if aw1 else "N/A"
            ax1.axhline(20, color=YEL, lw=1.2, ls="--", alpha=0.8, label="Danger: 20ms")
            ax1.axhline(10, color=YEL, lw=0.8, ls=":",  alpha=0.4, label="Caution: 10ms")
        else:
            # ← 비동기모드: PDH의 Batch/sec만 사용
            v1s, v10s   = b1, b10
            avg1, avg10 = ab1, ab10
            unit        = "req/sec"
            t1_lbl      = f"1G NIC  (avg {int(ab1):,})"
            t10_lbl     = f"10G NIC (avg {int(ab10):,})"
            c1_ttl      = "Batch Requests/sec  [ASYNC: HADR wait = 0ms]"
            d1_ttl      = "1G — Batch/sec distribution"
            d10_ttl     = "10G — Batch/sec distribution"
            diff        = round((ab10 - ab1) / ab1 * 100, 1) if ab1 else 0
            imp_txt     = f"Diff {diff:+.1f}%  (NIC는 처리량 병목 아님)"

        ax1.fill_between(range(len(v1s)),  v1s,  alpha=0.15, color=C1)
        ax1.fill_between(range(len(v10s)), v10s, alpha=0.15, color=C10)
        ax1.plot(v1s,  color=C1,  lw=1.5, label=t1_lbl)
        ax1.plot(v10s, color=C10, lw=1.5, label=t10_lbl)
        ax1.axhline(avg1,  color=C1,  lw=0.8, ls="--", alpha=0.4)
        ax1.axhline(avg10, color=C10, lw=0.8, ls="--", alpha=0.4)
        style(ax1, c1_ttl, ylabel=unit)
        ax1.legend(facecolor=CARD, labelcolor=TXT, fontsize=9, framealpha=0.8, loc="upper right")
        ax1.text(0.02, 0.92, imp_txt, transform=ax1.transAxes,
                 color=GRN, fontsize=10, fontweight="bold")

        ax2.hist(v1s,  bins=25, color=C1,  alpha=0.85, edgecolor=BG, lw=0.3)
        ax2.axvline(avg1,  color="white", lw=1.5, ls="--", label=f"avg {avg1}")
        style(ax2, d1_ttl, xlabel=unit, ylabel="count")
        ax2.legend(facecolor=CARD, labelcolor=TXT, fontsize=9)

        ax3.hist(v10s, bins=25, color=C10, alpha=0.85, edgecolor=BG, lw=0.3)
        ax3.axvline(avg10, color="white", lw=1.5, ls="--", label=f"avg {avg10}")
        style(ax3, d10_ttl, xlabel=unit, ylabel="count")
        ax3.legend(facecolor=CARD, labelcolor=TXT, fontsize=9)

        plt.savefig(os.path.join(CHARTS_DIR, "chart_01_main.png"),
                    dpi=150, bbox_inches="tight", facecolor=BG)
        plt.close(); print("  chart_01 OK")

        # ════════════════════════════════════════════════
        # 차트 02 — 처리량 3패널
        # ════════════════════════════════════════════════
        fig, axes = plt.subplots(1, 3, figsize=(16, 5), facecolor=BG)
        fig.patch.set_facecolor(BG)

        if has_hadr:
            panels2 = [
                (axes[0], t1,   t10,   "Theoretical Max TPS",  "TPS"),
                (axes[1], c1,   c10,   "Commits/sec",          "commits/sec"),
                (axes[2], b1,   b10,   "Batch Requests/sec",   "req/sec"),
            ]
            suptitle2 = "Throughput Comparison — 1G vs 10G NIC"
        else:
            # ← 비동기모드: 전부 PDH 데이터
            panels2 = [
                (axes[0], b1,   b10,   "Batch Requests/sec",   "req/sec"),
                (axes[1], cpu1, cpu10, "CPU Usage (%)",         "%"),
                (axes[2], dsk1, dsk10, "Disk IOPS",             "IOPS"),
            ]
            suptitle2 = "Performance Comparison (ASYNC Mode) — 1G vs 10G NIC"

        for ax, va, vb, lbl, unit in panels2:
            aa = round(avg(va), 0); ab_ = round(avg(vb), 0)
            ax.plot(va, color=C1,  lw=1.5, alpha=0.9, label=f"1G  ({int(aa):,})")
            ax.plot(vb, color=C10, lw=1.5, alpha=0.9, label=f"10G ({int(ab_):,})")
            ax.fill_between(range(len(va)), va, alpha=0.08, color=C1)
            ax.fill_between(range(len(vb)), vb, alpha=0.08, color=C10)
            style(ax, lbl, ylabel=unit)
            ax.legend(facecolor=CARD, labelcolor=TXT, fontsize=9)
            i     = round((ab_ - aa) / aa * 100, 1) if aa != 0 else 0
            i_txt = f"+{i}%" if aa != 0 else "N/A"
            ax.text(0.05, 0.93, i_txt, transform=ax.transAxes,
                    color=GRN, fontsize=10, fontweight="bold")

        plt.suptitle(suptitle2, color=TXT, fontsize=13, fontweight="bold", y=1.02)
        plt.tight_layout()
        plt.savefig(os.path.join(CHARTS_DIR, "chart_02_throughput.png"),
                    dpi=150, bbox_inches="tight", facecolor=BG)
        plt.close(); print("  chart_02 OK")

        # ════════════════════════════════════════════════
        # 차트 03 — CPU + NIC (항상 PDH 데이터)
        # ════════════════════════════════════════════════
        fig, axes = plt.subplots(1, 2, figsize=(14, 5), facecolor=BG)
        fig.patch.set_facecolor(BG)

        axes[0].plot(cpu1,  color=C1,  lw=1.5, label=f"1G  (avg {acpu1}%)")
        axes[0].plot(cpu10, color=C10, lw=1.5, label=f"10G (avg {acpu10}%)")
        axes[0].fill_between(range(len(cpu1)),  cpu1,  alpha=0.1, color=C1)
        axes[0].fill_between(range(len(cpu10)), cpu10, alpha=0.1, color=C10)
        axes[0].axhline(85, color=YEL, lw=1.2, ls="--", label="Danger: 85%")
        axes[0].axhspan(85, 100, alpha=0.05, color=YEL)
        axes[0].set_ylim(0, 100)
        style(axes[0], "CPU Usage (%)", ylabel="%")
        axes[0].legend(facecolor=CARD, labelcolor=TXT, fontsize=9)
        mx_cpu = max(cpu10) if cpu10 else 0
        axes[0].text(0.05, 0.93, f"Max {mx_cpu:.1f}%  ({round(85-mx_cpu,1)}%p margin)",
                     transform=axes[0].transAxes, color=GRN, fontsize=9)

        axes[1].plot(nic1,  color=C1,  lw=1.5, label=f"1G  (avg {anic1}%)")
        axes[1].plot(nic10, color=C10, lw=1.5, label=f"10G (avg {anic10}%)")
        axes[1].fill_between(range(len(nic1)),  nic1,  alpha=0.15, color=C1)
        axes[1].fill_between(range(len(nic10)), nic10, alpha=0.10, color=C10)
        axes[1].axhline(70, color=YEL, lw=1.2, ls="--", label="Danger: 70%")
        if nic1: axes[1].axhspan(70, max(nic1) + 5, alpha=0.05, color=YEL)
        style(axes[1], "NIC Usage (%)", ylabel="%")
        axes[1].legend(facecolor=CARD, labelcolor=TXT, fontsize=9)
        ni_txt = f"-{round((anic1-anic10)/anic1*100,1)}%  ({anic1}% → {anic10}%)" if anic1 else "N/A"
        axes[1].text(0.05, 0.93, ni_txt, transform=axes[1].transAxes, color=GRN, fontsize=9)

        plt.suptitle("Resource Usage — CPU & NIC", color=TXT, fontsize=13, fontweight="bold", y=1.02)
        plt.tight_layout()
        plt.savefig(os.path.join(CHARTS_DIR, "chart_03_cpu_nic.png"),
                    dpi=150, bbox_inches="tight", facecolor=BG)
        plt.close(); print("  chart_03 OK")

        # ════════════════════════════════════════════════
        # 차트 04 — KPI 요약 막대
        # ════════════════════════════════════════════════
        fig, axes = plt.subplots(1, 4, figsize=(16, 5), facecolor=BG)
        fig.patch.set_facecolor(BG)

        adsk1  = round(avg(dsk1),  0)
        adsk10 = round(avg(dsk10), 0)

        if has_hadr:
            kpis = [
                ("HADR wait\navg (ms)",  aw1,    aw10,    True,  20,  "{:.3f}"),
                ("Theoretical\nMax TPS", at1,    at10,    False, None,"{:,.0f}"),
                ("Batch\nReq/sec",       ab1,    ab10,    False, None,"{:,.0f}"),
                ("NIC\nUsage (%)",       anic1,  anic10,  True,  70,  "{:.1f}"),
            ]
        else:
            # ← 비동기모드: 전부 PDH 데이터
            kpis = [
                ("Batch\nReq/sec",       ab1,    ab10,    False, None,"{:,.0f}"),
                ("CPU\nUsage (%)",       acpu1,  acpu10,  False, 85,  "{:.1f}"),
                ("Disk\nIOPS",           adsk1,  adsk10,  False, None,"{:,.0f}"),
                ("NIC\nUsage (%)",       anic1,  anic10,  True,  70,  "{:.1f}"),
            ]

        for idx, (label, v1, v10, lower, threshold, fmt) in enumerate(kpis):
            ax = axes[idx]; ax.set_facecolor(CARD)
            bars = ax.bar(["1G", "10G"], [v1, v10], color=[C1, C10],
                          width=0.5, edgecolor=BG, linewidth=1.5, zorder=3)
            top = max(v1, v10) if max(v1, v10) > 0 else 1
            if threshold:
                ax.axhline(threshold, color=YEL, lw=1.2, ls="--", alpha=0.8, zorder=4)
                if top * 1.15 > threshold:
                    ax.axhspan(threshold, top * 1.15, alpha=0.04, color=YEL)
            for bar, val in zip(bars, [v1, v10]):
                ax.text(bar.get_x() + bar.get_width() / 2,
                        bar.get_height() + top * 0.02,
                        fmt.format(val), ha="center", va="bottom",
                        color=TXT, fontsize=10, fontweight="bold")
            if lower:
                i_val = round((v1 - v10) / v1 * 100, 1) if v1 != 0 else 0
                txt   = f"-{i_val}%" if v1 != 0 else "N/A"
            else:
                i_val = round((v10 - v1) / v1 * 100, 1) if v1 != 0 else 0
                txt   = f"+{i_val}%" if v1 != 0 else "N/A"
            ax.text(0.5, 0.97, txt, transform=ax.transAxes,
                    ha="center", va="top", color=GRN, fontsize=13, fontweight="bold")
            ax.set_title(label, color=TXT, fontsize=11, fontweight="bold", pad=10)
            ax.set_facecolor(CARD)
            ax.tick_params(colors=TXT2, labelsize=9)
            for s in ["bottom", "left"]: ax.spines[s].set_color(GRID)
            ax.spines["top"].set_visible(False); ax.spines["right"].set_visible(False)
            ax.grid(axis="y", color=GRID, lw=0.5, alpha=0.6, ls="--")
            ax.set_xticks([0, 1])
            ax.set_xticklabels(["1G", "10G"], color=TXT, fontsize=11)
            ax.set_ylim(0, top * 1.28)
            ax.grid(axis="x", visible=False)

        plt.suptitle("Key KPI Summary — 1G vs 10G NIC",
                     color=TXT, fontsize=13, fontweight="bold", y=1.04)
        plt.tight_layout()
        plt.savefig(os.path.join(CHARTS_DIR, "chart_04_kpi_summary.png"),
                    dpi=150, bbox_inches="tight", facecolor=BG)
        plt.close(); print("  chart_04 OK")

    except ImportError:
        print("  [경고] matplotlib 없음 — pip install matplotlib")
    except Exception as e:
        import traceback; traceback.print_exc()
        print(f"  [오류] 차트 생성 실패: {e}")


# ═══════════════════════════════════════════════════════════
#  Notion API
# ═══════════════════════════════════════════════════════════
def notion_req(method, path, body=None, content_type="application/json"):
    if not NOTION_TOKEN:
        return None
    url  = "https://api.notion.com/v1" + path
    data = json.dumps(body).encode() if body else None
    req  = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization",  f"Bearer {NOTION_TOKEN}")
    req.add_header("Notion-Version", "2022-06-28")
    req.add_header("Content-Type",   content_type)
    try:
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        print(f"  Notion API 오류 {e.code}: {e.read().decode()[:300]}")
        return None


def upload_image_to_notion(page_id, img_path):
    """서버 스펙 이미지를 Notion 페이지에 업로드"""
    if not os.path.exists(img_path):
        return None
    try:
        mime, _ = mimetypes.guess_type(img_path)
        mime = mime or "image/png"
        fname = os.path.basename(img_path)
        # Step 1: file_upload 요청
        upload = notion_req("POST", "/file_uploads", {
            "name": fname, "content_type": mime
        })
        if not upload:
            return None
        upload_id = upload.get("id")
        upload_url = upload.get("upload_url")
        if not upload_id or not upload_url:
            return None
        # Step 2: multipart 업로드
        with open(img_path, "rb") as f:
            img_data = f.read()
        boundary = "----NotionBoundary12345"
        body_parts = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="{fname}"\r\n'
            f"Content-Type: {mime}\r\n\r\n"
        ).encode() + img_data + f"\r\n--{boundary}--\r\n".encode()
        req2 = urllib.request.Request(upload_url, data=body_parts, method="POST")
        req2.add_header("Authorization", f"Bearer {NOTION_TOKEN}")
        req2.add_header("Notion-Version", "2022-06-28")
        req2.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
        try:
            with urllib.request.urlopen(req2) as r:
                r.read()
        except urllib.error.HTTPError as e:
            print(f"  이미지 업로드 오류: {e.code}")
            return None
        # Step 3: 블록으로 첨부
        block = {
            "children": [{
                "object": "block",
                "type":   "image",
                "image":  {"type": "file_upload", "file_upload": {"id": upload_id}}
            }]
        }
        notion_req("PATCH", f"/blocks/{page_id}/children", block)
        print(f"  서버 스펙 이미지 업로드 OK: {fname}")
        return upload_id
    except Exception as e:
        print(f"  이미지 업로드 실패: {e}")
        return None


# ═══════════════════════════════════════════════════════════
#  Notion 페이지 생성
# ═══════════════════════════════════════════════════════════
def create_page(stats, has_hadr, spec_img_path=None):
    today = datetime.now().strftime("%Y-%m-%d")
    commit_mode = "SYNCHRONOUS_COMMIT" if has_hadr else "ASYNCHRONOUS_COMMIT"
    title = f"[AG 분석] NIC 1G vs 10G — {MODE} — {today}"

    # 모드별 개요 인사이트
    if has_hadr:
        overview = (
            f"동기 모드(SYNCHRONOUS_COMMIT)에서 **NIC 1G → 10G 업그레이드**는 "
            f"HADR 복제 대기시간과 처리량 양쪽에 직접적인 개선 효과를 보입니다.\n\n"
            f"- HADR avg_wait: {stats['wait_1g']:.3f}ms → {stats['wait_10g']:.3f}ms "
            f"({pct(stats['wait_1g'], stats['wait_10g'], lower_is_better=True)})\n"
            f"- Theoretical Max TPS: {int(stats['tps_1g']):,} → {int(stats['tps_10g']):,} "
            f"({pct(stats['tps_1g'], stats['tps_10g'])})\n"
            f"- NIC 사용률: {stats['nic_1g']:.1f}% → {stats['nic_10g']:.1f}% "
            f"({pct(stats['nic_1g'], stats['nic_10g'], lower_is_better=True)})\n\n"
            f"동기 모드에서는 Primary가 Secondary의 로그 수신을 대기하므로 "
            f"NIC 대역폭이 HADR wait을 통해 처리량을 직접 제한합니다."
        )
    else:
        overview = (
            f"비동기 모드(ASYNCHRONOUS_COMMIT)에서 **NIC 1G → 10G 업그레이드**는 "
            f"처리량(Batch/sec)에 거의 영향을 주지 않습니다.\n\n"
            f"- Batch/sec: {int(stats['bat_1g']):,} → {int(stats['bat_10g']):,} "
            f"({pct(stats['bat_1g'], stats['bat_10g'])}) — **변화 없음**\n"
            f"- NIC 사용률: {stats['nic_1g']:.1f}% → {stats['nic_10g']:.1f}% "
            f"({pct(stats['nic_1g'], stats['nic_10g'], lower_is_better=True)})\n\n"
            f"비동기 모드에서는 Primary가 Secondary 응답을 대기하지 않으므로 "
            f"NIC 대역폭이 처리량 병목이 아닙니다. "
            f"10G 업그레이드의 핵심 가치는 **향후 부하 증가 대비 NIC 여유 확보**입니다."
        )

    # NIC 여유 계산
    nic1_margin  = round(70 - stats["nic_1g_max"],  1)
    nic10_margin = round(70 - stats["nic_10g_max"], 1)
    cpu1_margin  = round(85 - stats["cpu_1g_max"],  1)
    cpu10_margin = round(85 - stats["cpu_10g_max"], 1)

    content = f"""## 📌 개요

{overview}

---

## 📋 테스트 정보

| 항목 | 내용 |
|---|---|
| 분석 모드 | {MODE} |
| AG 커밋 모드 | {commit_mode} |
| SQL Server | 2025 Preview |
| Windows Server | 2022 |
| 클러스터 | WSFC |
| Primary / Secondary | PFDB01 / PFDB02 |
| 부하 도구 | HammerDB |
| 분석 일시 | {today} |

---

## 📊 핵심 KPI 요약

> **왜 이 차트를 먼저 보나요?**
> 4개 핵심 지표를 막대 그래프로 한눈에 비교합니다. 각 막대 위 % = 1G 대비 10G 개선율. 노란 점선 = 위험 임계값.
>
> **읽는 법:** 막대 위 초록 퍼센트가 클수록 개선 효과가 큽니다. 노란 점선에 가까울수록 위험합니다.

![KPI Summary]({GH_BASE}/chart_04_kpi_summary.png)

| 지표 | 1G NIC | 10G NIC | 개선율 | 평가 |
|---|---|---|---|---|
| HADR avg_wait (ms) | {stats["wait_1g"]:.3f} | {stats["wait_10g"]:.3f} | {pct(stats["wait_1g"], stats["wait_10g"], True)} | {"✅" if has_hadr else "ℹ️ ASYNC=0ms 정상"} |
| Theoretical Max TPS | {int(stats["tps_1g"]):,} | {int(stats["tps_10g"]):,} | {pct(stats["tps_1g"], stats["tps_10g"])} | {"✅" if has_hadr else "ℹ️"} |
| Commits/sec | {int(stats["com_1g"]):,} | {int(stats["com_10g"]):,} | {pct(stats["com_1g"], stats["com_10g"])} | {"✅" if has_hadr else "ℹ️"} |
| Batch Requests/sec | {int(stats["bat_1g"]):,} | {int(stats["bat_10g"]):,} | {pct(stats["bat_1g"], stats["bat_10g"])} | ✅ |
| NIC 사용률 (%) | {stats["nic_1g"]:.1f} | {stats["nic_10g"]:.1f} | {pct(stats["nic_1g"], stats["nic_10g"], True)} | ✅ |
| CPU 사용률 (%) | {stats["cpu_1g"]:.1f} | {stats["cpu_10g"]:.1f} | — | ✅ |

{"" if not has_hadr else ""}
{"" if has_hadr else "> ⚠️ **Transaction Delay = 0ms**: ASYNCHRONOUS_COMMIT 모드의 정상 동작. Primary가 Secondary를 대기하지 않으므로 복제 관련 지연이 발생하지 않습니다."}

---

## 🔬 {"HADR 대기시간 심층 분석" if has_hadr else "처리량 안정성 분석"}

> **왜 이 차트인가요?**
> {"HADR avg_wait는 동기 모드에서 NIC 병목을 가장 직접 반영하는 지표입니다. 시계열로 전체 추이를, 히스토그램으로 분포 형태를 확인합니다." if has_hadr else "비동기 모드에서 HADR wait=0이므로 Batch/sec 시계열로 처리량 안정성을 확인합니다. 1G/10G 라인이 유사하면 NIC는 처리량 병목이 아닙니다."}
>
> **읽는 법:** 상단 시계열에서 추이와 변동폭을, 하단 히스토그램에서 분포 집중도를 비교하세요.

![Main Chart]({GH_BASE}/chart_01_main.png)

---

## 📈 처리량 비교

> **왜 이 차트인가요?**
> {"TPS / Commits/sec / Batch/sec 3가지 처리량 지표를 나란히 비교합니다. NIC 대역폭 해소가 각 지표에 미치는 복합 효과를 확인합니다." if has_hadr else "Batch/sec / CPU / Disk IOPS를 나란히 비교합니다. 처리량 변화가 없다면 NIC는 처리량 병목이 아님을 확인합니다."}
>
> **읽는 법:** 각 패널 상단 초록 % = 개선율. 라인 변동폭이 작을수록 안정적입니다.

![Throughput]({GH_BASE}/chart_02_throughput.png)

---

## 🖥️ 리소스 사용률 분석

> **왜 이 차트인가요?**
> CPU와 NIC 사용률을 시계열로 비교합니다. NIC 사용률 감소는 향후 부하 증가 시 병목 예방 여부를 판단하는 핵심 지표입니다.
>
> **읽는 법:** 빨간(1G) 라인이 노란 임계선에 얼마나 근접하는지, 파란(10G) 라인의 여유가 얼마나 큰지 비교하세요.

![CPU & NIC]({GH_BASE}/chart_03_cpu_nic.png)

| 리소스 | 임계값 | 1G 최대 | 10G 최대 | 1G 여유 | 10G 여유 | 상태 |
|---|---|---|---|---|---|---|
| NIC 사용률 | 70% | {stats["nic_1g_max"]:.1f}% | {stats["nic_10g_max"]:.1f}% | {nic1_margin}%p | {nic10_margin}%p | {"⚠️" if stats["nic_1g_max"] > 50 else "✅"} → ✅ |
| CPU | 85% | {stats["cpu_1g_max"]:.1f}% | {stats["cpu_10g_max"]:.1f}% | {cpu1_margin}%p | {cpu10_margin}%p | ✅ ✅ |

---

## 💡 결론 및 권고사항

### 핵심 요약

{overview}

### 추가 최적화 권고

| 항목 | 내용 | 기대 효과 |
|---|---|---|
| Jumbo Frame (MTU 9000) | 대용량 패킷 처리 효율화 | 네트워크 오버헤드 감소 |
| RSS/VMQ 활성화 | NIC 멀티코어 분산 처리 | NIC 처리 효율 향상 |
| HADR 전용 NIC 분리 | 복제 트래픽 격리 | 일반 트래픽과 간섭 제거 |

### 다음 단계 테스트 권고

- 부하 증가 테스트: 현재 대비 2x, 3x 부하에서 1G NIC 포화 시점 확인
- 25G NIC 업그레이드 효과 측정
- {"비동기 모드와의 처리량/대기시간 트레이드오프 비교" if has_hadr else "동기 모드에서의 NIC 업그레이드 효과와 비교 분석"}
"""

    body = {
        "parent":     {"page_id": PARENT_PAGE_ID},
        "icon":       {"type": "emoji", "emoji": "📊"},
        "properties": {"title": {"title": [{"text": {"content": title}}]}},
        "children":   [{"object": "block", "type": "paragraph",
                        "paragraph": {"rich_text": [{"type": "text", "text": {"content": content}}]}}]
    }
    result = notion_req("POST", "/pages", body)
    if not result:
        return None, None
    page_id  = result["id"]
    page_url = result.get("url", "")
    print(f"  페이지 생성 OK: {page_url}")

    # 서버 스펙 이미지 업로드
    if spec_img_path:
        print(f"  서버 스펙 이미지 업로드 시도: {spec_img_path}")
        upload_image_to_notion(page_id, spec_img_path)

    return page_url, page_id


# ═══════════════════════════════════════════════════════════
#  메인
# ═══════════════════════════════════════════════════════════
def main():
    print(f"\n{'='*50}\nAG 성능 분석 — {MODE}\n{'='*50}")
    if not NOTION_TOKEN:
        print("[경고] NOTION_TOKEN 환경변수 없음 — Notion 저장 건너뜀")

    files = find_csv()
    missing = [k for k in ["pdh_1g", "pdh_10g", "hadr"] if k not in files]
    if missing:
        print(f"[오류] CSV 파일 없음: {missing}"); return

    print(f"\n[1] CSV 파싱...")
    d1  = load_pdh(files["pdh_1g"],  1e9)
    d10 = load_pdh(files["pdh_10g"], 10e9)
    h1  = load_hadr(files["hadr"], f"{MODE}_1G_NIC")
    h10 = load_hadr(files["hadr"], f"{MODE}_10G_NIC")
    print(f"  1G PDH:{len(d1)}행  10G PDH:{len(d10)}행  HADR 1G:{len(h1)}행  HADR 10G:{len(h10)}행")

    # HADR 유효성 판별
    w1_vals  = clean([fv(r["avg_wait_per_commit_ms"]) for r in h1])
    w10_vals = clean([fv(r["avg_wait_per_commit_ms"]) for r in h10])
    aw1  = round(avg(w1_vals),  3)
    aw10 = round(avg(w10_vals), 3)
    has_hadr = len(w1_vals) > 0 and len(w10_vals) > 0 and (aw1 > 0 or aw10 > 0)
    print(f"  HADR wait 1G:{aw1}ms  10G:{aw10}ms  has_hadr={has_hadr}")

    # PDH 통계
    nic1  = [d["nic"] for d in d1];  nic10  = [d["nic"] for d in d10]
    cpu1  = clean([d["cpu"]   for d in d1]); cpu10  = clean([d["cpu"]   for d in d10])
    b1    = clean([d["batch"] for d in d1]); b10    = clean([d["batch"] for d in d10])

    # HADR 통계 (has_hadr일 때만)
    t1_vals = clean([fv(r["theoretical_max_tps"]) for r in h1])
    t10_vals= clean([fv(r["theoretical_max_tps"]) for r in h10])
    c1_vals = clean([fv(r["commits_per_sec"])     for r in h1])
    c10_vals= clean([fv(r["commits_per_sec"])     for r in h10])

    stats = {
        "wait_1g":     aw1,
        "wait_10g":    aw10,
        "tps_1g":      round(avg(t1_vals),  0),
        "tps_10g":     round(avg(t10_vals), 0),
        "com_1g":      round(avg(c1_vals),  0),
        "com_10g":     round(avg(c10_vals), 0),
        "bat_1g":      round(avg(b1),       0),
        "bat_10g":     round(avg(b10),      0),
        "cpu_1g":      round(avg(cpu1),     1),
        "cpu_10g":     round(avg(cpu10),    1),
        "cpu_1g_max":  round(max(cpu1)  if cpu1  else 0, 1),
        "cpu_10g_max": round(max(cpu10) if cpu10 else 0, 1),
        "nic_1g":      round(avg(nic1),     1),
        "nic_10g":     round(avg(nic10),    1),
        "nic_1g_max":  round(max(nic1)  if nic1  else 0, 1),
        "nic_10g_max": round(max(nic10) if nic10 else 0, 1),
    }

    print(f"\n[2] 차트 생성...")
    make_charts(d1, d10, h1, h10, has_hadr)

    print(f"\n[3] git push...")
    os.chdir(BASE_DIR)
    subprocess.run("git add -A", shell=True)
    subprocess.run(f'git commit -m "[{MODE}] 차트 업데이트"', shell=True)
    r = subprocess.run("git push", shell=True, capture_output=True, text=True)
    print("  git push:", "OK" if r.returncode == 0 else r.stderr.strip())

    if NOTION_TOKEN:
        print(f"\n[4] Notion 페이지 생성...")
        spec = files.get("spec_img")
        url, _ = create_page(stats, has_hadr, spec_img_path=spec)
        print(f"\n{'='*50}\n완료! {url}\n{'='*50}\n")
    else:
        print(f"\n{'='*50}\n차트 생성/push 완료 (Notion 건너뜀)\n{'='*50}\n")


if __name__ == "__main__":
    main()
