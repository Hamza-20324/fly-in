PYTHON ?= python3
PIP ?= $(PYTHON) -m pip
MAP ?= example.map
ARGS ?= "--stats" "--visual"

.PHONY: install run debug clean lint lint-strict test

install:
	$(PIP) install -r requirements.txt

run:
	$(PYTHON) main.py $(MAP) $(ARGS)

debug:
	$(PYTHON) -m pdb main.py $(MAP) $(ARGS)

clean:
	find . -type d -name '__pycache__' -prune -exec rm -rf {} +
	rm -rf .mypy_cache .pytest_cache

lint:
	flake8 .
	mypy . --warn-return-any --warn-unused-ignores --ignore-missing-imports --disallow-untyped-defs --check-untyped-defs

lint-strict:
	flake8 .
	mypy . --strict

test:
	$(PYTHON) -m pytest -q
