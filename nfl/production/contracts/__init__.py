"""Typed artifact contracts for the production path (P0-A).

Blueprint 1.7: nothing, partial output, malformed output or unchecked output
may be read as success. A contract is how a stage says, in advance and in
code, what a complete instance of its artifact looks like -- so that
"complete" is a property the machine checks rather than a sentence a human
writes afterwards.
"""
from nfl.production.contracts.registry import (  # noqa: F401
    ArtifactContract, LayerSpec, REGISTRY, register, get, names)
from nfl.production.contracts.validate import (  # noqa: F401
    CODES, validate_draw_manifest, validate_row_count)
