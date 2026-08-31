import io
import os
import zipfile
import streamlit as st
from PIL import Image, ImageOps

# Page setup for modern aesthetic
st.set_page_config(
    page_title="SME Event Photo Generator", page_icon="⚙️", layout="wide"
)

# Inject Custom SME Branding CSS
st.markdown(
    """
    <style>
    /* Dark Navy Background for Main App */
    .stApp {
        background-color: #0A192F;
        color: #FFFFFF;
    }
    
    /* Headers Styling */
    h1, h2, h3, h4, label {
        color: #FFFFFF !important;
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    }
    
    /* Yellow/Gold Primary Accent Buttons */
    div.stButton > button:first-child {
        background-color: #DCE233 !important;
        color: #0D2342 !important;
        font-weight: bold !important;
        border-radius: 8px !important;
        border: none !important;
        padding: 0.6rem 1.2rem !important;
        transition: all 0.3s ease !important;
    }
    
    div.stButton > button:first-child:hover {
        background-color: #E2E855 !important;
        box-shadow: 0 4px 12px rgba(220, 226, 51, 0.4) !important;
        transform: translateY(-2px);
    }
    
    /* Download Button Specific Accent */
    div.stDownloadButton > button:first-child {
        background-color: #70A8D7 !important;
        color: #0A192F !important;
        font-weight: bold !important;
        border-radius: 8px !important;
    }

    /* Style Info and Success Boxes */
    .stAlert {
        background-color: #112240 !important;
        color: #70A8D7 !important;
        border: 1px solid #70A8D7 !important;
    }
    </style>
""",
    unsafe_allow_html=True,
)

# Header Section with SME Logo & Title
logo_path = "sme_logo.png"  # Make sure your logo image file is named 'sme_logo.png' in the same folder

header_col1, header_col2 = st.columns([1, 5])

with header_col1:
    if os.path.exists(logo_path):
        st.image(logo_path, width=130)
    else:
        # Placeholder indicator if logo file isn't in folder yet
        st.write("⚙️ **[SME Logo]**")

with header_col2:
    st.title("SME Event Photo Generator")
    st.caption(
        "Society of Manufacturing Engineers — De La Salle University Student Chapter 200"
    )

st.divider()

col1, col2 = st.columns([1, 2])

with col1:
    st.header("1. Upload & Settings")

    # Step 1: Upload Frame Templates
    portrait_frame_file = st.file_uploader(
        "Upload Portrait Frame (PNG with transparency)",
        type=["png"],
        key="p_frame",
    )

    landscape_frame_file = st.file_uploader(
        "Upload Landscape Frame (PNG with transparency)",
        type=["png"],
        key="l_frame",
    )

    # Step 2: Upload Photos
    photos_files = st.file_uploader(
        "Upload Event Photos",
        type=["jpg", "jpeg", "png"],
        accept_multiple_files=True,
        key="photos",
    )

    st.subheader("⚙️ Export Naming Settings")

    # File Naming Options
    naming_convention = st.radio(
        "File Naming Style",
        [
            "Custom Prefix + Number (e.g., SME_Event_001.jpg)",
            "Keep Original Filename (e.g., framed_IMG_1024.jpg)",
        ],
        index=0,
    )

    custom_prefix = ""
    if "Custom Prefix" in naming_convention:
        custom_prefix = st.text_input(
            "Enter File Prefix / Event Name",
            value="SME_Event",
            help="All exported photos will be named [Prefix]_[Number].jpg",
        )

    # Option: Frame position order
    frame_position = st.radio(
        "Frame Layer Position",
        ["Overlay (Frame on top)", "Underlay (Photo on top)"],
        index=0,
    )


def apply_frame(photo_file, p_frame_file, l_frame_file, position):
    """Detects orientation and applies center-cropping to fill frame perfectly."""
    photo = Image.open(photo_file).convert("RGBA")
    photo_width, photo_height = photo.size

    # Detect photo orientation
    if photo_height > photo_width:
        frame_file = p_frame_file
        orientation_label = "Portrait"
    else:
        frame_file = l_frame_file
        orientation_label = "Landscape"

    # Fallback if specific frame is missing
    if not frame_file:
        frame_file = p_frame_file if p_frame_file else l_frame_file

    frame_img = Image.open(frame_file).convert("RGBA")
    frame_size = frame_img.size

    # Scale & Center Crop photo to match frame aspect ratio without distortion
    photo_fitted = ImageOps.fit(
        photo,
        frame_size,
        method=Image.Resampling.LANCZOS,
        centering=(0.5, 0.5),
    )

    canvas = Image.new("RGBA", frame_size)
    if position == "Overlay (Frame on top)":
        canvas.paste(photo_fitted, (0, 0))
        canvas.paste(frame_img, (0, 0), frame_img)
    else:
        canvas.paste(frame_img, (0, 0))
        canvas.paste(photo_fitted, (0, 0), photo_fitted)

    return canvas, orientation_label


with col2:
    st.header("2. Preview & Export")

    if (portrait_frame_file or landscape_frame_file) and photos_files:

        # Show preview of first photo
        preview_canvas, preview_orientation = apply_frame(
            photos_files[0],
            portrait_frame_file,
            landscape_frame_file,
            frame_position,
        )

        st.subheader("Sample Preview")
        st.image(
            preview_canvas,
            caption=f"Previewing photo 1 of {len(photos_files)} (Detected: {preview_orientation})",
            use_container_width=True,
        )

        # Export Logic
        if st.button("🚀 Process & Download All Photos (.ZIP)"):
            zip_buffer = io.BytesIO()

            with zipfile.ZipFile(
                zip_buffer, "a", zipfile.ZIP_DEFLATED, False
            ) as zip_file:
                progress_bar = st.progress(0)

                for idx, photo_file in enumerate(photos_files):
                    framed_canvas, _ = apply_frame(
                        photo_file,
                        portrait_frame_file,
                        landscape_frame_file,
                        frame_position,
                    )

                    img_byte_arr = io.BytesIO()
                    framed_canvas.convert("RGB").save(
                        img_byte_arr, format="JPEG", quality=95
                    )

                    # Determine filename based on user settings
                    if "Custom Prefix" in naming_convention:
                        filename = f"{custom_prefix}_{idx + 1:03d}.jpg"
                    else:
                        original_name = photo_file.name.rsplit(".", 1)[0]
                        filename = f"framed_{original_name}.jpg"

                    zip_file.writestr(filename, img_byte_arr.getvalue())
                    progress_bar.progress((idx + 1) / len(photos_files))

            st.success("Processing Complete!")
            st.download_button(
                label="📥 Download ZIP File",
                data=zip_buffer.getvalue(),
                file_name=f"{custom_prefix if custom_prefix else 'SME_framed_photos'}.zip",
                mime="application/zip",
            )
    else:
        st.info(
            "Please upload your photos and at least one frame template to enable preview."
        )
