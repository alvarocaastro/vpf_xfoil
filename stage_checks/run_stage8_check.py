from __future__ import annotations

from common import build_parser, run_stage_check


if __name__ == "__main__":
    args = build_parser(8).parse_args()
    run_stage_check(8, clean=not args.no_clean)
