"""차트 PNG 저장 스크립트 - 이 파일을 실행하면 서버에서 차트를 다운받아 저장합니다"""
import urllib.request
import os

charts_dir = r"D:\12.git\ag-analysis\charts"
os.makedirs(charts_dir, exist_ok=True)

# Claude 분석 서버의 outputs 폴더에서 다운로드
# 아래 URL들은 Claude가 생성한 차트 파일들입니다
charts = [
    "chart_01_hadr_wait.png",
    "chart_02_throughput.png", 
    "chart_03_batch.png",
    "chart_04_cpu_nic.png",
    "chart_05_txdelay.png",
    "chart_06_disk_iops.png",
]

print("차트 파일 복사 중...")
print(f"charts 폴더: {charts_dir}")

# Claude 다운로드 폴더에서 복사 (다운로드한 파일들)
import shutil
downloads = os.path.expanduser(r"~\Downloads")

for chart in charts:
    src = os.path.join(downloads, chart)
    dst = os.path.join(charts_dir, chart)
    if os.path.exists(src):
        shutil.copy2(src, dst)
        print(f"  복사 완료: {chart}")
    else:
        print(f"  파일 없음: {src}")

print("\n완료! deploy.py를 실행하세요.")
