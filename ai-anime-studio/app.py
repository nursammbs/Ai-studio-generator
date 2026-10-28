from __future__ import annotations

import json
from pathlib import Path

import streamlit as st
from engine import ComfyUIClient, render_image_animatic, render_offline_animatic

APP_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = APP_DIR / "outputs"
OUTPUT_DIR.mkdir(exist_ok=True)

st.set_page_config(page_title="AI Anime Studio — Open Source", page_icon="🎬", layout="wide")
st.title("🎬 AI Anime Studio — Open Source")
st.caption("ComfyUI untuk gambar AI + render animatic MP4. Demo offline tersedia untuk tes tanpa GPU.")

with st.sidebar:
    st.header("1. Sambungan ComfyUI")
    base_url = st.text_input("ComfyUI URL", value="http://127.0.0.1:8188")
    if st.button("Tes koneksi ComfyUI", use_container_width=True):
        try:
            st.success("ComfyUI terhubung.")
            st.json(ComfyUIClient(base_url=base_url).health())
        except Exception as exc:
            st.error(str(exc))
    st.divider()
    st.header("2. Workflow API")
    workflow_file = st.file_uploader("Upload workflow JSON format API", type=["json"])
    st.caption("Di ComfyUI, buka workflow text-to-image yang bekerja lalu pilih Export → API.")

left, right = st.columns(2)
with left:
    st.subheader("Cerita dan prompt")
    character = st.text_area(
        "Deskripsi karakter tetap",
        value="original small gray cartoon cat, triangular ears, yellow eyes, short muzzle, white whiskers, consistent body proportions, clean 2D cel animation style",
        height=95,
    )
    st.text_area(
        "Ringkasan cerita",
        value="A curious cat notices a tiny mouse, chases it through a sunny garden, then comes to a funny stop while the mouse escapes.",
        height=80,
        key="story_summary",
    )
    scene_prompts = [
        st.text_area("Adegan 1 — perkenalan", value=f"{character}, in a sunny garden noticing a tiny gray mouse, wide shot, clean line art, 2D cel animation", height=78),
        st.text_area("Adegan 2 — kejar-kejaran", value=f"{character}, running after a tiny gray mouse across a sunny garden, dynamic side view, clean line art, 2D cel animation", height=78),
        st.text_area("Adegan 3 — penutup komedi", value=f"{character}, surprised expression after stopping suddenly, tiny mouse escaping in background, clean line art, 2D cel animation", height=78),
    ]
with right:
    st.subheader("Pengaturan render")
    negative = st.text_area("Negative prompt", value="different character design, extra limbs, deformed anatomy, blurry, text, watermark, photorealistic", height=85)
    seconds = st.slider("Detik per adegan", min_value=2, max_value=8, value=3)
    fps = st.select_slider("Frame rate", options=[12, 18, 24], value=24)
    st.write("Node IDs workflow API")
    positive_id = st.text_input("ID positive text node", value="6")
    negative_id = st.text_input("ID negative text node", value="7")
    seed_id = st.text_input("ID seed node (KSampler)", value="3")
    seed_start = st.number_input("Seed awal", min_value=0, max_value=2**32-1, value=12345, step=1)
    st.info("ID 6/7/3 hanya contoh. Sesuaikan dengan node ID di workflow yang di-export.")

st.divider()
st.subheader("3. Ubah storyboard AI menjadi video")
st.caption("Unggah gambar storyboard 3 panel yang dibuat dengan model gambar AI. Aplikasi akan memotong panel, memberi gerakan kamera sederhana, dan merender MP4.")
storyboard_upload = st.file_uploader("Gambar storyboard 3 panel", type=["png", "jpg", "jpeg"], key="storyboard_upload")
storyboard_left = st.text_input("Batas panel 1 (x kiri,kanan; 0–1)", value="0.000,0.325")
storyboard_mid = st.text_input("Batas panel 2 (x kiri,kanan; 0–1)", value="0.337,0.661")
storyboard_right = st.text_input("Batas panel 3 (x kiri,kanan; 0–1)", value="0.673,1.000")
if st.button("Render storyboard AI → MP4", use_container_width=True):
    if storyboard_upload is None:
        st.error("Unggah gambar storyboard terlebih dahulu.")
    else:
        try:
            from engine import render_storyboard_triptych
            panel_bounds = []
            for value in (storyboard_left, storyboard_mid, storyboard_right):
                pair = [float(part.strip()) for part in value.split(",")]
                if len(pair) != 2 or not (0 <= pair[0] < pair[1] <= 1):
                    raise ValueError("Setiap batas panel harus dua angka 0–1, misalnya 0.000,0.325.")
                panel_bounds.append((pair[0], pair[1]))
            source_path = OUTPUT_DIR / "uploaded_storyboard.png"
            source_path.write_bytes(storyboard_upload.getvalue())
            video = render_storyboard_triptych(
                source_path, OUTPUT_DIR / "storyboard_ai_animatic.mp4",
                panel_bounds=panel_bounds, fps=fps, seconds_per_panel=seconds,
            )
            st.session_state["last_video"] = str(video)
            st.session_state["last_images"] = []
            st.session_state["last_note"] = (
                "Video dibuat dari gambar storyboard yang diunggah. Gerakan adalah pan/zoom pada tiap panel; "
                "bukan generasi frame animasi penuh. Sesuaikan batas panel jika gambar memiliki gutter berbeda."
            )
            st.success("Storyboard AI berhasil dirender menjadi MP4.")
        except Exception as exc:
            st.error(f"Render storyboard gagal: {exc}")

st.divider()
col_demo, col_ai = st.columns(2)

with col_demo:
    if st.button("Buat demo offline 3 adegan", type="primary", use_container_width=True):
        video = OUTPUT_DIR / "offline_three_scene_animatic.mp4"
        with st.spinner("Merender frame dan memeriksa MP4..."):
            render_offline_animatic(video, fps=fps, seconds_per_scene=seconds)
        st.session_state["last_video"] = str(video)
        st.session_state["last_images"] = []
        st.session_state["last_note"] = "Demo offline: karakter vektor prosedural, bukan gambar model AI. Digunakan untuk menguji pipeline rendering."
        st.success("Demo dirender dan berhasil dibaca ulang untuk verifikasi.")

with col_ai:
    if st.button("Generate 3 gambar AI + video", use_container_width=True):
        if workflow_file is None:
            st.error("Upload workflow ComfyUI format API terlebih dahulu.")
        else:
            try:
                workflow = json.loads(workflow_file.getvalue().decode("utf-8"))
                if isinstance(workflow.get("prompt"), dict):
                    workflow = workflow["prompt"]
                client = ComfyUIClient(base_url=base_url, timeout=45)
                client.health()
                project_dir = OUTPUT_DIR / "comfyui_project"
                project_dir.mkdir(parents=True, exist_ok=True)
                generated = []
                progress = st.progress(0, text="Memulai generasi...")
                for index, prompt in enumerate(scene_prompts):
                    progress.progress(index / 3, text=f"Menghasilkan adegan {index + 1}/3...")
                    raw_path = client.generate_image(
                        workflow,
                        positive_node_id=positive_id.strip(),
                        negative_node_id=negative_id.strip(),
                        seed_node_id=seed_id.strip(),
                        positive_prompt=prompt,
                        negative_prompt=negative,
                        seed=int(seed_start) + index,
                        output_dir=project_dir,
                        timeout=600,
                    )
                    destination = project_dir / f"scene_{index + 1}.png"
                    raw_path.replace(destination)
                    generated.append(destination)
                progress.progress(1.0, text="Merender MP4...")
                video = render_image_animatic(
                    generated, OUTPUT_DIR / "comfyui_three_scene_animatic.mp4",
                    fps=fps, seconds_per_image=seconds,
                )
                st.session_state["last_video"] = str(video)
                st.session_state["last_images"] = [str(path) for path in generated]
                st.session_state["last_note"] = (
                    "Tiga gambar dibuat oleh workflow ComfyUI yang dipilih. Gerakan MP4 berupa camera push-in/pan, "
                    "bukan animasi tubuh frame-by-frame. Konsistensi karakter bergantung pada workflow/model."
                )
                st.success("Generasi tiga adegan dan rendering MP4 selesai.")
            except Exception as exc:
                st.error(f"Pipeline gagal: {exc}")

if st.session_state.get("last_video"):
    video_path = Path(st.session_state["last_video"])
    if video_path.exists():
        st.subheader("Hasil produksi")
        data = video_path.read_bytes()
        st.video(data)
        st.caption(st.session_state.get("last_note", ""))
        st.download_button("Unduh MP4", data=data, file_name=video_path.name, mime="video/mp4")
        image_paths = st.session_state.get("last_images", [])
        if image_paths:
            columns = st.columns(3)
            for column, image_path in zip(columns, image_paths):
                column.image(image_path, caption=Path(image_path).name, use_container_width=True)

with st.expander("Petunjuk mode AI dan batasannya"):
    st.markdown("""
1. Jalankan ComfyUI secara lokal dan pastikan ada checkpoint serta workflow text-to-image yang berhasil.
2. Buka workflow itu di ComfyUI dan pilih Export → API.
3. Upload JSON ke sidebar.
4. Masukkan ID node untuk positive prompt, negative prompt, dan seed. Input standar biasanya bernama text dan seed; custom nodes bisa berbeda.
5. Klik Generate 3 gambar AI + video.

**Batasan:** aplikasi menghasilkan tiga gambar lalu mengubahnya menjadi animatic pan/zoom. Ia belum membuat gerakan tubuh penuh. Prompt karakter yang sama membantu, tetapi tidak menjamin identitas visual konsisten. Untuk itu gunakan workflow referensi karakter (misalnya IP-Adapter/ControlNet) yang sesuai dengan model dan uji hasilnya.
""")
