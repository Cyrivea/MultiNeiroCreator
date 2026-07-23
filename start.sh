后端启动：
Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }
cd e:\Code_Project\MultiNeiroCreator\backend
$env:PYTHONDONTWRITEBYTECODE='1'
python -m uvicorn main:app --host 127.0.0.1 --port 8000


ssh root@47.79.85.117

# !xs7W/86RFUhBfd

