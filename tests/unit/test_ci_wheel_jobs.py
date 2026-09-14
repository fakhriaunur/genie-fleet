"""M10 verify: CI covers both wheel paths while the gates job stays fixed.

Pins the ``gates`` job of ``.github/workflows/ci.yml`` verbatim (any edit
fails this test on purpose) and requires the ``wheel-fallback`` and
``wheel-native`` jobs with their contract steps. Stdlib-only parsing so no
new test dependency is introduced.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CI_YML = REPO_ROOT / ".github" / "workflows" / "ci.yml"

#: Verbatim snapshot of the ``gates`` job. FAIL on any edit: the M10
#: contract requires the existing gates job to stay unmodified.
EXPECTED_GATES_JOB = """\
  gates:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Set up Python 3.14
        uses: actions/setup-python@v5
        with:
          python-version: "3.14"

      - name: Install mise
        uses: jdx/mise-action@v2

      - name: Install toolchain and dependencies
        run: mise run setup

      - name: Lint (ruff format check + ruff check)
        run: mise run lint

      - name: Typecheck (mypy strict)
        run: mise run type

      - name: Test (pytest with coverage floor)
        run: mise run test

      - name: Replay (golden fixtures)
        run: mise run replay
"""


def _ci_text() -> str:
    assert CI_YML.is_file(), ".github/workflows/ci.yml missing"
    return CI_YML.read_text()


def _job_block(text: str, job: str) -> str:
    start = text.index(f"\n  {job}:\n")
    following = [
        text.index(f"\n  {other}:\n", start + 1)
        for other in ("gates", "wheel-fallback", "wheel-native")
        if other != job and f"\n  {other}:\n" in text[start + 1 :]
    ]
    end = min(following) if following else len(text)
    return text[start:end]


def test_gates_job_unmodified() -> None:
    text = _ci_text()
    assert EXPECTED_GATES_JOB in text, "gates job changed; M10 keeps it unmodified"


def test_wheel_fallback_job_present_with_contract_steps() -> None:
    block = _job_block(_ci_text(), "wheel-fallback")
    assert "python -m build --wheel" in block
    assert "wheel_smoke.py --check-wheel" in block
    assert "--expect-pure" in block
    assert "pip install dist/" in block
    assert "GENIE_NATIVE=1" not in block


def test_wheel_native_job_present_with_contract_steps() -> None:
    block = _job_block(_ci_text(), "wheel-native")
    assert "pybind11==3.1.0" in block
    assert "GENIE_NATIVE=1" in block
    assert "python -m build --wheel" in block
    assert "wheel_smoke.py --check-wheel" in block
    assert "--expect-native" in block
    assert "pip install dist/" in block
