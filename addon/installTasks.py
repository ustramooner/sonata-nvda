# coding: utf-8

# Copyright (c) 2023 Musharraf Omer
# This file is covered by the GNU General Public License.


import contextlib
import os
import shutil
import sys
import tempfile

from logHandler import log


_DIR = os.path.abspath(os.path.dirname(__file__))
_PIPER_SYNTH_DIR = os.path.join(_DIR, "synthDrivers", "sonata_neural_voices")
LIB_DIR = os.path.join(_PIPER_SYNTH_DIR, "lib")
BIN_DIR = os.path.join(_PIPER_SYNTH_DIR, "bin")
del _DIR


def _same_model(src, dst):
    """True when the voice in dst has the same model file as the bundled one (size first, then SHA-256)."""
    import hashlib

    for name in os.listdir(src):
        if not name.endswith(".onnx"):
            continue
        a, b = os.path.join(src, name), os.path.join(dst, name)
        if not os.path.isfile(b) or os.path.getsize(a) != os.path.getsize(b):
            return False
        digests = []
        for path in (a, b):
            h = hashlib.sha256()
            with open(path, "rb") as f:
                for block in iter(lambda: f.read(1 << 20), b""):
                    h.update(block)
            digests.append(h.digest())
        if digests[0] != digests[1]:
            return False
    return True


def onInstall():
    """Copy voices bundled with the addon into the Sonata voices directory.

    A bundled voice replaces an installed voice of the same name when the model differs, so a new add-on release brings its new voice
    (uninstalling the add-on does not remove the voices folder, and the first versions never replaced an existing voice)."""
    import globalVars

    bundled = os.path.join(_PIPER_SYNTH_DIR, "bundled_voices")
    if not os.path.isdir(bundled):
        return
    voices_dir = os.path.join(
        globalVars.appArgs.configPath, "sonata", "voices", "piper"
    )
    os.makedirs(voices_dir, exist_ok=True)
    for name in os.listdir(bundled):
        src = os.path.join(bundled, name)
        dst = os.path.join(voices_dir, name)
        if not os.path.isdir(src):
            continue
        if os.path.exists(dst):
            if _same_model(src, dst):
                continue
            shutil.rmtree(dst)
            log.info(f"Replacing installed Sonata voice with the bundled one: {name}")
        shutil.copytree(src, dst)
        log.info(f"Installed bundled Sonata voice: {name}")


def onUninstall():
    with _temporary_import_psutil() as psutil:
        force_kill_sonata_grpc_server(psutil)


def force_kill_sonata_grpc_server(psutil):
    log.debug("Trying to force kill GRPC server process")
    grpc_server_processes = list(filter(
        lambda p: "sonata-grpc" in p.name().lower(),
        psutil.process_iter(attrs=["name", "exe"])
    ))
    grpc_server_exe = os.path.join(BIN_DIR, "sonata-grpc.exe")
    for proc in grpc_server_processes:
        if os.path.samefile(proc.exe(), grpc_server_exe):
            proc.kill()
            log.debug(f"Killed process with pid {proc.pid}")
    psutil.wait_procs(
        grpc_server_processes,
        timeout=5,
    )


@contextlib.contextmanager
def _temporary_import_psutil():
    temp_import_dir = tempfile.TemporaryDirectory()
    src = os.path.join(LIB_DIR, "psutil")
    # py3_lib_src = os.path.join(LIB_DIR, "python3.dll")
    dst = os.path.join(temp_import_dir.name, "psutil")
    shutil.copytree(src, dst)
    # shutil.copy2(py3_lib_src, dst)
    sys.path.insert(0, temp_import_dir.name)
    import psutil
    yield psutil
    sys.path.remove(temp_import_dir.name)
    with contextlib.suppress(Exception):
        temp_import_dir.cleanup()
