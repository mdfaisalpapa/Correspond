import io
import frappe
from frappe import _
from frappe.utils import now_datetime
import pypdf
from reportlab.pdfgen import canvas
from reportlab.lib import colors

def create_watermark_layer(watermark_text, width, height):
    """Generates a single-page transparent PDF in-memory containing diagonal security watermark."""
    packet = io.BytesIO()
    can = canvas.Canvas(packet, pagesize=(width, height))
    
    can.saveState()
    # Light gray translucent color for unobtrusive security watermarking
    can.setFillColor(colors.HexColor("#7f8c8d"), alpha=0.25)
    can.setFont("Helvetica-Bold", 18)
    
    # Position in center and rotate 45 degrees
    can.translate(width / 2.0, height / 2.0)
    can.rotate(45)
    
    # Draw primary watermark line and secondary metadata line
    can.drawCentredString(0, 15, "CONFIDENTIAL & PROPRIETARY")
    can.setFont("Helvetica", 11)
    can.drawCentredString(0, -10, watermark_text)
    
    can.restoreState()
    can.save()
    packet.seek(0)
    return packet

def apply_pdf_watermark(input_pdf_bytes, watermark_text):
    """
    Overlays a security watermark on each page of input_pdf_bytes.
    Returns stamped PDF bytes.
    """
    reader = pypdf.PdfReader(io.BytesIO(input_pdf_bytes))
    writer = pypdf.PdfWriter()
    
    for page in reader.pages:
        page_width = float(page.mediabox.width)
        page_height = float(page.mediabox.height)
        
        watermark_packet = create_watermark_layer(watermark_text, page_width, page_height)
        watermark_pdf = pypdf.PdfReader(watermark_packet)
        watermark_page = watermark_pdf.pages[0]
        
        page.merge_page(watermark_page)
        writer.add_page(page)
        
    output_stream = io.BytesIO()
    writer.write(output_stream)
    output_stream.seek(0)
    return output_stream.getvalue()

@frappe.whitelist()
def download_watermarked_file(file_url, file_name=None):
    """
    Fetches a file attachment, overlays current user/desk watermark, and returns base64 or download stream.
    """
    user = frappe.session.user
    full_name = frappe.db.get_value("User", user, "full_name") or user
    current_desk = ""
    if file_name and frappe.db.exists("Correspond File", file_name):
        current_desk = frappe.db.get_value("Correspond File", file_name, "current_custodian") or ""
        
    ip_address = getattr(frappe.local, "request_ip", "127.0.0.1") if hasattr(frappe, "local") else "127.0.0.1"
    timestamp_str = now_datetime().strftime("%Y-%m-%d %H:%M:%S")
    
    stamp_text = f"Viewed by: {full_name} ({user}) | Desk: {current_desk} | IP: {ip_address} | {timestamp_str}"
    
    # Fetch file doc
    file_doc = frappe.get_doc("File", {"file_url": file_url})
    file_content = file_doc.get_content()
    
    if file_url.lower().endswith(".pdf") or (file_doc.file_name and file_doc.file_name.lower().endswith(".pdf")):
        try:
            watermarked_bytes = apply_pdf_watermark(file_content, stamp_text)
            frappe.response.filename = file_doc.file_name or "document.pdf"
            frappe.response.filecontent = watermarked_bytes
            frappe.response.type = "download"
            return
        except Exception as e:
            frappe.log_error(f"Watermarking error: {str(e)}", "PDF Watermarking")
            
    # Fallback to normal download if non-pdf or watermarking fails
    frappe.response.filename = file_doc.file_name
    frappe.response.filecontent = file_content
    frappe.response.type = "download"
