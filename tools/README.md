# Adding Hi3D models to Paperland Trails

One command turns a Hi3D export (any single-mesh, textured GLB) into a game model:

```
python3 tools/hi3d_import.py tools/cfg/<name>.json
```

It writes `models/<name>.json` (geometry embedded), `models/<name>_color.jpg` and one `models/<name>_glow_<group>.png` per glow group.

What it does:

1. **Checks texture orientation automatically.** It compares colours across UV seams for both vertical orientations and keeps the matching one.
2. **Simplifies the mesh** to `tris` triangles (default 150,000) with `simplify_uv.cpp`, which keeps the UV seams exact so the texture stays sharp. It compiles itself with g++ on first run.
3. **Scales and places the model**: one extent (`size.axis` / `size.length`) is set to real metres, feet on y = 0, centred.
4. **Bakes the palette grade into the texture** (`palette`, 0–1). The game needs no colour shader for it.
5. **Paints glow maps** from the model's own triangles:
   - `disc`: a round lamp at a point on one face (`+z` front, `-z` back, `±x` sides);
   - `rect`: a window rectangle on one side; `tex: 1` keeps the glass texture showing through;
   - `color`: every texel matching a colour rule (`cyan` lights, `red`).
6. **Anchors** (optional): named points converted to game units, such as where to hang the van's door lamp.

Coordinates in the config are in the source GLB's own units. The quickest way to find them is a front or side render with a grid.

In the game, `hqLoad(name, cb)` loads any of these. For characters, `KIT.reskin(C, geo, material)` puts the textured mesh on the existing rig; see the Watcher. For props, add a `THREE.Mesh` (see the van).

Examples: `cfg/watcher.json` (character, cyan colour-rule glow, no baked palette because its palette slider is live) and `cfg/van.json` (prop, lamps, windows, door anchor).
