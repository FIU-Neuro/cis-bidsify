"""
Utilities used by other modules in cis-bidsify.
"""
import os
import sys
import shutil
import pathlib
import tarfile
import subprocess

import pydicom


def run(command, env={}):
    """
    Helper function that runs a given command and allows for specification of
    environment information

    Parameters
    ----------
    command: command to be sent to system
    env: parameters to be added to environment
    """
    merged_env = os.environ
    merged_env.update(env)
    process = subprocess.Popen(command, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, shell=True,
                               env=merged_env)
    while True:
        line = process.stdout.readline()
        line = line.decode('utf-8')
        sys.stdout.write(line)
        sys.stdout.flush()
        if line == '' and process.poll() is not None:
            break

    if process.returncode != 0:
        raise Exception("Non zero return code: {0}\n"
                        "{1}\n\n{2}".format(process.returncode, command,
                                            process.stdout.read()))


def manage_dicom_dir(dicom_dir):
    """
    Helper function to grab data from dicom header depending on the type of dicom
    directory given

    Parameters
    ----------
    dicom_dir: Directory containing dicoms for processing
    """
    if dicom_dir.suffix in ('.gz', '.tar'):
        open_type = 'r'
        if dicom_dir.suffix == '.gz':
            open_type = 'r:gz'
        with tarfile.open(dicom_dir, open_type) as tar:
            dicoms = [mem for mem in tar.getmembers() if
                      mem.name.endswith('.dcm')]
            f_obj = tar.extractfile(dicoms[0])
            data = pydicom.read_file(f_obj)
    elif dicom_dir.is_dir():
        f_obj = [x for x in pathlib.Path(dicom_dir).glob('**/*.dcm')][0].as_posix()
        data = pydicom.read_file(f_obj)
    return data


def maintain_bids(output_dir, sub, ses):
    """
    Clean up working directories. If all work is complete, this will return the
    directory to BIDS standard (removing .heudiconv and tmp directories).

    Parameters
    ----------
    output_dir: Path object of bids directory
    sub: Subject ID
    ses: Session ID, if required
    """
    for root in ['.heudiconv', 'tmp']:
        if ses:
            if root == '.heudiconv':
                print('Removing Temp Directory: ', output_dir / root / sub / f'ses-{ses}')
                shutil.rmtree(output_dir / root / sub / f'ses-{ses}')
            else:
                print('Removing Temp Directory: ', output_dir / root / sub / ses)
                shutil.rmtree(output_dir / root / sub / ses)
        if (output_dir / root / sub).is_dir():
            print('Removing Temp Directory: ', output_dir / root / sub)
            shutil.rmtree(output_dir / root / sub)
        if (output_dir / root).is_dir():
            if not [x for x in (output_dir / root).iterdir()]:
                print('Removing Temp Directory: ', output_dir / root)
                shutil.rmtree((output_dir / root))
