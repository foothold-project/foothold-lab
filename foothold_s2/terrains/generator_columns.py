"""Column names of a terrain generator cfg: the old sub_terrains cfg and the EX-42 combined mesh cfg.

The old cfg (Isaac TerrainGeneratorCfg) names columns by the fixed layout of `columns.column_types`
over `sub_terrains` proportions. The combined mesh cfg has no `sub_terrains`; it carries
`column_family` (one family letter per joined column) and the kinds come from the column table
(`ex42_column_reset.build_column_table`). One helper, used by every training-path reader.

Names of the combined mesh: family A keeps its Isaac kind name (`flat`, `pyramid_stairs`, ...), so
the readers that look for those names still mean the A columns; every other family is written
`<family>/<kind>` (or just `<family>` when the code does not know the kind), so the same kind name in
two families can never be counted as one.
"""
from __future__ import annotations

from foothold_s2.terrains import columns


def is_combined_mesh_cfg(generator) -> bool:
    return not hasattr(generator, "sub_terrains") and hasattr(generator, "column_family")


def has_column_source(generator) -> bool:
    return generator is not None and hasattr(generator, "num_cols") and (
        hasattr(generator, "sub_terrains") or is_combined_mesh_cfg(generator))


def generator_column_names(generator) -> list[str]:
    """Name of every column (length num_cols). Raises if the cfg offers neither source."""
    if is_combined_mesh_cfg(generator):
        from foothold_s2.terrains.ex42_column_reset import build_column_table

        families = [str(f) for f in generator.column_family]
        if len(families) != int(generator.num_cols):
            raise ValueError(f"combined mesh cfg: {len(families)} column_family entries, num_cols {generator.num_cols}")
        names = []
        for row in build_column_table(families, {}):
            kind, family = row["kind"], row["family"]
            names.append(kind if family == "A" and kind else f"{family}/{kind}" if kind else family)
        return names
    if hasattr(generator, "sub_terrains"):
        proportions = {name: float(spec.proportion) for name, spec in generator.sub_terrains.items()}
        return columns.column_types(proportions, int(generator.num_cols))
    raise ValueError("terrain generator cfg has neither sub_terrains nor column_family: column names unknown")
