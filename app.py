import io
import hashlib
import os
import re
import zipfile

import streamlit as st
from PIL import Image, ImageOps, UnidentifiedImageError

st.set_page_config(page_title="SME Event Photo Generator", page_icon="⚙️", layout="wide")

st.markdown("""
<style>
.stApp { background-color: #0A192F; color: #FFFFFF; }
h1, h2, h3, h4, label { color: #FFFFFF !important; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
div.stButton > button:first-child { background-color: #DCE233 !important; color: #0D2342 !important; font-weight: bold !important; border-radius: 8px !important; border: none !important; padding: 0.6rem 1.2rem !important; }
div.stButton > button:first-child:hover { background-color: #E2E855 !important; }
div.stDownloadButton > button:first-child { background-color: #70A8D7 !important; color: #0A192F !important; font-weight: bold !important; border-radius: 8px !important; }
.stAlert { background-color: #112240 !important; border: 1px solid #70A8D7 !important; }
</style>
""", unsafe_allow_html=True)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
logo_path = os.path.join(BASE_DIR, "sme_logo.png")
header_col1, header_col2 = st.columns([1, 5])
with header_col1:
    if os.path.isfile(logo_path):
        st.image(logo_path, width=130)
    else:
        st.write("⚙️ **[SME Logo]**")
with header_col2:
    st.title("SME Event Photo Generator")
    st.caption("Society of Manufacturing Engineers — De La Salle University Student Chapter 200")
st.divider()


def read_image(upload):
    """Read independently from an uploaded file's current pointer position."""
    with Image.open(io.BytesIO(upload.getvalue())) as source:
        return ImageOps.exif_transpose(source).convert("RGBA")


def apply_frame(photo_file, portrait_frame_file, landscape_frame_file, position):
    photo = read_image(photo_file)
    is_portrait = photo.height > photo.width
    orientation = "Portrait" if is_portrait else "Landscape"
    selected = (portrait_frame_file if is_portrait else landscape_frame_file)
    if selected is None:
        selected = landscape_frame_file if is_portrait else portrait_frame_file
    if selected is None:
        raise ValueError("Upload at least one PNG frame.")

    frame = read_image(selected)
    fitted = ImageOps.fit(photo, frame.size, method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))
    if position == "Overlay (Frame on top)":
        result = Image.alpha_composite(fitted, frame)
    else:
        result = Image.alpha_composite(frame, fitted)
    return result, orientation


def to_jpeg_bytes(canvas):
    """Flatten any transparency before JPEG export."""
    base = Image.new("RGB", canvas.size, (255, 255, 255))
    base.paste(canvas, mask=canvas.getchannel("A"))
    buffer = io.BytesIO()
    base.save(buffer, format="JPEG", quality=95, optimize=True)
    return buffer.getvalue()


def safe_name(name):
    result = re.sub(r"[^A-Za-z0-9_.-]+", "_", name).strip("._")
    return result or "SME_Event"


def upload_signature(upload):
    return (upload.name, upload.size, hashlib.sha256(upload.getvalue()).hexdigest()) if upload else None


col1, col2 = st.columns([1, 2])
with col1:
    st.header("1. Upload & Settings")
    portrait_frame_file = st.file_uploader("Upload Portrait Frame (PNG with transparency)", type=["png"], key="p_frame")
    landscape_frame_file = st.file_uploader("Upload Landscape Frame (PNG with transparency)", type=["png"], key="l_frame")
    photos_files = st.file_uploader("Upload Event Photos", type=["jpg", "jpeg", "png"], accept_multiple_files=True, key="photos")
    st.subheader("⚙️ Export Naming Settings")
    naming_convention = st.radio("File Naming Style", ["Custom Prefix + Number (e.g., SME_Event_001.jpg)", "Keep Original Filename (e.g., framed_IMG_1024.jpg)"], index=0)
    custom_prefix = ""
    if "Custom Prefix" in naming_convention:
        custom_prefix = st.text_input("Enter File Prefix / Event Name", value="SME_Event")
    frame_position = st.radio("Frame Layer Position", ["Overlay (Frame on top)", "Underlay (Photo on top)"], index=0)

with col2:
    st.header("2. Preview & Export")
    if (portrait_frame_file or landscape_frame_file) and photos_files:
        try:
            preview, orientation = apply_frame(photos_files[0], portrait_frame_file, landscape_frame_file, frame_position)
            st.subheader("Sample Preview")
            st.image(preview, caption=f"Previewing photo 1 of {len(photos_files)} (Detected: {orientation})", width="stretch")
        except (OSError, ValueError, UnidentifiedImageError) as exc:
            st.error(f"Unable to preview image: {exc}")
            st.stop()

        # A changed input invalidates the previous export, but ordinary button reruns do not.
        signature = (
            tuple(upload_signature(f) for f in photos_files),
            upload_signature(portrait_frame_file),
            upload_signature(landscape_frame_file),
            naming_convention, custom_prefix, frame_position,
        )
        if st.session_state.get("export_signature") != signature:
            st.session_state.pop("export_zip", None)
            st.session_state["export_signature"] = signature

        if st.button("🚀 Process All Photos (.ZIP)"):
            zip_buffer = io.BytesIO()
            progress = st.progress(0)
            failures = []
            successes = 0
            used_names = set()
            with zipfile.ZipFile(zip_buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                for idx, photo in enumerate(photos_files, start=1):
                    try:
                        result, _ = apply_frame(photo, portrait_frame_file, landscape_frame_file, frame_position)
                        if "Custom Prefix" in naming_convention:
                            name = f"{safe_name(custom_prefix)}_{idx:03d}.jpg"
                        else:
                            stem = os.path.splitext(os.path.basename(photo.name))[0]
                            name = f"framed_{safe_name(stem)}.jpg"
                        if name in used_names:
                            name = f"{os.path.splitext(name)[0]}_{idx:03d}.jpg"
                        used_names.add(name)
                        archive.writestr(name, to_jpeg_bytes(result))
                        successes += 1
                    except (OSError, ValueError, UnidentifiedImageError) as exc:
                        failures.append(f"{photo.name}: {exc}")
                    finally:
                        progress.progress(idx / len(photos_files))
            st.session_state["export_zip"] = zip_buffer.getvalue() if successes else None
            if successes:
                st.success(f"Processed {successes} of {len(photos_files)} photos!")
            else:
                st.error("No photos were processed successfully.")
            if failures:
                st.warning("Some images were skipped: " + "; ".join(failures[:5]))

        if st.session_state.get("export_zip"):
            st.download_button("📥 Download ZIP File", data=st.session_state["export_zip"], file_name=f"{safe_name(custom_prefix or 'SME_framed_photos')}.zip", mime="application/zip")
    else:
        st.info("Please upload your photos and at least one frame template to enable preview.")
