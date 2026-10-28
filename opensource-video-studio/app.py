from __future__ import annotations

import shutil
import streamlit as st

from engine import create_video, generate_scenes, research_topic

st.set_page_config(page_title="Open Source Video Studio", page_icon="🎬", layout="wide")
st.title("🎬 Open Source Video Studio")
st.caption("Topik → riset awal → draf naskah → suara → video MP4. Review semua hasil sebelum upload.")

with st.sidebar:
    st.subheader("Status")
    if shutil.which("ffmpeg") and shutil.which("ffprobe"):
        st.success("FFmpeg siap")
    else:
        st.error("FFmpeg/ffprobe belum ditemukan")
    st.caption("Ollama opsional. Edge TTS perlu internet. Rendering membutuhkan komputer.")

with st.form("create_video"):
    topic = st.text_input("Topik video", placeholder="Contoh: cara kerja panel surya untuk pemula")
    left, mid, right = st.columns(3)
    with left:
        language_label = st.selectbox("Bahasa", ["Bahasa Indonesia", "English"])
        language = "id" if language_label == "Bahasa Indonesia" else "en"
    with mid:
        format_label = st.selectbox("Format", ["YouTube Shorts 9:16", "YouTube 16:9"])
        aspect = "9:16" if format_label.startswith("YouTube Shorts") else "16:9"
    with right:
        count = st.slider("Jumlah scene", 3, 7, 5)
    style = st.selectbox("Gaya", ["Penjelasan edukatif", "Storytelling", "Tutorial", "Analisis kritis"])
    use_ollama = st.checkbox("Gunakan Ollama lokal untuk menyusun naskah", value=False)
    model = st.text_input("Model Ollama (jika aktif)", value="qwen2.5:3b")
    create = st.form_submit_button("Buat draf dan render video", type="primary", use_container_width=True)

if create:
    if not topic.strip():
        st.error("Isi topik terlebih dahulu.")
    elif not (shutil.which("ffmpeg") and shutil.which("ffprobe")):
        st.error("Pasang FFmpeg dan ffprobe lalu buka ulang aplikasi. Petunjuk ada di README.")
    else:
        try:
            with st.spinner("Mencari bahan riset awal..."):
                sources = research_topic(topic.strip(), language)
                scenes, note = generate_scenes(topic.strip(), sources, count, language, use_ollama, model.strip() or "qwen2.5:3b", style)
            st.warning(note)
            st.subheader("Draf naskah")
            for i, scene in enumerate(scenes, 1):
                with st.expander(f"Scene {i}: {scene['heading']}", expanded=(i == 1)):
                    st.write(scene["narration"])
            if sources:
                st.subheader("Sumber awal")
                for source in sources:
                    st.markdown(f"- [{source['title']}]({source['url']})")
            else:
                st.warning("Riset otomatis tidak menemukan sumber. Verifikasi klaim manual sebelum publikasi.")
            progress = st.progress(0.0, text="Menyiapkan render...")
            status = st.empty()
            def update(value, message):
                progress.progress(min(max(value, 0.0), 1.0), text=message)
                status.info(message)
            job = create_video(topic.strip(), scenes, sources, language, aspect, update)
            video = job / "video.mp4"
            st.success("Render selesai. Hasil belum diunggah ke YouTube.")
            st.video(str(video))
            st.subheader("Unduh hasil")
            c1, c2, c3 = st.columns(3)
            with c1:
                st.download_button("Video MP4", video.read_bytes(), "video.mp4", "video/mp4", use_container_width=True)
            with c2:
                st.download_button("Thumbnail", (job / "thumbnail.jpg").read_bytes(), "thumbnail.jpg", "image/jpeg", use_container_width=True)
            with c3:
                st.download_button("Naskah", (job / "script.md").read_bytes(), "script.md", "text/markdown", use_container_width=True)
            c4, c5 = st.columns(2)
            with c4:
                st.download_button("Sumber riset", (job / "sources.md").read_bytes(), "sources.md", "text/markdown")
            with c5:
                st.download_button("Deskripsi + atribusi", (job / "description.txt").read_bytes(), "description.txt", "text/plain")
            st.caption(f"File lokal disimpan di: {job}")
        except Exception as exc:
            st.error(f"Proses gagal: {exc}")
            st.info("Periksa koneksi internet, FFmpeg/ffprobe, dan layanan Edge TTS. Detail teknis tersedia di terminal.")
st.divider()
st.markdown("Jangan langsung memublikasikan hasil mentah. Verifikasi klaim, periksa lisensi setiap gambar, dengarkan audio, dan pastikan video memberi nilai orisinal. Otomatisasi tidak menjamin views, pendapatan, atau monetisasi.")
