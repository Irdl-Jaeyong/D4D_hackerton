# Ocean asset attribution

Source: https://github.com/osrf/vrx
Commit: 7609d1bd90ce7edb29d040a082f949e8b089c864 (jazzy branch)
Files copied unchanged:
- vrx_gz/models/coast_waves/meshes/waterlow.dae
- vrx_gz/models/coast_waves/materials/textures/wave_normals.dds

License: Apache-2.0; full upstream LICENSE is included here.
These are visual assets only. NAVIS uses a Gazebo Fortress PBR material;
VRX WaveVisual and wave physics plugins are not installed or invoked.

navis_water.dae is a previous NAVIS-derived height-displaced variant, preserved for provenance but no longer used. The active world uses the unmodified flat waterlow.dae to prevent visual occlusion of vessels.
