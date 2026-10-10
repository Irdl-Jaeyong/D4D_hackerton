# VRX ocean visual port for Gazebo Fortress

Source: Open Robotics VRX, Apache-2.0.
https://github.com/osrf/vrx/tree/dc30ed8d17aa1083fd872edad9c77c69896d2b07/vrx_gz/src
Revision: dc30ed8d17aa1083fd872edad9c77c69896d2b07 (humble branch), retrieved 10 October 2026.

WaveVisual.cc/.hh and Wavefield.cc/.hh retain their original copyright notices
and license. This project adapts gz-sim7 names/includes/macros to ignition-gazebo6,
changes rendering entity user data to Fortress's int type, accepts an explicit
model_path and guards missing shader parameters. Algorithm and shader parameter
semantics are inherited from VRX. CMake builds only this visual plugin.

The shaders in navis_ocean/materials/programs are VRX's unmodified Gerstner
wave shaders, originally copyright 2016 UUV Simulator Authors (Apache-2.0).
The skybox_lowres.dds reflection cubemap is from the same VRX revision.

This is visual wave displacement/reflection; no vessel buoyancy or hydrodynamic
controller is executed. Foam meshes are original deterministic NAVIS visual
representations, aligned with vessel headings, not fluid simulations.
