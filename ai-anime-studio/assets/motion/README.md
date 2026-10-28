# Driving-video inputs for Wan Animate 2

The example manifest expects these files, all 832×480, 24 fps, 81 frames (~3.375 seconds), without audio:

- `01_cheese_discovery.mp4`
- `02_chase_start.mp4`
- `03_kitchen_chaos.mp4`
- `04_final_gag.mp4`

They are included in the downloadable **Wan Animate 2 Motion-Transfer Starter Kit**. The clips are deterministic 2D sprite/cutout blocking guides—not live-action footage or model-generated final shots. Use them to validate the ComfyUI mapping and rough motion direction, then replace or refine them with higher-quality motion references when necessary.

The pipeline copies each selected driving video into the ComfyUI `input/` directory when `--comfy-input-dir` is supplied. That path must be the real input folder on the machine running ComfyUI. Only use motion references you own or have permission to use.
