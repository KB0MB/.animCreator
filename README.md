#🎬 Anim Creator 2.0

Anim Creator is a tool designed to export clean, optimized **.anim** files.

#🚀 Features

##🦴 Optimized Bone Export
Exports only keyed frames (no unnecessary frame spam)
Eliminates duplicate frame entries

**Result**: Smaller file sizes and cleaner animations.

##⚙️ Stable Export Behavior
Handles different source framerates consistently and prevents animation length issues caused by FPS mismatches.(if **Auto FPS** is enabled in settings)

**Result**: Reliable exports regardless of Blender scene settings.

##⌨️ Shortcuts

Ctrl + R — Rename selected animation
Ctrl + E — Export selected animation
Ctrl + C — Delete selected animation

##🦴 Bone Selection Controls
Shift + Click → Select a bone and all its children
Ctrl + Click (arrow) → Expand full child hierarchy


#⚠️ Important

##**Your version of Switch Toolbox includes a BrawlboxHelper.dll (22 KB):**

##Replace it with the updated version
##This resolves a frame count import issue **AND** allows for bones with no scale or location data to be imported.(Previously, if no location or scale was presentg duyring import, it would crumble the model)
