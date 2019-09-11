#!/usr/bin/env python
"""
Fill in the gaps left by heudiconv in the json files for a BIDS dataset.
For example:
-   Assign IntendedFor field to each field map, based on acquisition time
    relative to functional scans.
-   Add PhaseEncodingDirection and TotalReadoutTime fields to field map jsons.
-   Add TaskName to functional scan jsons.
"""
import json
import argparse
import os.path as op
import nibabel as nib
from bids import BIDSLayout

def intended_for_gen(niftis, fmap_nifti):
    out_dict = {x.get_metadata()['AcquisitionTime']: x for x in niftis}
    intended_for = []
    acq_time = fmap_nifti.get_metadata()['AcquisitionTime']
    for num in sorted([x for x in sorted(out_dict.keys()) if x > acq_time]):
        fmap_entities = fmap_nifti.get_entities()
        target_entities = out_dict[num].get_entities()
        if target_entities['datatype'] == 'fmap':
            if all([fmap_entities[x] == target_entities[x] for x in fmap_entities \
                    if x != 'run']):
                break
            else:
                continue
        if fmap_entities['acquisition'] != target_entities['datatype']:
            continue
        intended_for.append(op.join('ses-{0}/'.format(target_entities['session']),
                                    target_entities['datatype'],
                                    out_dict[num].filename))
    return intended_for

def complete_jsons(bids_dir, subs, ses, overwrite):
    """
    Assign 'IntendedFor' field to field maps in BIDS dataset.
    Uses the most recent field map before each functional or DWI scan, based on
    acquisition time.
    Calculate 'TotalReadoutTime'.

    Parameters
    ----------
    bids_dir: path to BIDS dataset
    subs: list of subjects
    ses: string of session
    overwrite: bool
    """
    layout = BIDSLayout(op.abspath(bids_dir))
    for sid in subs:
        niftis = layout.get(subject=sid, session=ses, extension='nii.gz')
        for nifti in niftis:
            img = nib.load(nifti.path)
            # get_nearest doesn't work with field maps atm
            data = nifti.get_metadata()
            dump = 0
            json_path = nifti.path.replace('.nii.gz', '.json')
            if 'EffectiveEchoSpacing' in data.keys() and \
            (overwrite or 'TotalReadoutTime' not in data.keys()):
                # This next bit taken shamelessly from fmriprep
                pe_idx = {'i': 0, 'j': 1, 'k': 2}[data['PhaseEncodingDirection'][0]]
                etl = img.shape[pe_idx] // float(data.get('ParallelReductionFactorInPlane', 1.0))
                ees = data.get('EffectiveEchoSpacing', None)
                if ees is None:
                    raise Exception('Field "EffectiveEchoSpacing" not '
                                    'found in json')
                data['TotalReadoutTime'] = ees * (etl - 1)
                dump = 1
            if 'task' in nifti.get_entities() and (overwrite or 'TaskName' not in data.keys()):
                data['TaskName'] = nifti.get_entities()['task']
                dump = 1
            if nifti.get_entities()['datatype'] == 'fmap' \
            and (overwrite or 'IntendedFor' not in data.keys()):
                data['IntendedFor'] = intended_for_gen(niftis, nifti)
                dump = 1
            if dump == 1:
                data['AcquisitionTime'] = ('1800-01-01' + 'T' +
                                           data['AcquisitionTime'].split('T')[-1])
                with open(json_path, 'w') as f_obj:
                    json.dump(data, f_obj, sort_keys=True, indent=4)

def main(args=None):
    docstr = __doc__
    parser = argparse.ArgumentParser(description=docstr)
    parser.add_argument('-d', '--bids_dir', dest='bids_dir', required=True,
                        type=str, help='location of BIDS dataset')
    parser.add_argument('-s', '--subjects', dest='subs', required=True,
                        type=str, nargs='+', help='list of subjects')
    parser.add_argument('-ss', '--ses', dest='session', required=False,
                        default=None,
                        help='session for longitudinal studies, default is '
                             'none')
    parser.add_argument('-o', '--overwrite', dest='overwrite', required=False,
                        default=False, action='store_true',
                        help='overwrite fmap jsons')
    args = parser.parse_args(args)
    if isinstance(args.session, str) and args.session == 'None':
        args.session = None
    complete_jsons(args.bids_dir, args.subs, args.session, args.overwrite)

if __name__ == '__main__':
    main()
