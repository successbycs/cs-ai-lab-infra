.PHONY: quality

quality:
	python3 -m pytest -q
	bash -n scripts/*.sh penpot/scripts/*.sh
	python3 -m compileall -q scripts t480_core monitoring tests
	python3 -m json.tool t480/command-catalog.json >/dev/null
	python3 -m json.tool tailscale/command-catalog.json >/dev/null
