def make_chunks(messages, max_chars=1500):
    """
    messages: list of (role, content, created_at) urut lama->baru
    output: list of chunk_text
    """
    chunks = []
    buf = ""

    for role, content, created_at in messages:
        line = f"[{role}] {content}\n"
        if len(buf) + len(line) > max_chars:
            if buf.strip():
                chunks.append(buf.strip())
            buf = line
        else:
            buf += line

    if buf.strip():
        chunks.append(buf.strip())

    return chunks
