#!/usr/bin/env bash
# Bootstrap ComfyUI in a cloud GPU VM. Run with: bash ai-anime-studio/cloud_gpu/bootstrap_comfyui.sh
set -Eeuo pipefail
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
COMFY_DIR="${COMFY_DIR:-$HOME/ComfyUI}"
COMFY_HOST="${COMFY_HOST:-127.0.0.1}"
COMFY_PORT="${COMFY_PORT:-8188}"
INSTALL_ANIMATE2=0
START_SERVER=0
usage() {
  cat <<'EOF'
Usage: bash ai-anime-studio/cloud_gpu/bootstrap_comfyui.sh [--with-wan-animate2] [--start]
  --with-wan-animate2  Download official Wan Animate 2 weights (~24 GB).
  --start              Start ComfyUI after setup.
  --help               Show this help.
Environment: COMFY_DIR, COMFY_HOST (default 127.0.0.1), COMFY_PORT,
             ALLOW_LOW_VRAM=1 to bypass the 24 GiB download warning.
Security: don't expose an unauthenticated ComfyUI port publicly.
EOF
}
while (($#)); do
  case "$1" in
    --with-wan-animate2) INSTALL_ANIMATE2=1 ;;
    --start) START_SERVER=1 ;;
    --help|-h) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
  shift
done
for cmd in git python3; do
  command -v "$cmd" >/dev/null 2>&1 || { echo "Missing required command: $cmd" >&2; exit 2; }
done
echo "== Cloud GPU preflight =="
if command -v nvidia-smi >/dev/null 2>&1; then
  nvidia-smi
  VRAM_MIB="$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits 2>/dev/null | head -n1 | tr -d '[:space:]' || true)"
  if [[ "$VRAM_MIB" =~ ^[0-9]+$ ]]; then
    VRAM_GIB=$((VRAM_MIB / 1024))
    echo "Detected GPU VRAM: ${VRAM_GIB} GiB"
    if (( INSTALL_ANIMATE2 == 1 && VRAM_GIB < 24 )); then
      echo "Wan Animate 2 is unlikely to run reliably on a GPU under 24 GiB." >&2
      echo "Its largest diffusion file is 15.5 GB; text encoder is 6.3 GB, before runtime memory." >&2
      if [[ "${ALLOW_LOW_VRAM:-0}" != "1" ]]; then
        echo "Choose a larger GPU or set ALLOW_LOW_VRAM=1 to continue anyway." >&2
        exit 3
      fi
    elif (( INSTALL_ANIMATE2 == 1 && VRAM_GIB < 40 )); then
      echo "Warning: this GPU may still OOM during Wan Animate 2 inference." >&2
    fi
  fi
else
  echo "Warning: nvidia-smi was not found. GPU inference is not verified." >&2
fi
if ! command -v ffmpeg >/dev/null 2>&1; then
  if command -v apt-get >/dev/null 2>&1 && [[ "$(id -u)" == "0" ]]; then
    apt-get update
    DEBIAN_FRONTEND=noninteractive apt-get install -y ffmpeg
  else
    echo "Install FFmpeg before rendering (Ubuntu/Debian: sudo apt-get install -y ffmpeg)." >&2
    exit 2
  fi
fi
if [[ ! -d "$COMFY_DIR/.git" ]]; then
  echo "== Cloning official ComfyUI into $COMFY_DIR =="
  git clone --depth 1 https://github.com/comfyanonymous/ComfyUI.git "$COMFY_DIR"
else
  echo "== Updating existing ComfyUI checkout =="
  git -C "$COMFY_DIR" pull --ff-only
fi
python3 -m pip install --upgrade pip
python3 -m pip install -r "$COMFY_DIR/requirements.txt"
python3 -m pip install --upgrade huggingface_hub Pillow requests
if (( START_SERVER == 1 || INSTALL_ANIMATE2 == 1 )); then
  python3 - <<'PY'
import sys
try:
    import torch
except Exception as exc:
    print(f"PyTorch import failed: {exc}", file=sys.stderr)
    print("Select a GPU runtime with CUDA-enabled PyTorch, then rerun bootstrap.", file=sys.stderr)
    raise SystemExit(4)
if not torch.cuda.is_available():
    print("PyTorch cannot see a CUDA GPU. Select a GPU instance and install a compatible CUDA-enabled PyTorch build.", file=sys.stderr)
    raise SystemExit(4)
print(f"PyTorch {torch.__version__}; CUDA {torch.version.cuda}; GPU: {torch.cuda.get_device_name(0)}")
PY
fi
mkdir -p "$COMFY_DIR/user/default/workflows"
WORKFLOW_URL="https://raw.githubusercontent.com/Comfy-Org/workflow_templates/main/templates/video_wan_animate2.json"
WORKFLOW_PATH="$COMFY_DIR/user/default/workflows/video_wan_animate2.json"
if command -v curl >/dev/null 2>&1; then
  curl -fL --retry 3 "$WORKFLOW_URL" -o "$WORKFLOW_PATH"
else
  python3 - "$WORKFLOW_URL" "$WORKFLOW_PATH" <<'PY'
import sys
from urllib.request import urlretrieve
urlretrieve(sys.argv[1], sys.argv[2])
PY
fi
echo "Workflow template saved: $WORKFLOW_PATH"
if (( INSTALL_ANIMATE2 == 1 )); then
  echo "== Downloading official Comfy-Org Wan Animate 2 weights (~24 GB) =="
  python3 - "$COMFY_DIR" <<'PY'
import sys
from pathlib import Path
from huggingface_hub import hf_hub_download
model_root = Path(sys.argv[1]) / "models"
files = [
    "diffusion_models/wan_animate_2_int8_convrot.safetensors",
    "loras/lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors",
    "text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors",
    "clip_vision/clip_vision_h.safetensors",
    "vae/Wan2_1_VAE_bf16.safetensors",
]
for filename in files:
    (model_root / Path(filename).parent).mkdir(parents=True, exist_ok=True)
    print(f"\nDownloading {filename}", flush=True)
    hf_hub_download(repo_id="Comfy-Org/Wan-Animate-2", filename=filename, local_dir=model_root)
print("\nModel downloads completed.")
PY
fi
echo
echo "Setup complete. ComfyUI: $COMFY_DIR"
echo "Project pipeline: $PROJECT_DIR/studio_pipeline.py"
echo "Next: open the template, verify model/input nodes, then export API format."
echo "API-format workflow required; the visual UI graph cannot be passed directly to the pipeline."
echo "No AI inference is claimed by this setup script."
if (( START_SERVER == 1 )); then
  cd "$COMFY_DIR"
  exec python3 main.py --listen "$COMFY_HOST" --port "$COMFY_PORT"
fi
