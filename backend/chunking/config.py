from pathlib import Path

# Project directories
PROJECT_ROOT = Path(__file__).resolve().parents[2]

DATA_DIR = PROJECT_ROOT / "data"
PDF_DIR = DATA_DIR / "pdfs"
OUTPUT_DIR = DATA_DIR / "evaluation"

# Chunking model and token limits
MODEL_NAME = "BAAI/bge-small-en-v1.5"

TARGET_TOKENS = 400
MAX_TOKENS = 512

# Docling configuration
MERGE_PEERS = False

# Eligible prose element types
PROSE_LABELS = {"text", "list_item", "footnote"}
