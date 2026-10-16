.PHONY: dev build sbom scan sign store verify test down clean

dev:
	./scripts/pipeline.sh dev

build:
	./scripts/pipeline.sh build

sbom:
	./scripts/pipeline.sh sbom

scan:
	./scripts/pipeline.sh scan

sign:
	./scripts/pipeline.sh sign

store:
	./scripts/pipeline.sh store

verify:
	./scripts/pipeline.sh verify

test:
	bash scripts/test-pipeline.sh
	python3 scripts/test-release-policy.py
	conftest verify --policy policy/release --data policy/release/data.json
	./scripts/pipeline.sh scan

down:
	docker compose down -v

clean:
	rm -rf artifacts
