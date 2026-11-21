# Anim Creator

Anim Creator takes the animations in an FBX and exports them as Maya `.anim` files for Switch Toolbox. It's handy when one FBX has a whole set of clips: you can rename them, skip bones you don't need, and export the batch instead of going through them one by one.

## Exporting a clip

Open your FBX, pick a clip, and press **Ctrl+E** to choose where to save it. For the whole list, choose an export folder and click **Export All**. If two clips have the same export name, rename one with **Ctrl+R** first. **Ctrl+C** removes the selected clip from the list, not from the FBX.

In the bone picker, click a bone to select just that bone, or Shift-click to include its children. Ctrl-click its arrow to expand the whole branch. You can also skip just a bone's location keys and keep its rotation.

Leave **Auto FPS** on to read frame numbers at the FBX scene's frame rate. The default exporter uses linear keys. With an updated Toolbox, you can turn on **Cubic curves** in Settings to keep curved motion without writing a key on every frame. Older Toolbox builds flatten those tangents, so stick to linear export with those. See [the cubic export notes](CUBIC_WORKFLOW.md) for the differences and tested file sizes.

## Running it

For a packaged Windows build, run `animCreator.exe` and keep the `_internal` folder next to it. Your settings and bone presets live in `%LOCALAPPDATA%/AnimCreator/settings.json`.

To run from source, use Python 3.10 with CustomTkinter and Autodesk's matching FBX Python bindings:

```powershell
python .anim_Creator.py
```

To build the Windows app, install PyInstaller in the same Python environment and run `python -m PyInstaller animCreator.spec`. The executable will be in `dist/animCreator/`.

**Older Toolbox builds:** If imported clips have the wrong frame count or bones without scale or location tracks come in broken, check whether you're still using the old 22 KB `Lib/BrawlboxHelper.dll`. Use the updated helper for that build.
