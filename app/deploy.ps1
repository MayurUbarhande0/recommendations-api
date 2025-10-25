# Ultra-Optimized Deployment Script for Windows
# This runs multiple Uvicorn processes behind a simple load balancer

Write-Host "🚀 Starting Ultra-Optimized API Deployment" -ForegroundColor Green

# Configuration
$BASE_PORT = 8000
$NUM_WORKERS = 4  # Adjust based on CPU cores
$PORTS = @()

# Kill existing processes
Write-Host "`n🧹 Cleaning up existing processes..." -ForegroundColor Yellow
Get-Process -Name "python" -ErrorAction SilentlyContinue | Where-Object {
    $_.CommandLine -like "*uvicorn*"
} | Stop-Process -Force

# Start workers
Write-Host "`n🔧 Starting $NUM_WORKERS worker processes..." -ForegroundColor Cyan

for ($i = 0; $i -lt $NUM_WORKERS; $i++) {
    $port = $BASE_PORT + $i
    $PORTS += $port
    
    Write-Host "  ✓ Starting worker on port $port" -ForegroundColor Green
    
    Start-Process powershell -ArgumentList @"
    -NoExit
    -Command "& {
        Write-Host 'Worker $i on port $port' -ForegroundColor Cyan;
        python -m uvicorn app.main:app --host 0.0.0.0 --port $port --limit-concurrency 500 --timeout-keep-alive 5 --backlog 2048 --no-access-log
    }"
"@
    
    Start-Sleep -Seconds 2
}

Write-Host "`n✅ All workers started!" -ForegroundColor Green
Write-Host "`nWorker ports: $($PORTS -join ', ')" -ForegroundColor White
Write-Host "`n💡 Use Nginx or HAProxy to load balance across these ports" -ForegroundColor Yellow
Write-Host "   Or test individual workers at: http://localhost:$BASE_PORT, http://localhost:$($BASE_PORT+1), etc." -ForegroundColor Yellow

# Optional: Start a simple Python load balancer
Write-Host "`n🔄 Starting simple round-robin load balancer on port 9000..." -ForegroundColor Cyan

$LoadBalancerScript = @"
from http.server import HTTPServer, BaseHTTPRequestHandler
import requests
from itertools import cycle

BACKENDS = ['http://localhost:{0}', 'http://localhost:{1}', 'http://localhost:{2}', 'http://localhost:{3}']
backend_cycle = cycle(BACKENDS)

class LoadBalancer(BaseHTTPRequestHandler):
    def do_GET(self):
        backend = next(backend_cycle)
        try:
            resp = requests.get(backend + self.path, timeout=30)
            self.send_response(resp.status_code)
            for key, value in resp.headers.items():
                if key.lower() not in ['transfer-encoding', 'connection']:
                    self.send_header(key, value)
            self.end_headers()
            self.wfile.write(resp.content)
        except Exception as e:
            self.send_error(502, str(e))
    
    def log_message(self, format, *args):
        pass  # Disable logging

print('🔄 Load balancer running on http://localhost:9000')
print(f'   Balancing across: {BACKENDS}')
HTTPServer(('0.0.0.0', 9000), LoadBalancer).serve_forever()
"@ -f $PORTS[0], $PORTS[1], $PORTS[2], $PORTS[3]

$LoadBalancerScript | Out-File -FilePath "load_balancer.py" -Encoding UTF8

Start-Process powershell -ArgumentList @"
    -NoExit
    -Command "& {
        Write-Host 'Load Balancer on port 9000' -ForegroundColor Magenta;
        python load_balancer.py
    }"
"@

Write-Host "`n✨ Deployment Complete!" -ForegroundColor Green
Write-Host "`n📊 Test endpoints:" -ForegroundColor White
Write-Host "   Load Balanced: http://localhost:9000/health" -ForegroundColor Cyan
Write-Host "   Direct Workers: http://localhost:$BASE_PORT/health ... http://localhost:$($BASE_PORT+$NUM_WORKERS-1)/health" -ForegroundColor Cyan
Write-Host "`n🧪 Run Locust test:" -ForegroundColor White
Write-Host "   locust -f locustfile.py --host=http://localhost:9000" -ForegroundColor Yellow