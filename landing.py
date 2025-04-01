# landing.py
import streamlit as st
import os
import base64
from PIL import Image

def get_base64_encoded_image(image_path):
    """Get base64 encoded version of an image file"""
    try:
        with open(image_path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode()
    except Exception as e:
        st.error(f"Error reading image file: {e}")
        return ""

def show_landing_page():
    """
    Display the landing page using Streamlit's native components
    Returns True if the user wants to start the main app
    """
    # NOTE: We don't call st.set_page_config() here to avoid conflicts with main.py
    
    # Get file paths
    logo_path = r"C:\Users\admin\OneDrive\Desktop\PDF Masker\logo\pwc.png"
    background_path = r"C:\Users\admin\OneDrive\Desktop\PDF Masker\logo\background.jpg"
    
    # Get background image if it exists
    background_style = "background-color: #d84315;"
    if os.path.exists(background_path):
        background_base64 = get_base64_encoded_image(background_path)
        background_style = f"background-image: url('data:image/jpeg;base64,{background_base64}'); background-size: cover; background-position: center;"
    
    # Set background and hide elements
    st.markdown(f"""
        <style>
            /* Hide Streamlit elements */
            #MainMenu {{visibility: hidden;}}
            header {{visibility: hidden;}}
            footer {{visibility: hidden;}}
            .stDeployButton {{display: none !important;}}
            
            /* Set background and disable scroll */
            body {{
                {background_style}
                overflow: hidden !important;
                margin: 0 !important;
                padding: 0 !important;
            }}
            
            .stApp {{
                {background_style}
                overflow: hidden !important;
            }}
            
            /* Remove all padding and margins */
            .main .block-container {{
                padding: 0 !important;
                margin: 0 !important;
                max-width: 100% !important;
            }}
            
            /* Completely eliminate scrolling */
            html {{
                overflow: hidden !important;
            }}
            
            /* Hide all scrollbars */
            ::-webkit-scrollbar {{
                display: none !important;
                width: 0 !important;
                height: 0 !important;
            }}
            
            /* Button styling */
            .stButton button {{
                background-color: transparent !important;
                color: white !important;
                border: 2px solid #ff0000 !important;
                border-radius: 0 !important;
                padding: 8px 20px !important;
                font-size: 16px !important;
            }}
            
            .stButton button:hover, .stButton button:active, .stButton button:focus {{
                background-color: transparent !important;
                color: white !important;
                border: 2px solid #ff0000 !important;
            }}
        </style>
    """, unsafe_allow_html=True)
    
    # Content with specific padding - reduce space between logo and content
    st.markdown('<div style="padding: 30px 40px;">', unsafe_allow_html=True)
    
    # Logo with reduced bottom margin
    if os.path.exists(logo_path):
        image = Image.open(logo_path)
        st.image(image, width=80)
    
    # Title with reduced spacing
    st.markdown("<h1 style='color: white; margin-top: 10px; margin-bottom: 20px;'>Data Shield Platform</h1>", unsafe_allow_html=True)
    
    # Protect What Matters box - with exact width to fit content
    st.markdown(
        "<div style='background-color: #ffda00; display: inline-block; padding: 10px 15px; margin-bottom: 15px;'>"
        "<h2 style='margin: 0; color: #333; font-size: 24px; white-space: nowrap;'>Protect What Matters</h2>"
        "</div>", 
        unsafe_allow_html=True
    )
    
    # Content box
    st.markdown(
        "<div style='background-color: #ffda00; padding: 15px; width: 750px;'>"
        "<p style='margin: 0; color: #333;'>Our platform intelligently masks confidential content in documents—including text, "
        "images, and even logos. Whether it's personal data, financial details, or brand-"
        "sensitive visuals, we safeguard your information to ensure privacy, compliance, and "
        "trust—automatically and effortlessly.</p>"
        "</div>",
        unsafe_allow_html=True
    )
    
    # Small space before button
    st.markdown("<div style='height: 20px;'></div>", unsafe_allow_html=True)
    
    # Use Streamlit's native button instead of HTML anchor for in-page transition
    if st.button("Let's start", key="start_button"):
        # Set the session state directly rather than using URL parameters
        st.session_state.start_app = True
        return True
    
    # Style the button to match design
    st.markdown("""
        <style>
            /* Style for the button */
            button[kind="secondary"] {
                background-color: transparent !important;
                color: white !important;
                border: 2px solid #ff0000 !important;
                border-radius: 0 !important;
                box-shadow: none !important;
            }
            
            button[kind="secondary"]:hover {
                background-color: rgba(255, 0, 0, 0.1) !important;
                color: white !important;
            }
        </style>
    """, unsafe_allow_html=True)
    
    # Close content container
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Footer
    st.markdown(
        """
        <div style="
            background-color: black;
            padding: 10px 40px;
            position: fixed;
            bottom: 0;
            left: 0;
            right: 0;
            z-index: 9999;
        ">
            <a href="#" style="color: white; text-decoration: underline; margin-right: 10px;">Quick demo</a> | 
            <a href="#" style="color: white; text-decoration: underline; margin-left: 10px;">FAQs</a>
        </div>
        """,
        unsafe_allow_html=True
    )
    
    # Force no scroll with JavaScript
    st.markdown(
        """
        <script>
            // Disable scrolling
            document.body.style.overflow = 'hidden';
            document.documentElement.style.overflow = 'hidden';
            
            // Lock scroll position
            window.onscroll = function() {
                window.scrollTo(0, 0);
            };
        </script>
        """,
        unsafe_allow_html=True
    )
    
    # If we're still showing the landing page, return False
    return False
