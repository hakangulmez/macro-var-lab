UV ?= $(or $(shell command -v uv),$(HOME)/portfolio/.tools/bin/uv)
.PHONY: setup data checks verify-metadata audit quick all test lint figures report design readme-numbers clean g2 g2-pilot g2-summary audit-g2
setup:
	$(UV) sync --locked
quick:
	$(UV) run python scripts/quick.py
lint:
	$(UV) run ruff check .
	$(UV) run ruff format --check .
	$(UV) run mypy src
test:
	$(UV) run pytest
data:
	$(UV) run python scripts/data.py
checks:
	$(UV) run python scripts/data_checks.py
verify-metadata:
	$(UV) run python scripts/verify_evds.py
audit: verify-metadata
	$(UV) run python scripts/audit_g1.py
g2-pilot:
	$(UV) run python scripts/g2.py --pilot
g2:
	$(UV) run python scripts/g2.py
g2-figures:
	$(UV) run python scripts/g2_outputs.py
figures:
	$(UV) run python scripts/release_outputs.py
g2-summary:
	pandoc docs/G2_SUMMARY.md --pdf-engine=typst --metadata-file=docs/g2_render.yaml -o docs/G2_SUMMARY.pdf
audit-g2:
	$(UV) run python scripts/audit_g2.py
readme-numbers:
	$(UV) run python scripts/release_outputs.py
report:
	$(UV) run python scripts/release_outputs.py
design:
	pandoc docs/DESIGN.md --pdf-engine=typst --metadata-file=docs/g0_render.yaml --include-in-header=docs/g0_header.typ -o docs/DESIGN.pdf
clean:
	@echo "Remove generated artifacts explicitly after inspecting them; no automatic data deletion."

all:
	$(UV) run python scripts/release.py
	$(UV) run python scripts/release_outputs.py

.PHONY: audit-release
audit-release:
	$(UV) run python scripts/audit_release.py
