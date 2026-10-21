import logging
import os
import subprocess
import sys
from pathlib import Path

log = logging.getLogger(__name__)

REEXEC_MARKER = "MURMURTYPE_CUDA_LIBRARY_PATH_SET"


def nvidia_library_dirs() -> list[str]:
    """Library dirs of the optional nvidia-cublas/cudnn pip wheels, if installed."""
    try:
        import nvidia
    except ImportError:
        return []
    directories = []
    for package_root in nvidia.__path__:
        for library_dir in sorted(Path(package_root).glob("*/lib")):
            directories.append(str(library_dir))
    return directories


def ensure_library_path():
    """Re-exec the process with LD_LIBRARY_PATH covering the pip CUDA libraries.

    ctranslate2 dlopens cuBLAS/cuDNN at model load time, and the dynamic loader
    reads LD_LIBRARY_PATH only at process start, so setting it later has no effect.
    """
    if os.environ.get(REEXEC_MARKER):
        return
    directories = nvidia_library_dirs()
    if not directories:
        return
    current = os.environ.get("LD_LIBRARY_PATH", "")
    environment = dict(os.environ)
    environment["LD_LIBRARY_PATH"] = os.pathsep.join(directories + ([current] if current else []))
    environment[REEXEC_MARKER] = "1"
    os.execve(sys.executable, [sys.executable, "-m", "murmurtype", *sys.argv[1:]], environment)


def free_memory_mb() -> int:
    try:
        output = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.free", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=3,
            check=True,
        ).stdout
    except (OSError, subprocess.SubprocessError) as error:
        log.debug("nvidia-smi unavailable: %s", error)
        return 0
    values = [int(line) for line in output.split() if line.strip().isdigit()]
    return max(values, default=0)
