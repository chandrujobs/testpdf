# main.py (Final Corrected Implementation)
import streamlit as st
import pandas as pd
import os
from io import BytesIO
import base64
import zipfile
import time
import uuid
import sys
import tempfile

# Set page configuration FIRST - before any other Streamlit commands or imports
# that might also call set_page_config
st.set_page_config(
    page_title="Data Shield Platform", 
    page_icon="🔒", 
    layout="wide",
    initial_sidebar_state="collapsed"  # Start with sidebar collapsed
)

# Then import other modules and functions
from pdf_processor import process_pdf_with_enhanced_protection, display_pdf_file, generate_preview, display_pdf_preview
from scanned_files import detect_scanned_pdf, process_scanned_pdf
from reset import check_for_reset_flag, clear_uploads
# Modified import to avoid duplicate set_page_config
from landing import show_landing_page
from user_journey import (
    horizontal_stepper, 
    hide_deploy_button, 
    init_journey_state, 
    render_navigation_buttons, 
    reset_journey,
    create_section_header
)

def process_single_pdf(pdf, words_to_replace, pdf_path, idx):
    """Helper function to process a single PDF and update UI"""
    # Create progress indicator
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    # Define output path
    output_pdf_path = pdf_path.replace(".pdf", "_masked.pdf")
    
    # Process document with progress updates
    status_text.text("Checking document type...")
    progress_bar.progress(10)
    
    # Check if this is a scanned PDF - always enabled but hidden from UI
    is_scanned = detect_scanned_pdf(pdf_path)
    if is_scanned:
        status_text.text("Detected scanned PDF. Using optimized processing...")
        progress_bar.progress(25)
        
        # Process scanned PDF with special handling
        start_time = time.time()
        log_data = process_scanned_pdf(
            pdf_path, 
            words_to_replace, 
            output_pdf_path,
            remove_logos=st.session_state.processing_options['remove_logos'],
            add_watermarks=st.session_state.processing_options['add_watermarks']
        )
        processing_time = time.time() - start_time
    else:
        status_text.text("Processing document...")
        progress_bar.progress(25)
        
        # Process PDF with enhanced protection
        start_time = time.time()
        log_data = process_pdf_with_enhanced_protection(
            pdf_path, 
            words_to_replace, 
            output_pdf_path, 
            remove_logos=st.session_state.processing_options['remove_logos'],
            add_watermarks=st.session_state.processing_options['add_watermarks']
        )
        processing_time = time.time() - start_time
    
    progress_bar.progress(75)
    
    # Track processed files in session state
    if 'processed_info' not in st.session_state:
        st.session_state.processed_info = {}
    
    st.session_state.processed_info[pdf.name] = {
        'path': output_pdf_path,
        'log': log_data,
        'processing_time': processing_time
    }
    
    # Update progress and status
    progress_bar.progress(100)
    status_text.text(f"Processing complete in {processing_time:.2f} seconds")
    
    return output_pdf_path, log_data

# Helper function to display word list to avoid the columns nesting issue
def display_word_list(words, current_file):
    """Display the list of words to mask directly in the UI"""
    if not words:
        st.markdown("""
        <div style="text-align: center; padding: 15px; color: #666; background-color: #f9f9f9; 
                    border-radius: 8px; margin-top: 15px; border: 1px dashed #ccc;">
            No words added yet. Enter words or phrases above.
        </div>
        """, unsafe_allow_html=True)
        return
    
    st.markdown("<p style='margin-top: 15px; margin-bottom: 5px; font-weight: 500;'>Current Words to Mask:</p>", unsafe_allow_html=True)
    
    # Create a container for word list
    for i, word in enumerate(words):
        cols = st.columns([5, 1])
        with cols[0]:
            st.markdown(f"• {word}")
        with cols[1]:
            if st.button("🗑️", key=f"delete_{i}", help=f"Remove '{word}'"):
                st.session_state.file_words_to_mask[current_file].pop(i)
                st.rerun()

def main():
    # Apply custom styling
    hide_deploy_button()
    
    # Initialize session state
    if 'start_app' not in st.session_state:
        st.session_state.start_app = False
    
    # If start parameter is in the URL, start the app
    if 'start' in st.query_params and st.query_params['start'] == 'true':
        st.session_state.start_app = True
    
    # Show landing page or main app
    if not st.session_state.start_app:
        # Show landing page
        start_app = show_landing_page()
        if start_app:
            st.session_state.start_app = True
            st.rerun()
        return  # Exit the function if we're showing the landing page
    
    # Check for reset flag first
    check_for_reset_flag()
    
    # Set a unique run ID if not already present
    if "run_id" not in st.session_state:
        st.session_state.run_id = str(uuid.uuid4())
    
    # Initialize the user journey state
    init_journey_state()
    
    # Application Header
    st.markdown("""
    <div style="display: flex; align-items: center; margin-bottom: 20px; background: rgba(255,255,255,0.9); padding: 10px;">
        <div style="margin-right: 15px; font-size: 36px;">🔒</div>
        <div>
            <h1 style="margin: 0; font-size: 32px; font-family: Arial, sans-serif;">Data Shield Platform</h1>
            <p style="margin: 5px 0 0 0; color: #555555; font-family: Arial, sans-serif;">
                Protect sensitive information by removing confidential text and logos from your documents.
            </p>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Display the horizontal stepper
    horizontal_stepper(
        st.session_state.journey_step, 
        st.session_state.max_completed_step
    )
    
    # Create main container for step content
    main_content = st.container()
    
    # Display the content for the current journey step
    with main_content:
        # Step 1: Upload Documents
        if st.session_state.journey_step == 1:
            create_section_header(
                "📂", 
                "Upload Documents", 
                "Upload the PDF documents you want to process. You can upload multiple files at once."
            )
            
            # File Uploader for PDFs
            uploaded_pdfs = st.file_uploader(
                "Upload PDFs", 
                type=["pdf"], 
                accept_multiple_files=True,
                key=f"pdf_uploader_{st.session_state.run_id}",
                help="Select one or more PDFs to process"
            )
            
            # Store the PDFs in session state
            if uploaded_pdfs is not None and len(uploaded_pdfs) > 0:
                st.session_state.uploaded_pdfs = uploaded_pdfs
                
                # Display success message
                st.success(f"Successfully uploaded {len(uploaded_pdfs)} document(s)")
                
                # Show uploaded files in a grid
                columns = st.columns(3)
                for i, pdf in enumerate(uploaded_pdfs):
                    col_idx = i % 3
                    with columns[col_idx]:
                        file_size_kb = len(pdf.getvalue()) / 1024
                        st.markdown(f"""
                        <div style="
                            background: rgba(255,255,255,0.9);
                            border: 1px solid #e0e0e0;
                            border-radius: 5px;
                            padding: 15px;
                            margin-bottom: 15px;
                        ">
                            <div style="font-size: 24px; color: #e0301e; margin-bottom: 10px;">📄</div>
                            <div style="font-weight: bold; margin-bottom: 5px; word-break: break-word;">{pdf.name}</div>
                            <div style="color: #666666; font-size: 12px;">{file_size_kb:.1f} KB</div>
                        </div>
                        """, unsafe_allow_html=True)
                
                # Navigation buttons
                render_navigation_buttons(True)
                
            else:
                st.info("Please upload at least one PDF document to continue.")
        
        # Step 2: Select Content to Mask
        elif st.session_state.journey_step == 2:
            create_section_header(
                "✏️", 
                "Select Content to Mask", 
                "Specify which words, phrases, or content you want to mask in each document."
            )
            
            # Helper functions for word list management
            def add_word():
                if st.session_state.current_file and st.session_state.new_word:
                    # Initialize list for current file if needed
                    if st.session_state.current_file not in st.session_state.file_words_to_mask:
                        st.session_state.file_words_to_mask[st.session_state.current_file] = []
                        
                    # Add word if not already in list
                    word_to_add = st.session_state.new_word.strip()
                    if word_to_add and word_to_add not in st.session_state.file_words_to_mask[st.session_state.current_file]:
                        st.session_state.file_words_to_mask[st.session_state.current_file].append(word_to_add)
                        st.session_state.new_word = ""
            
            def clear_words():
                if st.session_state.current_file:
                    st.session_state.file_words_to_mask[st.session_state.current_file] = []
            
            # File selection if multiple PDFs are uploaded
            if st.session_state.uploaded_pdfs and len(st.session_state.uploaded_pdfs) > 1:
                file_options = [pdf.name for pdf in st.session_state.uploaded_pdfs]
                
                # File selector in a container
                st.markdown("""
                <div style="background: rgba(255,255,255,0.9); padding: 15px; border-radius: 8px; margin-bottom: 20px;">
                    <h4 style="margin-top: 0; margin-bottom: 10px;">Choose a PDF to Configure</h4>
                </div>
                """, unsafe_allow_html=True)
                
                selected_file = st.selectbox(
                    "Select a document",
                    options=file_options,
                    index=0,
                    key="file_selector"
                )
                st.session_state.current_file = selected_file
                
                # Find the selected PDF
                selected_pdf = next((pdf for pdf in st.session_state.uploaded_pdfs if pdf.name == selected_file), None)
                
                if selected_pdf:
                    # Create a 2-column layout
                    col1, col2 = st.columns([2, 1])
                    
                    with col1:
                        # Create a temporary file to display preview
                        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
                            tmp_file.write(selected_pdf.getvalue())
                            tmp_file_path = tmp_file.name
                        
                        # Display PDF preview with header
                        st.markdown("""
                        <div style="background-color: rgba(255,255,255,0.9); padding: 10px; border-radius: 8px 8px 0 0; margin-bottom: 5px; border-bottom: 2px solid #f0f0f0;">
                            <h4 style="margin: 0;">PDF Preview</h4>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        display_pdf_file(tmp_file_path)
                        
                        # Clean up temporary file
                        os.unlink(tmp_file_path)
                    
                    with col2:
                        # Word masking section
                        st.markdown("""
                        <div style="background-color: rgba(255,255,255,0.9); padding: 10px; border-radius: 8px 8px 0 0; margin-bottom: 5px; border-bottom: 2px solid #f0f0f0;">
                            <h4 style="margin: 0;">Words to Mask</h4>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        st.text_input(
                            "Enter word or phrase:", 
                            key="new_word",
                            help="Type a word or phrase to mask and press Enter"
                        )
                        
                        # Add and Clear buttons
                        col_add, col_clear = st.columns(2)
                        with col_add:
                            st.button("Add Word", on_click=add_word, use_container_width=True)
                        with col_clear:
                            st.button("Clear All", on_click=clear_words, use_container_width=True)
                        
                        # Display word list container
                        word_list_container = st.container()
                        if st.session_state.current_file and st.session_state.current_file in st.session_state.file_words_to_mask:
                            current_words = st.session_state.file_words_to_mask[st.session_state.current_file]
                            with word_list_container:
                                display_word_list(current_words, st.session_state.current_file)
            
            elif st.session_state.uploaded_pdfs and len(st.session_state.uploaded_pdfs) == 1:
                # If only one PDF, use it directly
                selected_pdf = st.session_state.uploaded_pdfs[0]
                st.session_state.current_file = selected_pdf.name
                
                # Create columns for preview and word masking
                col1, col2 = st.columns([2, 1])
                
                with col1:
                    # Create a temporary file to display preview
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
                        tmp_file.write(selected_pdf.getvalue())
                        tmp_file_path = tmp_file.name
                    
                    # Display PDF preview with header
                    st.markdown("""
                    <div style="background-color: rgba(255,255,255,0.9); padding: 10px; border-radius: 8px 8px 0 0; margin-bottom: 5px; border-bottom: 2px solid #f0f0f0;">
                        <h4 style="margin: 0;">PDF Preview</h4>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    display_pdf_file(tmp_file_path)
                    
                    # Clean up temporary file
                    os.unlink(tmp_file_path)
                
                with col2:
                    # Word masking section with header
                    st.markdown("""
                    <div style="background-color: rgba(255,255,255,0.9); padding: 10px; border-radius: 8px 8px 0 0; margin-bottom: 5px; border-bottom: 2px solid #f0f0f0;">
                        <h4 style="margin: 0;">Words to Mask</h4>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    st.text_input(
                        "Enter word or phrase:", 
                        key="new_word",
                        help="Type a word or phrase to mask and press Enter"
                    )
                    
                    # Add and Clear buttons
                    col_add, col_clear = st.columns(2)
                    with col_add:
                        st.button("Add Word", on_click=add_word, use_container_width=True)
                    with col_clear:
                        st.button("Clear All", on_click=clear_words, use_container_width=True)
                    
                    # Display word list
                    word_list_container = st.container()
                    if st.session_state.current_file and st.session_state.current_file in st.session_state.file_words_to_mask:
                        current_words = st.session_state.file_words_to_mask[st.session_state.current_file]
                        with word_list_container:
                            display_word_list(current_words, st.session_state.current_file)
            
            # Check if any files have words to mask
            has_words_to_mask = any(
                len(words) > 0 
                for words in st.session_state.file_words_to_mask.values()
            )
            
            # Navigation buttons
            render_navigation_buttons(has_words_to_mask)
        
        # Step 3: Configure Options
        elif st.session_state.journey_step == 3:
            # Configuration Options Step
            create_section_header(
                "⚙️", 
                "Configure Options", 
                "Customize how your documents will be processed with the available options."
            )
            
            # Processing options
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("""
                <div style="background: rgba(255,255,255,0.9); padding: 15px; border-radius: 8px; margin-bottom: 15px;">
                    <h4 style="margin-top: 0; margin-bottom: 15px;">Processing Options</h4>
                """, unsafe_allow_html=True)
                
                remove_logos = st.checkbox(
                    "Remove Logos", 
                    value=st.session_state.processing_options['remove_logos'],
                    help="Detect and remove logo images from documents"
                )
                st.session_state.processing_options['remove_logos'] = remove_logos
                
                add_watermarks = st.checkbox(
                    "Add Logo Placeholders", 
                    value=st.session_state.processing_options['add_watermarks'],
                    help="Add light purple indicators showing where logos were originally present"
                )
                st.session_state.processing_options['add_watermarks'] = add_watermarks
                
                st.markdown("</div>", unsafe_allow_html=True)
            
            with col2:
                st.markdown("""
                <div style="background: rgba(255,255,255,0.9); padding: 15px; border-radius: 8px; margin-bottom: 15px;">
                    <h4 style="margin-top: 0; margin-bottom: 15px;">Selected Content Summary</h4>
                """, unsafe_allow_html=True)
                
                # Show files and word counts
                if st.session_state.uploaded_pdfs:
                    for pdf in st.session_state.uploaded_pdfs:
                        words_to_mask = st.session_state.file_words_to_mask.get(pdf.name, [])
                        st.markdown(f"• **{pdf.name}**: {len(words_to_mask)} word(s) to mask")
                
                st.markdown("</div>", unsafe_allow_html=True)
            
            # Navigation buttons
            render_navigation_buttons(True)
        
        # Step 4: Process Documents
        elif st.session_state.journey_step == 4:
            create_section_header(
                "🔄", 
                "Process Documents", 
                "Your documents are being processed. Please wait while we apply your masking settings."
            )
            
            # Process PDFs
            if st.session_state.uploaded_pdfs:
                # Save all PDFs to disk to ensure they are available
                for pdf in st.session_state.uploaded_pdfs:
                    pdf_path = os.path.join("downloads", pdf.name)
                    
                    # Ensure downloads directory exists
                    os.makedirs("downloads", exist_ok=True)
                    
                    if not os.path.exists(pdf_path):
                        with open(pdf_path, "wb") as f:
                            f.write(pdf.getvalue())
                
                # Count PDFs with words to process
                pdfs_to_process = []
                for pdf in st.session_state.uploaded_pdfs:
                    if pdf.name in st.session_state.file_words_to_mask and len(st.session_state.file_words_to_mask[pdf.name]) > 0:
                        pdfs_to_process.append(pdf)
                
                if pdfs_to_process:
                    # Process button
                    st.markdown("""
                    <div style="background: rgba(255,255,255,0.9); padding: 20px; border-radius: 8px; margin-bottom: 20px; text-align: center;">
                    """, unsafe_allow_html=True)
                    
                    if st.button("🚀 Start Processing", use_container_width=True, key="process_button"):
                        st.session_state.processing = True
                    
                    st.markdown("</div>", unsafe_allow_html=True)
                    
                    # If processing is active
                    if 'processing' in st.session_state and st.session_state.processing:
                        # Create a progress tracking container
                        batch_progress = st.container()
                        with batch_progress:
                            st.markdown("""
                            <div style="background: rgba(255,255,255,0.9); padding: 20px; border-radius: 8px; margin-bottom: 20px;">
                                <h4 style="margin-top: 0; margin-bottom: 15px;">🔄 Processing Documents</h4>
                            </div>
                            """, unsafe_allow_html=True)
                            
                            overall_progress = st.progress(0)
                            status_text = st.empty()
                            
                            status_text.text(f"Found {len(pdfs_to_process)} PDFs to process")
                            
                            # Process each PDF with words
                            pdfs_processed = 0
                            for idx, pdf in enumerate(pdfs_to_process):
                                status_text.text(f"Processing {pdf.name} ({idx+1}/{len(pdfs_to_process)})")
                                words_to_replace = st.session_state.file_words_to_mask[pdf.name]
                                pdf_path = os.path.join("downloads", pdf.name)
                                
                                try:
                                    # Process the PDF
                                    process_single_pdf(pdf, words_to_replace, pdf_path, idx)
                                    pdfs_processed += 1
                                    
                                    # Update overall progress
                                    progress_percentage = (idx + 1) / len(pdfs_to_process)
                                    overall_progress.progress(progress_percentage)
                                except Exception as e:
                                    st.error(f"Error processing {pdf.name}: {str(e)}")
                            
                            # Complete the process
                            if pdfs_processed > 0:
                                st.success(f"Processing complete! {pdfs_processed} PDF(s) processed successfully.")
                                # Allow moving to the next step
                                overall_progress.progress(1.0)
                                st.session_state.processing = False
                                
                                # Auto-navigate to next step after short delay
                                time.sleep(1)
                                st.session_state.journey_step += 1
                                st.rerun()
                            else:
                                st.warning("No PDFs were processed. Make sure to add words to mask for each PDF you want to process.")
                                st.session_state.processing = False
                else:
                    st.warning("No PDFs with content to mask. Please go back and add words to mask.")
            
            # Navigation buttons
            render_navigation_buttons('processing' not in st.session_state or not st.session_state.processing)
        
        # Step 5: Review Results
        elif st.session_state.journey_step == 5:
            create_section_header(
                "👁️", 
                "Review Results", 
                "Review the processed documents to ensure all sensitive information has been masked."
            )
            
            if st.session_state.processed_info:
                # Create tabs for multiple PDFs
                pdf_names = list(st.session_state.processed_info.keys())
                tab_labels = [f"PDF {i+1}: {os.path.basename(name)}" for i, name in enumerate(pdf_names)]
                tabs = st.tabs(tab_labels)
                
                # Show all PDFs in their tabs
                for idx, pdf_name in enumerate(pdf_names):
                    processed_data = st.session_state.processed_info[pdf_name]
                    output_path = processed_data['path']
                    log_data = processed_data['log']
                    pdf_path = os.path.join("downloads", pdf_name)
                    
                    # Show the processed version with original side by side
                    with tabs[idx]:
                        st.markdown(f"""
                        <div style="background: rgba(255,255,255,0.9); padding: 15px; border-radius: 8px; margin-bottom: 20px;">
                            <h4 style="margin-top: 0; margin-bottom: 5px;">Review Results for: {pdf_name}</h4>
                            <p style="margin-bottom: 0;">Processing time: {processed_data.get('processing_time', 0):.2f} seconds</p>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        # Show original and processed previews side by side
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            st.markdown("""
                            <div style="background-color: rgba(255,255,255,0.9); padding: 10px; border-radius: 8px 8px 0 0; margin-bottom: 5px; border-bottom: 2px solid #f0f0f0;">
                                <h5 style="margin: 0;">📄 Original PDF</h5>
                            </div>
                            """, unsafe_allow_html=True)
                            display_pdf_file(pdf_path)
                        
                        with col2:
                            st.markdown("""
                            <div style="background-color: rgba(255,255,255,0.9); padding: 10px; border-radius: 8px 8px 0 0; margin-bottom: 5px; border-bottom: 2px solid #f0f0f0;">
                                <h5 style="margin: 0;">🔒 Processed PDF</h5>
                            </div>
                            """, unsafe_allow_html=True)
                            display_pdf_file(output_path)
                        
                        # Show log data in an expander
                        if log_data:
                            with st.expander("View Processing Details"):
                                st.markdown("""
                                <div style="background: rgba(255,255,255,0.9); padding: 15px; border-radius: 8px; margin-bottom: 10px;">
                                    <h5 style="margin-top: 0; margin-bottom: 10px;">📋 Processing Log</h5>
                                </div>
                                """, unsafe_allow_html=True)
                                
                                displayed_logs = log_data if len(log_data) < 50 else log_data[:50]
                                for entry in displayed_logs:
                                    st.markdown(f"- {entry}")
                                if len(log_data) > 50:
                                    st.markdown(f"...and {len(log_data) - 50} more entries")
            else:
                st.warning("No processed documents to review. Please go back and process your documents first.")
            
            # Navigation buttons
            render_navigation_buttons(True)
        
        # Step 6: Download & Share
        elif st.session_state.journey_step == 6:
            create_section_header(
                "📥", 
                "Download & Share", 
                "Download your processed documents individually or as a ZIP file."
            )
            
            if st.session_state.processed_info:
                # Display individual download options
                st.markdown("""
                <div style="background: rgba(255,255,255,0.9); padding: 15px; border-radius: 8px; margin-bottom: 20px;">
                    <h4 style="margin-top: 0; margin-bottom: 15px;">Individual Downloads</h4>
                </div>
                """, unsafe_allow_html=True)
                
                # Create columns for download cards
                cols = st.columns(3)
                
                for idx, (pdf_name, processed_data) in enumerate(st.session_state.processed_info.items()):
                    output_path = processed_data['path']
                    col_idx = idx % 3
                    
                    with cols[col_idx]:
                        st.markdown("""
                        <div style="background: rgba(255,255,255,0.8); padding: 15px; border-radius: 8px; margin-bottom: 15px;">
                        """, unsafe_allow_html=True)
                        
                        st.markdown(f"**{pdf_name}**")
                        st.markdown("Processed file ready for download")
                        
                        with open(output_path, "rb") as f:
                            st.download_button(
                                "🔒 Download PDF", 
                                f, 
                                file_name=f"masked_{pdf_name}",
                                mime="application/pdf",
                                key=f"download_{pdf_name}_{idx}",
                                use_container_width=True
                            )
                        
                        st.markdown("</div>", unsafe_allow_html=True)
                
                # Batch download for multiple processed PDFs
                if len(st.session_state.processed_info) > 1:
                    st.markdown("""
                    <div style="background: rgba(255,255,255,0.9); padding: 15px; border-radius: 8px; margin-bottom: 20px; margin-top: 20px;">
                        <h4 style="margin-top: 0; margin-bottom: 15px;">📦 Batch Download</h4>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # Create ZIP of processed files
                    processed_paths = [info['path'] for info in st.session_state.processed_info.values()]
                    zip_path = os.path.join("downloads", "masked_pdfs.zip")
                    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                        for processed_file in processed_paths:
                            zipf.write(processed_file, os.path.basename(processed_file))
                    
                    # Bulk download button
                    with open(zip_path, "rb") as f:
                        st.download_button(
                            "📦 Download All Processed PDFs as ZIP", 
                            f, 
                            file_name="masked_pdfs.zip", 
                            mime="application/zip",
                            key=f"bulk_download_zip_{st.session_state.run_id}",
                            use_container_width=True
                        )
                
                # Success message
                st.success("Your documents have been successfully processed and are ready for download.")
                
                # Process more documents option
                st.markdown("""
                <div style="background: rgba(255,255,255,0.9); padding: 15px; border-radius: 8px; margin-top: 20px; text-align: center;">
                    <h4 style="margin-top: 0; margin-bottom: 15px;">Process More Documents</h4>
                </div>
                """, unsafe_allow_html=True)
                
                if st.button("Start New Processing Task", use_container_width=True):
                    # Clear necessary state variables but keep user preferences
                    st.session_state.file_words_to_mask = {}
                    st.session_state.current_file = None
                    st.session_state.processed_info = {}
                    st.session_state.journey_step = 1
                    clear_uploads()
                    st.rerun()
            else:
                st.warning("No processed documents available for download. Please go back and process your documents first.")
            
            # Only show back button on last step
            col1, col2, col3 = st.columns([1, 3, 1])
            with col1:
                if st.button("← Previous", use_container_width=True):
                    st.session_state.journey_step = 5
                    st.rerun()
            
            # Add home button on the last step too
            with col2:
                home_col1, home_col2, home_col3 = st.columns([3, 2, 3])
                with home_col2:
                    if st.button("🏠 Home", use_container_width=True, help="Return to start"):
                        reset_journey()

if __name__ == "__main__":
    try:
        # Ensure downloads directory exists
        os.makedirs("downloads", exist_ok=True)
        
        # Make sure the logo directory exists
        logo_dir = os.path.join("logo")
        os.makedirs(logo_dir, exist_ok=True)
        
        # Add query parameters to URL to help with cache busting
        query_params = st.query_params
        if "reload" in query_params:
            # This is a reload request, make sure we have a fresh session
            for key in list(st.session_state.keys()):
                # Keep only essential state if needed
                if key not in ["run_id", "start_app"]:
                    del st.session_state[key]
        
        # Check for step parameter
        if 'step' in query_params:
            try:
                step = int(query_params['step'])
                if 1 <= step <= 6:
                    st.session_state.journey_step = step
                    # Remove step parameter to prevent loops
                    query_params.pop('step')
            except:
                pass
        
        # Run the application
        main()
    except Exception as e:
        # Handle any exceptions gracefully
        st.error(f"An error occurred: {str(e)}")
        
        # Display friendly error message
        st.markdown("""
        <div style="background: rgba(255,255,255,0.9); padding: 20px; border-radius: 8px; text-align: center;">
            <h3>Oops! Something went wrong</h3>
            <p>Please try refreshing the page or contact support.</p>
            <button onclick="location.reload();" style="padding: 8px 16px; background-color: #e0301e; color: white; border: none; border-radius: 4px; cursor: pointer; margin-top: 10px;">
                Refresh Page
            </button>
        </div>
        """, unsafe_allow_html=True)
