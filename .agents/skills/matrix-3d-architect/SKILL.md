---
name: matrix-3d-architect
description: Design and verify high-precision 3D Matrix WebGL scenes (Three.js + UnrealBloomPass + contact-triggered green light propagation) for OmniNet.
---

# Matrix 3D Architect Skill

## Core Visual & Physical Rules
1. **Unified 3D Perspective (Never Flat 2D Stick Figures):**
   - Use a real `THREE.PerspectiveCamera` (FOV 52–60°) looking from **inside 1 transparent skyscraper** outward toward a **transparent perspective street**.
   - Keep strict real-world proportions: interior building bays (`width ~ 12m, height ~ 7m, depth ~ 34m`), street outside (`z = -28` to `-90`), and a **proportional human figure (~1.72m tall)** standing on the street outside.
2. **Invisible Until Touched (`energy = 0` at start):**
   - All building pillars, ceiling/floor beams, street curbs, streetlamps, and the woman's silhouette MUST start **100% invisible** (`opacity = 0`).
   - Only the variable-speed falling Matrix letters (Katakana + ASCII + hidden programming/math/physics/AI-to-AI messages) are visible initially.
3. **Contact-Triggered Green Light Propagation:**
   - Project 3D structural segments to 2D screen coordinates and test proximity against active falling Matrix glyphs.
   - On contact, inject emerald-green energy (`#00ff41` → `#bbf7d0`) proportional to glyph speed/intensity and propagate it along neighbor structural segments (`bldg`, `street`, `woman`), rendered with `UnrealBloomPass` glow.
4. **Visual Verification:**
   - Always inspect the live `/matrix` route using the `browser` subagent to confirm WebGL rendering, zero console errors, proportional scale, and smooth light propagation.
