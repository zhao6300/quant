from __future__ import annotations

from tools.check_spec_coverage import main


def test_traceability_json_passes():
    assert main(".kiro/specs/multi-market-quant-platform") == 0
