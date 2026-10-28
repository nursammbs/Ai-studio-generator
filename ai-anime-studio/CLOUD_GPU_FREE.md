# Free / trial cloud GPU for AI Anime Studio

A free GPU can help with experiments and small models, but **there is no dependable unlimited free GPU service** for full episodes with Wan Animate 2.

## Best first attempt for the current pipeline

**Lightning AI**: https://lightning.ai/pricing

Its current pricing page advertises up to 80 starting GPU hours without a credit card, but the actual credits, GPU types and availability depend on the account. If an A100 40 GB or L40S 48 GB instance is available in the account, use it for a one-shot experiment. This is introductory compute, not unlimited ongoing free hosting.

The official ComfyUI Wan Animate 2 workflow uses a 15.51 GB diffusion model, 6.27 GB text encoder, 1.18 GB CLIP vision model, LoRA and VAE. Those are disk sizes—not peak VRAM requirements. Runtime memory is additional, so a 16 GB GPU is not a realistic target for this whole workflow; even a larger GPU can OOM depending on settings and offloading.

### Bootstrap ComfyUI in a cloud GPU VM

In a GPU-enabled VM terminal:

\`\`\`bash
git clone https://github.com/nursammbs/Ai-studio-generator.git
cd Ai-studio-generator
bash ai-anime-studio/cloud_gpu/bootstrap_comfyui.sh
\`\`\`

The script clones/updates official ComfyUI, installs requirements, downloads the current official Wan Animate 2 workflow template and checks detected GPU memory. It does not download huge model weights unless you ask for them.

After checking the disk and GPU:

\`\`\`bash
bash ai-anime-studio/cloud_gpu/bootstrap_comfyui.sh --with-wan-animate2
\`\`\`

To start the UI:

\`\`\`bash
COMFY_HOST=127.0.0.1 bash ai-anime-studio/cloud_gpu/bootstrap_comfyui.sh --start
\`\`\`

Use the cloud provider's authenticated port-forwarding feature for port 8188. Do **not** expose an unauthenticated ComfyUI port to the public internet. If the provider's proxy requires another listen address, follow its port-forwarding/security instructions and restrict access.

The workflow template is saved at \`~/ComfyUI/user/default/workflows/video_wan_animate2.json\`. Load it in ComfyUI, confirm that all models and input clips resolve, then export as **API format**. The UI graph is not the API prompt dictionary expected by the pipeline.

### Connect it to the existing project

Copy the separate starter-kit assets into \`ai-anime-studio/assets/refs/\` and \`ai-anime-studio/assets/motion/\`. Then inspect your API export:

\`\`\`bash
cd ai-anime-studio
python workflow_inspect.py --workflow workflows/wan_animate2_api.json --output outputs/workflow_nodes.md
\`\`\`

Use the exact node IDs and fields reported, then run only one shot (all IDs here are placeholders):

\`\`\`bash
python studio_pipeline.py \\
  --project examples/shotlist.motion_reference.example.json \\
  --workflow workflows/wan_animate2_api.json \\
  --positive-node MAIN_NODE_ID --positive-field text \\
  --pose-prompt-node MOTION_NODE_ID --pose-prompt-field text_4 \\
  --image-node LOAD_IMAGE_NODE_ID --image-field image \\
  --motion-video-node LOAD_VIDEO_NODE_ID --motion-video-field file \\
  --comfy-input-dir "$HOME/ComfyUI/input" \\
  --limit-shots 1 --output outputs/smoke_test.mp4 --force
\`\`\`

Replace **every** placeholder with the node IDs/fields from the API export. If subgraphs are flattened differently, use the exported structure. Once the first clip exists and passes visual review, render more shots. Use \`--only-shot SHOT_ID\` to retry an individual scene.

If the project code and ComfyUI run on separate VMs, \`127.0.0.1:8188\` will not address the remote ComfyUI server; set \`--comfy-url\` to a protected reachable endpoint. Keep the API private.

## Alternatives if no larger GPU is available

| Service | Free access currently documented | Best use |
|---|---|---|
| [Kaggle Notebooks](https://www.kaggle.com/docs/notebooks) | Free P100 GPU when available; quota is limited (the docs describe around 30 hours/week, subject to capacity and quotas). | FFmpeg assembly, preprocessing and small models. P100 has ~16 GB VRAM; don't expect reliable full Wan Animate 2 inference. |
| [Google Colab](https://research.google.com/colaboratory/intl/id/faq.html) | Free GPU/TPU access, but GPU type and runtime limits vary and are not guaranteed. | Small-model experiments and pipeline tests; do not plan around a guaranteed GPU type. |
| [Hugging Face ZeroGPU](https://huggingface.co/docs/hub/spaces-zerogpu) | Free accounts currently have a small daily quota (documented as 5 GPU minutes/day). | Demo use or a tiny smoke test, not an episode render. |
| [Lightning AI](https://lightning.ai/pricing) | Advertises starting GPU credits (up to 80 hours depending on tier/instance). | First choice for a larger-GPU trial if A100/L40S is actually offered by the account. |

### Fallback for 16 GB cards

Use the official ComfyUI Wan 2.1 **1.3B** template for a lower-memory experiment: https://github.com/Comfy-Org/workflow_templates/blob/main/templates/text_to_video_wan.json

This is **not** the same as motion transfer or character animation. Character identity may be weaker; switch back to the Wan Animate 2 workflow once suitable compute is available.

## License and cost notes

- ComfyUI, workflow templates, model weights and custom nodes have separate terms; verify each before commercial use.
- Signup GPU credits are temporary, not an ongoing free host. Stop the VM when done.
- Model downloads use about 24 GB of disk and substantial bandwidth.
- This bootstrap script installs code/workflow/model files only. The actual test is a generated clip on the selected GPU followed by human visual review.
