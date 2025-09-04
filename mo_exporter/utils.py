from collections.abc import Callable
from typing import Any, Concatenate, cast


# based on: https://github.com/python/typing/issues/270#issuecomment-555966301
class copy_signature[F]:
    """Decorator to copy signature of other callable."""

    def __init__(self, target: F) -> None: ...
    def __call__(self, wrapped: Callable[..., Any]) -> F:
        return wrapped  # type: ignore


class extends[A1, **P]:
    """Decorator to copy signature of other callable."""

    def __init__(self, target: Callable[P, Any]) -> None: ...
    def __call__(
        self, wrapped: Callable[Concatenate[A1, ...], Any]
    ) -> Callable[Concatenate[A1, P], Any]:
        return wrapped  # type: ignore


# https://github.com/python/cpython/pull/121693
def copy_method_params[**Param, Arg1, RV](
    source_method: Callable[Concatenate[Any, Param], Any],
) -> Callable[
    [Callable[Concatenate[Arg1, ...], RV]], Callable[Concatenate[Arg1, Param], RV]
]:
    """Cast the decorated method's call signature to the source_method's.
    Same as :func:`copy_func_params` but intended to be used with methods.
    It keeps the first argument (``self``/``cls``) of the decorated method.
    """

    def return_func(
        func: Callable[Concatenate[Arg1, ...], RV],
    ) -> Callable[Concatenate[Arg1, Param], RV]:
        return cast(Callable[Concatenate[Arg1, Param], RV], func)

    return return_func
