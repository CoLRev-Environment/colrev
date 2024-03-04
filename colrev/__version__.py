# pylint: disable=missing-module-docstring
try:
    from importlib.metadata import version
except ImportError:
    # For Python < 3.8
    from importlib_metadata import version  # type: ignore

__version__ = version("colrev")
