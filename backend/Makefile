.PHONY: db-migrate db-seed run

PYTHON = E:\ANACONDA\envs\BERP\python.exe
ALEMBIC = E:\ANACONDA\envs\BERP\Scripts\alembic.exe

db-migrate:
	@echo "Generating and running migrations..."
	$(ALEMBIC) revision --autogenerate -m "initial"
	$(ALEMBIC) upgrade head

db-seed:
	@echo "Seeding database..."
	$(PYTHON) scripts/seed.py

run:
	@echo "Starting FastAPI server..."
	$(PYTHON) -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
