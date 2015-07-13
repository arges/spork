#!/bin/bash
# get the files necessary for reviewing the current kernel based on bug

# usage
if [ $# -lt 3 ]; then
  echo "$0 PKGNAME SERIES NEW_VERSION"
  exit
fi

PKGNAME=$1
SERIES=$2
NEW_VERSION=$3

get_kernel_upload() {
  PKGNAME=$1
  SERIES=$2
  NEW=$3

  # get the version in the archive
  ORIG=$(rmadison -a source $PKGNAME -s ${SERIES}-proposed | awk '{print $3}')
  
  KERNEL_PPA_URL=https://launchpad.net/~canonical-kernel-team/+archive/ppa/+files
  PRIMARY_ARCHIVE_URL=https://launchpad.net/ubuntu/+archive/primary/+files
  
  mkdir ${PKGNAME}_${NEW} && cd $_
  # get Changes File
  wget -q ${KERNEL_PPA_URL}/${PKGNAME}_${NEW}_source.changes
  
  # first attempt to download launchpad generated diff
  if wget -q ${KERNEL_PPA_URL}/${PKGNAME}_${ORIG}_${NEW}.diff.gz; then
    zcat ${PKGNAME}_${ORIG}_${NEW}.diff.gz | filterdiff -x '*/abi/*' > REVIEW-${PKGNAME}_${ORIG}_${NEW}.diff
    exit
  fi
  
  # if it doesn't work reconstruct the diff
  dget -u ${PRIMARY_ARCHIVE_URL}/${PKGNAME}_${ORIG}.dsc
  dget -u ${KERNEL_PPA_URL}/${PKGNAME}_${NEW}.dsc
  cd ${PKGNAME}*
  debdiff ../${PKGNAME}_${ORIG}.dsc ../${PKGNAME}_${NEW}.dsc > ../${PKGNAME}_${ORIG}_${NEW}.diff
  filterdiff -x '*/abi/*' ../${PKGNAME}_${ORIG}_${NEW}.diff > ../REVIEW-${PKGNAME}_${ORIG}_${NEW}.diff
  cd ..
}

get_kernel_upload $PKGNAME $SERIES $NEW_VERSION
