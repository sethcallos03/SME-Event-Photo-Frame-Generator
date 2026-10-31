"""SME Event Photo Frame Generator, optimized for big event photo sets."""
import os
import tempfile
import streamlit as st
from processor import HEIC_ENABLED, frame_image, process_batch, safe_name

st.set_page_config(page_title="SME Event Photo Generator", page_icon="⚙️", layout="wide")
st.markdown("""<style>
.stApp {background-color:#0A192F;color:#FFFFFF;}
h1,h2,h3,h4,label {color:#FFFFFF !important;}
div.stButton > button:first-child {background:#DCE233;color:#0D2342;font-weight:700;border:0;border-radius:8px;}
div.stDownloadButton > button:first-child {background:#70A8D7;color:#0A192F;font-weight:700;border:0;border-radius:8px;}
</style>""", unsafe_allow_html=True)

# A very large multipart upload may itself exhaust Streamlit Cloud's memory.
# 12 high-resolution photos per upload is intentionally conservative.
MAX_BATCH = 12
MAX_TOTAL_MB = 180

if "batch_num" not in st.session_state:
    st.session_state.batch_num = 1
if "export_path" not in st.session_state:
    st.session_state.export_path = None
if "export_meta" not in st.session_state:
    st.session_state.export_meta = None


def clear_prior_export():
    path = st.session_state.export_path
    if path and os.path.isfile(path):
        try:
            os.remove(path)
        except OSError:
            pass
    st.session_state.export_path = None
    st.session_state.export_meta = None


header1, header2 = st.columns([1, 5])
with header1:
    logo = os.path.join(os.path.dirname(__file__), "sme_logo.png")
    if os.path.isfile(logo):
        st.image(logo, width=120)
with header2:
    st.title("SME Event Photo Generator")
    st.caption("Society of Manufacturing Engineers — De La Salle University Student Chapter 200")
st.divider()
st.info("For 110+ large photos: upload up to 12 at a time, download the ZIP, then select **Next batch**. Files are processed one by one, not all at once.")
if not HEIC_ENABLED:
    st.warning("HEIC support is unavailable. Ensure pillow-heif is in requirements.txt.")

left, right = st.columns([1, 2], gap="large")
with left:
    st.subheader(f"Batch {st.session_state.batch_num} — Upload")
    portrait = st.file_uploader("Portrait frame (transparent PNG)", type=["png"], key="portrait_frame")
    landscape = st.file_uploader("Landscape frame (transparent PNG)", type=["png"], key="landscape_frame")
    photos = st.file_uploader(
        f"Upload up to {MAX_BATCH} event photos", type=["jpg", "jpeg", "png", "heic", "heif"] if HEIC_ENABLED else ["jpg", "jpeg", "png"],
        accept_multiple_files=True, key=f"photos_batch_{st.session_state.batch_num}"
    )
    prefix = st.text_input("Filename / event prefix", value="SME_Event")
    st.caption("Output: JPG (quality 82), longest side ≤ 2200 pixels. Frame graphics are placed over your photos.")
    st.caption("Tip: Keep each batch below about 180 MB. For 110 photos, plan on approximately 10 batches.")

with right:
    st.subheader("Preview & Download")
    if photos:
        total_mb = sum(p.size for p in photos) / (1024 * 1024)
        st.write(f"**Selected:** {len(photos)} photos · **Total:** {total_mb:.1f} MB")
        if len(photos) > MAX_BATCH:
            st.error(f"Please select no more than {MAX_BATCH} photos per batch.")
        elif total_mb > MAX_TOTAL_MB:
            st.error(f"This batch exceeds {MAX_TOTAL_MB} MB. Split it into smaller batches.")
        elif not (portrait or landscape):
            st.warning("Upload a portrait frame, a landscape frame, or both.")
        else:
            try:
                preview, orientation = frame_image(photos[0], portrait, landscape, max_side=750)
                st.image(preview, caption=f"First photo preview — {orientation}", width="stretch")
                preview.close()
            except Exception as exc:
                st.warning(f"Preview unavailable: {type(exc).__name__}: {exc}")

            if st.button("⚙️ Process this batch", type="primary"):
                clear_prior_export()
                tmp_path = None
                try:
                    with tempfile.NamedTemporaryFile(prefix="sme_export_", suffix=".zip", delete=False) as tmp:
                        tmp_path = tmp.name
                    progress = st.progress(0, text="Preparing images...")
                    def report(done, count):
                        progress.progress(done / count, text=f"Processed {done}/{count} photos")
                    successes, errors = process_batch(
                        photos, portrait, landscape, prefix, tmp_path, on_progress=report
                    )
                    if successes:
                        st.session_state.export_path = tmp_path
                        st.session_state.export_meta = (successes, errors, st.session_state.batch_num, safe_name(prefix))
                        st.success(f"Created {successes} framed photos in batch {st.session_state.batch_num}.")
                    else:
                        if os.path.exists(tmp_path):
                            os.remove(tmp_path)
                        st.error("None of the photos could be processed. Check your frames and image formats.")
                    if errors:
                        with st.expander(f"{len(errors)} photo(s) skipped — details"):
                            st.code("\n".join(errors))
                except Exception as exc:
                    if tmp_path and os.path.isfile(tmp_path):
                        os.remove(tmp_path)
                    st.error(f"Processing failed: {type(exc).__name__}: {exc}")
    else:
        st.write("Upload your frames and photos to start.")

    saved = st.session_state.export_path
    meta = st.session_state.export_meta
    if saved and meta and os.path.exists(saved):
        successes, errors, completed_batch, saved_prefix = meta
        st.success(f"Batch {completed_batch} ready: {successes} image(s)")
        # Streamlit may buffer download data in RAM. A 12-photo JPEG ZIP is deliberately small.
        with open(saved, "rb") as zip_file:
            st.download_button(
                "📥 Download framed photos ZIP", zip_file,
                file_name=f"{saved_prefix}_batch_{completed_batch:02d}.zip",
                mime="application/zip", type="primary", on_click="ignore"
            )
        st.warning("Download the ZIP before clicking Next batch. The previous ZIP is deleted when you move on.")
        if st.button("➡️ Next batch — upload more photos"):
            clear_prior_export()
            st.session_state.batch_num += 1
            st.rerun()
