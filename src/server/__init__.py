"""Backend service package for Mémoire des Territoires."""

__all__ = [
    "create_app",
]


def create_app(*args, **kwargs):
    from .app import create_app as _create_app  # pylint: disable=import-outside-toplevel

    return _create_app(*args, **kwargs)
