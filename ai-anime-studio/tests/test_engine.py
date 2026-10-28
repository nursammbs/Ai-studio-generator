import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread

import pytest
from PIL import Image

from engine import ComfyUIClient, concatenate_videos, render_image_animatic, render_offline_animatic


def tiny_workflow():
    return {
        "1": {"class_type": "CLIPTextEncode", "inputs": {"text": "old positive", "clip": ["4", 0]}},
        "2": {"class_type": "CLIPTextEncode", "inputs": {"text": "old negative", "clip": ["4", 0]}},
        "3": {"class_type": "KSampler", "inputs": {"seed": 4, "steps": 6}},
    }


def test_patch_workflow_replaces_requested_fields_without_mutating_input():
    source = tiny_workflow()
    patched = ComfyUIClient.patch_workflow(source, "1", "2", "3", "cat running", "blurry", 99)
    assert patched["1"]["inputs"]["text"] == "cat running"
    assert patched["2"]["inputs"]["text"] == "blurry"
    assert patched["3"]["inputs"]["seed"] == 99
    assert source["1"]["inputs"]["text"] == "old positive"


def test_patch_workflow_rejects_unknown_node():
    with pytest.raises(ValueError, match="tidak ditemukan"):
        ComfyUIClient.patch_workflow(tiny_workflow(), "88", "2", "3", "a", "b", 3)


def test_offline_animatic_renders_and_decodes(tmp_path):
    target = tmp_path / "test.mp4"
    render_offline_animatic(target, width=480, height=270, fps=12, seconds_per_scene=1)
    assert target.exists() and target.stat().st_size > 10_000


def test_image_animatic_renders_and_decodes(tmp_path):
    source = tmp_path / "scene.png"
    Image.new("RGB", (320, 240), (100, 160, 210)).save(source)
    target = tmp_path / "slideshow.mp4"
    render_image_animatic([source], target, width=320, height=180, fps=12, seconds_per_image=1)
    assert target.exists() and target.stat().st_size > 1_000


def test_comfyui_api_health_submit_history_and_download(tmp_path):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            if self.path == "/system_stats":
                body = json.dumps({"system": {"ok": True}}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(body)
            elif self.path == "/history/fake-id":
                body = json.dumps({"fake-id": {"outputs": {"9": {"images": [
                    {"filename": "ok.png", "subfolder": "", "type": "output"}
                ]}}}}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(body)
            elif self.path.startswith("/view?"):
                import io
                stream = io.BytesIO()
                Image.new("RGB", (5, 5), (20, 30, 40)).save(stream, format="PNG")
                body = stream.getvalue()
                self.send_response(200)
                self.send_header("Content-Type", "image/png")
                self.end_headers()
                self.wfile.write(body)
            else:
                self.send_response(404)
                self.end_headers()

        def do_POST(self):
            self.rfile.read(int(self.headers.get("Content-Length", "0")))
            body = json.dumps({"prompt_id": "fake-id"}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        client = ComfyUIClient(f"http://127.0.0.1:{server.server_port}", timeout=3)
        assert client.health()["system"]["ok"] is True
        assert client.submit(tiny_workflow()) == "fake-id"
        outputs = client.wait_for_outputs("fake-id", timeout=1, poll_seconds=.2)
        assert outputs[0]["filename"] == "ok.png"
        assert client.download_image(outputs[0], tmp_path / "download.png").exists()
    finally:
        server.shutdown()
        thread.join(timeout=2)
        server.server_close()



def test_storyboard_triptych_renders_and_decodes(tmp_path):
    from PIL import ImageDraw
    from engine import render_storyboard_triptych

    storyboard = Image.new("RGB", (300, 120), "white")
    draw = ImageDraw.Draw(storyboard)
    draw.rectangle((0, 0, 98, 119), fill=(200, 60, 60))
    draw.rectangle((101, 0, 198, 119), fill=(60, 180, 80))
    draw.rectangle((201, 0, 299, 119), fill=(60, 90, 200))
    source = tmp_path / "storyboard.png"
    storyboard.save(source)
    target = tmp_path / "storyboard.mp4"
    render_storyboard_triptych(
        source, target, panel_bounds=[(0, .33), (.337, .66), (.67, 1)],
        width=480, height=270, fps=12, seconds_per_panel=1,
    )
    assert target.exists() and target.stat().st_size > 1_000

def test_patch_video_workflow_updates_prompt_seed_and_uploaded_image():
    workflow = {
        "1": {"inputs": {"text": "old prompt"}},
        "3": {"inputs": {"seed": 1}},
        "10": {"inputs": {"image": "old.png"}},
    }
    patched = ComfyUIClient.patch_video_workflow(
        workflow,
        positive_node_id="1",
        seed_node_id="3",
        image_node_id="10",
        positive_prompt="a cat runs",
        seed=42,
        uploaded_image_name="input.png",
    )
    assert patched["1"]["inputs"]["text"] == "a cat runs"
    assert patched["3"]["inputs"]["seed"] == 42
    assert patched["10"]["inputs"]["image"] == "input.png"
    assert workflow["10"]["inputs"]["image"] == "old.png"


def test_concatenate_videos_normalizes_and_decodes(tmp_path):
    from engine import render_offline_animatic
    first = render_offline_animatic(tmp_path / "one.mp4", width=320, height=180, fps=6, seconds_per_scene=1)
    second = render_offline_animatic(tmp_path / "two.mp4", width=320, height=180, fps=6, seconds_per_scene=1)
    output = concatenate_videos([first, second], tmp_path / "joined.mp4", fps=6, width=320, height=180)
    assert output.exists() and output.stat().st_size > 1000

