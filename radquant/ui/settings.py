"""radquant/ui/settings.py — Settings / runtime info Streamlit page."""

import streamlit as st
from radquant.ui.theme import inject_css


def render() -> None:
    inject_css()
    st.title("⚙️ Settings")

    # Runtime info
    st.subheader("Runtime")
    try:
        import torch
        cuda = torch.cuda.is_available()
        if cuda:
            props = torch.cuda.get_device_properties(0)
            vram_gb = props.total_memory / 1e9
            st.metric("GPU", props.name)
            st.metric("VRAM total", f"{vram_gb:.1f} GB")
            alloc = torch.cuda.memory_allocated(0) / 1e9
            st.metric("VRAM allocated", f"{alloc:.2f} GB")
        else:
            st.warning("No CUDA GPU detected — running on CPU.")
    except ImportError:
        st.warning("PyTorch not available.")

    from radquant.config import quant_mode, device as cfg_device
    st.metric("Quantization mode", quant_mode())
    st.metric("Device", cfg_device())

    # Credentials status
    st.subheader("Credentials")
    from radquant import config
    for name, fn in [("HF_TOKEN", config.hf_token), ("GROQ_TOKEN", config.groq_key), ("NVIDIA_KEY", config.nvidia_key)]:
        try:
            val = fn()
            st.success(f"✅ {name} — set ({val[:6]}…)")
        except EnvironmentError as e:
            st.warning(f"⚠️ {name} — {e}")

    # Model IDs
    st.subheader("Model IDs")
    st.code("Medical VLM:  google/medgemma-1.5-4b-it\nClassifier:   torchxrayvision DenseNet-121 (densenet121-res224-all)")

    st.subheader("About")
    st.markdown("**RadQuant** v0.1.0 — research/assistive demo, not a medical device.")
