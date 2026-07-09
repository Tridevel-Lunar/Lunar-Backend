def laika_provider_error_message(exc: Exception) -> str:
    text = str(exc).strip()
    lowered = text.lower()

    if "cuda error" in lowered or "llama-server process has terminated" in lowered:
        return (
            "Ollama ไม่สามารถสร้างคำตอบได้ (GPU/CUDA error) — "
            "ลอง restart Ollama, ลด OLLAMA_NUM_CTX (เช่น 4096–8192), "
            "เปลี่ยน OLLAMA_LLM_MODEL เป็นโมเดลเล็กลง, "
            "หรือใช้ LAIKA_LLM_PROVIDER=gemini"
        )
    if "model" in lowered and "not found" in lowered:
        return (
            "Ollama model not found — run `ollama pull` for OLLAMA_LLM_MODEL / OLLAMA_EMBED_MODEL"
        )
    if "connection" in lowered or "connect" in lowered:
        return "Cannot reach Ollama — ensure Ollama is running and OLLAMA_BASE_URL is correct"

    return f"LAIKA provider error: {text}"
