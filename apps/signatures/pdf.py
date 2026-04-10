import hashlib
import io
import re
import base64

from django.core.files.base import ContentFile
from PyPDF2 import PdfReader, PdfWriter
from PyPDF2.generic import ContentStream
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas as pdf_canvas

from apps.signatures.models import SignerFieldValue, AuditEvent


FIELD_LABEL_BLOCKLIST = {
    'type of change',
    'events consistent with adding family members to coverage',
    'events consistent with removing family members from coverage',
    'other events',
    'add coverage for',
    'terminate coverage for',
    'dependents',
    'qualifying life event and benefit change form',
}


def extract_text_fingerprint(pdf_file):
    """Extract normalized text from a PDF for template matching.

    Returns (fingerprint_text, page_count). The fingerprint strips out
    variable data (names, dates, amounts) and keeps structural text like
    headings, labels, and boilerplate that identify the contract type.
    """
    pdf_file.seek(0)
    reader = PdfReader(pdf_file)
    page_count = len(reader.pages)
    all_text = []

    for page in reader.pages:
        text = page.extract_text() or ''
        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        all_text.append(text)

    fingerprint = '\n---PAGE---\n'.join(all_text)
    pdf_file.seek(0)
    return fingerprint, page_count


def match_template(pdf_file, team):
    """Try to match an uploaded PDF against existing templates.

    Uses page count as a quick filter, then compares text similarity.
    Returns (template, confidence) or (None, 0).
    """
    from apps.signatures.models import DocumentTemplate
    from difflib import SequenceMatcher

    fingerprint, page_count = extract_text_fingerprint(pdf_file)
    if not fingerprint.strip():
        return None, 0

    # Only consider templates with matching page count and a fingerprint
    candidates = DocumentTemplate.objects.filter(
        team=team,
        page_count=page_count,
    ).exclude(text_fingerprint='')

    best_match = None
    best_score = 0

    for template in candidates:
        # Compare the structural text using SequenceMatcher
        score = SequenceMatcher(
            None,
            _normalize_for_comparison(template.text_fingerprint),
            _normalize_for_comparison(fingerprint),
        ).ratio()

        if score > best_score:
            best_score = score
            best_match = template

    # Require at least 60% similarity to consider it a match
    if best_score >= 0.60:
        return best_match, best_score

    return None, 0


def _normalize_for_comparison(text):
    """Strip out variable content (dates, dollar amounts, phone numbers)
    to focus comparison on structural/boilerplate text."""
    # Remove dates like MM/DD/YYYY, YYYY-MM-DD, etc.
    text = re.sub(r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}', '', text)
    text = re.sub(r'\d{4}-\d{2}-\d{2}', '', text)
    # Remove dollar amounts
    text = re.sub(r'\$[\d,]+\.?\d*', '', text)
    # Remove phone numbers
    text = re.sub(r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', '', text)
    # Remove standalone numbers (but keep words with numbers)
    text = re.sub(r'\b\d+\b', '', text)
    # Collapse whitespace
    text = re.sub(r'\s+', ' ', text).strip().lower()
    return text


def suggest_fields_from_pdf(pdf_file, existing_fields=None):
    """Return suggested document fields detected from the PDF structure."""
    pdf_file.seek(0)
    reader = PdfReader(pdf_file)
    suggestions = []
    existing_fields = existing_fields or []

    for page_index, page in enumerate(reader.pages):
        page_num = page_index + 1
        page_width = float(page.mediabox.width)
        page_height = float(page.mediabox.height)

        page_suggestions = []
        page_suggestions.extend(_extract_widget_field_suggestions(page, page_num, page_width, page_height))

        text_items = _extract_text_items(page)
        vector_shapes = _extract_vector_shapes(page)
        page_suggestions.extend(_detect_text_field_suggestions(
            text_items, vector_shapes, page_num, page_width, page_height
        ))
        page_suggestions.extend(_detect_checkbox_suggestions(
            text_items, vector_shapes, page_num, page_width, page_height
        ))

        for suggestion in page_suggestions:
            if _overlaps_existing_field(suggestion, existing_fields):
                continue
            if _overlaps_existing_field(suggestion, suggestions):
                continue
            suggestions.append(suggestion)

    pdf_file.seek(0)
    return suggestions


def _extract_widget_field_suggestions(page, page_num, page_width, page_height):
    suggestions = []
    annots = page.get('/Annots') or []
    try:
        annots = annots.get_object()
    except Exception:
        pass
    if not isinstance(annots, (list, tuple)):
        annots = []
    for annot_ref in annots:
        try:
            annot = annot_ref.get_object()
        except Exception:
            continue
        if annot.get('/Subtype') != '/Widget':
            continue
        rect = annot.get('/Rect')
        if not rect or len(rect) != 4:
            continue

        field_type = annot.get('/FT')
        parent = None
        if field_type is None and annot.get('/Parent'):
            try:
                parent = annot['/Parent'].get_object()
                field_type = parent.get('/FT')
            except Exception:
                parent = None

        if field_type == '/Tx':
            detected_type = 'text'
        elif field_type == '/Btn':
            detected_type = 'checkbox'
        else:
            continue

        x1, y1, x2, y2 = [float(value) for value in rect]
        x = min(x1, x2)
        y = min(y1, y2)
        w = abs(x2 - x1)
        h = abs(y2 - y1)
        if w <= 1 or h <= 1:
            continue

        label = annot.get('/TU') or annot.get('/T')
        if parent and not label:
            label = parent.get('/TU') or parent.get('/T')

        suggestions.append({
            'page': page_num,
            'type': detected_type,
            'label': str(label or '').strip(),
            'x': x / page_width * 100,
            'y': (page_height - y - h) / page_height * 100,
            'width': w / page_width * 100,
            'height': h / page_height * 100,
            'confidence': 0.99,
            'source': 'acroform',
        })
    return suggestions


def _extract_text_items(page):
    items = []

    def visitor_text(text, cm, tm, font_dict, font_size):
        cleaned = re.sub(r'\s+', ' ', (text or '')).strip()
        if not cleaned:
            return
        x = float(tm[4])
        y = float(tm[5])
        estimated_width = max(len(cleaned) * max(font_size, 8) * 0.42, max(font_size, 8) * 0.8)
        items.append({
            'text': cleaned,
            'text_norm': cleaned.lower().strip(':').strip(),
            'x': x,
            'y': y,
            'width': estimated_width,
            'height': max(float(font_size) * 1.15, 8.0),
        })

    try:
        page.extract_text(visitor_text=visitor_text)
    except Exception:
        return items

    return sorted(items, key=lambda item: (-item['y'], item['x']))


_IDENTITY_MATRIX = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)


def _mat_mul(m1, m2):
    """Multiply two 2D affine transforms stored as (a, b, c, d, e, f)."""
    a = m1[0] * m2[0] + m1[1] * m2[2]
    b = m1[0] * m2[1] + m1[1] * m2[3]
    c = m1[2] * m2[0] + m1[3] * m2[2]
    d = m1[2] * m2[1] + m1[3] * m2[3]
    e = m1[4] * m2[0] + m1[5] * m2[2] + m2[4]
    f = m1[4] * m2[1] + m1[5] * m2[3] + m2[5]
    return (a, b, c, d, e, f)


def _transform_point(m, x, y):
    return (x * m[0] + y * m[2] + m[4], x * m[1] + y * m[3] + m[5])


def _extract_vector_shapes(page):
    """Extract rectangles and horizontal lines from a page.

    Recurses into Form XObjects referenced via the ``Do`` operator so
    that government/tax forms — which typically wrap their entire
    layout in a Form XObject — still expose their table cells and
    checkboxes for downstream field detection.
    """
    rects = []
    lines = []

    try:
        contents = page.get_contents()
    except Exception:
        contents = None
    if contents is None:
        return {'rects': rects, 'lines': lines}

    resources = page.get('/Resources')
    try:
        if resources is not None:
            resources = resources.get_object()
    except Exception:
        resources = None

    try:
        _walk_content_stream(
            contents, page.pdf, resources, _IDENTITY_MATRIX,
            rects, lines, depth=0,
        )
    except Exception:
        pass

    horizontal_lines = [
        line for line in lines
        if line['width'] >= 25 and line['height'] <= 2
    ]
    normalized_rects = [
        rect for rect in rects
        if rect['width'] >= 6 and rect['height'] >= 6
    ]
    return {'rects': normalized_rects, 'lines': horizontal_lines}


def _walk_content_stream(content, pdf, resources, ctm, rects, lines, depth=0):
    """Walk a content stream, emitting rects/lines in page coordinates.

    Tracks the current transformation matrix via q/Q/cm and follows
    ``Do`` operators into Form XObjects so shapes drawn inside nested
    XObjects are not missed. Depth is capped to prevent pathological
    recursion.
    """
    if depth > 4:
        return
    try:
        stream = ContentStream(content, pdf)
    except Exception:
        return

    ctm_stack = []
    current_ctm = ctm
    current_point = None
    subpath_start = None

    for operands, operator in stream.operations:
        op = operator.decode('latin1') if isinstance(operator, bytes) else operator
        try:
            if op == 'q':
                ctm_stack.append(current_ctm)
            elif op == 'Q':
                if ctm_stack:
                    current_ctm = ctm_stack.pop()
            elif op == 'cm':
                local = tuple(float(value) for value in operands[:6])
                current_ctm = _mat_mul(local, current_ctm)
            elif op == 're':
                x, y, w, h = [float(value) for value in operands[:4]]
                corners = [
                    _transform_point(current_ctm, x, y),
                    _transform_point(current_ctm, x + w, y),
                    _transform_point(current_ctm, x + w, y + h),
                    _transform_point(current_ctm, x, y + h),
                ]
                xs = [c[0] for c in corners]
                ys = [c[1] for c in corners]
                rects.append({
                    'x': min(xs),
                    'y': min(ys),
                    'width': max(xs) - min(xs),
                    'height': max(ys) - min(ys),
                })
            elif op == 'm':
                px, py = float(operands[0]), float(operands[1])
                current_point = _transform_point(current_ctm, px, py)
                subpath_start = current_point
            elif op == 'l' and current_point is not None:
                px, py = float(operands[0]), float(operands[1])
                next_point = _transform_point(current_ctm, px, py)
                lines.append({
                    'x1': current_point[0],
                    'y1': current_point[1],
                    'x2': next_point[0],
                    'y2': next_point[1],
                    'width': abs(next_point[0] - current_point[0]),
                    'height': abs(next_point[1] - current_point[1]),
                })
                current_point = next_point
            elif op == 'h' and current_point is not None and subpath_start is not None:
                lines.append({
                    'x1': current_point[0],
                    'y1': current_point[1],
                    'x2': subpath_start[0],
                    'y2': subpath_start[1],
                    'width': abs(subpath_start[0] - current_point[0]),
                    'height': abs(subpath_start[1] - current_point[1]),
                })
                current_point = subpath_start
            elif op in {'S', 's', 'f', 'F', 'B', 'B*', 'b', 'b*', 'f*', 'n'}:
                current_point = None
                subpath_start = None
            elif op == 'Do':
                if not operands or resources is None:
                    continue
                name = operands[0]
                try:
                    xobjects = resources.get('/XObject')
                    if xobjects is None:
                        continue
                    xobjects = xobjects.get_object()
                    xobj = xobjects.get(name)
                    if xobj is None:
                        continue
                    xobj = xobj.get_object()
                except Exception:
                    continue
                if xobj.get('/Subtype') != '/Form':
                    continue
                form_matrix_raw = xobj.get('/Matrix')
                if form_matrix_raw and len(form_matrix_raw) == 6:
                    form_matrix = tuple(float(v) for v in form_matrix_raw)
                else:
                    form_matrix = _IDENTITY_MATRIX
                sub_resources = xobj.get('/Resources')
                try:
                    if sub_resources is not None:
                        sub_resources = sub_resources.get_object()
                except Exception:
                    sub_resources = None
                if sub_resources is None:
                    sub_resources = resources
                inner_ctm = _mat_mul(form_matrix, current_ctm)
                _walk_content_stream(
                    xobj, pdf, sub_resources, inner_ctm,
                    rects, lines, depth + 1,
                )
        except Exception:
            continue


def _detect_text_field_suggestions(text_items, vector_shapes, page_num, page_width, page_height):
    suggestions = []
    rectangles = [
        rect for rect in vector_shapes['rects']
        if 25 <= rect['width'] <= 500 and 8 <= rect['height'] <= 42
    ]
    lines = [
        line for line in vector_shapes['lines']
        if 30 <= line['width'] <= 500
    ]

    for item in text_items:
        if not _looks_like_fillable_label(item):
            continue

        label_right = item['x'] + item['width']
        label_mid_y = item['y'] + item['height'] * 0.4
        best = None
        best_score = 0

        for rect in rectangles:
            gap = rect['x'] - label_right
            mid_y = rect['y'] + rect['height'] / 2
            if gap < -8 or gap > 90:
                continue
            if abs(mid_y - label_mid_y) > max(12, item['height'] * 1.2):
                continue
            score = 0.75 - max(gap, 0) / 180 - abs(mid_y - label_mid_y) / 80
            if score > best_score:
                best = {
                    'x': rect['x'],
                    'y': rect['y'],
                    'width': rect['width'],
                    'height': rect['height'],
                    'source': 'vector-rect',
                }
                best_score = score

        for line in lines:
            gap = min(line['x1'], line['x2']) - label_right
            mid_y = (line['y1'] + line['y2']) / 2
            if gap < -8 or gap > 90:
                continue
            if abs(mid_y - label_mid_y) > max(12, item['height'] * 1.4):
                continue
            inferred_height = max(item['height'] * 1.55, 14)
            score = 0.68 - max(gap, 0) / 180 - abs(mid_y - label_mid_y) / 80
            if score > best_score:
                best = {
                    'x': min(line['x1'], line['x2']),
                    'y': mid_y - inferred_height * 0.45,
                    'width': line['width'],
                    'height': inferred_height,
                    'source': 'vector-line',
                }
                best_score = score

        if not best:
            continue

        suggestions.append({
            'page': page_num,
            'type': _infer_text_field_type(item['text_norm']),
            'label': item['text'],
            'x': best['x'] / page_width * 100,
            'y': (page_height - best['y'] - best['height']) / page_height * 100,
            'width': best['width'] / page_width * 100,
            'height': best['height'] / page_height * 100,
            'confidence': round(max(best_score, 0.4), 2),
            'source': best['source'],
        })

    return suggestions


def _detect_checkbox_suggestions(text_items, vector_shapes, page_num, page_width, page_height):
    suggestions = []
    checkbox_rects = [
        rect for rect in vector_shapes['rects']
        if 6 <= rect['width'] <= 18 and 6 <= rect['height'] <= 18 and abs(rect['width'] - rect['height']) <= 4
    ]

    for rect in checkbox_rects:
        box_right = rect['x'] + rect['width']
        box_mid_y = rect['y'] + rect['height'] / 2
        nearby_text = None
        best_score = 0

        for item in text_items:
            gap = item['x'] - box_right
            if gap < 0 or gap > 140:
                continue
            text_mid_y = item['y'] + item['height'] * 0.4
            if abs(text_mid_y - box_mid_y) > max(10, item['height']):
                continue
            if len(item['text']) > 90 or item['text_norm'] in FIELD_LABEL_BLOCKLIST:
                continue
            score = 0.72 - gap / 180 - abs(text_mid_y - box_mid_y) / 60
            if score > best_score:
                nearby_text = item
                best_score = score

        if not nearby_text:
            continue

        suggestions.append({
            'page': page_num,
            'type': 'checkbox',
            'label': nearby_text['text'],
            'x': rect['x'] / page_width * 100,
            'y': (page_height - rect['y'] - rect['height']) / page_height * 100,
            'width': rect['width'] / page_width * 100,
            'height': rect['height'] / page_height * 100,
            'confidence': round(max(best_score, 0.42), 2),
            'source': 'vector-checkbox',
        })

    return suggestions


def _looks_like_fillable_label(item):
    norm = item['text_norm']
    if not norm or norm in FIELD_LABEL_BLOCKLIST:
        return False
    if len(norm) > 80:
        return False
    if norm.count(' ') > 12:
        return False
    # Require at least a couple of letters so we skip pure numbers,
    # punctuation, standalone page numbers, and similar noise.
    if sum(1 for ch in norm if ch.isalpha()) < 2:
        return False
    # Skip things that clearly aren't labels (dollar amounts, raw
    # instructions starting with lowercase mid-sentence fragments).
    if norm.startswith('$'):
        return False
    # We intentionally no longer require a keyword match — the geometric
    # pairing step in the caller only emits a suggestion if a nearby
    # fillable rectangle or line is found, which filters out the bulk
    # of non-label text that passes these surface checks.
    return True


def _infer_text_field_type(normalized_label):
    if any(token in normalized_label for token in ('date', 'dob', 'mm/dd', 'yyyy')):
        return 'date'
    if normalized_label in {'name', 'employee first name', 'employee last name'}:
        return 'name'
    return 'text'


def _overlaps_existing_field(candidate, existing_fields):
    for field in existing_fields:
        if int(field.get('page', 0)) != int(candidate.get('page', 0)):
            continue
        field_type = field.get('type')
        candidate_type = candidate.get('type')
        text_like_types = {'text', 'date', 'name'}
        same_family = (
            field_type == candidate_type or
            (field_type in text_like_types and candidate_type in text_like_types)
        )
        if not same_family:
            continue
        overlap = _intersection_over_union(candidate, field)
        if overlap >= 0.35:
            return True
    return False


def _intersection_over_union(a, b):
    ax1 = float(a['x'])
    ay1 = float(a['y'])
    ax2 = ax1 + float(a['width'])
    ay2 = ay1 + float(a['height'])
    bx1 = float(b['x'])
    by1 = float(b['y'])
    bx2 = bx1 + float(b['width'])
    by2 = by1 + float(b['height'])

    inter_x1 = max(ax1, bx1)
    inter_y1 = max(ay1, by1)
    inter_x2 = min(ax2, bx2)
    inter_y2 = min(ay2, by2)
    if inter_x2 <= inter_x1 or inter_y2 <= inter_y1:
        return 0.0

    intersection = (inter_x2 - inter_x1) * (inter_y2 - inter_y1)
    a_area = max(ax2 - ax1, 0) * max(ay2 - ay1, 0)
    b_area = max(bx2 - bx1, 0) * max(by2 - by1, 0)
    union = a_area + b_area - intersection
    if union <= 0:
        return 0.0
    return intersection / union


def generate_signed_pdf(document):
    """Stamp all signer field values onto the original PDF and save."""
    reader = PdfReader(document.pdf_file)
    writer = PdfWriter()

    # Collect all field values grouped by page
    field_values = SignerFieldValue.objects.filter(
        field__document=document
    ).select_related('field', 'field__assigned_to', 'signer')

    pages_fields = {}
    for fv in field_values:
        page_num = fv.field.page
        if page_num not in pages_fields:
            pages_fields[page_num] = []
        pages_fields[page_num].append(fv)

    # Also collect prefilled fields that have no signer value
    from apps.signatures.models import DocumentField
    prefilled_fields = DocumentField.objects.filter(
        document=document
    ).exclude(prefill_value='').exclude(
        pk__in=[fv.field_id for fv in field_values]
    )
    for pf in prefilled_fields:
        if pf.page not in pages_fields:
            pages_fields[pf.page] = []
        pages_fields[pf.page].append(pf)

    for page_idx, page in enumerate(reader.pages):
        page_num = page_idx + 1  # fields use 1-indexed pages
        page_width = float(page.mediabox.width)
        page_height = float(page.mediabox.height)

        if page_num in pages_fields:
            # Create overlay with reportlab
            overlay_buffer = io.BytesIO()
            c = pdf_canvas.Canvas(overlay_buffer, pagesize=(page_width, page_height))

            for item in pages_fields[page_num]:
                # item is either a SignerFieldValue or a DocumentField (prefilled)
                if isinstance(item, DocumentField):
                    field = item
                    value = item.prefill_value
                else:
                    field = item.field
                    value = item.value

                x = field.x / 100 * page_width
                # PDF coordinates are from bottom-left, field positions from top-left
                y = page_height - (field.y / 100 * page_height) - (field.height / 100 * page_height)
                w = field.width / 100 * page_width
                h = field.height / 100 * page_height

                # Determine font name based on bold/italic
                is_bold = getattr(field, 'bold', False)
                is_italic = getattr(field, 'italic', False)
                if is_bold and is_italic:
                    font_name = 'Helvetica-BoldOblique'
                elif is_bold:
                    font_name = 'Helvetica-Bold'
                elif is_italic:
                    font_name = 'Helvetica-Oblique'
                else:
                    font_name = 'Helvetica'

                # Use stored font_size if set, otherwise auto-calculate
                stored_fs = getattr(field, 'font_size', 0) or 0

                if field.field_type == 'name':
                    font_size = stored_fs if stored_fs > 0 else max(12, min(h * 0.7, 24))
                    c.setFont(font_name, font_size)
                    c.drawString(x + 2, y + h * 0.25, str(value))
                elif field.field_type in ('signature', 'initials') and value.startswith('data:image'):
                    img_data = base64.b64decode(value.split(',')[1])
                    img = ImageReader(io.BytesIO(img_data))
                    c.drawImage(img, x, y, w, h, preserveAspectRatio=True, mask='auto')
                elif field.field_type == 'checkbox':
                    if value == 'true':
                        font_size = stored_fs if stored_fs > 0 else max(12, min(h * 0.8, 24))
                        c.setFont('Helvetica-Bold', font_size)
                        c.drawString(x + 2, y + h * 0.2, '✓')
                else:
                    # Text, date
                    font_size = stored_fs if stored_fs > 0 else max(12, min(h * 0.7, 24))
                    c.setFont(font_name, font_size)
                    c.drawString(x + 2, y + h * 0.25, str(value))

            c.save()
            overlay_buffer.seek(0)
            overlay_reader = PdfReader(overlay_buffer)
            page.merge_page(overlay_reader.pages[0])

        writer.add_page(page)

    # Append audit trail certificate page
    audit_page_bytes = generate_audit_certificate(document)
    audit_reader = PdfReader(io.BytesIO(audit_page_bytes))
    for audit_page in audit_reader.pages:
        writer.add_page(audit_page)

    # Write final PDF
    output = io.BytesIO()
    writer.write(output)
    pdf_bytes = output.getvalue()

    # Compute SHA-256 hash
    pdf_hash = hashlib.sha256(pdf_bytes).hexdigest()
    document.pdf_hash = pdf_hash

    # Save signed PDF
    safe_title = ''.join(c for c in document.title[:50] if c.isalnum() or c in ' -_').strip()
    filename = f"signed_{document.pk}_{safe_title}.pdf"
    document.signed_pdf.save(filename, ContentFile(pdf_bytes), save=False)
    document.save()

    return pdf_bytes


def generate_audit_certificate(document):
    """Generate a PDF page with the audit trail certificate."""
    buffer = io.BytesIO()
    c = pdf_canvas.Canvas(buffer, pagesize=letter)
    width, height = letter

    y = height - inch
    c.setFont('Helvetica-Bold', 16)
    c.drawString(inch, y, 'Audit Trail Certificate')
    y -= 30

    c.setFont('Helvetica', 10)
    c.drawString(inch, y, f'Document: {document.title}')
    y -= 15
    c.drawString(inch, y, f'Document ID: {document.pk}')
    y -= 15
    c.drawString(inch, y, f'Created: {document.created_at.strftime("%Y-%m-%d %H:%M:%S UTC")}')
    y -= 15
    if document.completed_at:
        c.drawString(inch, y, f'Completed: {document.completed_at.strftime("%Y-%m-%d %H:%M:%S UTC")}')
        y -= 15
    y -= 10

    # Signers section
    c.setFont('Helvetica-Bold', 12)
    c.drawString(inch, y, 'Signers')
    y -= 18
    c.setFont('Helvetica', 10)
    for signer in document.signers.all():
        if y < inch:
            c.showPage()
            y = height - inch
            c.setFont('Helvetica', 10)
        c.drawString(inch, y, f'{signer.name} ({signer.email})')
        y -= 14
        if signer.role:
            c.drawString(inch + 20, y, f'Role: {signer.role}')
            y -= 14
        if signer.signed_at:
            c.drawString(inch + 20, y, f'Signed: {signer.signed_at.strftime("%Y-%m-%d %H:%M:%S UTC")}')
            y -= 14
            c.drawString(inch + 20, y, f'IP: {signer.ip_address or "N/A"}')
            y -= 18
        else:
            c.drawString(inch + 20, y, f'Status: {signer.get_status_display()}')
            y -= 18

    # Events section
    y -= 10
    if y < inch * 2:
        c.showPage()
        y = height - inch
    c.setFont('Helvetica-Bold', 12)
    c.drawString(inch, y, 'Event Log')
    y -= 18
    c.setFont('Helvetica', 9)
    for event in document.audit_events.all():
        if y < inch:
            c.showPage()
            y = height - inch
            c.setFont('Helvetica', 9)
        line = f'{event.created_at.strftime("%Y-%m-%d %H:%M:%S")} | {event.get_event_type_display()}'
        if event.signer:
            line += f' | {event.signer.name}'
        if event.ip_address:
            line += f' | IP: {event.ip_address}'
        if event.detail:
            line += f' | {event.detail[:60]}'
        c.drawString(inch, y, line)
        y -= 13

    # Hash note
    y -= 20
    if y < inch:
        c.showPage()
        y = height - inch
    c.setFont('Helvetica-Oblique', 8)
    c.drawString(inch, y, 'This document has been digitally sealed. The SHA-256 hash of the signed PDF')
    y -= 12
    c.drawString(inch, y, 'can be used to verify that the document has not been altered after signing.')

    c.save()
    return buffer.getvalue()
