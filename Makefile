SHELL := /bin/bash

.PHONY: setup run test test-pbt

setup:
	./setup.sh

run:
	./run_local.sh

# Syntax / compile check for all Python source files
test:
	python3 -m compileall app streamlit_app.py run_pipeline.py auto_apply

# Property-based tests (Hypothesis)
test-pbt:
	python3 -m pytest auto_apply/tests/ -v
