# pylint: disable=missing-module-docstring
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version

try:
    __version__ = version("colrev")
except PackageNotFoundError:
    __version__ = "0.0.0"
