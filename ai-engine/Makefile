.PHONY: install run test

PYTHON = E:\ANACONDA\envs\BERP\python.exe
PIP = E:\ANACONDA\envs\BERP\Scripts\pip.exe

install:
	@echo "Installing dependencies..."
	$(PIP) install -r requirements.txt
	@echo "Downloading Whisper base model (this may take a while)..."
	$(PYTHON) -c "import whisper; whisper.load_model('base', download_root='./models')"
	@echo "Install complete!"

run:
	@echo "Starting AI Engine on port 8001..."
	$(PYTHON) main.py

test:
	@echo "Testing Health Endpoint..."
	curl http://localhost:8001/health
	@echo "\n\nTesting Evaluate Endpoint..."
	curl -X POST http://localhost:8001/evaluate -H "Content-Type: application/json" -d '{"audio_base64":"data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEARKwAAIhYAQACABAAZGF0YQAAAAA=", "standard_text":"春眠不觉晓"}'
