import os
from contextlib import contextmanager
from pathlib import Path, PureWindowsPath
from tempfile import NamedTemporaryFile


@contextmanager
def atomic_text(path):
    """Replace the destination only after the complete new file closes."""
    path = Path(path)
    with NamedTemporaryFile(dir=path.parent, prefix=".anim-", suffix=".tmp",
                            encoding="utf-8", mode="w", delete=False) as stream:
        temp = Path(stream.name)
        try:
            yield stream
            stream.close()
            os.replace(temp, path)
        finally:
            stream.close()
            temp.unlink(missing_ok=True)


def plan_exports(animations, directory):
    seen, outputs = set(), []
    for item in animations:
        stack, name = item[:2] if isinstance(item, (tuple, list)) else (item, item)
        if (not name or name != name.rstrip(" .") or PureWindowsPath(name).is_reserved()
                or any(c in '<>:"/\\|?*' or ord(c) < 32 for c in name)):
            raise ValueError(f"Rename this animation before exporting: {name!r}")
        if name.casefold() in seen:
            raise ValueError(f"Two animations would overwrite {name}.anim. Rename one first.")
        seen.add(name.casefold())
        outputs.append((stack, os.path.join(directory, name + ".anim")))
    return outputs
