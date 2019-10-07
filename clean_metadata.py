#!/usr/bin/env python
"""
Author: Taylor Salo, tsalo006@fiu.edu
Edited: Michael Riedel, miriedel@fiu.edu; 4/18/2018
"""
from __future__ import print_function

import sys
import json

from bids import BIDSLayout


def main(bids_dir, sub, sess):
    '''
    Removes unnecessary metadata from scan sidecar jsons

    Parameters
    ----------
    bids_dir: path to BIDS dataset
    '''
    layout = BIDSLayout(bids_dir)
    scans = layout.get(extension='nii.gz', subject=sub, session=sess)

    """
    KEEP_KEYS = [
        'AnatomicalLandmarkCoordinates', 'AcquisitionTime',
        'AcquisitionDuration', 'CogAtlasID',
        'CogPOID', 'CoilCombinationMethod', 'ConversionSoftware',
        'ConversionSoftwareVersion', 'DelayAfterTrigger', 'DelayTime',
        'DeviceSerialNumber', 'DwellTime', 'EchoNumbers', 'EchoTime',
        'EchoTime1', 'EchoTime2',
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
    """
    for scan in scans:
        json_file = scan.path.replace('.nii.gz', '.json')
        metadata = layout.get_metadata(scan.path)
        metadata2 = {key: metadata[key] for key in metadata.keys() if key != 'global'}
        global_keys = {}
        if 'global' in metadata.keys():
            if 'const' in metadata['global']:
                global_keys = metadata['global']['const']

        for key in global_keys:
            if key not in metadata:
                metadata2[key] = global_keys[key]

        with open(json_file, 'w') as fo:
            json.dump(metadata2, fo, sort_keys=True, indent=4)


if __name__ == '__main__':
    folder = sys.argv[1]
    sub = sys.argv[2]
    sess = sys.argv[3]
    main(folder, sub, sess)
