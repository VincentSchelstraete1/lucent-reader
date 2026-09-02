#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

from app.ingestion import MarkItDownAdapter, PdfDocumentIngestor, PyMuPDFPageExtractor
from app.normalization import build_evaluation_report, normalize_document


def evaluate(path: Path) -> dict:
    raw = PdfDocumentIngestor(PyMuPDFPageExtractor(), MarkItDownAdapter()).ingest_pdf(
        path.read_bytes(), filename=path.name
    )
    return build_evaluation_report(raw, normalize_document(raw))


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect deterministic PDF normalization without persistence")
    parser.add_argument("pdf", nargs="+", type=Path)
    args = parser.parse_args()
    reports = []
    for path in args.pdf:
        if not path.is_file() or path.suffix.casefold() != ".pdf":
            parser.error(f"not a readable PDF: {path}")
        reports.append(evaluate(path))
    print(json.dumps(reports, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
