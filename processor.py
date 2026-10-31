"""Image framing helpers; no Streamlit dependency, so they can be tested."""
import io
import re
import zipfile
from PIL import Image, ImageOps

try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
    HEIC_ENABLED = True
except ImportError:
    HEIC_ENABLED = False

MAX_SIDE = 2200
QUALITY = 82


def safe_name(name):
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", name).strip("._")[:90] or "SME_Event"


def image_from_upload(upload, target=None, mode="RGB"):
    """Decode one file, correct camera orientation, resize before converting."""
    upload.seek(0)
    with Image.open(upload) as raw:
        if target:
            raw.draft("RGB", target)  # Efficient decode on JPEG where supported.
        corrected = ImageOps.exif_transpose(raw)
        try:
            if target:
                corrected.thumbnail(target, Image.Resampling.LANCZOS)
            return corrected.convert(mode)
        finally:
            corrected.close()


def frame_image(upload, portrait_frame, landscape_frame, frame_on_top=True, max_side=MAX_SIDE):
    """Produce one framed RGB image, with no retained full-resolution copies."""
    # Determine orientation cheaply using dimensions + EXIF rotation metadata.
    upload.seek(0)
    with Image.open(upload) as raw:
        portrait = raw.height > raw.width
        if raw.getexif().get(274, 1) in (5, 6, 7, 8):
            portrait = not portrait
    frame_upload = (portrait_frame or landscape_frame) if portrait else (landscape_frame or portrait_frame)
    if frame_upload is None:
        raise ValueError("Upload at least one transparent PNG frame.")
    frame_upload.seek(0)
    with Image.open(frame_upload) as raw_frame:
        w, h = raw_frame.size
    scale = min(1.0, max_side / max(w, h))
    target = (max(1, int(round(w * scale))), max(1, int(round(h * scale))))
    frame = image_from_upload(frame_upload, target, "RGBA")
    try:
        if frame.size != target:
            resized = frame.resize(target, Image.Resampling.LANCZOS)
            frame.close()
            frame = resized
        photo = image_from_upload(upload, target, "RGB")
        try:
            fitted = ImageOps.fit(photo, target, Image.Resampling.LANCZOS)
            try:
                if frame_on_top:
                    fitted.paste(frame, (0, 0), frame)
                else:
                    # Underlay mode: opaque photo covers the frame entirely.
                    # Retained only for compatibility with prior user-facing option.
                    pass
                return fitted.copy(), ("Portrait" if portrait else "Landscape")
            finally:
                fitted.close()
        finally:
            photo.close()
    finally:
        frame.close()


def encode_jpeg(image):
    b = io.BytesIO()
    image.save(b, "JPEG", quality=QUALITY, optimize=True)
    return b.getvalue()


def process_batch(photos, portrait_frame, landscape_frame, prefix, zip_path, on_progress=None):
    """Process sequentially and write directly to a ZIP file on disk."""
    errors = []
    successes = 0
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_STORED, allowZip64=True) as z:
        for n, photo_upload in enumerate(photos, 1):
            try:
                image, _ = frame_image(photo_upload, portrait_frame, landscape_frame)
                try:
                    jpeg = encode_jpeg(image)
                finally:
                    image.close()
                filename = f"{safe_name(prefix)}_{n:03d}.jpg"
                z.writestr(filename, jpeg)
                successes += 1
                del jpeg
            except (OSError, ValueError, MemoryError, SyntaxError) as exc:
                errors.append(f"{photo_upload.name}: {type(exc).__name__}: {exc}")
            if on_progress:
                on_progress(n, len(photos))
        if errors:
            z.writestr("processing_errors.txt", "\n".join(errors).encode("utf-8"))
    return successes, errors
