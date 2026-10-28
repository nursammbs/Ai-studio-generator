# Motion guide inputs

Place short, licensed motion-guide clips here. For Wan Animate 2, keep each guide close to the intended shot duration (the upstream template documents 81 frames, about 3.4 seconds at 24 fps per Motion Transfer subgraph), with one clear action and framing comparable to the character reference image.

Suggested filenames: `01_sneak_and_peek.mp4`, `02_run_and_skid.mp4`, `03_jump_and_land.mp4`, `04_surprised_reaction.mp4`.

These files are *inputs to generate the cartoon character animation*, not final animated shots. They must exist on the same machine/network-accessible filesystem as the project. The pipeline copies them to ComfyUI's `input/` folder if `--comfy-input-dir` is supplied. Only use footage you own or have permission to use.
