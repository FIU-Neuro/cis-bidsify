#!/usr/bin/env python
"""
From https://github.com/BIDS-Apps/example/blob/aa0d4808974d79c9fbe54d56d3b47bb2cf4e0a0d/run.py
"""
import argparse
from pathlib import Path
from dateutil.parser import parse

import numpy as np
import pandas as pd
from bidsutils import complete_jsons, clean_metadata

# Local imports
from bidsify.utils import run, manage_dicom_dir, maintain_bids

def _get_parser():
    """
    Set up argument parser for scripts
    """
    parser = argparse.ArgumentParser(description='BIDS conversion and '
                                                 'anonymization.')
    parser.add_argument('-d', '--dicomdir', type=Path,
                        required=True, dest='dicom_dir',
                        help='Directory or tar file containing raw data.')
    parser.add_argument('-f', '--heuristics', type=Path,
                        required=True, dest='heuristics',
                        metavar='FILE',
                        help='Path to the heuristics file.')
    parser.add_argument('-s', '--sub',
                        required=True, dest='subject',
                        help='The label of the subject to analyze.')
    parser.add_argument('-ss', '--ses',
                        required=False, dest='session',
                        help='Session number',
                        default=None)
    parser.add_argument('-o', '--output_dir', type=Path,
                        dest='output_dir', required=True,
                        metavar='PATH',
                        help='Output directory')
    return parser


def bidsify_workflow(dicom_dir, heuristics, subject, session=None, output_dir='.'):
    """
    Run the BIDSification workflow.

    Parameters
    ----------
    dicom_dir : str
        Directory or tar file containing dicom data to be processed
    heuristics : str
        Path to heuristic file
    subject : str
        Subject ID
    session : str or None, optional
        Session ID. Default is None.
    output_dir : str, optional
        Directory to output bidsified data. Default is '.' (current working
        directory).
    """
    if not heuristics.is_file():
        raise ValueError('Argument "heuristics" must be an existing file.')

    if dicom_dir.is_file() and str(dicom_dir).endswith('.gz') or str(dicom_dir.endswith('.tar')):
        dir_type = '-d'
        heudiconv_input = dicom_dir.as_posix().replace(subject, '{subject}')
        if session:
            heudiconv_input = heudiconv_input.replace(session, '{session}')
    elif dicom_dir.is_dir():
        dir_type = '--files'
        heudiconv_input = dicom_dir.as_posix()
    else:
        raise ValueError('dicom-dir must be a tarball or directory containing dicoms'
                         'value of ')

    sub_dir = output_dir / f'sub-{subject}'
    if session:
        sub_dir = output_dir / f'sub-{subject}/ses-{session}'

    output_dir.mkdir(parents=True, exist_ok=True)
    tmp_path = output_dir / 'tmp' / subject
    tmp_path.mkdir(parents=True, exist_ok=True)
    if session:
        tmp_path = output_dir / 'tmp' / subject / session
    if not (output_dir / '.bidsignore').is_file():
        with (output_dir / '.bidsignore').open('w') as wk_file:
            wk_file.write('.heudiconv/\ntmp/\nvalidator.txt\n')

    # Run heudiconv
    cmd = (f'heudiconv {dir_type} {dicom_dir} -s {subject} -f '
           f'{heuristics} -c dcm2niix -o {output_dir} --bids --overwrite '
           '--minmeta')
    #heudiconv_retval = run(cmd, env={'TMPDIR': tmp_path.name})

    # Run defacer
    anat_files = sub_dir.glob('/anat/*.nii.gz')
    for anat in anat_files:
        cmd = (f'mri_deface {anat} /src/deface/talairach_mixed_with_skull.gca '
               '/src/deface/face.gca {anat}')
        run(cmd, env={'TMPDIR': tmp_path.name})

    # Run json completer
    complete_jsons(output_dir, subject, session, overwrite=True)

    # Run metadata cleaner
    clean_metadata(output_dir, subject, session)

    # Run BIDS validator
    cmd = ('bids-validator {out_dir} --ignoreWarnings > '
           '{out_file}').format(
               out_dir=output_dir,
               out_file=output_dir / 'validator.txt')
    run(cmd, env={'TMPDIR': tmp_path.name})

    # Clean up output directory, returning it to bids standard
    maintain_bids(output_dir, subject, session)

    # Grab some info from the dicoms to add to the participants file
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


def main(argv=None):
    '''
    Bidsify Runtime
    '''
    options = _get_parser().parse_args(argv)
    kwargs = vars(options)
    bidsify_workflow(**kwargs)
