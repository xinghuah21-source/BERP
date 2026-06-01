# Check PostgreSQL port
try {
    $tcp = New-Object System.Net.Sockets.TcpClient
    $tcp.Connect("localhost", 5432)
    Write-Host "✓ PostgreSQL is running on port 5432"
    $tcp.Close()
} catch {
    Write-Host "✗ Failed: PostgreSQL port 5432 is not reachable"
    exit 1
}

# Check Redis port
try {
    $tcp = New-Object System.Net.Sockets.TcpClient
    $tcp.Connect("localhost", 6379)
    Write-Host "✓ Redis is running on port 6379"
    $tcp.Close()
} catch {
    Write-Host "✗ Failed: Redis port 6379 is not reachable"
    exit 1
}

# Check PostgreSQL database access
$dbCheck = docker exec berp_postgres pg_isready -U recitation -d recitation
if ($LASTEXITCODE -eq 0) {
    Write-Host "✓ Database 'recitation' is accessible"
} else {
    Write-Host "✗ Failed: Database 'recitation' is not accessible"
    exit 1
}

exit 0
