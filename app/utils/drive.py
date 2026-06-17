import re
import tempfile
from pathlib import Path


def _folder_id(url: str) -> str:
    match = re.search(r"/folders/([a-zA-Z0-9_-]+)", url)
    if match:
        return match.group(1)
    raise ValueError(f"Cannot extract Google Drive folder ID from URL: {url!r}")


def download_drive_pdfs(folder_url: str) -> list[tuple[str, bytes]]:
    """Download all PDF files from a public Google Drive folder.

    Returns list of (filename, pdf_bytes). Raises ValueError on failure.
    """
    try:
        import gdown
    except ImportError:
        raise ImportError("gdown is required for Drive support: pip install gdown>=5.0")

    folder_id = _folder_id(folder_url)

    with tempfile.TemporaryDirectory() as tmpdir:
        try:
            gdown.download_folder(
                id=folder_id,
                output=tmpdir,
                quiet=True,
                use_cookies=False,
            )
        except Exception as exc:
            raise ValueError(f"Failed to download Drive folder '{folder_url}': {exc}")

        items = [(p.name, p.read_bytes()) for p in Path(tmpdir).rglob("*.pdf")]

    if not items:
        raise ValueError(
            "No PDF files found in the Drive folder. "
            "Ensure the folder is publicly shared and contains PDF files."
        )

    return items
