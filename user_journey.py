# user_journey.py
import streamlit as st
import streamlit.components.v1 as components
import os
import base64

def horizontal_stepper(current_step, max_completed_step=1):
    """
    Display a horizontal stepper with icons for navigation
    current_step: Integer (1-7) representing the current active step
    max_completed_step: Maximum step user has completed
    """
    steps = [
        {"title": "Upload Documents", "icon": "📂"},
        {"title": "Select Content", "icon": "✏️"},
        {"title": "Configure Options", "icon": "⚙️"},
        {"title": "Process Documents", "icon": "🔄"},
        {"title": "Review Results", "icon": "👁️"},
        {"title": "Download & Share", "icon": "📥"}
    ]
    
    # Create stepper HTML
    stepper_html = """
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {
                margin: 0;
                padding: 0;
                font-family: Arial, sans-serif;
                background: transparent;
            }
            
            .stepper-container {
                display: flex;
                justify-content: space-between;
                align-items: center;
                width: 100%;
                position: relative;
                padding: 20px 0;
                background: rgba(255,255,255,0.9);
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                margin-bottom: 30px;
            }
            
            .stepper-line {
                position: absolute;
                height: 3px;
                width: 90%;
                top: 50%;
                left: 5%;
                background: linear-gradient(to right, 
                    #eb8c00 0%, 
                    #eb8c00 {completed_percentage}%, 
                    #e0e0e0 {completed_percentage}%, 
                    #e0e0e0 100%
                );
                transform: translateY(-50%);
                z-index: 1;
            }
            
            .step-container {
                display: flex;
                justify-content: space-between;
                width: 96%;
                margin: 0 auto;
                position: relative;
                z-index: 2;
            }
            
            .step {
                display: flex;
                flex-direction: column;
                align-items: center;
                position: relative;
                z-index: 2;
                width: 100px;
                flex-shrink: 0;
            }
            
            .step-circle {
                width: 40px;
                height: 40px;
                border-radius: 50%;
                background-color: #f0f0f0;
                display: flex;
                justify-content: center;
                align-items: center;
                font-size: 18px;
                border: 2px solid #cccccc;
                margin-bottom: 8px;
                position: relative;
                transition: all 0.3s ease;
            }
            
            .step-number {
                font-size: 14px;
                color: #666;
                font-weight: bold;
            }
            
            .step-completed .step-circle {
                background-color: #eb8c00;
                border-color: #eb8c00;
                color: white;
            }
            
            .step-active .step-circle {
                background-color: #eb8c00;
                border-color: #eb8c00;
                color: white;
                box-shadow: 0 0 10px rgba(235, 140, 0, 0.5);
            }
            
            .step-completed .step-circle::after {
                content: '✓';
                position: absolute;
                top: 50%;
                left: 50%;
                transform: translate(-50%, -50%);
                color: white;
                font-size: 16px;
            }
            
            .step-title {
                font-size: 10px;
                color: #616161;
                text-align: center;
                max-width: 90px;
                opacity: 0.7;
                word-wrap: break-word;
            }
            
            .step-active .step-title {
                color: #eb8c00;
                font-weight: bold;
                opacity: 1;
            }
            
            .step-completed .step-title {
                color: #eb8c00;
                opacity: 1;
            }
        </style>
    </head>
    <body>
        <div class="stepper-container">
    """
    
    # Calculate completed percentage
    completed_percentage = min(100, ((current_step - 1) / (len(steps) - 1)) * 100)
    
    # Add stepper line with dynamic gradient
    stepper_html = stepper_html.replace("{completed_percentage}", str(completed_percentage))
    stepper_html += f'<div class="stepper-line"></div>'
    
    # Add step container
    stepper_html += '<div class="step-container">'
    
    # Add steps to the stepper
    for i, step in enumerate(steps, 1):
        # Determine step class based on current progress
        if i < current_step:
            step_class = "step-completed"
        elif i == current_step:
            step_class = "step-active"
        else:
            step_class = ""
        
        stepper_html += f"""
            <div class="step {step_class}">
                <div class="step-circle">
                    <span class="step-number">{i}</span>
                </div>
                <div class="step-title">{step['title']}</div>
            </div>
        """
    
    stepper_html += """
            </div>
        </div>
    </body>
    </html>
    """
    
    # Render the stepper
    components.html(stepper_html, height=120, scrolling=False)

def hide_deploy_button():
    """Hide the deploy button and three dots menu"""
    st.markdown("""
    <style>
        /* Background styling */
        .stApp {
            background-image: url('file:///C:/Users/admin/OneDrive/Desktop/PDF Masker/logo/background.png');
            background-size: cover !important;
            background-position: center !important;
            background-repeat: no-repeat !important;
        }

        /* Hide Streamlit elements */
        #MainMenu {visibility: hidden;}
        header {visibility: hidden;}
        footer {visibility: hidden;}
        .stDeployButton {display: none !important;}
        
        /* Use Arial font throughout the app */
        html, body, [class*="css"] {
            font-family: Arial, sans-serif !important;
        }
        
        /* Remove default Streamlit margins */
        .main .block-container {
            padding-top: 0 !important;
            padding-bottom: 0 !important;
            margin-top: 0 !important;
            margin-bottom: 0 !important;
        }
        
        /* Section dividers */
        .section-divider {
            margin: 30px 0;
            border-bottom: 1px solid #e0e0e0;
        }
        
        /* Words to mask styling */
        .words-list-container {
            background-color: #f9f9f9;
            border-radius: 8px;
            padding: 15px;
            margin-top: 15px;
            margin-bottom: 20px;
            border: 1px solid #e0e0e0;
            max-height: 250px;
            overflow-y: auto;
        }
        
        .word-item {
            display: flex;
            align-items: center;
            background-color: white;
            padding: 8px 12px;
            border-radius: 4px;
            margin-bottom: 8px;
            border: 1px solid #eaeaea;
        }
        
        .word-text {
            flex-grow: 1;
        }
        
        .delete-button {
            color: #e0301e;
            cursor: pointer;
            margin-left: 10px;
        }
        
        /* Full screen background */
        .stApp {
            background-color: transparent !important;
            background-image: url('file:///C:/Users/admin/OneDrive/Desktop/PDF Masker/logo/background.png');
            background-size: cover !important;
            background-position: center !important;
            background-repeat: no-repeat !important;
        }
        
        /* Hide hamburger menu */
        #MainMenu {visibility: hidden;}
        header {visibility: hidden;}
        footer {visibility: hidden;}
        
        /* Fix button styling */
        .stButton button {
            border-radius: 4px !important;
            font-weight: 500 !important;
            transition: all 0.3s ease !important;
        }
        
        /* Container styling */
        .content-section {
            background: rgba(255,255,255,0.9);
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 20px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.05);
        }
        
        /* Fix streamlit column gap */
        .row-widget.stHorizontal {
            gap: 15px !important;
        }
        
        /* Navigation buttons */
        .nav-button {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            padding: 8px 16px;
            background-color: #f0f0f0;
            color: #333;
            border-radius: 4px;
            text-decoration: none;
            margin-right: 10px;
            transition: all 0.3s ease;
        }
        
        .nav-button:hover {
            background-color: #e0e0e0;
        }
        
        .nav-button-icon {
            margin-right: 8px;
        }
    </style>
    """, unsafe_allow_html=True)

def create_section_header(icon, title, description=None):
    """Create a consistent section header with icon and title"""
    st.markdown(f"""
    <div style="background: rgba(255,255,255,0.9); padding: 20px; border-radius: 10px; margin-bottom: 20px; box-shadow: 0 2px 5px rgba(0,0,0,0.05);">
        <h3 style="color: #333333; font-family: Arial, sans-serif; margin-bottom: {10 if description else 0}px;">
            {icon} {title}
        </h3>
        {f'<p style="margin-bottom: 0; font-family: Arial, sans-serif;">{description}</p>' if description else ''}
    </div>
    """, unsafe_allow_html=True)

def display_word_list(words, current_file):
    """
    Simple function to display words without nested columns
    This avoids the column nesting error
    """
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

def init_journey_state():
    """Initialize the user journey state variables"""
    if 'journey_step' not in st.session_state:
        st.session_state.journey_step = 1
    
    if 'max_completed_step' not in st.session_state:
        st.session_state.max_completed_step = 1
    
    if 'uploaded_pdfs' not in st.session_state:
        st.session_state.uploaded_pdfs = None
    
    if 'file_words_to_mask' not in st.session_state:
        st.session_state.file_words_to_mask = {}
    
    if 'current_file' not in st.session_state:
        st.session_state.current_file = None
    
    if 'processing_options' not in st.session_state:
        st.session_state.processing_options = {
            'remove_logos': True,
            'add_watermarks': True,
            'handle_scanned_pdfs': True
        }
    
    if 'processed_info' not in st.session_state:
        st.session_state.processed_info = {}

def render_navigation_buttons(can_proceed=True):
    """Render navigation buttons with home button"""
    st.markdown('<div style="margin-top: 30px;"></div>', unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 3, 1])
    
    with col1:
        if st.session_state.journey_step > 1:
            prev_button = st.button("← Previous", use_container_width=True)
            if prev_button:
                st.session_state.journey_step = st.session_state.journey_step - 1
                st.rerun()
    
    with col2:
        # Center column - add home button
        if st.session_state.journey_step > 1:
            home_col1, home_col2, home_col3 = st.columns([3, 2, 3])
            with home_col2:
                if st.button("🏠 Home", use_container_width=True, help="Return to start"):
                    reset_journey()
    
    with col3:
        if st.session_state.journey_step < 6 and can_proceed:
            next_step = st.session_state.journey_step + 1
            # Update max completed step to track progress
            if st.button("Next →", use_container_width=True, type="primary"):
                # Only advance max_completed_step if moving forward
                st.session_state.max_completed_step = max(
                    st.session_state.max_completed_step, 
                    st.session_state.journey_step + 1
                )
                st.session_state.journey_step = next_step
                st.rerun()

def reset_journey():
    """Reset the journey state"""
    st.session_state.file_words_to_mask = {}
    st.session_state.current_file = None
    st.session_state.processed_info = {}
    st.session_state.journey_step = 1
    st.session_state.max_completed_step = 1
    st.session_state.uploaded_pdfs = None
    
    # Clear processing options to default
    st.session_state.processing_options ={
        'remove_logos': True,
        'add_watermarks': True,
        'handle_scanned_pdfs': True
    }
    
    st.rerun()
