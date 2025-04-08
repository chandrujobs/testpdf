# pdf_processor.py
import fitz  # PyMuPDF
import os
import base64
import io
import re  # Import regular expressions
import tempfile
import streamlit as st
import numpy as np
from PIL import Image

# --- Display/Preview Functions ---

def display_pdf_preview(pdf_bytes):
    """Display a PDF preview from bytes."""
    try:
        if pdf_bytes:
            base64_pdf = base64.b64encode(pdf_bytes).decode("utf-8")
            pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="500px" type="application/pdf" style="border: 1px solid #ccc; border-radius: 5px; background-color: #eee;"></iframe>'
            return pdf_display
        else:
            return "<p>No PDF data available</p>"
    except Exception as e:
        st.error(f"Error displaying PDF preview: {str(e)}")
        return f"<p>Preview Error: {e}</p>"

def generate_preview(pdf_path, max_pages=3):
    """Generate preview bytes for first few pages."""
    preview_doc, doc = None, None
    try:
        doc = fitz.open(pdf_path)
        total_pages = len(doc)
        if total_pages == 0:
            st.warning(f"Document '{os.path.basename(pdf_path)}' has 0 pages.")
            return None
        num_pages = min(max_pages, total_pages)
        preview_doc = fitz.open()
        if num_pages > 0:
             preview_doc.insert_pdf(doc, from_page=0, to_page=num_pages - 1)
        else:
             # This case should be caught by total_pages == 0 check, but as safeguard:
             return None
        return preview_doc.tobytes(garbage=3, clean=True)
    except Exception as e:
        st.error(f"Preview Gen Error for '{os.path.basename(pdf_path)}': {e}")
        return None
    finally:
        if preview_doc: preview_doc.close()
        if doc: doc.close()

def display_pdf_file(pdf_path, max_preview_size_mb=15):
    """Display PDF, using preview for large files."""
    if not os.path.exists(pdf_path):
        st.error(f"PDF not found: {pdf_path}")
        return
    try:
        size_mb = os.path.getsize(pdf_path) / (1024 * 1024)
        if size_mb > max_preview_size_mb:
            st.warning(f"Large PDF ({size_mb:.1f}MB), showing preview.")
            preview_bytes = generate_preview(pdf_path)
            if preview_bytes:
                st.markdown(display_pdf_preview(preview_bytes), unsafe_allow_html=True)
            else:
                st.error("Preview failed for large PDF.")
        else:
            with open(pdf_path, "rb") as f:
                pdf_bytes = f.read()
            st.markdown(display_pdf_preview(pdf_bytes), unsafe_allow_html=True)
    except Exception as e:
        st.error(f"PDF Display Error for '{os.path.basename(pdf_path)}': {e}")

# --- REFORMATTED Quality Analysis function ---
def analyze_pdf_quality(pdf_path):
    """
    Analyzes PDF quality based on text, image, and structure metrics.
    (Reformatted for clarity and to address Pylance errors).
    """
    doc = None
    # Initialize with default low scores and a message
    quality_metrics = {
        "text_quality": 1, "image_quality": 1, "structure_quality": 1,
        "overall_score": 1, "details": ["Analysis could not be completed."]
    }
    try:
        doc = fitz.open(pdf_path)
        quality_metrics["details"] = [] # Reset details for this run

        total_pages = len(doc)
        if total_pages == 0:
            quality_metrics["details"].append("PDF has 0 pages.")
            quality_metrics.update({"text_quality": 0, "image_quality": 0, "structure_quality": 0, "overall_score": 0})
            return quality_metrics

        # --- 1. Text Extraction Quality ---
        searchable_pages = 0
        text_check_pages = min(10, total_pages)
        for page_num in range(text_check_pages):
            try:
                page = doc[page_num]
                # Check for meaningful text content quickly
                text = page.get_text("text", flags=fitz.TEXT_INHIBIT_SPACES) # Ignore spaces for length check
                if text and len(text) > 50:  # Arbitrary threshold for meaningful content
                    searchable_pages += 1
            except Exception as text_err:
                 quality_metrics["details"].append(f"Warning: Text check error page {page_num+1}: {text_err}")

        # Calculate text quality score
        if text_check_pages > 0:
            text_searchable_ratio = searchable_pages / text_check_pages
            # Assign score based on ratio thresholds
            if text_searchable_ratio > 0.9: score = 5
            elif text_searchable_ratio > 0.7: score = 4
            elif text_searchable_ratio > 0.5: score = 3
            elif text_searchable_ratio > 0.3: score = 2
            elif text_searchable_ratio > 0.1: score = 1
            else: score = 0
            quality_metrics["text_quality"] = score
            if score <= 2:
                quality_metrics["details"].append("Low text searchability (potential scan/image).")
        else:
             quality_metrics["text_quality"] = 0 # Should not happen if total_pages > 0
             quality_metrics["details"].append("Could not analyze text quality.")


        # --- 2. Image Resolution Quality ---
        total_images_analyzed = 0
        high_res_images = 0
        low_res_images = 0
        image_check_pages = min(5, total_pages)

        for page_num in range(image_check_pages):
            page = doc[page_num]
            img_list = [] # Defined outside try
            try:
                img_list = page.get_images(full=True) # Line 75 context
            except Exception as img_e:
                 quality_metrics["details"].append(f"Warning: Could not get images page {page_num+1}: {img_e}")
                 continue # Skip page if image list fails

            # Line 76 context
            for img_index, img_info in enumerate(img_list):
                total_images_analyzed += 1
                xref = img_info[0]
                # Line 77 context (rewritten for clarity)
                try:
                    img_dict = doc.extract_image(xref) # Gets properties like width, height, bpc
                    if img_dict:
                        pix_width = img_dict.get("width", 0)
                        pix_height = img_dict.get("height", 0)
                        pixel_count = pix_width * pix_height
                        # Simple check: if image pixel count is reasonably high assume good quality
                        if pixel_count > 250000: # ~0.25 Megapixel threshold (500x500)
                            high_res_images += 1
                        elif pixel_count > 0: # If it has dimensions but isn't high-res
                             low_res_images += 1
                except Exception:
                    # Ignore errors analyzing single images silently
                    pass

        # Calculate image quality score
        if total_images_analyzed > 0:
            image_quality_ratio = high_res_images / total_images_analyzed
            if image_quality_ratio > 0.8: score = 5
            elif image_quality_ratio > 0.6: score = 4
            elif image_quality_ratio > 0.4: score = 3
            elif image_quality_ratio > 0.2: score = 2
            else: score = 1
            quality_metrics["image_quality"] = score
            # Add detail if significant low res images found
            if low_res_images > high_res_images * 0.5 and low_res_images > 0:
                quality_metrics["details"].append("Potential low image resolution detected.")
        else:
            quality_metrics["image_quality"] = 3 # Default if no images found/analyzed
            quality_metrics["details"].append("No images analyzed for resolution.")


        # --- 3. Document Structure Quality ---
        has_bookmarks = False
        has_metadata = False
        # Line 87 context (rewritten for clarity)
        try:
             has_bookmarks = len(doc.get_toc(simple=True)) > 0
        except Exception: pass # Ignore TOC errors
        try:
             meta = doc.metadata
             if meta and (meta.get('title') or meta.get('author') or meta.get('producer')):
                 has_metadata = True
        except Exception: pass # Ignore metadata errors

        structure_score = 0
        if has_bookmarks: structure_score += 2
        if has_metadata: structure_score += 1

        # Check page layout consistency (size)
        page_sizes = set()
        structure_check_pages = min(10, total_pages)
        # Line 90 context (rewritten for clarity)
        for page_num in range(structure_check_pages):
            try:
                page = doc[page_num]
                # Round dimensions slightly to account for minor variations
                page_size_tuple = (round(page.rect.width, 1), round(page.rect.height, 1))
                page_sizes.add(page_size_tuple)
            except Exception:
                # Ignore errors getting page size silently
                pass

        if len(page_sizes) == 1 and structure_check_pages > 0:
            structure_score += 2  # Consistent page sizes are good
        elif len(page_sizes) > 1:
            structure_score = max(0, structure_score - 1)  # Penalize inconsistent sizes
            quality_metrics["details"].append("Inconsistent page sizes detected.")

        quality_metrics["structure_quality"] = min(5, structure_score) # Cap score at 5
        if structure_score <= 2:
            quality_metrics["details"].append("Basic document structure quality.")


        # --- Calculate Overall Score ---
        quality_metrics["overall_score"] = round(
            (quality_metrics["text_quality"] * 0.5) +
            (quality_metrics["image_quality"] * 0.3) +
            (quality_metrics["structure_quality"] * 0.2)
        )

        # Default detail message if nothing specific was found
        if not quality_metrics["details"]:
             quality_metrics["details"].append("Basic quality analysis completed.")

        return quality_metrics

    except Exception as e:
        st.error(f"Error during PDF quality analysis for '{os.path.basename(pdf_path)}': {e}")
        # Ensure details list exists and add error message
        if "details" not in quality_metrics: quality_metrics["details"] = []
        quality_metrics["details"].append(f"Analysis Error: {str(e)}")
        # Return default low scores on major error
        return {
            "text_quality": 1, "image_quality": 1, "structure_quality": 1,
            "overall_score": 1, "details": quality_metrics["details"]
        }
    finally:
        if doc:
            doc.close()


# --- Logo Removal function ---
def merge_rects(rects, tolerance=5):
    """Merges overlapping or close rectangles."""
    if not rects: return []
    rects.sort(key=lambda r: (r.y0, r.x0))
    merged = []
    if not rects: return merged # Return empty if no rects after sort (shouldn't happen)
    current_rect = rects[0].irect
    for i in range(1, len(rects)):
        next_rect = rects[i].irect
        if current_rect.intersects(next_rect + (-tolerance, -tolerance, tolerance, tolerance)):
            current_rect |= next_rect # Merge
        else:
            merged.append(fitz.Rect(current_rect))
            current_rect = next_rect
    merged.append(fitz.Rect(current_rect)) # Add the last one
    return merged

def remove_all_logos(page, add_watermarks=True):
    """Refined approach to remove logos."""
    log_entries = []
    watermark_areas = []
    potential_logo_rects = []
    try:
        page_width = page.rect.width; page_height = page.rect.height
        max_logo_y0 = page_height * 0.10; max_logo_width = page_width * 0.40
        min_dim = 20; max_dim = 200

        # Strategy 1: Images
        try:
            img_list = page.get_images(full=True)
            for _, img_info in enumerate(img_list):
                xref = img_info[0]; img_instances = page.get_image_rects(xref, transform=False)
                for r in img_instances:
                    if r.y0 < max_logo_y0 and min_dim < r.width < max_logo_width and min_dim < r.height < max_dim and r.is_valid and not r.is_empty:
                        exp_r = (r + (-2, -2, 2, 2)).normalize()
                        potential_logo_rects.append(exp_r); watermark_areas.append({"rect": exp_r, "priority": 1, "type": "image"})
        except Exception as e: log_entries.append(f"Warn: Img L Rmv pg {page.number + 1}: {e}")

        # Strategy 2: Drawings
        try:
            draw_rect = fitz.Rect(0, 0, page_width, max_logo_y0 + 10)
            drawings = page.get_drawings(rect=draw_rect)
            for d in drawings:
                if "rect" in d:
                    r = fitz.Rect(d["rect"])
                    if r.y0 < max_logo_y0 and min_dim < r.width < max_logo_width and min_dim < r.height < max_dim and r.is_valid and not r.is_empty:
                        potential_logo_rects.append(r); watermark_areas.append({"rect": r, "priority": 1, "type": "drawing"})
        except Exception as e: log_entries.append(f"Warn: Draw L Rmv pg {page.number + 1}: {e}")

        # Strategy 3: Text Patterns
        try:
            patterns = ["Ltd","Inc","GmbH","LLC","Corp","Limited","S.A.","B.V.","AG","Co.","Group","Tech","Solutions","Software","Intl","Holdings","PwC"]
            txt_rect = fitz.Rect(0, 0, page_width, page_height * 0.15)
            blocks = page.get_text("dict", flags=fitz.TEXT_PRESERVE_LIGATURES, clip=txt_rect)["blocks"]
            for block in blocks:
                if block["type"] == 0:
                    for line in block.get("lines", []):
                        for span in line.get("spans", []):
                            txt = span.get("text",""); r = fitz.Rect(span.get("bbox",(0,0,0,0)))
                            if r.y0 < max_logo_y0:
                                for p in patterns:
                                    if re.search(r'\b' + re.escape(p) + r'\b', txt, re.IGNORECASE):
                                        exp_r = (r + (-5, -3, 5, 3)).normalize()
                                        if exp_r.is_valid and not exp_r.is_empty:
                                            potential_logo_rects.append(exp_r); watermark_areas.append({"rect": exp_r, "priority": 2, "type": "text", "text": p})
                                            break # Found pattern, next span
        except Exception as e: log_entries.append(f"Warn: Text L Rmv pg {page.number + 1}: {e}")

        # Consolidate and Apply Redactions
        applied_count = 0
        if potential_logo_rects:
            final_rects = merge_rects(potential_logo_rects, tolerance=5)
            if final_rects:
                log_entries.append(f"Applying {len(final_rects)} logo redaction(s) pg {page.number + 1}")
                for r in final_rects:
                    if r.is_valid and not r.is_empty: page.add_redact_annot(r, fill=(1, 1, 1))
                applied_count = page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_REMOVE)
                if applied_count > 0: log_entries.append(f"Applied {applied_count} logo annot(s) pg {page.number + 1}")

        # Add Watermarks
        if add_watermarks and applied_count > 0:
            color=(0.7,0.0,0.7); fill=(0.98,0.9,0.98); fs=9; max_wm=2
            watermark_areas.sort(key=lambda x: x["priority"])
            placed = []
            for r in final_rects: # Base placement on actual redacted rects
                if len(placed) >= max_wm: break
                if r.y1 > page_height*0.2 or not r.is_valid or r.is_empty: continue
                overlap = False
                for p in placed:
                    inter=r.intersect(p); min_a=min(r.get_area(),p.get_area())
                    if inter.is_valid and not inter.is_empty and min_a>0 and (inter.get_area()/min_a)>0.3: overlap=True; break
                if overlap: continue
                wm_w=max(50,min(120,r.width*0.7)); wm_h=max(12,min(25,r.height*0.7))
                wm_r=fitz.Rect(r.x0+(r.width-wm_w)/2, r.y0+(r.height-wm_h)/2, r.x0+(r.width+wm_w)/2, r.y0+(r.height+wm_h)/2).normalize()
                if wm_r.width<30 or wm_r.height<10 or not wm_r.is_valid or wm_r.is_empty: continue
                try:
                    page.draw_rect(wm_r, color=color, width=0.5, dashes="[2 2]", fill=fill, fill_opacity=0.4, overlay=True)
                    tp = wm_r.tl+(wm_r.width/2, wm_r.height/2+fs*0.5)
                    page.insert_text(tp, "LOGO", color=color, fontsize=fs, fontname="helv", align=fitz.TEXT_ALIGN_CENTER, overlay=True)
                    placed.append(wm_r); log_entries.append(f"Added logo watermark pg {page.number + 1}")
                except Exception as e: log_entries.append(f"Warn: WM Draw pg {page.number+1}: {e}")

    except Exception as e: log_entries.append(f"ERROR Logo Removal pg {page.number + 1}: {e}")
    return log_entries

# --- Currency Value Masking function ---
def mask_currency_values(page):
    """Finds currency symbols and masks the adjacent numerical value."""
    log_entries = []
    redaction_rects_data = []
    processed_indices = set()
    num_re = re.compile(r"^-?([0-9]{1,3}(?:[,.\s][0-9]{3})*|[0-9]+)(?:[,.][0-9]+)?$")
    pre_sym = {"$", "£", "€", "₹", "¥"}; post_sym = {"€", "₽", "zł"}

    try:
        words = sorted(page.get_text("words", delimiters="", flags=fitz.TEXT_PRESERVE_WHITESPACE), key=lambda w: (w[1], w[0]))
        for i, w_info in enumerate(words):
            if i in processed_indices: continue
            x0,y0,x1,y1,w_txt,_,_,_ = w_info; curr_r=fitz.Rect(x0,y0,x1,y1); w_strip=w_txt.strip()
            found_val, comb_r, match_idx, curr_x1 = None, None, {i}, x1

            # Check 1: Pre-symbol -> Number(s)
            if w_strip in pre_sym:
                curr_r=fitz.Rect(x0,y0,x1,y1); parts=[w_txt]
                for j in range(i+1, len(words)):
                    nw_info=words[j]; nx0,ny0,nx1,ny1,ntxt,_,_,_=nw_info
                    if abs(ny0-y0)>5 or j in processed_indices: break
                    if nx0 > curr_x1 + 15: break
                    ntxt_strip = ntxt.strip()
                    if num_re.match(ntxt_strip):
                        curr_r|=fitz.Rect(nx0,ny0,nx1,ny1); parts.append(ntxt); match_idx.add(j); curr_x1=nx1
                    elif ntxt_strip and not ntxt_strip.startswith(("-","+")): break
                if len(parts)>1: found_val="".join(parts); comb_r=curr_r

            # Check 2: Number -> Post-symbol
            elif num_re.match(w_strip):
                num_r=curr_r; parts=[w_txt]; match_idx={i}; curr_x1=x1
                for k in range(i+1, min(i+3, len(words))):
                    nw_info=words[k]; nx0,ny0,nx1,ny1,ntxt,_,_,_=nw_info
                    if abs(ny0-y0)>5 or k in processed_indices: continue
                    ntxt_strip = ntxt.strip()
                    if ntxt_strip in post_sym and nx0 < curr_x1+15:
                        comb_r=num_r|fitz.Rect(nx0,ny0,nx1,ny1); found_val="".join(parts+[ntxt]); match_idx.add(k); break

            # Process match
            if found_val and comb_r and comb_r.is_valid and not comb_r.is_empty:
                redaction_rects_data.append({"rect": comb_r, "text": found_val.strip()})
                processed_indices.update(match_idx)

    except Exception as e: log_entries.append(f"ERROR Currency Search pg {page.number + 1}: {e}")

    # Apply redactions
    applied_count = 0
    if redaction_rects_data:
        log_entries.append(f"Applying {len(redaction_rects_data)} currency val redaction(s) pg {page.number + 1}")
        for item in redaction_rects_data:
            r=item["rect"]; repl="XXXX"
            page.add_redact_annot(r, text=repl, fill=(1,1,1), fontsize=8, text_color=(0,0,0), align=fitz.TEXT_ALIGN_CENTER)
        applied_count = page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE)
        if applied_count > 0: log_entries.append(f"Applied {applied_count} currency val annot(s) pg {page.number + 1}")

    return log_entries

# --- User-Defined Text Masking function ---
def replace_text_efficiently(page, words_to_replace):
    """Efficiently replaces user-defined words/phrases with 'X's."""
    log_entries = []
    redaction_items = []
    if not isinstance(words_to_replace, (list, tuple, set)): words_to_replace = []

    for word in words_to_replace:
        word_str = str(word).strip()
        if not word_str: continue
        try:
            instances = page.search_for(word_str, quads=False, hit_max=500)
            if instances:
                # log_entries.append(f"Found {len(instances)} of '{word_str}' pg {page.number + 1}")
                for inst in instances:
                    if inst.is_valid and not inst.is_empty:
                        num_xxx = max(3, round(inst.width / 5.0))
                        redaction_items.append((inst, "X" * num_xxx))
        except Exception as e: log_entries.append(f"Warn: Search User Word '{word_str}' pg {page.number + 1}: {e}")

    applied_count = 0
    if redaction_items:
        log_entries.append(f"Applying {len(redaction_items)} user word redaction(s) pg {page.number + 1}")
        for rect, replacement in redaction_items:
            page.add_redact_annot(rect, text=replacement, fill=(1,1,1), fontsize=8, text_color=(0,0,0), align=fitz.TEXT_ALIGN_CENTER)
        applied_count = page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE)
        if applied_count > 0: log_entries.append(f"Applied {applied_count} user word annot(s) pg {page.number + 1}")

    return log_entries

# --- Main Processing Function ---
def process_pdf_with_enhanced_protection(pdf_path, words_to_replace, output_path, remove_logos=True, add_watermarks=True):
    """Main processing function for standard PDFs."""
    doc = None; log_data = []; filename = os.path.basename(pdf_path); success = False
    try:
        doc = fitz.open(pdf_path)
        if len(doc) == 0: log_data.append(f"Skip '{filename}': 0 pages."); return log_data
        log_data.append(f"Processing '{filename}'...")

        for page_num in range(len(doc)):
            page = doc[page_num]; page_logs = []
            if remove_logos: logo_logs = remove_all_logos(page, add_watermarks); page_logs.extend(logo_logs)
            curr_logs = mask_currency_values(page); page_logs.extend(curr_logs)
            if words_to_replace: user_logs = replace_text_efficiently(page, words_to_replace); page_logs.extend(user_logs)
            if page_logs: log_data.append(f"--- Page {page_num + 1} ---"); log_data.extend(page_logs)

        doc.save(output_path, garbage=4, deflate=True, clean=True, linear=False)
        success = True; log_data.append(f"--- FINISHED OK: '{filename}' ---")
    except fitz.fitz.FileNotFoundError: log_data.append(f"FATAL Error: Not found '{pdf_path}'")
    except Exception as e:
        log_data.append(f"FATAL Error processing '{filename}': {type(e).__name__} - {e}")
        import traceback; log_data.append(traceback.format_exc())
        success = False
    finally:
        if doc:
            try: doc.close()
            except Exception as close_e: log_data.append(f"Warn: Error closing '{filename}': {close_e}")
    if not success: log_data.append(f"--- FINISHED FAILED: '{filename}' ---")
    return log_data
