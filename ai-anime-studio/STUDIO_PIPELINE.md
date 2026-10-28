# Upgrade jalur produksi: kartun berbasis shot dengan model video open-source

Jalur sprite/cutout lama tetap berguna untuk animatic, tetapi bukan pengganti gerakan karakter per frame. Upgrade ini menambahkan produksi berbasis shot: buat keyframe/pose yang disetujui per adegan, generate klip image-to-video terpisah lewat ComfyUI, lalu normalisasi, atur kecepatan, beri transisi, dan gabungkan menjadi episode final.

## Stack open-source

- ComfyUI: https://github.com/Comfy-Org/ComfyUI
- Wan2.2: https://github.com/Wan-Video/Wan2.2
- ComfyUI-WanVideoWrapper (opsional): https://github.com/kijai/ComfyUI-WanVideoWrapper
- OpenToonz untuk cleanup 2D, timing, in-between dan compositing: https://github.com/opentoonz/opentoonz
- Blender untuk previs, staging, layout kamera dan compositing: https://github.com/blender/blender

Wan2.2 menyatakan lisensi model Apache 2.0 di repositori upstream. Tetap periksa file LICENSE pada model, checkpoint dan ekstensi yang dipasang. Untuk percobaan, mulai dari workflow Wan2.2 TI2V 5B bila perangkat cukup; model 14B/Wan-Animate lebih berat. Kebutuhan VRAM, node dan nama model dapat berubah, jadi ikuti instruksi upstream terbaru.

## Instalasi dan menjalankan

1. Pasang Python 3.10+, FFmpeg dan ffprobe. Instal ComfyUI dari repo resmi dan tambahkan checkpoint video yang sesuai dengan workflow.
2. Di ComfyUI, buka workflow image-to-video yang bekerja, uji satu shot, lalu ekspor dalam format API JSON.
3. Buat still/keyframe yang sudah disetujui untuk setiap shot. Jaga character bible, proporsi, palet, arah layar, dan lokasi. Letakkan gambarnya sesuai path pada project JSON.
4. Jalankan perintah dari direktori ai-anime-studio supaya engine.py tersedia.

Contoh (ganti workflow dan ID node berdasarkan JSON yang diekspor; ID berikut hanya contoh):

```bash
python studio_pipeline.py \
  --project examples/shotlist.example.json \
  --workflow workflows/wan_i2v_api.json \
  --positive-node 6 --seed-node 3 --image-node 56 --negative-node 7 \
  --output outputs/episode_final.mp4 \
  --music assets/original_score.wav \
  --width 1280 --height 720 --fps 24 --transition 0.25
```

Workflow harus menerima input gambar, prompt positif, seed dan output video yang dibaca oleh engine.py (node output bertipe videos atau gifs). Node ID dapat berbeda. Parameter --negative-node opsional; gunakan jika workflow mempunyai node CLIP Text Encode negatif dengan input text. Tanpa ComfyUI, --assemble-only dapat menggabungkan klip yang sudah dibuat jika tiap shot mempunyai atribut source_video.

## Kenapa dibuat banyak klip

Klip pendek per shot memberi kontrol lebih baik daripada satu video panjang: prompt, seed, keyframe, tempo, dan hasil bisa diperiksa satu per satu. File mentah disimpan di outputs/studio_pipeline/raw, jadi shot yang sudah berhasil tidak dibuat ulang saat resume. File hasil normalisasi masuk ke outputs/studio_pipeline/normalized.

## Prinsip untuk mendekati kartun TV

1. **Character bible dan model sheet.** Buat tampak depan/samping/3-4, palet, proporsi dan ekspresi. Prompt teks saja tidak menjamin identitas konsisten.
2. **Storyboard dan animatic dulu.** Kunci durasi, komposisi, arah gerak, staging dan punchline sebelum generasi video.
3. **Render beberapa take.** Variasikan seed dan pilih take terbaik; jangan anggap keluaran pertama layak tayang.
4. **QC continuity.** Periksa wajah, telinga/ekor, warna, anggota badan, arah gerak, skala, props, lighting, serta frame awal/akhir setiap shot. Ulangi shot yang gagal.
5. **Editing dan timing.** Percepatan hanya mengubah tempo; itu tidak memperbaiki anatomi yang rusak. Gunakan dissolve singkat saat sesuai, hard cut untuk aksi cepat. Tambahkan dialog, foley dan musik secara terpisah.
6. **Cleanup shot hero.** Close-up, ekspresi dan gerakan penting mungkin perlu diperbaiki manual di OpenToonz atau compositing. Produksi profesional masih memerlukan keputusan artistik dan review manusia.

## Validasi dan batasan

Pipeline menguji apakah output bisa didekode FFmpeg dan memeriksa durasi/ukuran file. Unit test mencakup validasi manifest. Itu bukan pengganti review visual atas flicker, konsistensi karakter dan kontinuitas. Inferensi model sungguhan harus diuji pada komputer yang menjalankan ComfyUI, checkpoint dan workflow yang kompatibel; model belum dijalankan di lingkungan build ini.

## Motion-reference mode (lebih terarah)

Untuk ekspresi dan gerakan yang lebih terkendali, pertimbangkan **Wan2.2-Animate** sebagai workflow, bukan text-only image-to-video. Framework tersebut menggunakan video pemandu gerakan/ekspresi dan gambar karakter sebagai referensi; periksa panduan resmi untuk mode animate/replace dan format yang tepat: https://docs.comfy.org/tutorials/video/wan/wan2-2-animate dan https://github.com/Wan-Video/Wan2.2.

Pada shot yang memiliki driving-video, tambahkan field `motion_video` ke manifest:

```json
{
  "id": "02_chase",
  "reference_image": "assets/cat_mouse_keyframe.png",
  "motion_video": "assets/motion/chase_blocking.mp4",
  "prompt": "The gray cat chases the mouse from left to right, preserve the approved cartoon design.",
  "seed": 41002,
  "speed": 1.0
}
```

Pastikan video pemandu legal untuk digunakan dan hanya berisi gerakan yang ingin ditiru. Ekspor workflow Wan-Animate sebagai API JSON, lalu jalankan:

```bash
python studio_pipeline.py \
  --project examples/shotlist.example.json \
  --workflow workflows/wan_animate_api.json \
  --positive-node 6 --seed-node 3 --image-node 56 \
  --motion-video-node 58 --motion-video-field file \
  --comfy-input-dir /path/to/ComfyUI/input \
  --output outputs/episode_animate.mp4
```

Semua node ID dan nama field pada contoh hanyalah ilustrasi. `--comfy-input-dir` harus menunjuk ke folder input **di mesin yang menjalankan ComfyUI**; skrip menyalin motion clip ke sana dan memasukkan nama file ke node video yang dipilih. Workflow harus benar-benar memakai node video itu untuk mengendalikan animasi. Tidak semua workflow Wan-Animate mempunyai struktur node/input yang sama.

Motion reference meningkatkan arahan gerak, tetapi tidak menjamin hasil sempurna: gerakan sumber yang rumit, occlusion, kamera, proporsi hewan kartun, dan perbedaan bentuk manusia/hewan dapat menghasilkan deformasi. Tinjau setiap take dan bersihkan shot penting di OpenToonz/compositing.


## Update pipeline: workflow API fields are configurable

The new `studio_pipeline.py` accepts custom input names, because native ComfyUI workflows do not all use the same node fields. It also writes a three-frame-per-shot HTML review page and contact sheet after rendering; every shot has a start, middle and end frame for a human continuity check.

The cache is now keyed to a fingerprint of the source reference image, optional driving video, workflow file, prompt, seed, style/character brief, speed and node configuration. If those values change, the old output is **not** silently reused. Add `--force` to regenerate all shots even when the fingerprint matches.

## Current ComfyUI native workflow option: Wan Animate 2

Comfy-Org publishes a newer native template called [Wan Animate 2: Motion Transfer](https://github.com/Comfy-Org/workflow_templates/blob/main/templates/video_wan_animate2.json). There is also a documented earlier [Wan2.2 Animate workflow](https://docs.comfy.org/tutorials/video/wan/wan2-2-animate), which uses a reference image and motion video in its Move/animation mode. Template internals and node IDs change, so export the workflow as **API format** in the installed ComfyUI version and inspect that exported prompt dictionary before running the script.

For a workflow API that uses a nonstandard prompt or image input field, set the CLI field options explicitly. Example node IDs below are placeholders; they must match your API export:

```bash
python studio_pipeline.py \
  --project examples/shotlist.motion_reference.example.json \
  --workflow workflows/wan_animate_api.json \
  --positive-node MAIN_NODE_ID --positive-field text \
  --pose-prompt-node MAIN_NODE_ID --pose-prompt-field text_4 \
  --seed-node SAMPLER_NODE_ID --seed-field seed \
  --image-node LOAD_IMAGE_NODE_ID --image-field image \
  --motion-video-node LOAD_VIDEO_NODE_ID --motion-video-field file \
  --comfy-input-dir /path/to/ComfyUI/input \
  --output outputs/episode_final.mp4 --force
```

Use the exact node and field names present in your exported API workflow. If the graph includes a subgraph, conditioning nodes or multiple samplers, select the actual input nodes in that graph. The command is not a one-click import of a UI-format workflow: it expects the workflow to be exported into the API format accepted by `POST /prompt`.

### Review before publication

After assembly, open `outputs/studio_pipeline/review/index.html`. Inspect all starts/middles/ends and reject shots with changing character design, flicker, malformed limbs/ears/tails, broken object continuity, screen-direction jumps or abrupt camera moves. The contact sheet is a triage tool, **not** an automated animation-quality score. Generate alternate seeds for failures and manually clean essential shots in OpenToonz or a compositing application.

### Compute requirements

No model weights are bundled with this repository. Wan2.2 Animate is a large model family; model variants and memory requirements vary significantly. The upstream Wan2.2 repository lists the TI2V-5B workflow as its smaller 5B path, while its 14B Animate path has a larger footprint and additional workflow dependencies. Use official Comfy-Org templates and the model card for the exact files and current hardware guidance: [Wan2.2](https://github.com/Wan-Video/Wan2.2), [ComfyUI model templates](https://github.com/Comfy-Org/workflow_templates/tree/main/templates). This environment does not run the actual model inference; install model weights on the target computer and verify one short shot before queuing a full episode.


The official Wan Animate 2 UI template currently exposes separate inputs on the Motion Transfer subgraph: an appearance/background prompt and a pose/motion prompt. If the exported API workflow preserves these inputs, configure `--positive-node MAIN_NODE_ID --positive-field text` for appearance and `--pose-prompt-node MAIN_NODE_ID --pose-prompt-field text_4` for movement. The actual API export may flatten subgraphs or rename fields; inspect the **API prompt JSON** and replace all placeholder node IDs/fields before queuing a shot. Keep each driving-video clip short enough for the configured workflow: the current template documentation describes 81 frames per Motion Transfer subgraph (~3.4 s at 24 fps), and longer movement requires chaining/extension in the workflow.

After generation completes, `outputs/studio_pipeline/review/index.html` provides human QC. The code checks file decoding and cache validity; it does not automatically approve animation quality.


## Find node IDs without guessing

Use the new inspector before starting a long render:

```bash
python workflow_inspect.py --workflow workflows/wan_animate_api.json --output outputs/workflow_nodes.md
```

Open `outputs/workflow_nodes.md` and use the exact node IDs and API input names it reports for the appearance prompt, pose prompt, seed, reference image and driving video. If the tool reports that the file is a UI graph (with a nodes array), export **API format** from ComfyUI and run the inspector again on that API JSON. This is particularly useful for Wan Animate 2, whose nested subgraphs can be flattened and assigned different IDs by the installed ComfyUI version.


## Starter assets ready to test

The downloadable **Wan Animate 2 Motion-Transfer Starter Kit** contains four matching 832×480 reference compositions and driving clips (81 frames at 24 fps) for the example manifest. These are deliberately simple 2D puppet/blocking guides from the existing cat/mouse sprite art—not final AI-generated animation. They give the pipeline actual input files so you can test node mapping and continuity one shot at a time.

Copy the kit's `ai-anime-studio/assets/refs/`, `ai-anime-studio/assets/motion/`, and `ai-anime-studio/examples/shotlist.motion_reference.example.json` into the corresponding paths in this repository. Do not overwrite `engine.py` or `studio_pipeline.py` when copying the assets. The reference images are paired with matching first-frame compositions from each driving video.

### Wan Animate 2 field names

In the current Comfy-Org UI template, the top-level **LoadVideo** node's filename input is usually `file` (the driving video itself is passed to the Motion Transfer subgraph's `video` input). Motion Transfer exposes a main appearance/background prompt and a separate pose prompt. In this pipeline, the input names are configurable; set `--motion-video-node` to the LoadVideo node ID and `--motion-video-field file`, but only after checking the API JSON report. The subgraph's `text` and `text_4` fields are the current UI template's prompt labels, not guaranteed API field names after export. The sampler seed node may also be internal; select the actual node/field reported by the API inspector.

**Important:** the official UI workflow is not itself an API prompt. Export API format in ComfyUI, inspect it with `workflow_inspect.py`, then do a single-shot validation. The script cannot infer hidden/nested node mappings that the export did not expose.


## Recreate the starter guides locally

Place the two transparent pose sheets from the starter kit in `ai-anime-studio/assets/source/`, then run from the `ai-anime-studio/` folder:

```bash
python generate_motion_guides.py
```

The generator writes the four PNG reference frames and four 81-frame MP4 blocking guides to `assets/refs/` and `assets/motion/`. It is deterministic sprite/cutout animation for motion-reference testing; it does not run an AI video model.


## Smoke test satu shot sebelum membuat satu episode

Karena model Wan Animate 2 besar dan render per shot memakan komputasi, jangan langsung antrekan semua adegan. Jalankan hanya adegan pertama dengan `--limit-shots 1`:

```bash
python studio_pipeline.py \
  --project examples/shotlist.motion_reference.example.json \
  --workflow workflows/wan_animate2_api.json \
  --positive-node MOTION_NODE_ID --positive-field text \
  --pose-prompt-node MOTION_NODE_ID --pose-prompt-field text_4 \
  --seed-node SAMPLER_NODE_ID --seed-field seed \
  --image-node LOAD_IMAGE_NODE_ID --image-field image \
  --motion-video-node LOAD_VIDEO_NODE_ID --motion-video-field file \
  --comfy-input-dir /path/to/ComfyUI/input \
  --limit-shots 1 --output outputs/smoke_test.mp4 --force
```

Ganti semua ID dan field placeholder berdasarkan hasil `workflow_inspect.py`. Jika seed tidak diekspos oleh API graph, hilangkan `--seed-node` dan `--seed-field`; pipeline mempertahankan seed yang sudah tersimpan dalam workflow. Setelah hasil pertama lolos inspeksi, hapus `--limit-shots 1` untuk membuat semua shot, atau gunakan `--only-shot 03_kitchen_chaos` untuk mengulang hanya adegan tertentu.
