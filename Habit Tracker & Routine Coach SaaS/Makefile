.PHONY: dev test demo down

dev:
	@echo "Run backend: (cd backend && npm ci && npm run dev)"
	@echo "Run frontend: (cd frontend && npm ci && npm run dev)"

test:
	cd backend && npm ci && npm test
	cd frontend && npm ci && npm test && npm run build

demo:
	docker compose up -d --build

down:
	docker compose down
