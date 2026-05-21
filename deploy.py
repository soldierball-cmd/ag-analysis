"""
AG 분석 자동화 배포 스크립트
실행: python deploy.py
"""
import subprocess
import sys
import os
import urllib.request
import urllib.parse
import json
import base64

NOTION_TOKEN = os.environ.get("NOTION_TOKEN", "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")
NOTION_PARENT_PAGE_ID = "366dadb56b2f80198e65d0de1d942753"
GITHUB_PAGES_URL = "https://soldierball-cmd.github.io/ag-analysis/"
REPO_PATH = r"D:\12.git\ag-analysis"

def run(cmd, cwd=None):
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=cwd or REPO_PATH)
    if result.returncode != 0:
        print(f"ERROR: {result.stderr}")
    else:
        print(result.stdout.strip())
    return result.returncode == 0

def git_push():
    print("\n=== GitHub 배포 중 ===")
    run("git add -A")
    run('git commit -m "Update AG analysis charts and report"')
    return run("git push")

def notion_api(method, endpoint, body=None):
    url = f"https://api.notion.com/v1/{endpoint}"
    headers = {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28"
    }
    data = json.dumps(body).encode("utf-8") if body else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req) as res:
        return json.loads(res.read().decode("utf-8"))

def create_notion_page(title, content_blocks):
    print(f"\n=== Notion 페이지 생성: {title} ===")
    page = notion_api("POST", "pages", {
        "parent": {"page_id": NOTION_PARENT_PAGE_ID},
        "properties": {
            "title": [{"type": "text", "text": {"content": title}}]
        }
    })
    page_id = page["id"]
    print(f"페이지 생성 완료: {page['url']}")

    # 블록 추가
    notion_api("PATCH", f"blocks/{page_id}/children", {"children": content_blocks})
    print("컨텐츠 추가 완료!")
    return page["url"]

def image_block(url, caption=""):
    return {
        "object": "block",
        "type": "image",
        "image": {
            "type": "external",
            "external": {"url": url},
            "caption": [{"type": "text", "text": {"content": caption}}]
        }
    }

def heading_block(text, level=2):
    return {
        "object": "block",
        "type": f"heading_{level}",
        f"heading_{level}": {
            "rich_text": [{"type": "text", "text": {"content": text}}]
        }
    }

def paragraph_block(text):
    return {
        "object": "block",
        "type": "paragraph",
        "paragraph": {
            "rich_text": [{"type": "text", "text": {"content": text}}]
        }
    }

def divider_block():
    return {"object": "block", "type": "divider", "divider": {}}

if __name__ == "__main__":
    # 1. git push
    git_push()

    # 2. Notion 새 페이지 생성
    from datetime import datetime
    today = datetime.now().strftime("%Y-%m-%d")
    title = f"[AG 비교분석] NIC 업그레이드 효과 검증 — {today}"

    blocks = [
        heading_block("📋 테스트 환경", 2),
        paragraph_block("SQL Server 2025 Preview / Windows Server 2022 / SYNCHRONOUS_COMMIT / WSFC\nPrimary: PFDB01 → Secondary: PFDB02 / 부하도구: HAMMERDB"),
        divider_block(),
        heading_block("🏆 핵심 성과 KPI", 2),
        paragraph_block("HADR avg_wait: 0.722ms → 0.348ms (▼51.8%) | TPS: 1,386 → 2,894 (▲108.8%) | Batch/sec: 1,612 → 3,669 (▲127.5%)"),
        divider_block(),
        heading_block("📊 인터랙티브 분석 대시보드", 2),
        paragraph_block(f"전체화면 보기: {GITHUB_PAGES_URL}"),
        divider_block(),
        heading_block("📈 차트", 2),
        image_block(f"{GITHUB_PAGES_URL}charts/chart_01_hadr_wait.png", "HADR avg_wait 시계열 (1G vs 10G)"),
        image_block(f"{GITHUB_PAGES_URL}charts/chart_02_throughput.png", "처리량 비교 (Commits/sec + TPS)"),
        image_block(f"{GITHUB_PAGES_URL}charts/chart_03_batch.png", "Batch Requests/sec"),
        image_block(f"{GITHUB_PAGES_URL}charts/chart_04_cpu_nic.png", "CPU + NIC 사용률"),
        image_block(f"{GITHUB_PAGES_URL}charts/chart_05_txdelay.png", "Transaction Delay"),
        image_block(f"{GITHUB_PAGES_URL}charts/chart_06_disk_iops.png", "Disk IOPS"),
        divider_block(),
        heading_block("🏁 결론", 2),
        paragraph_block("1G → 10G NIC 업그레이드는 SYNCHRONOUS_COMMIT 환경에서 HADR 대기시간 51.8% 감소, TPS 108.8% 증가의 유의미한 성능 개선 효과를 가져왔습니다."),
    ]

    url = create_notion_page(title, blocks)
    print(f"\n✅ 완료! Notion 페이지: {url}")
