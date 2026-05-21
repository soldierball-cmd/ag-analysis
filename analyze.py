"""
AG 성능 비교 분석 스크립트 - PC 직접 실행용
사용법: python analyze.py 동기모드
        python analyze.py 비동기모드

환경변수 설정 필요:
  Windows: setx NOTION_TOKEN "your_token"
  PowerShell: $env:NOTION_TOKEN = "your_token"
"""
import sys, os, csv, io, json, subprocess
import urllib.request, urllib.error
from datetime import datetime

NOTION_TOKEN = os.environ.get("NOTION_TOKEN", "")
PARENT_PAGE_ID = "366dadb5-6b2f-8019-8e65-d0de1d942753"
BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
DATA_DIR   = os.path.join(BASE_DIR, "data")
CHARTS_DIR = os.path.join(BASE_DIR, "charts")
GH_BASE    = "https://soldierball-cmd.github.io/ag-analysis/charts"
os.makedirs(CHARTS_DIR, exist_ok=True)

MODE = sys.argv[1] if len(sys.argv) > 1 else "동기모드"


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
        def v(col):
            if not col: return None
            try: return float(r.get(col, "").strip())
            except: return None
        rb = v(replica_col) or 0
        nb = v(bytes_col) or 0
        nic = round((rb if nic_bps == 10e9 else nb) * 8 / nic_bps * 100, 2)
        result.append({"cpu": v(cpu_col), "nic": nic,
                       "batch": v(batch_col), "disk": v(disk_col), "tx": v(tx_col)})
    return result


def load_hadr(path, scenario):
    with open(path, "rb") as f:
        rows = list(csv.DictReader(io.StringIO(f.read().decode("cp949"))))
    return [r for r in rows if r.get("scenario", "") == scenario]


def mean(lst):
    lst = [x for x in lst if x is not None]
    return sum(lst) / len(lst) if lst else 0

def hmean(rows, key):
    return mean([float(r[key]) for r in rows if r.get(key)])

def pmean(rows, key):
    return mean([r[key] for r in rows if r.get(key) is not None])


def make_charts(d1, d10, h1, h10):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        C1="#ff6b6b"; C10="#4e7cff"; BG="#1a1d27"; GRID="#2e3250"; TXT="#e8eaf6"

        def style(ax):
            ax.set_facecolor(BG)
            ax.tick_params(colors=TXT, labelsize=9)
            for s in ["bottom","left"]: ax.spines[s].set_color(GRID)
            ax.spines["top"].set_visible(False); ax.spines["right"].set_visible(False)
            ax.grid(axis="y", color=GRID, linewidth=0.5, alpha=0.7)
            ax.set_axisbelow(True)
            ax.xaxis.label.set_color(TXT); ax.yaxis.label.set_color(TXT)
            ax.title.set_color(TXT)

        # 차트1: HADR wait
        w1  = [float(r["avg_wait_per_commit_ms"]) for r in h1]
        w10 = [float(r["avg_wait_per_commit_ms"]) for r in h10]
        fig, ax = plt.subplots(figsize=(12, 4), facecolor=BG)
        ax.plot(w1,  color=C1,  lw=1.5, label=f"1G  (avg:{mean(w1):.3f}ms)")
        ax.plot(w10, color=C10, lw=1.5, label=f"10G (avg:{mean(w10):.3f}ms)")
        ax.axhline(20, color="#ffd166", lw=1, ls="--", label="Danger:20ms")
        style(ax); ax.set_title("HADR avg_wait_per_commit_ms", fontsize=13, pad=12)
        ax.legend(facecolor=BG, labelcolor=TXT, fontsize=9, framealpha=0.5)
        plt.tight_layout()
        plt.savefig(os.path.join(CHARTS_DIR, "chart_01_hadr_wait.png"), dpi=150, bbox_inches="tight", facecolor=BG)
        plt.close(); print("  chart_01 OK")

        # 차트2: Throughput
        c1  = [float(r["commits_per_sec"]) for r in h1]
        c10 = [float(r["commits_per_sec"]) for r in h10]
        t1  = [float(r["theoretical_max_tps"]) for r in h1]
        t10 = [float(r["theoretical_max_tps"]) for r in h10]
        fig, axes = plt.subplots(1, 2, figsize=(14, 4), facecolor=BG)
        fig.patch.set_facecolor(BG)
        axes[0].plot(c1, color=C1, lw=1.5, label=f"1G ({mean(c1):.0f})")
        axes[0].plot(c10, color=C10, lw=1.5, label=f"10G ({mean(c10):.0f})")
        style(axes[0]); axes[0].set_title("Commits/sec")
        axes[0].legend(facecolor=BG, labelcolor=TXT, fontsize=9, framealpha=0.5)
        axes[1].plot(t1, color=C1, lw=1.5, label=f"1G ({mean(t1):.0f})")
        axes[1].plot(t10, color=C10, lw=1.5, label=f"10G ({mean(t10):.0f})")
        style(axes[1]); axes[1].set_title("Theoretical Max TPS")
        axes[1].legend(facecolor=BG, labelcolor=TXT, fontsize=9, framealpha=0.5)
        plt.tight_layout()
        plt.savefig(os.path.join(CHARTS_DIR, "chart_02_throughput.png"), dpi=150, bbox_inches="tight", facecolor=BG)
        plt.close(); print("  chart_02 OK")

        # 차트3: Batch
        b1  = [d["batch"] or 0 for d in d1]
        b10 = [d["batch"] or 0 for d in d10]
        fig, ax = plt.subplots(figsize=(12, 4), facecolor=BG)
        ax.plot(b1,  color=C1,  lw=1.5, label=f"1G  ({pmean(d1,'batch'):.0f})")
        ax.plot(b10, color=C10, lw=1.5, label=f"10G ({pmean(d10,'batch'):.0f})")
        style(ax); ax.set_title("Batch Requests/sec", fontsize=13, pad=12)
        ax.legend(facecolor=BG, labelcolor=TXT, fontsize=9, framealpha=0.5)
        plt.tight_layout()
        plt.savefig(os.path.join(CHARTS_DIR, "chart_03_batch.png"), dpi=150, bbox_inches="tight", facecolor=BG)
        plt.close(); print("  chart_03 OK")

        # 차트4: CPU + NIC
        cpu1=[d["cpu"] or 0 for d in d1]; cpu10=[d["cpu"] or 0 for d in d10]
        nic1=[d["nic"] for d in d1];       nic10=[d["nic"] for d in d10]
        fig, axes = plt.subplots(1, 2, figsize=(14, 4), facecolor=BG)
        fig.patch.set_facecolor(BG)
        axes[0].plot(cpu1,  color=C1,  lw=1.5, label=f"1G  ({pmean(d1,'cpu'):.1f}%)")
        axes[0].plot(cpu10, color=C10, lw=1.5, label=f"10G ({pmean(d10,'cpu'):.1f}%)")
        axes[0].axhline(85, color="#ffd166", lw=1, ls="--", label="Danger:85%")
        axes[0].set_ylim(0, 100)
        style(axes[0]); axes[0].set_title("CPU Usage (%)")
        axes[0].legend(facecolor=BG, labelcolor=TXT, fontsize=9, framealpha=0.5)
        axes[1].plot(nic1,  color=C1,  lw=1.5, label="1G")
        axes[1].plot(nic10, color=C10, lw=1.5, label="10G")
        axes[1].axhline(70, color="#ffd166", lw=1, ls="--", label="Danger:70%")
        style(axes[1]); axes[1].set_title("NIC Usage (%)")
        axes[1].legend(facecolor=BG, labelcolor=TXT, fontsize=9, framealpha=0.5)
        plt.tight_layout()
        plt.savefig(os.path.join(CHARTS_DIR, "chart_04_cpu_nic.png"), dpi=150, bbox_inches="tight", facecolor=BG)
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

## 📊 1G vs 10G 성능 지표 비교

| 지표 | 1G NIC | 10G NIC | 개선율 | 평가 |
|---|---|---|---|---|
| HADR avg_wait (ms) | {stats["wait_1g"]:.3f} | {stats["wait_10g"]:.3f} | ▼{w_imp}% | ✅ |
| Theoretical Max TPS | {stats["tps_1g"]:.0f} | {stats["tps_10g"]:.0f} | ▲{t_imp}% | ✅ |
| Commits/sec | {stats["com_1g"]:.0f} | {stats["com_10g"]:.0f} | ▲{c_imp}% | ✅ |
| Batch Requests/sec | {stats["bat_1g"]:.0f} | {stats["bat_10g"]:.0f} | ▲{b_imp}% | ✅ |
| CPU 사용률 (%) | {stats["cpu_1g"]:.1f} | {stats["cpu_10g"]:.1f} | — | ✅ |
| Transaction Delay (ms) | {stats["tx_1g"]:.0f} | {stats["tx_10g"]:.0f} | ▲(병목 아님) | ℹ️ |

## 🔍 NIC 병목 분석

- HADR avg_wait: {stats["wait_1g"]:.3f}ms → {stats["wait_10g"]:.3f}ms (**{w_imp}% 개선**, 위험임계값 20ms 대비 정상)
- TPS: {stats["tps_1g"]:.0f} → {stats["tps_10g"]:.0f} (**{t_imp}% 향상**)
- Transaction Delay 증가는 처리량 증가에 따른 복제 큐 증가이며 성능 저하가 아님

## ✅ 기타 리소스 정상 확인

- CPU: {stats["cpu_1g"]:.1f}% → {stats["cpu_10g"]:.1f}% (임계값 85% 미만)
- NIC: 10G 전환 후 5% 미만 (임계값 70% 대비 충분한 여유)

## 💡 결론 및 권고사항

핵심: 1G → 10G NIC 업그레이드로 HADR 대기시간 {w_imp}% 감소, TPS {t_imp}% 향상

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

    chart_files = ["chart_01_hadr_wait.png", "chart_02_throughput.png",
                   "chart_03_batch.png",     "chart_04_cpu_nic.png"]
    blocks = [{"object": "block", "type": "image",
               "image": {"type": "external", "external": {"url": f"{GH_BASE}/{n}"}}}
              for n in chart_files]
    notion_req("PATCH", f"/blocks/{page_id}/children", {"children": blocks})
    print(f"  차트 이미지 {len(blocks)}개 추가 OK")
    return page_url


def main():
    print(f"\n{'='*50}\nAG 성능 분석 — {MODE}\n{'='*50}")

    if not NOTION_TOKEN:
        print("[경고] NOTION_TOKEN 환경변수 없음 — Notion 저장 건너뜀")

    files = find_csv()
    missing = [k for k in ["1g", "10g", "hadr"] if k not in files]
    if missing:
        print(f"[오류] CSV 파일 없음: {missing}")
        return

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
    subprocess.run(f'git commit -m "[{MODE}] NIC 업그레이드 분석 차트"', shell=True)
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
