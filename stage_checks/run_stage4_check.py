from __future__ import annotations

from common import build_parser, run_stage_check


if __name__ == "__main__":
    args = build_parser(4).parse_args()
    run_stage_check(4, clean=not args.no_clean)
