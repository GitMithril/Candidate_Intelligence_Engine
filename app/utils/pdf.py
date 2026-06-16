import io

from pypdf import PdfReader


def _page_links(page) -> list[str]:
    """Return all HTTP/S URIs from link annotations on a PDF page."""
    urls: list[str] = []
    try:
        annots = page.get("/Annots")
        if not annots:
            return urls
        for ref in annots:
            try:
                annot = ref.get_object()
                if annot.get("/Subtype") != "/Link":
                    continue
                action = annot.get("/A")
                if not action:
                    continue
                action_obj = action.get_object() if hasattr(action, "get_object") else action
                uri = action_obj.get("/URI")
                if not uri:
                    continue
                uri_str = uri if isinstance(uri, str) else uri.decode("utf-8", errors="ignore")
                if uri_str.startswith("http"):
                    urls.append(uri_str)
            except Exception:
                continue
    except Exception:
        pass
    return urls


def extract_pdf_text(content: bytes) -> str:
    reader = PdfReader(io.BytesIO(content))
    parts: list[str] = []
    all_links: list[str] = []

    for page in reader.pages:
        parts.append(page.extract_text() or "")
        all_links.extend(_page_links(page))

    text = "\n".join(parts)

    # Deduplicate and append links so the LLM can see hyperlink URLs
    # even when the visible text is just anchor text like "GitHub" or "LinkedIn".
    seen: set[str] = set()
    unique_links = [u for u in all_links if not (u in seen or seen.add(u))]  # type: ignore[func-returns-value]
    if unique_links:
        text += "\n\nLinks found in document:\n" + "\n".join(unique_links)

    return text
