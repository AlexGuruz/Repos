"""First-party agent packages.

Must stay a regular package (not a namespace package): the installed
``openai-agents`` SDK also publishes a top-level ``agents`` module, and a
namespace directory loses to it during import resolution.
"""
