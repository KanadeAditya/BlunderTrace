"""Theory and AI: library loading, retrieval SQL, the LangGraph writing flow, prompts, the move
checker, the fallback text and AI call logging (build steps 6–8). So far: the fallback text
and loading the shipped library.
"""

from app.rag.fallback import CardText, fallback_card
from app.rag.library import LibraryError, load_library

__all__ = ["CardText", "LibraryError", "fallback_card", "load_library"]
