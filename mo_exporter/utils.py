from collections.abc import Callable
from typing import Any


# based on: https://github.com/python/typing/issues/270#issuecomment-555966301
class copy_signature[F]:
    """Decorator to copy signature of other callable."""

    def __init__(self, target: F) -> None: ...
    def __call__(self, wrapped: Callable[..., Any]) -> F:
        return wrapped  # type: ignore
