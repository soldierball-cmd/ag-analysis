@echo off
:: AG 분석 자동화 감시 스크립트 시작
:: 이 파일을 Windows 시작 프로그램에 등록하면 PC 켤 때 자동 실행됩니다

cd /d D:\12.git\ag-analysis
pip install watchdog -q 2>nul
start "AG 분석 자동화" /min python watcher.py
