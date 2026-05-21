"""
AG 분석 자동화 감시 스크립트
- data/ 폴더에 CSV 파일이 생기면 자동으로 analyze_and_deploy.py 실행
- PC 시작 시 자동 실행되도록 설정 가능

실행: python watcher.py
"""
import time
import os
import subprocess
import logging
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# ── 설정 ─────────────────────────────────────────────
BASE_DIR  = Path(__file__).parent
DATA_DIR  = BASE_DIR / "data"
LOG_FILE  = BASE_DIR / "watcher.log"
SCRIPT    = BASE_DIR / "analyze_and_deploy.py"

# CSV 파일명 패턴
REQUIRED = {
    "1g":   lambda f: "1g" in f.lower() and "hadr" not in f.lower() and f.endswith(".csv"),
    "10g":  lambda f: "10g" in f.lower() and "hadr" not in f.lower() and f.endswith(".csv"),
    "hadr": lambda f: "hadr" in f.lower() and f.endswith(".csv"),
}

# ── 로깅 설정 ─────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler()
    ]
)
log = logging.getLogger(__name__)

# ── 파일 탐색 ─────────────────────────────────────────
def find_csv():
    """data 폴더에서 1G, 10G, HADR CSV 자동 탐색"""
    found = {}
    for f in os.listdir(DATA_DIR):
        fl = f.lower()
        if REQUIRED["1g"](fl) and "1g" not in found:
            found["1g"] = str(DATA_DIR / f)
        elif REQUIRED["10g"](fl) and "10g" not in found:
            found["10g"] = str(DATA_DIR / f)
        elif REQUIRED["hadr"](fl) and "hadr" not in found:
            found["hadr"] = str(DATA_DIR / f)
    return found

# ── 분석 실행 ─────────────────────────────────────────
def run_analysis():
    found = find_csv()
    if len(found) < 3:
        missing = [k for k in ["1g","10g","hadr"] if k not in found]
        log.warning(f"CSV 파일 부족 — 누락: {missing}")
        return

    log.info("=" * 50)
    log.info("✅ CSV 3개 감지! 자동 분석 시작...")
    log.info(f"  1G  : {found['1g']}")
    log.info(f"  10G : {found['10g']}")
    log.info(f"  HADR: {found['hadr']}")

    cmd = [
        "python",
        str(SCRIPT),
        found["1g"],
        found["10g"],
        found["hadr"],
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=str(BASE_DIR),
            timeout=300  # 5분 타임아웃
        )
        if result.stdout:
            log.info(result.stdout)
        if result.returncode == 0:
            log.info("🎉 분석 완료! Notion 페이지 생성됨")
        else:
            log.error(f"❌ 오류 발생:\n{result.stderr}")
    except subprocess.TimeoutExpired:
        log.error("❌ 타임아웃 (5분 초과)")
    except Exception as e:
        log.error(f"❌ 예외 발생: {e}")

# ── 파일 감시 핸들러 ──────────────────────────────────
class CsvHandler(FileSystemEventHandler):
    def __init__(self):
        self.last_run = 0
        self.cooldown = 10  # 10초 쿨다운 (중복 실행 방지)

    def on_created(self, event):
        if event.is_directory:
            return
        if event.src_path.lower().endswith(".csv"):
            now = time.time()
            if now - self.last_run < self.cooldown:
                return
            self.last_run = now
            log.info(f"📂 새 CSV 감지: {os.path.basename(event.src_path)}")
            time.sleep(2)  # 파일 쓰기 완료 대기
            run_analysis()

    def on_modified(self, event):
        self.on_created(event)

# ── 메인 ─────────────────────────────────────────────
def main():
    DATA_DIR.mkdir(exist_ok=True)
    log.info("=" * 50)
    log.info("🚀 AG 분석 자동화 감시 시작!")
    log.info(f"   감시 폴더: {DATA_DIR}")
    log.info(f"   로그 파일: {LOG_FILE}")
    log.info("   CSV 3개 (1G, 10G, HADR)가 data/ 폴더에 복사되면 자동 실행됩니다.")
    log.info("=" * 50)

    # 이미 파일이 있으면 바로 실행
    found = find_csv()
    if len(found) == 3:
        log.info("기존 CSV 파일 발견! 즉시 분석 시작...")
        run_analysis()

    handler = CsvHandler()
    observer = Observer()
    observer.schedule(handler, str(DATA_DIR), recursive=False)
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        log.info("감시 중지됨")
        observer.stop()
    observer.join()

if __name__ == "__main__":
    main()
