import hashlib
import io
import base64

from django.core.files.base import ContentFile
from PyPDF2 import PdfReader, PdfWriter
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas as pdf_canvas

from apps.signatures.models import SignerFieldValue, AuditEvent


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

                if field.field_type == 'name':
                    # Name field - render as text
                    font_size = min(h * 0.7, 12)
                    c.setFont('Helvetica', font_size)
                    c.drawString(x + 2, y + h * 0.25, str(value))
                elif field.field_type in ('signature', 'initials') and value.startswith('data:image'):
                    # Base64 image
                    img_data = base64.b64decode(value.split(',')[1])
                    img = ImageReader(io.BytesIO(img_data))
                    c.drawImage(img, x, y, w, h, preserveAspectRatio=True, mask='auto')
                elif field.field_type == 'checkbox':
                    if value == 'true':
                        font_size = min(h * 0.8, 14)
                        c.setFont('Helvetica-Bold', font_size)
                        c.drawString(x + 2, y + h * 0.2, '✓')
                else:
                    # Text, date
                    font_size = min(h * 0.7, 12)
                    c.setFont('Helvetica', font_size)
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
