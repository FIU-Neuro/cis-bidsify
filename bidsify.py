#!/usr/bin/env python
"""
From https://github.com/BIDS-Apps/example/blob/aa0d4808974d79c9fbe54d56d3b47bb2cf4e0a0d/run.py
"""
import pathlib
import argparse
import os.path as op
from glob import glob
from dateutil.parser import parse

import numpy as np
import pandas as pd

# Local imports
from complete_jsons import complete_jsons
from clean_metadata import clean_metadata
from utils import run, manage_dicom_dir, maintain_bids


def _get_parser():
    """
    Set up argument parser for scripts
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


def bidsify_workflow(dicom_dir, heuristics, sub, ses=None, output_dir='.'):
    """
    Entrypoint function

    Parameters inherited from argparser
    ----------
    dicom_dir: Directory cointaining dicom data to be processed
    heuristics: Path to heuristics file
    sub: Subject ID
    ses: Session ID, if required
    output_dir: Directory to output bidsified data
    """
    dicom_dir = pathlib.Path(dicom_dir)
    heuristics = pathlib.Path(heuristics)
    output_dir = pathlib.Path(output_dir)
    if dicom_dir.is_file():
        dir_type = '-d'
        heudiconv_input = dicom_dir.as_posix().replace(sub, '{subject}')
        if ses:
            heudiconv_input = heudiconv_input.replace(ses, '{session}')
    else:
        dir_type = '--files'
        heudiconv_input = dicom_dir.as_posix()

    if ses:
        sub_dir = 'sub-{}/ses-{}'.format(sub, ses)
    else:
        sub_dir = 'sub-{}'.format(sub)

    if not heuristics.is_file():
        raise ValueError('Argument "heuristics" must be an existing file.')

    output_dir.mkdir(parents=True, exist_ok=True)
    tmp_path = output_dir / 'tmp' / sub
    if not (output_dir / '.bidsignore').is_file():
        with (output_dir / '.bidsignore').open('a') as wk_file:
            wk_file.write('.heudiconv/\n')
            wk_file.write('tmp/\n')
            wk_file.write('validator.txt\n')
    if ses:
        tmp_path = tmp_path / ses
    tmp_path.mkdir(parents=True, exist_ok=True)

    # Run heudiconv
    cmd = ('heudiconv {dir_type} {dicom_dir} -s {sub} -f '
           '{heuristics} -c dcm2niix -o {out_dir} --bids --overwrite '
           '--minmeta').format(dir_type=dir_type, dicom_dir=heudiconv_input,
                               heuristics=heuristics, our_dir=output_dir)
    run(cmd, env={'TMPDIR': tmp_path.name})

    # Run defacer
    anat_files = sorted(glob('{out_dir}/{sub_dir}/anat/*.nii.gz'))
    for anat in anat_files:
        cmd = ('mri_deface {anat} /src/deface/talairach_mixed_with_skull.gca '
               '/src/deface/face.gca {anat}').format(anat=anat)
        run(cmd, env={'TMPDIR': tmp_path.name})

    # Run json completer
    complete_jsons(output_dir, sub, ses, overwrite=True)

    # Run metadata cleaner
    clean_metadata(output_dir, sub, ses)

    # Run BIDS validator
    cmd = ('bids-validator {out_dir} --ignoreWarnings > '
           '{out_file}').format(
                out_dir=output_dir,
                out_file=op.join(output_dir, 'validator.txt'))
    run(cmd, env={'TMPDIR': tmp_path.name})

    # Clean up output directory, returning it to bids standard
    maintain_bids(output_dir, sub, ses)

    # Grab some info to add to the participants file
    participants_file = output_dir / 'participants.tsv'
    if participants_file.is_file():
        participant_df = pd.read_table(participants_file)
        data = manage_dicom_dir(dicom_dir)
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


def _main(argv=None):
    options = _get_parser().parse_args(argv)
    kwargs = vars(options)
    bidsify_workflow(**kwargs)


if __name__ == '__main__':
    _main()
