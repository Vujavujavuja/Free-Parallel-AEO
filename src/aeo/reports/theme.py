"""Shared visual theme for reports — warm ink/ember/wine editorial palette."""

from __future__ import annotations

# Core palette
INK = "#171411"        # near-black warm (primary text)
INK_SOFT = "#2b2620"
EMBER = "#ee5e13"      # primary accent
EMBER_DARK = "#c3420a"
EMBER_LIGHT = "#f3823f"
WINE = "#b23656"       # secondary accent
WINE_DARK = "#8f2334"
DUNE = "#776455"       # muted text
DUNE_LIGHT = "#968c82"
PAPER = "#faf7f2"      # warm page background
PARCHMENT = "#f2ede5"  # tile / panel fill
CREAM = "#ece7df"
RULE = "#e2d9cc"       # hairline on light
RULE_SOFT = "#efe8dd"

PROVENANCE = {"organic": EMBER, "search_driven": WINE, "absent": DUNE_LIGHT}

# Warm sequential heatmap stops (light parchment -> ember -> deep ember)
HEATMAP_STOPS = [PARCHMENT, EMBER_LIGHT, EMBER, "#8a2f04"]
