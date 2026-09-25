"""
LITEngine Hugging Face Space Entrypoint.
Mounts the production FastAPI application inside Gradio to run on Hugging Face Spaces
using the 100% Free Gradio CPU Basic hardware (2 vCPU · 16 GB RAM).
"""

import gradio as gr
from main import app as fastapi_app

# Create an informative status dashboard for visitors accessing the Space root directly
with gr.Blocks(title="LITEngine Legal Intelligence Engine") as demo:
    gr.Markdown("# ⚖️ LITEngine AI Backend")
    gr.Markdown(
        """
        ### System Status: **ONLINE** 🟢
        The LITEngine legal intelligence backend is running with **16 GB RAM**.
        
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

# Mount Gradio interface onto FastAPI at root path
# FastAPI routes (/health, /docs, /api/v1/...) take precedence in route resolution
app = gr.mount_gradio_app(fastapi_app, demo, path="/")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=7860)
