"""
Claude가 생성한 base64 CSV 데이터를 PC에 저장하는 스크립트
Claude가 자동으로 이 파일을 업데이트하고 실행합니다
"""
import base64, os, json, sys

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
os.makedirs(DATA_DIR, exist_ok=True)

# Claude가 이 딕셔너리를 자동으로 채워넣습니다
CSV_DATA = {}

for name, b64 in CSV_DATA.items():
    path = os.path.join(DATA_DIR, name)
    with open(path, 'wb') as f:
        f.write(base64.b64decode(b64))
    print(f"저장 완료: {path}")

print("모든 CSV 저장 완료!")
