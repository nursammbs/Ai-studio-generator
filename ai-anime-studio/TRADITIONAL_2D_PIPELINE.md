# Asset-first 2D animation: the default low-compute path

Use deterministic 2D animation for recurring characters and ordinary scenes. Use generative video only when a particular shot needs motion that would be expensive to author manually.

This reuses traditional cel-animation principles:
- reuse the approved character drawing and background;
- switch between hand-authored poses at keyframes;
- tween position, scale and rotation between poses;
- hold frames on dialogue/reaction beats;
- assemble shots and audio after rendering.

It is intentionally **not** described as equivalent to feature-quality hand-drawn animation. Professional-looking output still needs good artwork, pose sheets, timing, staging and cleanup. This renderer interpolates transforms; it does not invent missing anatomy or automatically draw every in-between.

## Run

From the ai-anime-studio directory:

~~~bash
python traditional_2d_pipeline.py --manifest examples/traditional_2d.example.json --validate-only
python traditional_2d_pipeline.py --manifest examples/traditional_2d.example.json --output outputs/episode_2d.mp4
~~~

Use your own transparent 2x2 pose sheets. The four cells are read left-to-right, top-to-bottom. Each cell should contain one complete character pose on a transparent background. Configure characters.cat.sheet and characters.mouse.sheet in the manifest; asset paths are relative to the JSON manifest.

## Timeline format

Each scene has a duration, background color or optional background image, and characters in back-to-front render order. Each character instance has keyframes with seconds (t), horizontal position (x), baseline (y), size multiplier (scale), angle in degrees (rotation), and pose index (pose, 0–3). Transforms interpolate between keys; poses hold until the next pose key. Use ease: "smoothstep" for eased movement, or cycle_fps to cycle through the four sheet cells.

A minimal keyframe sequence can make a character enter, stop, and react without an AI video model. Add more authored poses for walk/run/anticipation/impact/recovery; use held poses for dialogue and comedy timing. Reuse the same background and character sheet across shots to preserve identity.

## Quality upgrade path

1. Make a model sheet and transparent pose assets for each character: neutral, anticipation, walk/run, turn, impact, reaction and mouth shapes.
2. Approve a storyboard and shot timings before rendering.
3. For higher quality, draw additional poses/in-betweens or rig body parts in OpenToonz; export transparent pose frames into this pipeline.
4. Add a small number of AI-generated hero shots only where needed, using ComfyUI/Wan if adequate GPU memory is actually available.
5. Review the whole episode for continuity, then do audio mix and export.

No GPU model download is needed for this path. Rendering uses Python/Pillow plus imageio/FFmpeg. Output is as consistent as the input art and timing; this is a limited/cutout animation system, not a one-click replacement for a human animation team.
