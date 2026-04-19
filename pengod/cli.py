"""Command-line entry (`pengh`)."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from pengod.config import get_settings
from pengod.ingest.pipeline import ingest_case_file
from pengod.rag.search import semantic_search


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="pengh", description="PenGod CLI")
    sub = parser.add_subparsers(dest="command")

    p_ingest = sub.add_parser("ingest", help="Ingest a Casestudies.txt-style file into Qdrant")
    p_ingest.add_argument("file", type=Path, help="Path to case study export")

    p_search = sub.add_parser("search", help="Semantic search over ingested chunks")
    p_search.add_argument("query", help="Search text")
    p_search.add_argument("--limit", type=int, default=8, help="Max hits")

    args = parser.parse_args(argv)
    if args.command == "ingest":
        stats = asyncio.run(ingest_case_file(args.file))
        print(
            json.dumps(
                {
                    "cases": stats.cases,
                    "chunks": stats.chunks,
                    "points_upserted": stats.points_upserted,
                    "errors": stats.errors,
                },
                indent=2,
            )
        )
        if stats.errors:
            sys.exit(1)
        return
    if args.command == "search":

        async def _run() -> None:
            rows = await semantic_search(args.query, limit=args.limit)
            print(json.dumps(rows, indent=2))

        asyncio.run(_run())
        return

    parser.print_help()
    sys.exit(2)


if __name__ == "__main__":
    main()
