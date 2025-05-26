import io
import re
import fitz
import logging

IGNORECASE = 1

def redact_pdf_bytes(pdf_bytes, terms, redact_logos=False, redact_numbers=False, logo_replacement_text="LOGO", text_redaction_color=(0, 0, 0), logo_redaction_color=(1, 1, 1)):
    """
    Main PDF redaction function that handles text, numbers, and visual logos
    
    Args:
        pdf_bytes: Raw PDF bytes
        terms: List of text terms to redact
        redact_logos: Whether to redact visual logo elements
        redact_numbers: Whether to redact currency/numbers
        logo_replacement_text: Text to show in logo placeholders
        text_redaction_color: Color for text redaction (black)
        logo_redaction_color: Color for logo redaction (white)
    
    Returns:
        bytes: Redacted PDF as raw bytes
    """
    doc = None
    new_doc = None
    
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        
        if not doc.page_count:
            raise ValueError("PDF contains no pages")
        
        for page_num, page in enumerate(doc):
            logging.info("Processing page %d", page_num + 1)
            logging.info("User terms to redact: %s", terms)
            logging.info("Logo redaction enabled: %s", redact_logos)
            logging.info("Number redaction enabled: %s", redact_numbers)
            
            # Redact keyword terms (black redaction)
            for term in terms:
                if not term.strip():
                    continue
                search_results = page.search_for(term.strip(), flags=IGNORECASE)
                for rect in search_results:
                    page.add_redact_annot(rect, fill=text_redaction_color)
                    logging.info("Redacting keyword: '%s' at %s", term, rect)
            
            # Redact numbers if requested (black redaction)
            number_boxes = []
            if redact_numbers:
                logging.info("Redacting numbers")
                number_boxes = find_numbers_simple(page)
                for bbox in number_boxes:
                    page.add_redact_annot(bbox, fill=text_redaction_color)
                    logging.info("Redacting number at %s", bbox)
                    
            # Redact visual logos if requested (white redaction)
            logo_boxes = []
            if redact_logos:
                logging.info("Redacting visual logos")
                # Pass the user terms to logo detection so they can be excluded
                logo_boxes = find_logos_simple(page, exclude_terms=terms)
                for bbox in logo_boxes:
                    page.add_redact_annot(bbox, fill=logo_redaction_color)
                    logging.info("Redacting visual logo at %s", bbox)
            
            # Apply all redactions
            page.apply_redactions()
            
            # Add logo placeholders after redaction
            if redact_logos and logo_boxes:
                for bbox in logo_boxes:
                    try:
                        add_simple_placeholder(page, bbox, logo_replacement_text)
                        logging.info("Added logo placeholder at %s", bbox)
                    except Exception as e:
                        logging.warning("Could not add placeholder: %s", e)
            
            logging.info("Page %d processing complete. Applied %d keyword redactions, %d number redactions, %d logo redactions", 
                        page_num + 1, len(terms), len(number_boxes), len(logo_boxes))
        
        # Create new document
        new_doc = fitz.open()
        new_doc.insert_pdf(doc)
        out_bytes = new_doc.write()
        return out_bytes
        
    except Exception as e:
        logging.error("PDF redaction failed: %s", e)
        raise Exception("Failed to process PDF: " + str(e))
        
    finally:
        if doc:
            doc.close()
        if new_doc:
            new_doc.close()


def find_logos_simple(page, exclude_terms=None):
    """
    COMPREHENSIVE logo detection - images, drawings, and company text patterns
    Based on the working pdf_processor.py approach
    
    Args:
        page: PyMuPDF page object
        exclude_terms: List of user-specified terms to exclude from logo detection
    """
    if exclude_terms is None:
        exclude_terms = []
    
    # Convert exclude_terms to lowercase for case-insensitive comparison
    exclude_terms_lower = [term.lower().strip() for term in exclude_terms if term.strip()]
    
    logo_boxes = []
    page_rect = page.rect
    
    logging.info("=== COMPREHENSIVE LOGO DETECTION START ===")
    logging.info("Excluding user terms: %s", exclude_terms_lower)
    
    try:
        page_width = page_rect.width
        page_height = page_rect.height
        max_logo_y0 = page_height * 0.15  # Top 15% for logos
        max_logo_width = page_width * 0.40  # Max 40% width
        min_dim = 15
        max_dim = 200
        
        # Strategy 1: Image-based logos
        try:
            images = page.get_images(full=True)
            logging.info("Found %d images on page", len(images))
            
            for img_index, img_info in enumerate(images):
                try:
                    xref = img_info[0]
                    img_instances = page.get_image_rects(xref, transform=False)
                    
                    for rect in img_instances:
                        if (rect.y0 < max_logo_y0 and 
                            min_dim < rect.width < max_logo_width and 
                            min_dim < rect.height < max_dim and 
                            rect.is_valid and not rect.is_empty):
                            
                            # Expand slightly for better coverage
                            expanded_rect = (rect + (-2, -2, 2, 2)).normalize()
                            logo_boxes.append(expanded_rect)
                            logging.info("*** IMAGE LOGO DETECTED: %s ***", expanded_rect)
                            
                except Exception as e:
                    logging.warning("Error processing image %d: %s", img_index, e)
                    
        except Exception as e:
            logging.warning("Error in image logo detection: %s", e)
        
        # Strategy 2: Vector drawings/graphics
        try:
            draw_rect = fitz.Rect(0, 0, page_width, max_logo_y0 + 10)
            drawings = page.get_drawings(rect=draw_rect)
            
            for drawing in drawings:
                if "rect" in drawing:
                    rect = fitz.Rect(drawing["rect"])
                    if (rect.y0 < max_logo_y0 and 
                        min_dim < rect.width < max_logo_width and 
                        min_dim < rect.height < max_dim and 
                        rect.is_valid and not rect.is_empty):
                        
                        logo_boxes.append(rect)
                        logging.info("*** VECTOR LOGO DETECTED: %s ***", rect)
                        
        except Exception as e:
            logging.warning("Error in vector logo detection: %s", e)
        
        # Strategy 3: Company name text patterns (like working version)
        try:
            # Company patterns from working version
            company_patterns = [
                "Ltd", "Inc", "GmbH", "LLC", "Corp", "Limited", "S.A.", "B.V.", 
                "AG", "Co.", "Group", "Tech", "Solutions", "Software", "Intl", 
                "Holdings", "PwC", "CPB", "SOFTWARE", "GERMANY"
            ]
            
            txt_rect = fitz.Rect(0, 0, page_width, page_height * 0.15)
            blocks = page.get_text("dict", flags=fitz.TEXT_PRESERVE_LIGATURES, clip=txt_rect)["blocks"]
            
            for block in blocks:
                if block["type"] == 0:  # Text block
                    for line in block.get("lines", []):
                        for span in line.get("spans", []):
                            text = span.get("text", "").strip()
                            rect = fitz.Rect(span.get("bbox", (0, 0, 0, 0)))
                            
                            if text and rect.y0 < max_logo_y0:
                                # Skip user-specified terms completely
                                text_lower = text.lower().strip()
                                user_term_excluded = False
                                for term in exclude_terms_lower:
                                    if term and (term in text_lower or text_lower in term or text_lower == term):
                                        logging.info("EXCLUDING user term: '%s' (matches '%s')", text, term)
                                        user_term_excluded = True
                                        break
                                
                                if user_term_excluded:
                                    continue
                                
                                # Check for company patterns
                                for pattern in company_patterns:
                                    pattern_regex = r'\b' + re.escape(pattern) + r'\b'
                                    if re.search(pattern_regex, text, re.IGNORECASE):
                                        # Expand text rect slightly
                                        expanded_rect = (rect + (-5, -3, 5, 3)).normalize()
                                        if expanded_rect.is_valid and not expanded_rect.is_empty:
                                            logo_boxes.append(expanded_rect)
                                            logging.info("*** COMPANY TEXT LOGO DETECTED: '%s' (pattern: %s) at %s ***", 
                                                       text, pattern, expanded_rect)
                                            break  # Found pattern, move to next span
                                        
        except Exception as e:
            logging.warning("Error in text pattern logo detection: %s", e)
        
        # Merge overlapping rectangles (from working version)
        if logo_boxes:
            logo_boxes = merge_logo_rects(logo_boxes, tolerance=5)
        
    except Exception as e:
        logging.error("Error in comprehensive logo detection: %s", e)
    
    logging.info("=== COMPREHENSIVE DETECTION COMPLETE: %d logos found ===", len(logo_boxes))
    for i, box in enumerate(logo_boxes):
        logging.info("Logo %d: %s", i+1, box)
    
    return logo_boxes


def merge_logo_rects(rects, tolerance=5):
    """
    Merges overlapping or close rectangles (from working version)
    """
    if not rects:
        return []
    
    # Sort rectangles by position
    rects.sort(key=lambda r: (r.y0, r.x0))
    merged = []
    
    if not rects:
        return merged
    
    current_rect = rects[0].irect
    
    for i in range(1, len(rects)):
        next_rect = rects[i].irect
        
        # Check if rectangles are close or overlapping
        tolerance_rect = fitz.Rect(next_rect) + (-tolerance, -tolerance, tolerance, tolerance)
        if current_rect.intersects(tolerance_rect):
            # Merge rectangles
            current_rect |= next_rect
        else:
            # Add current merged rectangle and start new one
            merged.append(fitz.Rect(current_rect))
            current_rect = next_rect
    
    # Add the last rectangle
    merged.append(fitz.Rect(current_rect))
    
    return merged


def find_numbers_simple(page):
    """
    Enhanced number detection for currency amounts and financial data
    
    Targets:
    - Currency symbols with amounts (€, $, CHF, etc.)
    - Formatted monetary amounts with decimal places
    - Large numbers that appear to be financial
    
    Excludes:
    - Dates
    - Addresses
    - Phone numbers
    - Reference numbers
    
    Returns:
        list: List of bounding boxes for detected numbers
    """
    number_boxes = []
    
    try:
        text_dict = page.get_text("dict")
        for block in text_dict.get("blocks", []):
            if "lines" in block:
                for line in block["lines"]:
                    for span in line.get("spans", []):
                        text = span.get("text", "").strip()
                        bbox = fitz.Rect(span["bbox"])
                        
                        if not text:
                            continue
                        
                        # Skip dates and addresses
                        if re.search(r"\d{1,2}[./]\d{1,2}[./]\d{4}|\d{6}|street|phone|email", text, re.IGNORECASE):
                            continue
                        
                        # Enhanced currency patterns
                        patterns = [
                            r"€\s*\d+[.,]\d{2}",           # €123.45
                            r"\$\s*\d+[.,]\d{2}",          # $123.45
                            r"CHF\s*\d+[.,]\d{2}",         # CHF 123.45
                            r"\b\d{1,4}[.,]\d{2}\b",       # 123.45, 1234.56
                            r"\b\d+[.,]0{1,2}\b",          # 123.00, 45.0
                            r"\b[1-9]\d{0,2}[.,]\d{1,2}\b" # 1.2, 12.34, 123.45
                        ]
                        
                        for pattern in patterns:
                            matches = list(re.finditer(pattern, text))
                            for match in matches:
                                start_char = match.start()
                                end_char = match.end()
                                char_width = bbox.width / len(text) if len(text) > 0 else 0
                                
                                number_bbox = fitz.Rect(
                                    bbox.x0 + (start_char * char_width),
                                    bbox.y0,
                                    bbox.x0 + (end_char * char_width),
                                    bbox.y1
                                )
                                
                                number_boxes.append(number_bbox)
                                logging.info("Found currency: '%s' in '%s'", match.group(), text)
                                
    except Exception as e:
        logging.warning("Error in number detection: %s", e)
    
    return number_boxes


def remove_overlaps(boxes):
    """
    Remove overlapping bounding boxes to prevent duplicate redactions
    
    Args:
        boxes: List of fitz.Rect objects
        
    Returns:
        list: List of non-overlapping boxes
    """
    if len(boxes) <= 1:
        return boxes
    
    # Sort by area (smaller first)
    boxes_with_area = [(box, box.width * box.height) for box in boxes]
    boxes_with_area.sort(key=lambda x: x[1])
    
    result = []
    for box, area in boxes_with_area:
        # Check if this box overlaps significantly with any already added box
        overlaps = False
        for existing_box in result:
            intersection = box & existing_box  # Intersection
            if intersection:
                # If intersection is more than 50% of the smaller box, consider it overlap
                intersection_area = intersection.width * intersection.height
                if intersection_area > min(area, existing_box.width * existing_box.height) * 0.5:
                    overlaps = True
                    break
        
        if not overlaps:
            result.append(box)
    
    return result


def add_simple_placeholder(page, bbox, text="LOGO"):
    """
    Add a simple placeholder for redacted logos
    
    Args:
        page: PyMuPDF page object
        bbox: Bounding box where placeholder should be added
        text: Text to display in placeholder
    """
    try:
        # Draw simple border around redacted area
        page.draw_rect(bbox, color=(0.5, 0.5, 0.5), width=1)
        
        # Add placeholder text
        font_size = min(10, bbox.height * 0.4)
        page.insert_textbox(
            bbox,
            text,
            fontsize=font_size,
            fontname="helv",
            align=1,  # Center alignment
            color=(0.5, 0.5, 0.5)
        )
    except Exception as e:
        logging.warning("Could not add placeholder: %s", e)


def validate_pdf_bytes(pdf_bytes):
    """
    Validate that the provided bytes represent a valid PDF
    
    Args:
        pdf_bytes: Raw PDF bytes to validate
        
    Returns:
        bool: True if valid PDF, False otherwise
    """
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        is_valid = doc.page_count > 0
        doc.close()
        return is_valid
    except:
        return False


def get_pdf_info(pdf_bytes):
    """
    Extract basic information about the PDF
    
    Args:
        pdf_bytes: Raw PDF bytes
        
    Returns:
        dict: PDF information including page count, metadata, etc.
    """
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        info = {
            "page_count": doc.page_count,
            "metadata": doc.metadata,
            "is_encrypted": doc.is_encrypted,
            "needs_pass": doc.needs_pass
        }
        doc.close()
        return info
    except Exception as e:
        return {"error": str(e)}
