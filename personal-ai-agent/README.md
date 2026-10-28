# Personal AI Workbench

A local-first personal AI assistant that connects to an open-weight model running in Ollama and gives it a small, explicit toolset. This is a practical foundation for a private AI workspace—not a copy of any proprietary model.

## What it does

- Chat through a simple Streamlit interface.
- Connect to a model running locally with Ollama.
- Let the model call a small allowlist of tools: web search, public GitHub repository search, calculator, and local time.
- Attach text, Markdown, or CSV notes as temporary context.
- Export the conversation as Markdown.
- Keep tool execution explicit and bounded; it does not run arbitrary shell commands or automatically publish/upload content.

## What it does not do

This does **not** copy GPT-6 weights, private training data, hidden internal tools, or proprietary service infrastructure. It will not automatically be better than a frontier model. The goal is to make an assistant you control and improve through model choice, evaluation, better tools, your own knowledge base, and task-specific workflows.

Image/video generation is a separate capability. The companion project `opensource-video-studio/` creates basic narrated MP4 drafts; ComfyUI can later be connected as a visual generation backend.

## Requirements

- Python 3.10+
- [Ollama](https://ollama.com/) running on the same machine (or on a trusted computer on your network)
- A downloaded chat model that supports tool calling. As a small starting point, try `qwen3.5:4b` if available in your Ollama catalog; for stronger results use a larger compatible model that your hardware can handle.
- Internet is required only for web/GitHub search tools. Prompts are sent to your configured Ollama endpoint; using a remote endpoint means that provider may receive your prompts.

## Windows quick start

1. Install Python and Ollama.
2. In a terminal, download a compatible model, for example:

   ```powershell
   ollama pull qwen3.5:4b
   ```

3. Download/clone this repository, then open the `personal-ai-agent` folder.
4. Double-click `run_windows.bat`, or run manually:

   ```powershell
   python -m venv .venv
   .venv\Scripts\Activate.ps1
   python -m pip install --upgrade pip
   pip install -r requirements.txt
   streamlit run app.py
   ```

5. Open the local Streamlit URL shown in the terminal. In the sidebar, check the model name and Ollama URL.

macOS/Linux: create a virtual environment, install `requirements.txt`, and run `streamlit run app.py`.

## Improve it responsibly

1. Measure it on a repeatable set of your real tasks before calling a model an “upgrade”.
2. Add only tools you need, each with a narrow schema and clear permission boundaries.
3. Keep API keys in environment variables, never in source control.
4. Verify search results and generated claims before using them commercially.
5. Check the chosen model's own license and acceptable-use terms before redistribution or commercial deployment.

## License

The starter code in this folder is MIT licensed. Model weights, data, third-party tools, and external services have separate licenses and terms.
