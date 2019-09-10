#!/usr/bin/env python
"""
From https://github.com/BIDS-Apps/example/blob/aa0d4808974d79c9fbe54d56d3b47bb2cf4e0a0d/run.py
"""
import os
import tarfile
import pathlib
import argparse
import subprocess
import shutil
import pydicom
import numpy as np
import pandas as pd
from dateutil.parser import parse

def manage_dicom_dir(dicom_dir):
    '''
    Helper function to grab data from dicom header depending on the type of dicom
    directory given

    Parameters
    ----------
    dicom_dir: Directory containing dicoms for processing
    '''
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
        f_obj = [x for x in pathlib.Path(dicom_dir).glob('**/*.dcm')][0]
        data = pydicom.read_file(f_obj)
    return data

def maintain_bids(output_dir, sub, ses):
    '''
    Function that cleans up working directories when called,
    if all work is complete, will return directory to bids standard
    (removing .heudiconv and tmp directories)

    Parameters
    ----------
    output_dir: Path object of bids directory
    sub: Subject ID
    ses: Session ID, if required
    '''
    for root in ['.heudiconv', 'tmp']:
        if ses:
            if root == '.heudiconv':
                shutil.rmtree(output_dir / root / sub / f'ses-{ses}')
            else:
                shutil.rmtree(output_dir / root / sub / ses)
        if (output_dir / root / sub).is_dir():
            if not [x for x in (output_dir / root / sub).iterdir()]:
                shutil.rmtree((output_dir / root / sub))
        if (output_dir / root).is_dir():
            if not [x for x in (output_dir / root).iterdir()]:
                shutil.rmtree((output_dir / root))

def run(command, env={}):
    '''
    Helper function that runs a given command and allows for specification of
    environment information

    Parameters
    ----------
    command: command to be sent to system
    env: parameters to be added to environment
    '''
    merged_env = os.environ
    merged_env.update(env)
    process = subprocess.Popen(command, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, shell=True,
                               env=merged_env)
    while True:
        line = process.stdout.readline()
        line = str(line, 'utf-8')[:-1]
        print(line)
        if line == '' and process.poll() is not None:
            break

    if process.returncode != 0:
        raise Exception("Non zero return code: {0}\n"
                        "{1}\n\n{2}".format(process.returncode, command,
                                            process.stdout.read()))


def get_parser():
    '''
    Sets up argument parser for scripts

    Parameters
    ----------
    '''
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
    '''
    Function that executes when bidsify.py is called

    Parameters inherited from argparser
    ----------
    dicom_dir: Directory cointaining dicom data to be processed
    heuristics: Path to heuristics file
    sub: Subject ID
    ses: Session ID, if required
    output_dir: Directory to output bidsified data
    '''
    args = get_parser().parse_args(argv)

    args.dicom_dir = pathlib.Path(args.dicom_dir)
    args.heuristics = pathlib.Path(args.heuristics)
    args.output_dir = pathlib.Path(args.output_dir)
    if args.dicom_dir.is_file():
        dir_type = '-d'
        heudiconv_input = args.dicom_dir.absolute().replace(args.sub, '{subject}')
        if args.ses:
            heudiconv_input = heudiconv_input.replace(args.ses, '{session}')
    else:
        dir_type = '--files'
        heudiconv_input = args.dicom_dir.absolute()
    #if not args.dicom_dir.startswith('/scratch'):
    #    raise ValueError('Dicom files must be in scratch.')
    if not args.heuristics.is_file():
        raise ValueError('Argument "heuristics" must be an existing file.')

    # Compile and run command
    cmd = ('/scripts/bidsconvert.sh {0} {1} {2} {3} {4} {5}'.format(dir_type,
                                                                    heudiconv_input,
                                                                    args.heuristics,
                                                                    args.output_dir,
                                                                    args.sub,
                                                                    args.ses))
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
    run(cmd, env={'TMPDIR': tmp_path.name})
    #Cleans up output directory, returning it to bids standard
    maintain_bids(args.output_dir, args.sub, args.ses)

    # Grab some info to add to the participants file
    participants_file = args.output_dir / 'participants.tsv'
    if participants_file.is_file():
        df = pd.read_csv(participants_file, sep='\t')
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
        df2 = pd.DataFrame(columns=['age', 'sex', 'weight'],
                           data=[[age, data.PatientSex, data.PatientWeight]])
        df = pd.concat([df, df2], axis=1)
        df.to_csv(participants_file, sep='\t', index=False)


if __name__ == '__main__':
    main()
