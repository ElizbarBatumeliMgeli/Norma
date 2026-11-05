"""What NORMA reads from a PDF: page sizes, page images and the positioned text used to point at things."""
from pathlib import Path
import pymupdf

MAX_ANCHORS = 2500       # per page; beyond this the sheet is read from its image only
SCANNED_BELOW = 20       # fewer text items than this: treat the page as an image


class UnreadablePdf(ValueError):
    pass


def open_pdf(path):
    try:
        document = pymupdf.open(path)
    except Exception as error:
        raise UnreadablePdf(str(error))
    if not document.is_pdf or document.page_count == 0:
        raise UnreadablePdf('not a PDF')
    if document.needs_pass:
        raise UnreadablePdf('password protected')
    return document


def page_sizes(path):
    with open_pdf(path) as document:
        return [dict(number=i + 1, width=p.rect.width, height=p.rect.height) for i, p in enumerate(document)]


def anchors(path):
    """Text lines of every page with an id and a box in page fractions (0–1, top left origin).
    The model refers to these ids, so a finding points at the exact text on the sheet."""
    found = []
    with open_pdf(path) as document:
        for number, page in enumerate(document, 1):
            width, height = page.rect.width, page.rect.height
            lines = []
            for block in page.get_text('dict')['blocks']:
                for line in block.get('lines', []):
                    text = ' '.join(span['text'] for span in line['spans']).strip()
                    if text:
                        # CAD exports are often rotated pages: text boxes come unrotated, the picture does not.
                        box = (pymupdf.Rect(line['bbox']) * page.rotation_matrix).normalize()
                        lines.append((text, box.x0 / width, box.y0 / height, box.x1 / width, box.y1 / height))
            for text, x0, y0, x1, y1 in lines[:MAX_ANCHORS]:
                found.append(dict(id=len(found), page=number, text=text, box=[round(v, 4) for v in (x0, y0, x1, y1)]))
    return found


def render_page(path, number, target, longest=2400):
    """The page as a PNG with its longest side `longest` pixels; kept so each size renders once."""
    target = Path(target)
    if not target.exists():
        with open_pdf(path) as document:
            page = document[number - 1]
            zoom = longest / max(page.rect.width, page.rect.height)
            page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False).save(target)
    return target


def for_model(path, target, limit, first=()):
    """A PDF within `limit` bytes for the AI: the original if it fits, else a copy with smaller images, else a copy
    of page images. If even that is too large, the sheets in `first` come first and the rest are left blank, so page
    numbers stay right. The app keeps showing the original. None if nothing fits."""
    path, target = Path(path), Path(target)
    if path.stat().st_size <= limit:
        return path
    if target.exists():
        return target
    with open_pdf(path) as document:
        document.rewrite_images(dpi_threshold=150, dpi_target=120, quality=65)
        document.save(target, garbage=3, deflate=True)
    if target.stat().st_size <= limit:
        return target
    with open_pdf(path) as document, pymupdf.open() as images:
        shown, size = {}, 0
        for number in [*first, *(n for n in range(1, document.page_count + 1) if n not in first)]:
            page = document[number - 1]
            zoom = 2200 / max(page.rect.width, page.rect.height)
            picture = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False).tobytes('jpeg', jpg_quality=70)
            if size + len(picture) > limit * 0.95:
                break
            shown[number] = picture
            size += len(picture)
        for number, page in enumerate(document, 1):
            sheet = images.new_page(width=page.rect.width, height=page.rect.height)
            if number in shown:
                sheet.insert_image(sheet.rect, stream=shown[number])
        images.save(target, garbage=3, deflate=True)
    if shown and target.stat().st_size <= limit:
        return target
    target.unlink()
    return None


def tiles(path, number, grid=2, longest=1500):
    """A page in `grid`×`grid` JPEG tiles: for sheets whose text is drawn as lines, so only the image can be read."""
    with open_pdf(path) as document:
        page = document[number - 1]
        rect = page.rect
        zoom = longest * grid / max(rect.width, rect.height)
        images = []
        for row in range(grid):
            for column in range(grid):
                clip = pymupdf.Rect(rect.x0 + rect.width * column / grid, rect.y0 + rect.height * row / grid,
                                    rect.x0 + rect.width * (column + 1) / grid, rect.y0 + rect.height * (row + 1) / grid)
                images.append(page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), clip=clip, alpha=False).tobytes('jpeg', jpg_quality=80))
        return images
