# Compact animation export for Toolbox

## Use

1. Run the updated Anim Creator Python source.
2. Open Settings and enable **Cubic curves (updated Toolbox)**, then Save.
3. Leave **Clean: On**. Start with a rotation error tolerance of **0.003 degrees**.
4. Load the FBX and export .anim as usual. Existing bone exclusions, location exclusions, scale toggle, and reverse options still apply.
5. Replace/import the animation in the updated Toolbox, save the BFRES, and test a few clips in game before replacing the entire animation bank.

The new mode is opt-in. Turning it off uses the existing linear exporter.
Both tools must be updated. Older Toolbox builds silently flatten these curves through CHR0 and will not retain the new export's tangents.

The updated Python files are .anim_Creator.py, animExport.py, curveFit.py, and graphExport.py. An existing packaged executable must be rebuilt; updating the source files alone does not change that executable.

## What changes

The exporter reads FBX curve tangents and fractional times, validates the cubic representation against the FBX SDK between keys, and fits new cubic spans with an error bound over the entire input graph. Intentional Euler turns are preserved; angles are not automatically wrapped.

The file remains text .anim with unweighted fixed tangents. A version comment selects Toolbox's direct graph importer, bypassing the old CHR0 conversion that discarded tangents.

Toolbox preserves independent incoming/outgoing tangents and fractional timing, stores constant channels in bone base data, and chooses exact compact frame storage. It tries 8-bit and 16-bit coefficient storage only when the entire decoded polynomial stays within a separate error budget; otherwise it uses floats. Existing matched bones retain the replaced animation's segment-scale compensation setting.

## Accuracy and limitations

- Default fit limits: rotation 0.003 degrees per Euler channel; translation 0.0001 source units; scale 0.00001.
- Additional coefficient packing budget: rotation 0.001 degrees; translation 0.00001; scale 0.000001.
- These are channel bounds, not a guaranteed global end-effector distance after hierarchical skinning.
- Weighted/non-Hermite FBX curves and multiple animation layers that cannot be represented faithfully are rejected with an error. Bake them in Blender, or use the legacy mode. They are not silently approximated by dropping tangent information.
- This does not remove animated bones just because a particular model lacks them.
- The current native animation duration is an integer frame count. Fractional key times are preserved; a fractional end frame is rounded up.
- Already exported legacy .anim files are not automatically refitted. Re-export the FBX using the new mode.
- This is tested serialization, not an in-game compatibility guarantee.

## Measured custom-animation results

36 clips selected across the supplied A, B, N, R, V, and W FBX batches, compared with matching vanilla TOTK clips. The same clip set was saved into otherwise equivalent test banks.

| Test bank | BFRES bytes | Zstd level 19 bytes |
| --- | ---: | ---: |
| Vanilla | 709,640 | 349,922 |
| Existing workflow | 2,937,000 | 676,485 |
| New cubic workflow | 1,090,672 | 423,913 |

That is 1.54x vanilla uncompressed and 1.21x compressed, versus 4.14x and 1.93x with the existing workflow. Compression was applied identically to all three test banks, without a dictionary; this is not a comparison against Nintendo's original compressed file bytes.

12,947,616 FBX SDK sample comparisons passed after standalone BFSKA and full BFRES save/reload. Maximum observed rotation-component error was 0.003495 degrees; maximum translation-component error was 0.00009976. Synthetic tests also cover cubic slopes, fractional frames, base-only channels, full turns, reversed slopes, overshoot, invalid inputs, and Switch/Wii U serialization.

Some individual clips remain larger than 1.5x. The whole player animation bank and game behavior have not been validated.
