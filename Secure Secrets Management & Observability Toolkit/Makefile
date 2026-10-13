.PHONY: dev down logs rotate-secret test

dev:
	docker compose up --build

down:
	docker compose down -v

logs:
	docker compose logs -f --tail=200

rotate-secret:
	docker compose run --rm --entrypoint /init/rotate-secret.sh vault-init

test:
	docker build --target test --progress=plain ./app
