from __future__ import annotations

import argparse
from collections.abc import Sequence


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="NVIDIA relationship research")
    try:
        parser.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code)
    return 0
