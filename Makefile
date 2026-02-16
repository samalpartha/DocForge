.PHONY: setup backend cli generate demo clean help

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

setup: ## One-command full setup (backend + CLI)
	@echo "\n  Setting up DocForge CLI...\n"
	@cd backend && python3 -m venv .venv && \
		. .venv/bin/activate && pip install -q -r requirements.txt
	@test -f backend/.env || cp backend/.env.example backend/.env && \
		echo "  Created backend/.env from .env.example — edit with your Foxit keys"
	@cd cli && npm install --silent
	@echo "\n  Setup complete. Run: make backend  (then in another terminal: make demo)\n"

backend: ## Start the FastAPI backend
	@cd backend && . .venv/bin/activate && uvicorn app.main:app --reload

cli: ## Link CLI globally (optional)
	@cd cli && npm link

generate: ## Generate PDF from examples/release.json
	@cd cli && node src/index.js generate ../examples/release.json --out ../output.pdf

demo: ## Full demo: generate with DRAFT watermark + password
	@cd cli && node src/index.js generate ../examples/release.json \
		--watermark "DRAFT" \
		--password "docforge2026" \
		--out ../demo-output.pdf

clean: ## Remove generated PDFs and build artifacts
	@rm -f *.pdf output*.pdf demo-output.pdf
	@rm -rf backend/.venv backend/app/__pycache__ backend/app/**/__pycache__
	@rm -rf cli/node_modules
	@echo "  Cleaned."
