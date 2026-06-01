.PHONY: start stop test logs

start:
	powershell -ExecutionPolicy Bypass -File .\start.ps1

stop:
	powershell -ExecutionPolicy Bypass -File .\stop.ps1

test:
	powershell -ExecutionPolicy Bypass -File .\test-integration.ps1

logs:
	docker compose -f docker-compose.full.yml logs -f
