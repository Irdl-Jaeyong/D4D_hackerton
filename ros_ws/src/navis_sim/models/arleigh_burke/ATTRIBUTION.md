# Arleigh Burke (DDG-51) high-detail ship

Creator: LT Patrick Sullivan. Source: NPS SAVAGE X3D archive.
https://savage.nps.edu/Savage/ShipsMilitary/DDGArleighBurkeUnitedStates/ArleighBurkeHighDetail.x3d
Source created 23 March 2005; modified 20 October 2019; retrieved 10 October 2026.
License: Web3D Consortium Open-Source License (BSD-style), copied in LICENSE.
https://savage.nps.edu/Savage/license.html

The original X3D is retained in source/. scripts/convert_ddg_model.py preserves
static surface transforms and diffuse materials, converts Y-up to Z-up,
centers horizontal bounds, and emits COLLADA/OBJ derivatives plus 59 separate OBJ surfaces with explicit
face normals and a diffuse-material manifest. The Gazebo scene uses those
surfaces with explicit SDF materials to avoid imported material overrides. Animation, camera
helpers and non-surface lines are omitted. No geometry is invented or enlarged.
Native source dimensions: 153.781 × 20.435 × 49.288 m including the underwater hull.
This is an author's visualization of a real ship class, not a scanned ship or
an exact engineering digital twin. The source date predates current refits.

Additional surface textures from the NPS SAVAGE Flight IIA archive (same Web3D license):
https://savage.nps.edu/Savage/ShipsMilitary/DDG51FlightIIaUnitedStates/nonskid.jpg
https://savage.nps.edu/Savage/ShipsMilitary/DDG51FlightIIaUnitedStates/nsflightdeck.jpg
https://savage.nps.edu/Savage/ShipsMilitary/DDGArleighBurkeUnitedStates/forwardvertrep.jpg
Deck surfaces copy the original part_47 top triangles at their original
coordinates. Those triangles are removed from a derived side mesh to avoid
z-fighting without moving the deck geometry. UV mapping and aft safety rails are NAVIS visualization additions
and have not been validated against engineering drawings.
