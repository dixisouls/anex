"""Small shared helpers for the backend."""

def to_str(value):
    """Redis with decode_responses=False returns bytes. Decode to str, and pass
    anything already a str straight through. Used everywhere we read a hash,
    a stream entry, or a search result field."""
    if isinstance(value, bytes):
        return value.decode("utf-8")
    return value