"""Rollback protection for the existing fixed-path source and feature contract."""
from contextlib import contextmanager
from pathlib import Path
import os
import shutil

@contextmanager
def publication_transaction(stage: Path, targets):
    """Back up only files being replaced; preserve prior snapshots without copying them."""
    targets=list(dict.fromkeys(Path(p) for p in targets))
    backups=stage/'publication_backups';backups.mkdir()
    originals={}
    new_dirs=set()
    for i,path in enumerate(targets):
        if path.exists():
            backup=backups/str(i);shutil.copy2(path,backup);originals[path]=backup
        else:
            originals[path]=None
            parent=path.parent
            while not parent.exists():new_dirs.add(parent);parent=parent.parent
    try:
        yield
    except BaseException:
        for path,backup in originals.items():
            if backup is None:
                if path.is_file():path.unlink()
            else:
                os.replace(backup,path)
        for folder in sorted(new_dirs,key=lambda p:len(p.parts),reverse=True):
            if folder.is_dir() and not any(folder.iterdir()):folder.rmdir()
        raise
