#!/bin/bash

# usage
if [ $# -lt 3 ]; then
  echo "$0 BUG# SERIES COMMITS..."
  exit
fi

BUG=$1 && shift
SERIES=$1 && shift
COMMITS=$@

echo $BUG $SERIES
echo $COMMITS

cd ~/src/kernel/ubuntu-${SERIES}
git checkout master
git pull --rebase
git checkout -b lp${BUG}
for commit in $COMMITS; do
  git cherry-pick -sex $commit
done

# extract patches

# add BugLinks, subject SRU, desc

# do a test build


