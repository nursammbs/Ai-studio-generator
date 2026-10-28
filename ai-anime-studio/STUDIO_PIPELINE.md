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
