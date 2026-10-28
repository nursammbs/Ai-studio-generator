# AI Anime Studio — Open Source Prototype

An experimental local-first pipeline combining **ComfyUI** (AI image generation) with a Python/Streamlit production UI and MP4 rendering.

## What works
- Offline three-scene cartoon animatic with original vector characters and deterministic motion; no GPU or model download required.
- ComfyUI local API client: connection test, prompt/seed injection, job submission, history polling, and generated-image download.
- Storyboard mode accepts an AI-generated 3-panel image, crops its three panels, adds captions and gentle camera movement, and exports an MP4.
- AI mode generates three scene stills using a workflow you provide, then creates a short MP4 with gentle camera push-in.
- Optional image-to-video mode accepts a second ComfyUI API workflow, uploads each generated still, runs a video workflow, downloads its video/GIF output, and concatenates clips into an MP4.
- Automated tests cover workflow mutation, a mocked ComfyUI HTTP API, MP4 render/decode, and clip concatenation.

## Limitations — please read
This is a prototype, not an automatic anime studio. Storyboard mode animates camera movement over a generated triptych; ComfyUI mode generates **still images** and turns them into a pan/zoom animatic. Neither mode generates full frame-by-frame body animation. Reusing the same character description helps but does not guarantee character identity consistency. Stronger consistency requires a compatible reference-image workflow (for example IP-Adapter/ControlNet) configured and tested with your installed model.

The build environment had no running local ComfyUI server or installed image/video-generation checkpoint, so real model inference was not executed here. The offline MP4 was rendered and decode-tested, and API integration logic is covered by tests. The image-to-video feature requires a compatible, already-working ComfyUI I2V workflow and a video output node; workflow node IDs and output formats vary.

## Requirements
- Python 3.10+
- FFmpeg, or a working imageio-ffmpeg installation
- For AI mode: a working local ComfyUI install, a loaded checkpoint and a working text-to-image workflow exported in API format

## Windows
```bat
py -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

## Linux/macOS
```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

## Storyboard image workflow
1. Generate a 3-panel storyboard with your preferred image model, keeping the same character design in all panels.
2. In the app, upload the PNG/JPG under **Ubah storyboard AI menjadi video**.
3. Adjust the normalized left/right panel boundaries to avoid white gutters.
4. Render and download the captioned MP4.

The renderer can make an actual video from an AI-generated storyboard, but its motion is camera pan/zoom, not new AI-generated motion frames.

## AI workflow setup
1. Start ComfyUI locally (default URL: `http://127.0.0.1:8188`).
2. Open a working text-to-image workflow in ComfyUI.
3. Export **API format** JSON.
4. In this app, upload the JSON and enter the node IDs for positive prompt, negative prompt, and seed. The default IDs in the UI are examples; use the IDs in your exported workflow.
5. Click **Generate 3 gambar AI + video**.
6. Optional motion generation: upload a second, working image-to-video workflow in API format. Set its positive prompt node, seed node, and LoadImage node IDs. This workflow must produce a video/GIF output. When present, the app runs the I2V workflow for each of the three generated images and concatenates the clips.

The selected nodes must have inputs named `text` and `seed`. Custom workflows may use different node classes or input names and require adapting `engine.py`.

## Test
```bash
python -m pytest -q
```

## Licensing
Code in this folder is MIT-licensed. ComfyUI, FFmpeg, checkpoints, custom nodes and generated assets have their own license/usage terms. Verify every component before commercial use.


## AI-generated sprite animation pilot (new)

The separate `sprite_animator.py` renderer animates the included transparent AI-generated cat/mouse pose sheet when you download the accompanying **AI Anime Studio pilot package** linked from the chat delivery. It builds a garden background, switches among generated poses, adds movement, captions, and a synthesized original music cue, then renders H.264 MP4. It is reproducible without a GPU after the image sheet is available locally.

Run:
```bash
python sprite_animator.py --sheet assets/character_sheet.png --output output.mp4 --seconds 15 --fps 24
```

**Capability boundary:** this is AI-art-assisted 2D sprite/cutout animation, not a diffusion text-to-video result or frame-by-frame anime animation. The actual video in the pilot package was rendered and decode-tested. The separate ComfyUI connection remains the path toward testing a real Wan image-to-video workflow; that still requires a running ComfyUI instance and compatible model weights.


## Quick start: real image-to-video with Wan 2.2

The official ComfyUI workflow library provides Wan 2.2 text-to-video and image-to-video templates. Start with the **Wan 2.2 5B Video Generation** template for a smaller model than the 14B I2V workflow. Official references:
- Template workflow JSON: https://github.com/Comfy-Org/workflow_templates/blob/main/templates/video_wan2_2_5B_ti2v.json
- Official guide: https://docs.comfy.org/tutorials/video/wan/wan2_2
- Model package: https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged

### Model files

The template references a roughly 9.31 GB diffusion model (`wan2.2_ti2v_5B_fp16.safetensors`), a 1.31 GB VAE (`wan2.2_vae.safetensors`) and a 6.27 GB text encoder (`umt5_xxl_fp8_e4m3fn_scaled.safetensors`). Check the latest official model card for exact files and sizes before downloading.

### Wiring the app to an I2V workflow

1. In ComfyUI, open the official Wan 2.2 5B template, make sure all model files are present, and run it once directly in ComfyUI. The template can be used in image-to-video mode by enabling the input-image path; use the template instructions for your ComfyUI version.
2. Export the working graph as **API format** from ComfyUI.
3. In this app, upload that JSON under “Workflow API image-to-video”. Default node IDs match the official UI template's typical IDs (positive prompt `6`, KSampler `3`, Load Image `56`), but always inspect the API export and change them if it differs.
4. Set the positive prompt to describe both the action and camera motion, e.g. “same gray cartoon cat character, takes three quick running steps to the right, tail swishes, side tracking camera, preserve the supplied character design”.
5. Upload a separate, working text-to-image API workflow in the first workflow field to generate the scene stills. Then click “Generate 3 gambar AI + video”. The app will render the stills, run the I2V graph once per scene, and concatenate the returned clips.
6. Review each clip for character drift, malformed movement, and continuity before publishing.

### Important boundary

This is the actual path for **generative motion**. However, a successful unit test only verifies API request construction and video stitching, not that a local GPU has enough memory or that a real Wan inference succeeds. The first real inference must be run on the target ComfyUI machine; if VRAM is insufficient, start with lower output resolution/frame count or use a GPU/cloud environment you control. This repository does not silently use a paid cloud service.
