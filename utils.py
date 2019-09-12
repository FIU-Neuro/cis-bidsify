#!/usr/bin/env python
"""
Fill in the gaps left by heudiconv in the json files for a BIDS dataset.
For example:
-   Assign IntendedFor field to each field map, based on acquisition time
    relative to functional scans.
-   Add PhaseEncodingDirection and TotalReadoutTime fields to field map jsons.
-   Add TaskName to functional scan jsons.
"""
import sys
import json
import pathlib
import os.path as op
import subprocess as sp
import nibabel as nib

from bids import BIDSLayout


def intended_for_gen(niftis, fmap_nifti):
    intended_for = []
    fmap_entities = fmap_nifti.get_entities()
    acq_time = fmap_nifti.get_metadata()['AcquisitionTime']
    out_dict = {}
    for nifti in niftis:
        nifti_meta = nifti.get_metadata()
        if nifti_meta['AcquisitionTime'] <= acq_time:
            continue
        if nifti_meta['AcquisitionTime'] in out_dict \
        and nifti not in out_dict[nifti_meta['AcquisitionTime']]:
            out_dict[nifti_meta['AcquisitionTime']].append(nifti)
        elif nifti_meta['AcquisitionTime'] not in out_dict:
            out_dict[nifti_meta['AcquisitionTime']] = [nifti]
    for num in sorted([x for x in out_dict]):
        target_entities = [x.get_entities() for x in out_dict[num]]
        if target_entities[0]['datatype'] == 'fmap':
            if any([all([fmap_entities[x] == i[x] for x in fmap_entities \
                    if x != 'run']) for i in target_entities]):
                break
            else:
                continue
        if 'acquisition' in fmap_entities \
        and fmap_entities['acquisition'] != target_entities[0]['datatype']:
            continue
        if 'session' in target_entities[0]:
            intended_for.extend(sorted([op.join('ses-{0}'.format(target_entities[0]['session']),
                                                target_entities[0]['datatype'],
                                                x.filename) for x in out_dict[num]]))
        else:
            intended_for.extend(sorted([op.join(target_entities[0]['datatype'],
                                                x.filename) for x in out_dict[num]]))
    return sorted(intended_for)

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
    layout = BIDSLayout(op.abspath(bids_dir), validate=False)
    for sid in subs:
        if ses:
            niftis = layout.get(subject=sid, session=ses,
                                extension='nii.gz',
                                datatype=['func', 'fmap', 'dwi'])
        else:
            niftis = layout.get(subject=sid,
                                extension='nii.gz',
                                datatype=['func', 'fmap', 'dwi'])
        for nifti in niftis:
            # get_nearest doesn't work with field maps atm
            data = nifti.get_metadata()
            dump = 0
            json_path = nifti.path.replace('.nii.gz', '.json')
            if 'EffectiveEchoSpacing' in data.keys() and \
            (overwrite or 'TotalReadoutTime' not in data.keys()):
                # This next bit taken shamelessly from fmriprep
                pe_idx = {'i': 0, 'j': 1, 'k': 2}[data['PhaseEncodingDirection'][0]]
                etl = nib.load(nifti.path).shape[pe_idx] \
                      // float(data.get('ParallelReductionFactorInPlane', 1.0))
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
                with open(json_path, 'w') as f_obj:
                    json.dump(data, f_obj, sort_keys=True, indent=4)


def clean_jsons(bids_dir, sub, sess):
    '''
    Removes unnecessary metadata from scan sidecar jsons

    Parameters
    ----------
    bids_dir: path to BIDS dataset
    '''
    layout = BIDSLayout(bids_dir)
    scans = layout.get(extension='nii.gz', subject=sub, session=sess)

    KEEP_KEYS = [
        'AnatomicalLandmarkCoordinates', 'AcquisitionTime',
        'AcquisitionDuration', 'CogAtlasID',
        'CogPOID', 'CoilCombinationMethod', 'ConversionSoftware',
        'ConversionSoftwareVersion', 'DelayAfterTrigger', 'DelayTime',
        'DeviceSerialNumber', 'DwellTime', 'EchoNumbers', 'EchoTime',
        'EchoTrainLength', 'EffectiveEchoSpacing', 'FlipAngle',
        'GradientSetType', 'HighBit',
        'ImagedNucleus', 'ImageType', 'ImagingFrequency',
        'InPlanePhaseEncodingDirection', 'InstitutionName',
        'InstitutionAddress', 'InstitutionalDepartmentName',
        'Instructions', 'IntendedFor', 'InversionTime',
        'MRAcquisitionType', 'MagneticFieldStrength', 'Manufacturer',
        'ManufacturersModelName', 'MatrixCoilMode', 'Modality',
        'MRTransmitCoilSequence', 'MultibandAccelerationFactor',
        'NumberOfAverages', 'NumberOfPhaseEncodingSteps',
        'NumberOfVolumesDiscardedByScanner', 'NumberOfVolumesDiscardedByUser',
        'NumberShots', 'ParallelAcquisitionTechnique',
        'ParallelReductionFactorInPlane', 'PartialFourier',
        'PartialFourierDirection', 'PhaseEncodingDirection',
        'PixelBandwidth', 'ProtocolName', 'PulseSequenceDetails',
        'PulseSequenceType', 'ReceiveCoilActiveElements', 'ReceiveCoilName',
        'RepetitionTime', 'Rows',
        'SAR', 'ScanningSequence', 'ScanOptions', 'SequenceName',
        'SequenceVariant', 'SeriesDescription', 'SeriesNumber',
        'SliceEncodingDirection', 'SliceLocation',
        'SliceThickness', 'SliceTiming', 'SoftwareVersions',
        'SpacingBetweenSlices', 'StationName', 'TaskDescription',
        'TaskName', 'TotalReadoutTime', 'Units', 'VolumeTiming']

    for scan in scans:
        json_file = scan.path.replace('.nii.gz', '.json')
        metadata = layout.get_metadata(scan.path)
        metadata2 = {key: metadata[key] for key in KEEP_KEYS if key in
                     metadata.keys()}
        global_keys = {}
        if 'global' in metadata.keys():
            if 'const' in metadata['global']:
                global_keys = metadata['global']['const']

        for key in KEEP_KEYS:
            if key not in metadata and key in global_keys:
                metadata2[key] = global_keys[key]

        with open(json_file, 'w') as fo:
            json.dump(metadata2, fo, sort_keys=True, indent=4)

def run_heudiconv(dicom_dir, heuristics, out_dir, sub, ses):
    if pathlib.Path(dicom_dir).is_file():
        dir_type = '-d'
    elif pathlib.Path(dicom_dir).is_dir():
        dir_type = '--file'
    if ses:
        heudi_cmd = f'heudiconv {dir_type} {dicom_dir} \
                      -s {sub} -ss {ses} -f {heuristics} \
                     -c dcm2niix -o {out_dir} --bids --overwrite'
    else:
        heudi_cmd = f'heudiconv {dir_type} {dicom_dir} \
                      -s {sub} -f {heuristics} \
                      -c dcm2niix -o {out_dir} --bids --overwrite'
    proc = sp.Popen(heudi_cmd, shell=True, stdout=sp.PIPE, stderr=sp.STDOUT)
    for line in proc.stdout:
        sys.stdout.write(line)
    proc.wait()
