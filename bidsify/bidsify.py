#!/usr/bin/env python
"""Run process and anonymize dicoms."""
import argparse
import os.path as op
from pathlib import Path
from dateutil.parser import parse

import numpy as np
import pandas as pd
from bidsutils.metadata import complete_jsons, clean_metadata
# Local imports
from bidsify.utils import run, manage_dicom_dir, maintain_bids


def _get_parser():
    """Set up argument parser for scripts."""
    parser = argparse.ArgumentParser(description='BIDS conversion and '
                                                 'anonymization.')
    parser.add_argument('-d', '--dicomdir',
                        type=Path,
                        required=True,
                        dest='dicomdir',
                        help='Directory or tar file containing raw data.')
    parser.add_argument('-f', '--heuristic',
                        type=str,
                        dest='heuristic',
                        metavar='HEUR',
                        help='Path to a heuristic file or name of a builtin '
                             'heudiconv heuristic.')
    parser.add_argument('-s', '--sub',
                        required=True,
                        dest='subject',
                        help='The label of the subject to analyze.')
    parser.add_argument('-ss', '--ses',
                        required=False,
                        dest='session',
                        help='Session identifier',
                        default=None)
    parser.add_argument('-o', '--output_dir',
                        type=Path,
                        dest='output_dir',
                        required=True,
                        metavar='PATH',
                        help='Output directory')
    return parser


def bidsify_workflow(dicomdir, heuristic, subject, session=None, output_dir='.'):
    """Run the BIDSification workflow.

    This workflow (1) runs heudiconv to convert dicoms to nifti BIDS format,
    (2) defaces anatomical scans, (3) completes relevant metadata in the
    dataset, (4) removes extraneous metadata, and (5) cleans up working
    directories generated by heudiconv and the workflow.

    Parameters
    ----------
    dicomdir : str
        Directory or tar file containing dicom data to be processed
    heuristic : str
        Path to heuristic file or name of builtin heudiconv heuristic
    subject : str
        Subject ID
    session : str or None, optional
        Session ID. Default is None.
    output_dir : str, optional
        Directory to output bidsified data. Default is '.' (current working
        directory).
    """
    # Heuristic may be file or heudiconv builtin
    # Use existence of file extension to determine if builtin or file
    if op.splitext(heuristic)[1] and (not heuristic.is_file()):
        raise ValueError('Heuristic file must be an existing file.')

    if dicomdir.is_file():
        dcm_name = str(dicomdir.as_posix())
        if not dcm_name.endswith('.gz') or dcm_name.endswith('.tar'):
            raise ValueError('Heudiconv currently only accepts '
                             '.tar and .tar.gz inputs')
        dir_type = '-d'
        heudiconv_input = dcm_name.replace(subject, '{subject}')
        if session:
            heudiconv_input = heudiconv_input.replace(session, '{session}')
    elif dicomdir.is_dir():
        dir_type = '--files'
        heudiconv_input = str(dicomdir.as_posix())
    else:
        raise ValueError('dicomdir must be a tarball '
                         'or directory containing dicoms')

    sub_dir = output_dir / f'sub-{subject}'
    if session:
        sub_dir = output_dir / f'sub-{subject}/ses-{session}'

    output_dir.mkdir(parents=True, exist_ok=True)
    tmp_path = output_dir / '.tmp' / subject
    tmp_path.mkdir(parents=True, exist_ok=True)
    if session:
        tmp_path = output_dir / '.tmp' / subject / session
    if not (output_dir / '.bidsignore').is_file():
        with (output_dir / '.bidsignore').open('w') as wk_file:
            wk_file.write('.heudiconv/\n.tmp/\nvalidator.txt\n')

    # Run heudiconv
    cmd = (f'heudiconv {dir_type} {dicomdir} '
           f'-s {subject} -f {heuristic} -c dcm2niix '
           f'-o {output_dir} --bids --overwrite --minmeta')
    run(cmd, env={'TMPDIR': tmp_path.name})

    # Run defacer
    anat_files = sub_dir.glob('/anat/*.nii.gz')
    for anat in anat_files:
        cmd = (f'mri_deface {anat} /src/deface/talairach_mixed_with_skull.gca '
               f'/src/deface/face.gca {anat}')
        run(cmd, env={'TMPDIR': tmp_path.name})

    # Run json completer
    complete_jsons(output_dir, subject, session, overwrite=True)

    # Run metadata cleaner
    clean_metadata(output_dir, subject, session)

    # Run BIDS validator
    cmd = (f'bids-validator {output_dir} --ignoreWarnings > '
           f'{output_dir / "validator.txt"}')
    run(cmd, env={'TMPDIR': tmp_path.name})

    # Clean up output directory, returning it to bids standard
    maintain_bids(output_dir, subject, session)

    # Grab some info from the dicoms to add to the participants file
    participants_file = output_dir / 'participants.tsv'
    if participants_file.is_file():
        participant_df = pd.read_table(
            participants_file, index_col='participant_id')
        data = manage_dicom_dir(dicomdir)
        participant_id = f'sub-{subject}'
        if data.get('PatientAge'):
            age = data.PatientAge.replace('Y', '')
            try:
                age = int(age)
            except ValueError:
                age = np.nan
        elif data.get('PatientBirthDate'):
            age = parse(data.StudyDate) - parse(data.PatientBirthDate)
            age = np.round(age.days / 365.25, 2)
        else:
            age = np.nan

        additional_data = pd.DataFrame(
            columns=['age', 'sex', 'weight'],
            data=[[age, data.PatientSex, data.PatientWeight]],
            index=[participant_id])

        missing_cols = [col for col in additional_data.columns
                        if col not in data.columns]
        for mc in missing_cols:
            participant_df[mc] = np.nan
        if participant_id not in participant_df.index.values:
            participant_df.loc[participant_id] = np.nan

        participant_df.update(additional_data, overwrite=True)
        participant_df.sort_index(inplace=True)
        participant_df.to_csv(
            participants_file, sep='\t', na_rep='n/a',
            line_terminator='\n', index_label='participant_id')


def _main(argv=None):
    """Bidsify runtime."""
    options = _get_parser().parse_args(argv)
    kwargs = vars(options)
    bidsify_workflow(**kwargs)
