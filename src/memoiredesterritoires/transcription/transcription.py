from faster_whisper import WhisperModel

def transcribe_chunks(path, max_time=180, chunk_size=30):
    # 1. Setup
    model_size = "large-v3-turbo"
    model = WhisperModel(model_size, device="cpu", compute_type="int8")

    # 2. Transcribe
    segments, info = model.transcribe(
        path, 
        vad_filter=True, 
        vad_parameters=dict(min_silence_duration_ms=500)
    )

    # 3. Chunk logic
    current_chunk_text = []
    next_checkpoint = chunk_size

    print(f"--- Transcribing first {max_time}s in {chunk_size}s chunks ---")

    for segment in segments:
        current_chunk_text.append(segment.text)

        if segment.end >= next_checkpoint:
            chunk_num = next_checkpoint // chunk_size
            print(f"\n[CHUNK {chunk_num} | Ends at {segment.end:.2f}s]:")
            print(" ".join(current_chunk_text).strip())

            current_chunk_text = []
            next_checkpoint += chunk_size

        if segment.end >= max_time:
            break
