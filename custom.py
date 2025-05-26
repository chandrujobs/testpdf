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
            logging.info(f"Processing page {page_num + 1}")
            logging.info(f"User terms to redact: {terms}")
            logging.info(f"Logo redaction enabled: {redact_logos}")
            logging.info(f"Number redaction enabled: {redact_numbers}")
            
            # Redact keyword terms (black redaction)
            for term in terms:
                if not term.strip():
                    continue
                search_results = page.search_for(term.strip(), flags=IGNORECASE)
                for rect in search_results:
                    page.add_redact_annot(rect, fill=text_redaction_color)
                    logging.info(f"Redacting keyword: '{term}' at {rect}")
            
            # Redact numbers if requested (black redaction)
            number_boxes = []
            if redact_numbers:
                logging.info("Redacting numbers")
                number_boxes = find_numbers_simple(page)
                for bbox in number_boxes:
                    page.add_redact_annot(bbox, fill=text_redaction_color)
                    logging.info(f"Redacting number at {bbox}")
                    
            # Redact visual logos if requested (white redaction)
            logo_boxes = []
            if redact_logos:
                logging.info("Redacting visual logos")
                # Pass the user terms to logo detection so they can be excluded
                logo_boxes = find_logos_simple(page, exclude_terms=terms)
                for bbox in logo_boxes:
                    page.add_redact_annot(bbox, fill=logo_redaction_color)
                    logging.info(f"Redacting visual logo at {bbox}")
            
            # Apply all redactions
            page.apply_redactions()
            
            # Add logo placeholders after redaction
            if redact_logos and logo_boxes:
                for bbox in logo_boxes:
                    try:
                        add_simple_placeholder(page, bbox, logo_replacement_text)
                        logging.info(f"Added logo placeholder at {bbox}")
                    except Exception as e:
                        logging.warning(f"Could not add placeholder: {e}")
            
            logging.info(f"Page {page_num + 1} processing complete. Applied {len(terms)} keyword redactions, {len(number_boxes)} number redactions, {len(logo_boxes)} logo redactions")
        
        # Create new document
        new_doc = fitz.open()
        new_doc.insert_pdf(doc)
        out_bytes = new_doc.write()
        return out_bytes
        
    except Exception as e:
        logging.error(f"PDF redaction failed: {e}")
        raise Exception(f"Failed to process PDF: {str(e)}")
        
    finally:
        if doc:
            doc.close()
        if new_doc:
            new_doc.close()


def find_logos_simple(page, exclude_terms=None):
    """
    IMPROVED logo detection with better accuracy
    Focuses on actual logos while avoiding table content and user-specified terms
    
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
    
    logging.info("=== IMPROVED LOGO DETECTION START ===")
    logging.info(f"Excluding user terms: {exclude_terms_lower}")
    
    try:
        # Method 1: Detect images (most reliable for logos)
        images = page.get_images(full=True)
        # FIXED: Reduced header area to top 25% instead of 40%
        header_height = page_rect.height * 0.25  
        
        logging.info(f"Found {len(images)} images on page")
        
        for img_index, img in enumerate(images):
            try:
                xref = img[0]
                bbox = page.get_image_bbox(xref)
                
                if bbox:
                    logging.info(f"Image {img_index}: {bbox} (size: {bbox.width:.1f}x{bbox.height:.1f})")
                    
                    # IMPROVED: More restrictive image logo criteria
                    is_logo_image = False
                    
                    # Position check - logos typically in top 25% and left 60%
                    if (bbox.y0 <= header_height and 
                        bbox.x0 <= page_rect.width * 0.6):
                        # Size check - reasonable logo dimensions
                        if (15 <= bbox.width <= 200 and 10 <= bbox.height <= 80):
                            is_logo_image = True
                            logging.info(f"  Image passes improved criteria")
                    
                    if is_logo_image:
                        logo_boxes.append(bbox)
                        logging.info(f"*** IMAGE LOGO DETECTED: {bbox} ***")
                        
            except Exception as e:
                logging.warning(f"Error processing image {img_index}: {e}")
        
        # Method 2: IMPROVED text-based logo detection
        text_dict = page.get_text("dict")
        
        for block in text_dict.get("blocks", []):
            if "lines" in block:
                for line in block["lines"]:
                    for span in line.get("spans", []):
                        text = span.get("text", "").strip()
                        bbox = fitz.Rect(span["bbox"])
                        
                        # FIXED: Only look in top 20% for text logos
                        if text and bbox.y0 <= page_rect.height * 0.20:
                            # CRITICAL: Skip user-specified terms completely
                            text_lower = text.lower().strip()
                            if any(term in text_lower or text_lower in term for term in exclude_terms_lower):
                                logging.info(f"SKIPPING user term: '{text}' (matches excluded terms)")
                                continue
                            
                            color = span.get("color", 0)
                            size = span.get("size", 12)
                            font = span.get("font", "").lower()
                            flags = span.get("flags", 0)
                            
                            logo_score = 0
                            reasons = []
                            
                            # IMPROVED: More restrictive position scoring
                            # Only top 20% and left 50% area
                            if (bbox.y0 <= page_rect.height * 0.20 and 
                                bbox.x0 <= page_rect.width * 0.50):
                                logo_score += 30
                                reasons.append("prime_logo_position")
                            else:
                                # Heavy penalty for text outside prime logo area
                                logo_score -= 40
                                reasons.append("outside_logo_area")
                            
                            # IMPROVED: Visual styling detection
                            if color != 0:  # Colored text
                                logo_score += 50  # Increased weight
                                reasons.append(f"colored_text({color})")
                            
                            if flags & 2**4:  # Bold styling
                                logo_score += 40  # Increased weight
                                reasons.append("bold")
                            
                            # IMPROVED: Font size criteria (more restrictive)
                            if size >= 20:  # Large distinctive text
                                logo_score += 45
                                reasons.append(f"large_font({size})")
                            elif size >= 14:  # Medium large
                                logo_score += 25
                                reasons.append(f"medium_large_font({size})")
                            elif size <= 9:  # Very small text (less likely to be logo)
                                logo_score -= 30
                                reasons.append(f"too_small_font({size})")
                            
                            # IMPROVED: Text characteristics
                            text_length = len(text)
                            if text_length <= 6:  # Very short (typical logos)
                                logo_score += 35
                                reasons.append(f"short_text({text_length})")
                            elif text_length <= 12:
                                logo_score += 20
                                reasons.append(f"medium_text({text_length})")
                            else:
                                # Penalty for long text (unlikely to be logo)
                                logo_score -= 25
                                reasons.append(f"long_text({text_length})")
                            
                            # IMPROVED: Enhanced exclusions for table content
                            exclude_patterns = [
                                # Table headers and content
                                r'\bname\b|\bdate\b|\btotal\b|\bamount\b|\bprice\b|\bcost\b',
                                r'\bquantity\b|\bqty\b|\bdescription\b|\bservice\b|\bitem\b',
                                r'\binvoice\b|\bbill\b|\breceipt\b|\bcustomer\b|\bclient\b',
                                r'\baddress\b|\bstreet\b|\bphone\b|\bemail\b|\bfax\b',
                                r'\btax\b|\bvat\b|\bsubtotal\b|\bdiscount\b|\bbalance\b',
                                r'\bperiod\b|\bfrom\b|\bto\b|\bref\b|\breference\b|\bnumber\b',
                                r'\bno\.\b|\bnr\.\b|\bcompany\b|\bcorp\b|\bcontact\b',
                                
                                # Contact information
                                r'\+\d+',  # Phone numbers
                                r'@\w+',   # Email addresses
                                r'www\.',  # Websites
                                r'http',   # URLs
                                
                                # Document content
                                r'\d{2}[./]\d{2}[./]\d{4}',  # Dates
                                r'\d{5,}',  # Long numbers
                                
                                # Business suffixes
                                r'\b(gmbh|ltd|inc|corp|llc|ag|sa|spa)\b',
                                
                                # Specific exclusions based on your PDF
                                r'software|germany|master|musterfirma|invoice|wmaccess|internet',
                            ]
                            
                            # ADDITIONAL: Check if text matches any user-specified term (double check)
                            text_lower = text.lower().strip()
                            user_term_match = False
                            for term in exclude_terms_lower:
                                if term and (term in text_lower or text_lower in term):
                                    user_term_match = True
                                    logging.info(f"EXCLUDED: '{text}' matches user term '{term}'")
                                    break
                            
                            if user_term_match:
                                continue
                            
                            excluded = False
                            for pattern in exclude_patterns:
                                if re.search(pattern, text_lower, re.IGNORECASE):
                                    logo_score -= 100  # Heavy penalty
                                    reasons.append(f"excluded_table_content({pattern[:15]})")
                                    excluded = True
                                    break
                            
                            # IMPROVED: Numbers penalty (table content often has numbers)
                            if not excluded:
                                digit_ratio = sum(c.isdigit() for c in text) / len(text) if len(text) > 0 else 0
                                if digit_ratio > 0.2:  # More than 20% digits
                                    logo_score -= 50
                                    reasons.append(f"too_many_digits({digit_ratio:.1f})")
                                
                                # IMPROVED: All caps check (many logos are in caps)
                                if text.isupper() and len(text) >= 2:
                                    logo_score += 30
                                    reasons.append("all_caps")
                                
                                # IMPROVED: Single word bonus (but not common words)
                                words = text.split()
                                if (len(words) == 1 and 
                                    len(text) >= 2 and 
                                    text.lower() not in ['the', 'and', 'for', 'with', 'from', 'date', 'name', 'total']):
                                    logo_score += 35
                                    reasons.append("single_distinctive_word")
                            
                            # Log analysis for debugging
                            logging.info(f"Text: '{text}' | Score: {logo_score} | Reasons: {reasons}")
                            
                            # FIXED: Increased threshold to reduce false positives
                            if logo_score >= 80:  # Increased from 50 to 80
                                # Precise boundaries
                                logo_bbox = fitz.Rect(
                                    max(0, bbox.x0 - 1),
                                    max(0, bbox.y0 - 1),
                                    min(page_rect.width, bbox.x1 + 1),
                                    min(page_rect.height, bbox.y1 + 1)
                                )
                                logo_boxes.append(logo_bbox)
                                logging.info(f"*** TEXT LOGO DETECTED: '{text}' (score: {logo_score}) at {logo_bbox} ***")
        
        # Method 3: Vector graphics detection
        try:
            drawings = page.get_drawings()
            if drawings:
                logging.info(f"Found {len(drawings)} vector drawings")
                
                for i, drawing in enumerate(drawings):
                    rect = drawing.get("rect", fitz.Rect())
                    
                    if rect:
                        logging.info(f"Drawing {i}: {rect} (size: {rect.width:.1f}x{rect.height:.1f})")
                        
                        # IMPROVED: More restrictive vector logo criteria
                        if (rect.y0 <= header_height and 
                            rect.x0 <= page_rect.width * 0.6 and
                            15 <= rect.width <= 150 and 
                            10 <= rect.height <= 60):
                            
                            logo_boxes.append(rect)
                            logging.info(f"*** VECTOR LOGO DETECTED: {rect} ***")
                            
        except Exception as e:
            logging.warning(f"Error detecting vector graphics: {e}")
        
        # Remove overlapping detections
        logo_boxes = remove_overlaps(logo_boxes)
        
    except Exception as e:
        logging.error(f"Error in improved logo detection: {e}")
    
    logging.info(f"=== IMPROVED DETECTION COMPLETE: {len(logo_boxes)} logos found ===")
    for i, box in enumerate(logo_boxes):
        logging.info(f"Logo {i+1}: {box}")
    
    return logo_boxes


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
                                logging.info(f"Found currency: '{match.group()}' in '{text}'")
                                
    except Exception as e:
        logging.warning(f"Error in number detection: {e}")
    
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
        logging.warning(f"Could not add placeholder: {e}")


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
