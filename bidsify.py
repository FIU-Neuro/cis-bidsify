#!/usr/bin/env python
"""
From https://github.com/BIDS-Apps/example/blob/aa0d4808974d79c9fbe54d56d3b47bb2cf4e0a0d/run.py
"""
import os
import sys
import tarfile
import pathlib
import argparse
import subprocess
import shutil
import numpy as np
import pandas as pd
from dateutil.parser import parse
import pydicom

# Local imports
from complete_jsons import complete_jsons
from clean_metadata import clean_metadata


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
    Function that cleans up working directories when called,
    if all work is complete, will return directory to bids standard
    (removing .heudiconv and tmp directories)

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
            #print(process.returncode)
            #process.returncode = 1
            break


    if process.returncode != 0:
        raise Exception("Non zero return code: {0}\n"
                        "{1}\n\n{2}".format(process.returncode, command,
                                            process.stdout.read()))


def get_parser():
    """
    Sets up argument parser for scripts

    Parameters
    ----------
    """
    parser = argparse.ArgumentParser(description='BIDS conversion and '
                                                 'anonymization for the FIU '
                                                 'scanner.')
    parser.add_argument('-d', '--dicomdir', required=True, dest='dicom_dir',
                        help='Directory containing raw data.')
    parser.add_argument('-f', '--heuristics', required=True, dest='heuristics',
                        help='Path to the heuristics file.')
    parser.add_argument('-s', '--sub', required=True, dest='sub',
                        help='The label of the subject to analyze.')
    parser.add_argument('-ss', '--ses', required=False, dest='ses',
                        help='Session number', default=None)
    parser.add_argument('-o', '--output_dir', dest='output_dir', required=True)
    return parser


def main(argv=None):
    """
    Function that executes when bidsify.py is called

    Parameters inherited from argparser
    ----------
    dicom_dir: Directory cointaining dicom data to be processed
    heuristics: Path to heuristics file
    sub: Subject ID
    ses: Session ID, if required
    output_dir: Directory to output bidsified data
    """
    args = get_parser().parse_args(argv)

    args.dicom_dir = pathlib.Path(args.dicom_dir)
    args.heuristics = pathlib.Path(args.heuristics)
    args.output_dir = pathlib.Path(args.output_dir)
    if args.dicom_dir.is_file():
        dir_type = '-d'
        heudiconv_input = args.dicom_dir.as_posix().replace(args.sub, '{subject}')
        if args.ses:
            heudiconv_input = heudiconv_input.replace(args.ses, '{session}')
    else:
        dir_type = '--files'
        heudiconv_input = args.dicom_dir.as_posix()

    if args.ses:
        sub_dir = 'sub-{}/ses-{}'.format(args.sub, args.ses)
    else:
        sub_dir = 'sub-{}'.format(args.sub)

    if not args.heuristics.is_file():
        raise ValueError('Argument "heuristics" must be an existing file.')

    args.output_dir.mkdir(parents=True, exist_ok=True)
    tmp_path = args.output_dir / 'tmp' / args.sub
    if not (args.output_dir / '.bidsignore').is_file():
        with (args.output_dir / '.bidsignore').open('a') as wk_file:
            wk_file.write('.heudiconv/\n')
            wk_file.write('tmp/\n')
            wk_file.write('validator.txt\n')
    if args.ses:
        tmp_path = tmp_path / args.ses
    tmp_path.mkdir(parents=True, exist_ok=True)

    # Run heudiconv
    cmd = ('heudiconv {dir_type} {dicom_dir} -s {sub} -f '
           '{heuristics} -c dcm2niix -o {out_dir} --bids --overwrite '
           '--minmeta').format(dir_type=dir_type, dicom_dir=heudiconv_input,
                               heuristics=args.heuristics, our_dir=args.output_dir)
    run(cmd, env={'TMPDIR': tmp_path.name})

    # Run defacer
    anat_files = sorted(glob('{out_dir}/{sub_dir}/anat/*.nii.gz'))
    for anat in anat_files:
        cmd = ('mri_deface {anat} /src/deface/talairach_mixed_with_skull.gca '
               '/src/deface/face.gca {anat}').format(anat=anat)
        run(cmd, env={'TMPDIR': tmp_path.name})

    # Run json completer
    complete_jsons(args.output_dir, args.sub, args.ses, overwrite=True)

    # Run metadata cleaner
    clean_metadata(args.output_dir, args.sub, args.ses)

    # Run BIDS validator
    cmd = ('bids-validator {out_dir} --ignoreWarnings > '
           '{out_file}').format(
                out_dir=args.output_dir,
                out_file=op.join(args.output_dir, 'validator.txt'))
    run(cmd, env={'TMPDIR': tmp_path.name})

    # Clean up output directory, returning it to bids standard
    maintain_bids(args.output_dir, args.sub, args.ses)

    # Grab some info to add to the participants file
    participants_file = args.output_dir / 'participants.tsv'
    if participants_file.is_file():
        df = pd.read_table(participants_file)
        data = manage_dicom_dir(args.dicom_dir)
        if data.get('PatientAge'):
            age = data.PatientAge.replace('Y', '')
            try:
                age = int(age)
            except ValueError:
                pass
        elif data.get('PatientBirthDate'):
            age = parse(data.StudyDate) - parse(data.PatientBirthDate)
            age = np.round(age.days / 365.25, 2)
        else:
            age = np.nan

        new_participant = pd.DataFrame(columns=['age', 'sex', 'weight'],
                                       data=[[age, data.PatientSex,
                                              data.PatientWeight]])
        participant_df = pd.concat([participant_df, new_participant], axis=1)
        participant_df.to_csv(participants_file, sep='\t',
                              line_terminator='\n', index=False)


if __name__ == '__main__':
    main()
