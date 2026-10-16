.PHONY: dev down test lint policy

dev:
	docker compose up --build

down:
	docker compose down

test:
	./scripts/test.sh

lint:
	./scripts/lint.sh

policy:
	python ../scripts/check-policy.py .
