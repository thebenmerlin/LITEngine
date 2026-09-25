"""
LITEngine Hugging Face Space Entrypoint.
Mounts the production FastAPI application inside Gradio on ZeroGPU hardware.
"""

import gradio as gr
from main import app as fastapi_app

try:
    import spaces  # Installed by the ZeroGPU Space runtime.
except ImportError:
    spaces = None


if spaces is not None:
    @spaces.GPU(duration=1)
    def _zerogpu_startup_probe():
        """Register a GPU callback for ZeroGPU startup; never used by the API."""
        return None

# Create an informative status dashboard for visitors accessing the Space root directly
with gr.Blocks(title="LITEngine Legal Intelligence Engine") as demo:
    gr.Markdown("# ⚖️ LITEngine AI Backend")
    gr.Markdown(
        """
        ### System Status: **ONLINE** 🟢
        The REST API runs on CPU in this ZeroGPU Space.
        
        - **Interactive API Documentation:** [`/docs`](/docs)
        - **Readiness Probe:** [`/api/v1/health/ready`](/api/v1/health/ready)
        - **Health Endpoint:** [`/health`](/health)
        - **Precedent & Vector Search:** `/api/v1/precedent`
        - **Simulation & Outcome Engine:** `/api/v1/simulation`
        """
    )
    with gr.Row():
        test_btn = gr.Button("Test API Health")
        test_out = gr.Textbox(label="Health Status", value="Click above to test")

    def test_health():
        return "FastAPI Engine is alive and responding!"

    test_btn.click(test_health, outputs=test_out)

    # ZeroGPU requires a registered GPU event even though the backend uses CPU.
    # This hidden event is never invoked by normal visitors or REST requests.
    if spaces is not None:
        probe_btn = gr.Button(visible=False)
        probe_btn.click(_zerogpu_startup_probe, api_name=False)

# Mount Gradio interface onto FastAPI at root path
# FastAPI routes (/health, /docs, /api/v1/...) take precedence in route resolution
app = gr.mount_gradio_app(fastapi_app, demo, path="/")

if __name__ == "__main__":
    import uvicorn
    if spaces is not None:
        # mount_gradio_app bypasses Blocks.launch(), which normally reports
        # decorated functions to ZeroGPU. Report them before serving FastAPI.
        import spaces.zero
        spaces.zero.startup()
    uvicorn.run(app, host="0.0.0.0", port=7860)
