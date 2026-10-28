# AI Anime Studio — Open Source Prototype

An experimental local-first pipeline combining ComfyUI video/image workflows with a Python/Streamlit UI and MP4 rendering.

## Modes

- Offline three-scene cartoon animatic with vector characters and deterministic motion; no GPU/model download required.
- ComfyUI client with workflow injection, job polling and output downloads.
- Image-to-video workflow mode for generating separate moving clips from approved stills.
- **Shot-based production pipeline**: batch multiple scene clips, resume completed renders, set shot speeds, normalize H.264 output, add transitions, and assemble an episode with optional background music. See [STUDIO_PIPELINE.md](STUDIO_PIPELINE.md), [studio_pipeline.py](studio_pipeline.py), and [example shot list](examples/shotlist.example.json).
- Automated tests cover workflow mutation, mocked API interaction, offline rendering, clip concatenation, and production-manifest validation.

## Production-quality caveat

This is an open-source AI-assisted production pipeline, not a promise of one-click studio-quality animation. Generative video can still show character identity drift, flicker, malformed anatomy, and continuity errors. Human review, multiple takes, keyframe approval, sound design, and manual cleanup of hero shots are required. This environment does not have a running ComfyUI model server/checkpoint, so real Wan inference has not been claimed or verified here.

## Open-source references

- ComfyUI: https://github.com/Comfy-Org/ComfyUI
- Wan2.2: https://github.com/Wan-Video/Wan2.2
- ComfyUI-WanVideoWrapper (optional): https://github.com/kijai/ComfyUI-WanVideoWrapper
- OpenToonz: https://github.com/opentoonz/opentoonz
- Blender: https://github.com/blender/blender

Check each upstream repo for installation details, model size/VRAM requirements, current workflow templates and license terms before deploying.
