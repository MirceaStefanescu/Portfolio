.PHONY: dev down logs rotate-secret test unit-test integration-test

dev:
	docker compose up --build

down:
	docker compose down -v

logs:
	docker compose logs -f --tail=200

rotate-secret:
	docker compose run --rm --entrypoint /init/rotate-secret.sh vault-init

test: unit-test integration-test

unit-test:
	docker build --target test --progress=plain ./app

integration-test:
	bash tests/test-vault.sh

policy:
	python ../scripts/check-policy.py .
