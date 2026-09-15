from .base import Adapter, RunSpec
from .acpx import AcpxAdapter

ADAPTERS: dict[str, type[Adapter]] = {
    "acpx": AcpxAdapter,
}


def get_adapter(name: str, binary: str | None = None) -> Adapter:
    """`name` is `acpx` or `acpx:<agent>` where <agent> is an acpx subcommand
    name, an alias in RAW_AGENTS, or a raw ACP server command."""
    base, _, agent = name.partition(":")
    cls = ADAPTERS.get(base)
    if cls is None:
        raise SystemExit(f"unknown adapter {name!r}; known: acpx[:<agent>]")
    ad = cls(binary or "acpx")
    if agent:
        ad.agent = agent
    return ad


__all__ = ["Adapter", "RunSpec", "ADAPTERS", "get_adapter"]
