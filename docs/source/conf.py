# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

from importlib.metadata import version as get_version

# -- Project information -----------------------------------------------------

project = "PyHardwareLibrary"
copyright = "2026, Daniel C. Cote"
author = "Daniel C. Cote"

try:
    release = get_version("hardwarelibrary")
except Exception:
    release = "unknown"

# -- General configuration ---------------------------------------------------

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "sphinx.ext.autosummary",
    "sphinx.ext.intersphinx",
    "myst_parser",
    "sphinxcontrib.mermaid",
]

# Render ```mermaid fenced blocks in the README files as diagrams rather than
# letting them fall through to a code block with an unknown lexer.
myst_fence_as_directive = ["mermaid"]

templates_path = ["_templates"]
exclude_patterns = []

source_suffix = {
    ".rst": "restructuredtext",
    ".md": "markdown",
}

# -- MyST settings -----------------------------------------------------------
# Generate GitHub-style slug anchors for headings so in-page links in the
# included README files resolve.
myst_heading_anchors = 3

# The README files are authored for GitHub, where relative links between them
# (and a few stale filenames) resolve against the repo root. Sphinx cannot
# follow those, so it degrades them to plain text; silence the per-link noise
# rather than rewrite the source markdown.
suppress_warnings = ["myst.xref_missing"]

# -- Autodoc settings --------------------------------------------------------
# Hardware drivers import vendor packages (pyusb, pyftdi, LabJackPython, ...)
# that need a backend or native library not present on the docs builder. Mock
# them so autodoc can import the modules and read docstrings regardless.
autodoc_mock_imports = [
    "usb",
    "serial",
    "pyftdi",
    "u3",
    "u6",
    "ue9",
    "LabJackPython",
    "cv2",
]

autodoc_member_order = "bysource"
autodoc_default_options = {
    "members": True,
    "show-inheritance": True,
}

autosummary_generate = True

# -- Napoleon settings -------------------------------------------------------

napoleon_google_docstring = True
napoleon_numpy_docstring = False

# -- Intersphinx settings ----------------------------------------------------

intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
}

# -- Options for HTML output -------------------------------------------------

html_theme = "furo"
html_static_path = ["_static"]
