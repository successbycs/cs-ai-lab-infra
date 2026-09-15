.PHONY: quality execplan-check

execplan-check:
	python3 scripts/validate_execplan.py

quality: execplan-check
	python3 -m pytest -q
	bash -n scripts/*.sh penpot/scripts/*.sh
	python3 -m compileall -q scripts t480_core monitoring tests
	python3 -m json.tool t480/command-catalog.json >/dev/null
	python3 -m json.tool tailscale/command-catalog.json >/dev/null
