import argparse

from pathlib import Path
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.chunking import HybridChunker
from docling_core.transforms.chunker.tokenizer.huggingface import HuggingFaceTokenizer

from backend.chunking.config import PDF_DIR, PROSE_LABELS, TARGET_TOKENS, MERGE_PEERS, MAX_TOKENS
from backend.chunking.utils import (
    get_tokenizer,
    normalize_text,
    validate_token_limit,
    pages_of,
    refs_of,
    label_of,
)


def get_pdf_path(filename: str) -> Path:
    """Resolve and validate a PDF inside the configured PDF directory."""

    if Path(filename).name != filename:
        raise ValueError("Provide only the PDF filename, not a directory path.")

    pdf_path = PDF_DIR / filename

    if pdf_path.suffix.lower() != ".pdf":
        raise ValueError("Input file must have a .pdf extension.")

    if not pdf_path.is_file():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    return pdf_path


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Process a research paper PDF using Docling."
    )

    parser.add_argument("filename", help="PDF filename located inside data/pdfs/")

    return parser.parse_args()


def convert_pdf(pdf_path: Path):
    """Convert a text-based PDF into a Docling document."""

    pipeline_options = PdfPipelineOptions(
        do_ocr=False,
        do_table_structure=True,
        do_picture_classification=False,
        do_picture_description=False,
        do_code_enrichment=False,
        do_formula_enrichment=False,
    )

    converter = DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
        }
    )

    result = converter.convert(str(pdf_path))

    return result.document


def initialize_chunker():
    """Initialize Docling HybridChunker with the BGE tokenizer."""

    tokenizer = HuggingFaceTokenizer(
        tokenizer=get_tokenizer(),
        max_tokens=TARGET_TOKENS,
    )

    chunker = HybridChunker(
        tokenizer=tokenizer,
        merge_peers=MERGE_PEERS,
    )

    return chunker


def generate_hybrid_chunks(doc):
    """Generate structure-aware chunks from a Docling document."""

    chunker = initialize_chunker()
    chunks = list(chunker.chunk(doc))

    return chunker, chunks


def get_prose_items(chunk):
    """Extract only eligible prose elements from a HybridChunker chunk."""
    items = list(chunk.meta.doc_items or [])

    return [item for item in items if label_of(item) in PROSE_LABELS]


def build_prose_record(chunk):
    """Build a prose chunk record using HybridChunker's canonical text."""

    items = list(chunk.meta.doc_items or [])

    # Identify eligible prose elements
    prose_items = get_prose_items(chunk)

    if not prose_items:
        return None

    # Use HybridChunker's text to preserve its original chunk boundaries
    prose_text = normalize_text(chunk.text)

    if not prose_text:
        return None

    # Validate final canonical text
    validation = validate_token_limit(prose_text)

    labels = sorted({label_of(item) for item in items})
    mixed_content = bool(set(labels) - PROSE_LABELS)

    record = {
        "chunk_type": "text",
        "text": prose_text,
        "token_count": validation["token_count"],
        "page_numbers": pages_of(prose_items),
        "section_path": list(chunk.meta.headings or []),
        "source_refs": refs_of(prose_items),
        "source_kind": "hybrid_chunk",
        "source_labels": labels,
        "mixed_content": mixed_content,
        "review_required": (
            validation["review_required"] or not validation["valid"] or mixed_content
        ),
    }

    return record


if __name__ == "__main__":
    args = parse_arguments()
    pdf_path = get_pdf_path(args.filename)

    print(f"Processing: {pdf_path.name}")

    # Step 1: Convert PDF into a Docling document
    doc = convert_pdf(pdf_path)

    # Step 2: Generate HybridChunks
    chunker, hybrid_chunks = generate_hybrid_chunks(doc)

    # Step 3: Build prose chunk records
    prose_records = []

    for chunk in hybrid_chunks:
        record = build_prose_record(chunk)

        if record is not None:
            prose_records.append(record)

    # Step 4: Display processing summary
    print("\n--- Prose Chunking Summary ---")
    print(f"Total HybridChunks: {len(hybrid_chunks)}")
    print(f"Prose chunks: {len(prose_records)}")

    review_count = sum(record["review_required"] for record in prose_records)

    invalid_count = sum(record["token_count"] > MAX_TOKENS for record in prose_records)

    print(f"Chunks requiring review: {review_count}")
    print(f"Chunks exceeding MAX_TOKENS: {invalid_count}")

    print("\nFirst 3 prose chunks:")

    for record in prose_records[:3]:
        print(f"\nPages: {record['page_numbers']}")
        print(f"Section: {' > '.join(record['section_path'])}")
        print(f"Tokens: {record['token_count']}")
        print(f"Text: {record['text'][:300]}...")
    args = parse_arguments()
    pdf_path = get_pdf_path(args.filename)

    print(f"Input PDF: {pdf_path}")
