.PHONY: infra-up infra-down infra-logs infra-check backend-run backend-migrate backend-seed ai-install ai-run ai-test

DOCKER_COMPOSE = docker-compose -f docker-compose.base.yml
CONDA_PYTHON = E:\ANACONDA\envs\BERP\python.exe

infra-up:
	@echo "Starting infrastructure..."
	$(DOCKER_COMPOSE) up -d

infra-down:
	@echo "Stopping infrastructure and cleaning volumes..."
	$(DOCKER_COMPOSE) down -v

infra-logs:
	$(DOCKER_COMPOSE) logs -f

infra-check:
	@echo "Running health checks..."
	@.\scripts\health_check.ps1

backend-run:
	@cd backend && $(CONDA_PYTHON) run.py

backend-migrate:
	@cd backend && make db-migrate

backend-seed:
	@cd backend && make db-seed

ai-install:
	@cd ai-engine && make install

ai-run:
	@cd ai-engine && $$env:PATH="E:\game\BERP\ai-engine\ffmpeg\ffmpeg-master-latest-win64-gpl\bin;" + $$env:PATH; make run

ai-test:
	@cd ai-engine && make test
