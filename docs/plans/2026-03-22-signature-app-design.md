# E-Signature App Design

**Date**: 2026-03-22
**Status**: Approved

## Overview

DocuSign-like e-signature functionality built as a new Django app (`apps/signatures`) inside the existing Follow Up Boss CRM. Allows Dave and Kelly to upload PDFs, visually place signature/initial/text/date/checkbox fields, and send documents to clients for signing via email link — no client account required.

## Requirements

- Upload PDF documents
- Drag-and-drop field placement on PDF pages (signature, initials, text, date, checkbox)
- Multiple signers per document with color-coded field assignment
- Email-based signing links (no login required for clients)
- Draw-to-sign and type-to-sign options
- Reusable document templates with role placeholders
- Full audit trail (opened, viewed, signed, completed) with IP/timestamp
- Tamper detection via SHA-256 hash of final signed PDF
- Audit certificate page appended to completed documents
- Mobile-friendly signing experience

## Data Models

### Document
- Links to uploading user and team
- Stores original PDF file, title
- Status: `draft`, `sent`, `viewed`, `completed`, `declined`, `expired`
- Optional expiration date
- Optional link to CRM Contact
- Created/updated timestamps

### DocumentField
- Links to a Document
- Field type: `signature`, `initials`, `text`, `date`, `checkbox`
- Position: page number, x, y, width, height (as percentages)
- Required flag, label
- Assigned to a DocumentSigner

### DocumentSigner
- Links to a Document
- Name, email, role label (e.g. "Buyer", "Seller")
- Unique access token (UUID) for signing link
- Status: `pending`, `opened`, `completed`, `declined`
- IP address and completion timestamp captured on signing

### SignerFieldValue
- Links to a DocumentField and DocumentSigner
- Stores the value (text, base64 signature image, etc.)
- Timestamp of when filled

### AuditEvent
- Links to Document, optionally to a Signer
- Event type: `created`, `sent`, `opened`, `field_signed`, `completed`, `declined`, `downloaded`
- IP address, user agent, timestamp

### DocumentTemplate
- Same structure as Document but with placeholder signer roles
- Template fields with positions saved
- "Use template" creates a new Document pre-populated with template fields

## User Workflows

### Sending a Document
1. Upload PDF, give it a title
2. Add signers by name + email (optionally pick from CRM contacts)
3. Place fields on PDF via drag-and-drop (PDF.js viewer + toolbar)
4. Each field assigned to a signer (color-coded)
5. Review and send — each signer gets email with unique link
6. Track status from document list; notifications on open/complete/decline

### Client Signing Experience
1. Click link in email — no login needed
2. See PDF with assigned fields highlighted, guided field-by-field
3. Signature fields: draw with mouse/finger or type (script font)
4. Other fields: type text, pick date, check boxes
5. Click "Finish" — signed PDF generated server-side
6. Confirmation page + email with download link
7. Sender notified of completion

### Templates
1. Create template with role placeholders instead of real signers
2. "Start from Template" when sending new document
3. Assign real signers to roles, fields pre-placed
4. Adjust if needed, then send

### Final Document
- All signatures/values stamped into PDF
- Audit trail certificate page appended
- SHA-256 hash computed and stored for tamper verification

## Technical Architecture

### Frontend
- PDF.js for document rendering
- Vanilla JS drag-and-drop for field placement (consistent with CRM's Django templates + HTMX approach)
- HTML5 Canvas for draw-to-sign
- Type-to-sign with script font
- Mobile-responsive signing experience

### Backend
- New Django app: `apps/signatures`
- PyPDF2 for reading PDFs
- ReportLab for stamping signatures/text onto PDF pages
- Existing SMTP email infrastructure for sending signing links
- Files stored in `/media/signatures/` (originals + signed versions)
- All audit events logged with IP, user agent, timestamp
- SHA-256 hash of final PDF for tamper verification endpoint

### Security
- UUID tokens for signing links (unguessable, one per signer)
- Optional expiration dates on links
- Signed PDFs immutable once generated
- CSRF protection on all internal forms
- Server-side validation of all signing submissions
- Rate limiting on signing endpoints

### CRM Integration
- Documents can link to CRM Contacts (auto-populates signer info)
- ContactActivity entries logged: `document_sent`, `document_signed`
- Signatures section in CRM sidebar navigation

### New Dependencies
- `PyPDF2` — PDF reading/parsing (MIT license)
- `reportlab` — PDF content generation/stamping (BSD license)
- `pdf.js` — client-side PDF rendering (Apache license, CDN or static)

All free, no paid services or API keys required.
