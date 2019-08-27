#!/usr/bin/env python3
"""
From https://github.com/BIDS-Apps/example/blob/aa0d4808974d79c9fbe54d56d3b47bb2cf4e0a0d/run.py
"""
import os
import os.path as op
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
    if op.splitext(dicom_dir) in ('.gz', '.tar'):
        open_type = 'r'
        if '.gz' in dicom_dir:
            open_type = 'r:gz'
        with tarfile.open(dicom_dir, open_type) as tar:
            dicoms = [mem for mem in tar.getmembers() if
                      mem.name.endswith('.dcm')]
            f_obj = tar.extractfile(dicoms[0])
            data = pydicom.read_file(f_obj)
    elif op.isdir(dicom_dir):
        f_obj = [x for x in pathlib.Path(dicom_dir).glob('**/*.dcm')][0]
        data = pydicom.read_file(f_obj)
    return data

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
    parser.add_argument('--heuristics', required=True, dest='heuristics',
                        help='Path to the heuristics file.')
    parser.add_argument('--sub', required=True, dest='sub',
                        help='The label of the subject to analyze.')
    parser.add_argument('--ses', required=False, dest='ses',
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
    heudiconv_input = args.dicom_dir.replace(args.sub, '{subject}')
    print(args.dicom_dir)
    if args.ses:
        heudiconv_input.replace(args.ses, '{session}')
    if not args.dicom_dir.startswith('/scratch'):
        raise ValueError('Dicom files must be in scratch.')

    if not op.isfile(args.heuristics):
        raise ValueError('Argument "heuristics" must be an existing file.')

    # Compile and run command
    cmd = ('./scripts/bidsconvert.sh {0} {1} {2} {3} {4}'.format(heudiconv_input,
                                                                 args.heuristics,
                                                                 args.output_dir,
                                                                 args.sub,
                                                                 args.ses))
    tmp_path = args.output_dir + '/tmp/' + args.sub + '/'
    if args.ses:
        tmp_path += args.ses
    os.makedirs(tmp_path, exist_ok=True)
    run(cmd, env={'TMPDIR': tmp_path})
    shutil.rmtree(tmp_path)
    # Grab some info to add to the participants file
    participants_file = op.join(args.output_dir, '/participants.tsv')
    if op.isfile(participants_file):
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
        df = pd.concat((df, df2), axis=1)
        df.to_csv(participants_file, sep='\t', index=False)


if __name__ == '__main__':
    main()
