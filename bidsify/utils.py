"""Utilities used by other modules in cis-bidsify."""
import os
import sys
import shutil
import tarfile
import subprocess
from pathlib import Path

import pydicom


def run(command, env=None):
    """Run a command with specific environment information.

    Parameters
    ----------
    command: command to be sent to system
    env: parameters to be added to environment
    """
    merged_env = os.environ
    if env:
        merged_env.update(env)

    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        shell=True,
        env=merged_env,
    )
    while True:
        line = process.stdout.readline()
        line = line.decode("utf-8")
        sys.stdout.write(line)
        sys.stdout.flush()
        if line == "" and process.poll() is not None:
            break

    if process.returncode != 0:
        raise Exception(
            f"Non zero return code: {process.returncode}\n"
            f"{command}\n\n{process.stdout.read()}"
        )
    return process.returncode


def load_dicomdir_metadata(dicomdir):
    """Grab data from dicom directory of a given type (tar, tar.gz, directory).

    Parameters
    ----------
    dicomdir: Directory containing dicoms for processing

    Returns
    -------
    data : dicom header
        DICOM information from first dicom in directory.
    """
    if dicomdir.is_file() and dicomdir.suffix in (".gz", ".tar"):
        open_type = "r"
        if dicomdir.suffix == ".gz":
            open_type = "r:gz"
        with tarfile.open(dicomdir, open_type) as tar:
            dicoms = [mem for mem in tar.getmembers() if mem.name.endswith(".dcm")]
            f_obj = tar.extractfile(dicoms[0])
            data = pydicom.read_file(f_obj)
    elif dicomdir.is_dir():
        dcm_files = list(Path(dicomdir).glob("**/*.dcm"))
        f_obj = dcm_files[0].as_posix()
        data = pydicom.read_file(f_obj)
    else:
        raise ValueError(
            "dicomdir is neither file nor directory, "
            "dicomdir must be a tarball (.tar), "
            "gzipped tarball (.tar.gz) or a folder structure containing dicoms (.dcm) files"
        )
    return data


def clean_tempdirs(output_dir, sub, ses):
    """Clean up working directories (.heudiconv and .tmp).

    If all work is complete, this will return the
    directory to BIDS standard (removing .heudiconv and .tmp directories).

    Parameters
    ----------
    output_dir: Path object of bids directory
    sub: Subject ID
    ses: Session ID, if required
    """
    for root in [".heudiconv"]:
        if ses:
            if root == ".heudiconv":
                print(
                    "Removing Temp Directory: ", output_dir / root / sub / f"ses-{ses}"
                )
                shutil.rmtree(output_dir / root / sub / f"ses-{ses}")
            else:
                print("Removing Temp Directory: ", output_dir / root / sub / ses)
                shutil.rmtree(output_dir / root / sub / ses)
        if (output_dir / root / sub).is_dir():
            print("Removing Temp Directory: ", output_dir / root / sub)
            shutil.rmtree(output_dir / root / sub)
        if (output_dir / root).is_dir():
            if not (output_dir / root).iterdir():
                print("Removing Temp Directory: ", output_dir / root)
                shutil.rmtree((output_dir / root))
