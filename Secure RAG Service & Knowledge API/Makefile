.PHONY: dev demo test

dev:
	docker compose up --build

demo:
	./scripts/demo.sh

test:
	python -m unittest discover -s scripts -p "test_*.py"
	python -O -m unittest discover -s scripts -p "test_*.py"
	mvn -f api/pom.xml test
