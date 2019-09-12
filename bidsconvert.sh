################################################################################
# This script is designed to convert scans from the CIS to BIDS formatted datasets on the FIU
# HPC.

# Author: Michael Cody Riedel, miriedel@fiu.edu, Taylor Salo, tsalo006@fiu.edu 04/16/2018

################################################################################
################################################################################
##########################
# Get command line options
##########################
dir_type=$1
dicom_dir=$2
heuristics=$3
out_dir=$4
sub=$5
sess=${6:-None}
######################################
######################################

#############################################
# Begin by converting the data to BIDS format
#############################################
if [ "$sess" = "None" ]; then
  # Put data in BIDS format
  heudiconv $dir_type $dicom_dir -s $sub -f \
    $heuristics -c dcm2niix -o $out_dir --bids --overwrite --minmeta
  minipath=sub-$sub
else
  # Put data in BIDS format
  heudiconv $dir_type $dicom_dir -s $sub -ss $sess -f \
    $heuristics -c dcm2niix -o $out_dir --bids --overwrite --minmeta
  minipath=sub-$sub/ses-$sess
fi

##############################################
# Check results, anonymize, and clean metadata
##############################################
if [ -d $out_dir/$minipath ]; then
  chmod -R 774 $out_dir/$minipath

  # Deface structural scans
  if [ -d $out_dir/$minipath/anat/ ]; then
    imglist=$(ls $out_dir/$minipath/anat/*.nii.gz)
    for tmpimg in $imglist; do
      mri_deface $tmpimg /src/deface/talairach_mixed_with_skull.gca \
      /src/deface/face.gca $tmpimg
    done
  fi
  #rm ./*.log

  # Add IntendedFor and TotalReadoutTime fields to jsons
  python /scripts/complete_jsons.py -d $out_dir -s $sub -ss $sess --overwrite
  # Remove extraneous fields from jsons
  python /scripts/clean_metadata.py $out_dir $sub $sess
  # Validate dataset and, if it passes, copy files to outdir
  bids-validator $out_dir --ignoreWarnings --json > validator.json
else
  echo "FAILED" > $out_dir/validator.json
  echo "Heudiconv failed to convert this dataset to BIDS format."
fi
######################################
######################################
