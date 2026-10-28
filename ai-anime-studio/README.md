# AI Anime Studio — Open Source Prototype

An experimental local-first pipeline combining **ComfyUI** (AI image generation) with a Python/Streamlit production UI and MP4 rendering.

## What works
- Offline three-scene cartoon animatic with original vector characters and deterministic motion; no GPU or model download required.
- ComfyUI local API client: connection test, prompt/seed injection, job submission, history polling, and generated-image download.
- Storyboard mode accepts an AI-generated 3-panel image, crops its three panels, adds captions and gentle camera movement, and exports an MP4.
- AI mode generates three scene stills using a workflow you provide, then creates a short MP4 with gentle camera push-in.
- Automated tests cover workflow mutation, a mocked ComfyUI HTTP API, and MP4 render/decode smoke tests.

## Limitations — please read
This is a prototype, not an automatic anime studio. Storyboard mode animates camera movement over a generated triptych; ComfyUI mode generates **still images** and turns them into a pan/zoom animatic. Neither mode generates full frame-by-frame body animation. Reusing the same character description helps but does not guarantee character identity consistency. Stronger consistency requires a compatible reference-image workflow (for example IP-Adapter/ControlNet) configured and tested with your installed model.

The build environment had no running local ComfyUI server or installed image-generation checkpoint, so real model inference was not executed here. The offline MP4 was rendered and decode-tested, and the API integration has mock-server tests.

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

The selected nodes must have inputs named `text` and `seed`. Custom workflows may use different node classes or input names and require adapting `engine.py`.

## Test
```bash
python -m pytest -q
```

## Licensing
Code in this folder is MIT-licensed. ComfyUI, FFmpeg, checkpoints, custom nodes and generated assets have their own license/usage terms. Verify every component before commercial use.
