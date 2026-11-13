set shell := ["bash", "-eu", "-o", "pipefail", "-c"]
set positional-arguments

# Copy this wrapper and install-hooks with the shell setting to sibling justfiles.
[private]
_ai +args:
    #!/usr/bin/env bash
    set -euo pipefail
    if env AI= just --quiet "$@" > .ci-ai.log 2>&1; then
        printf 'PASS: %s\n' "$*"
    else
        result=$?
        printf 'FAIL: %s (exit %s)\n' "$*" "$result"
        if [[ -f scripts/ai_filter_log.py ]]; then
            uv run python scripts/ai_filter_log.py .ci-ai.log
        else
            tail -50 .ci-ai.log
        fi
        exit "$result"
    fi

install-hooks:
    #!/usr/bin/env bash
    set -euo pipefail
    if [[ -n "${AI:-}" ]]; then exec just --quiet _ai install-hooks; fi
    if [[ -f .git ]]; then
        echo "hooks: worktree checkout - the canonical repo owns them, skipping"
    elif [[ -n "$(git config --get core.hooksPath || true)" ]]; then
        echo "hooks: core.hooksPath is set - leaving it alone, skipping"
    else
        uv run pre-commit install --hook-type pre-commit --hook-type commit-msg
    fi

[default]
ci:
    #!/usr/bin/env bash
    set -euo pipefail
    if [[ -n ${AI:-} ]]; then exec just --quiet _ai ci; fi
    just setup pre-commit-check lint-check typecheck test build
    docgraph check --strict

ci-slow:
    #!/usr/bin/env bash
    set -euo pipefail
    if [[ -n ${AI:-} ]]; then exec just --quiet _ai ci-slow; fi
    just ci

setup:
    #!/usr/bin/env bash
    set -euo pipefail
    if [[ -n ${AI:-} ]]; then exec just --quiet _ai setup; fi
    uv sync --locked --group dev
    just install-hooks

lint:
    #!/usr/bin/env bash
    set -euo pipefail
    if [[ -n ${AI:-} ]]; then exec just --quiet _ai lint; fi
    uv run ruff check --select I --fix
    uv run ruff check --fix

lint-check:
    #!/usr/bin/env bash
    set -euo pipefail
    if [[ -n ${AI:-} ]]; then exec just --quiet _ai lint-check; fi
    uv run ruff format --check .
    uv run ruff check .

format-check:
    #!/usr/bin/env bash
    set -euo pipefail
    if [[ -n ${AI:-} ]]; then exec just --quiet _ai format-check; fi
    uv run ruff format --check .

format:
    #!/usr/bin/env bash
    set -euo pipefail
    if [[ -n ${AI:-} ]]; then exec just --quiet _ai format; fi
    uv run ruff format pdomain_ops tests

typecheck:
    #!/usr/bin/env bash
    set -euo pipefail
    if [[ -n ${AI:-} ]]; then exec just --quiet _ai typecheck; fi
    uv run basedpyright pdomain_ops --level error

test:
    #!/usr/bin/env bash
    set -euo pipefail
    if [[ -n ${AI:-} ]]; then exec just --quiet _ai test; fi
    uv run pytest -n auto

build:
    #!/usr/bin/env bash
    set -euo pipefail
    if [[ -n ${AI:-} ]]; then exec just --quiet _ai build; fi
    uv build

pre-commit-check:
    #!/usr/bin/env bash
    set -euo pipefail
    if [[ -n ${AI:-} ]]; then exec just --quiet _ai pre-commit-check; fi
    SKIP="basedpyright${SKIP:+,$SKIP}" uv run pre-commit run --all-files

update-hooks:
    #!/usr/bin/env bash
    set -euo pipefail
    if [[ -n ${AI:-} ]]; then exec just --quiet _ai update-hooks; fi
    uv run pre-commit autoupdate --freeze

help:
    #!/usr/bin/env bash
    set -euo pipefail
    if [[ -n ${AI:-} ]]; then exec just --quiet _ai help; fi
    just --list

remove-venv:
    #!/usr/bin/env bash
    set -euo pipefail
    if [[ -n ${AI:-} ]]; then exec just --quiet _ai remove-venv; fi
    rm -rf "${UV_PROJECT_ENVIRONMENT:-.venv}"

reset:
    #!/usr/bin/env bash
    set -euo pipefail
    if [[ -n ${AI:-} ]]; then exec just --quiet _ai reset; fi
    just clean remove-venv setup

reset-venv:
    #!/usr/bin/env bash
    set -euo pipefail
    if [[ -n ${AI:-} ]]; then exec just --quiet _ai reset-venv; fi
    just reset

reset-full:
    #!/usr/bin/env bash
    set -euo pipefail
    if [[ -n ${AI:-} ]]; then exec just --quiet _ai reset-full; fi
    just clean remove-venv
    uv cache clean
    just setup

clean:
    #!/usr/bin/env bash
    set -euo pipefail
    if [[ -n ${AI:-} ]]; then exec just --quiet _ai clean; fi
    rm -rf dist .pytest_cache .ruff_cache htmlcov

upgrade-deps:
    #!/usr/bin/env bash
    set -euo pipefail
    if [[ -n ${AI:-} ]]; then exec just --quiet _ai upgrade-deps; fi
    venv=${UV_PROJECT_ENVIRONMENT:-.venv}
    common_dir=$(git rev-parse --path-format=absolute --git-common-dir)
    canonical_root=$(dirname "$common_dir")
    canonical_venv=$venv
    if [[ $venv != /* ]]; then canonical_venv=$canonical_root/$venv; fi
    for marker in "$venv/.pdomain-local-mode" "$venv/.pdomain-dev-local" "$canonical_venv/.pdomain-local-mode" "$canonical_venv/.pdomain-dev-local"; do
        if [[ -f $marker ]]; then
            echo "ERROR: leave local dependency mode before upgrade-deps ($marker)"
            exit 1
        fi
    done
    uv lock --upgrade
    uv sync --group dev
    just update-hooks

dev-local:
    #!/usr/bin/env bash
    set -euo pipefail
    if [[ -n ${AI:-} ]]; then exec just --quiet _ai dev-local; fi
    if [[ ! -d ../pdomain-book-tools ]]; then
        echo "Cannot find pdomain-book-tools at ../pdomain-book-tools"
        exit 1
    fi
    peer=$(realpath ../pdomain-book-tools)
    venv=${UV_PROJECT_ENVIRONMENT:-.venv}
    UV_LINK_MODE=copy uv pip install --python "$venv/bin/python" -e "$peer"
    UV_LINK_MODE=copy uv pip install --python "$venv/bin/python" -e . --no-deps
    UV_LINK_MODE=copy uv pip install --python "$venv/bin/python" --group dev
    touch "$venv/.pdomain-local-mode"

local-setup:
    #!/usr/bin/env bash
    set -euo pipefail
    if [[ -n ${AI:-} ]]; then exec just --quiet _ai local-setup; fi
    ./scripts/local-setup.sh

local-dev:
    #!/usr/bin/env bash
    set -euo pipefail
    if [[ -n ${AI:-} ]]; then exec just --quiet _ai local-dev; fi
    ./scripts/local-dev.sh

local-check:
    #!/usr/bin/env bash
    set -euo pipefail
    if [[ -n ${AI:-} ]]; then exec just --quiet _ai local-check; fi
    ./scripts/local-check.sh

local-upgrade-deps:
    #!/usr/bin/env bash
    set -euo pipefail
    if [[ -n ${AI:-} ]]; then exec just --quiet _ai local-upgrade-deps; fi
    ./scripts/local-upgrade-deps.sh

update-pdomain-deps:
    #!/usr/bin/env bash
    set -euo pipefail
    if [[ -n ${AI:-} ]]; then exec just --quiet _ai update-pdomain-deps; fi
    ./scripts/update-pdomain-deps.sh

ci-against-master:
    #!/usr/bin/env bash
    set -euo pipefail
    if [[ -n ${AI:-} ]]; then exec just --quiet _ai ci-against-master; fi
    ./scripts/ci-against-master.sh

release-patch:
    #!/usr/bin/env bash
    set -euo pipefail
    if [[ -n ${AI:-} ]]; then exec just --quiet _ai release-patch; fi
    BUMP=patch ./scripts/do-release.sh

release-minor:
    #!/usr/bin/env bash
    set -euo pipefail
    if [[ -n ${AI:-} ]]; then exec just --quiet _ai release-minor; fi
    BUMP=minor ./scripts/do-release.sh

release-major:
    #!/usr/bin/env bash
    set -euo pipefail
    if [[ -n ${AI:-} ]]; then exec just --quiet _ai release-major; fi
    BUMP=major ./scripts/do-release.sh

[private]
_do-release:
    BUMP="${BUMP:-minor}" ./scripts/do-release.sh
