#!/bin/bash
#
# Simple remote builder script to provide test packages for LP bugs.
#
# Author: Chris J Arges <chris.j.arges@ubuntu.com>
# Based on work by Seth Forshee <seth.forshee@canonical.com>
#

# Default arguments
ARCH="amd64"
FLAVOR="generic"
DDEB=""
PREFIX="test"
#BUILDSERVER="" # Edit this to add default value.
REMOTE_GIT_REPOS=/usr3/ubuntu

# parse arguments
while getopts "a:f:p:b:dvh" opt; do
    case $opt in
        a) ARCH=$OPTARG ;;
        f) FLAVOR=$OPTARG ;;
        d) DDEB="skipdbg=false" ;;
        b) BUILDSERVER=$OPTARG ;;
        p) PREFIX=$OPTARG ;;
        h|*)
            echo "usage: $0 -a <arch> b <buildserver> -f <flavor> -p <prefix> -d"
            echo "	a - arch - one of amd64,i386,armhf DEFAULT: amd64"
            echo "	b - buildserver - buildd server with schroots"
            echo "	f - flavor - generic,virtual, server for appropriate series DEFAULT: generic"
            echo "	p - prefix - appended to version (ex: lpXXXXXX) DEFAULT: test"
            echo "	d - build with ddebs DEFAULT: off"
            exit 0
            ;;
    esac
done

function dump_vars() {
    echo ARCH=$ARCH
    echo FLAVOR=$FLAVOR
    echo SERIES=$SERIES
    echo DDEB=$DDEB
    echo BUILDSERVER=$BUILDSERVER
    echo LOCAL_BRANCH=$LOCAL_BRANCH
    echo REMOTE_BRANCH=$REMOTE_BRANCH
    echo TIMESTAMP=$TIMESTAMP
    echo ORIG_VERSION=$ORIG_VERSION
    echo VERSION=$VERSION
    echo REMOTE_SRC_PATH=$REMOTE_SRC_PATH
    echo REMOTE_DEST_PATH=$REMOTE_DEST_PATH
    echo ""
}

# construct variables from git repo
function get_vars() {
    if [ ! -d .git ]; then
        echo "Must be run from within a git repo."
        exit
    fi
    LOCAL_BRANCH=`git rev-parse --abbrev-ref HEAD`
    REMOTE_BRANCH=$PREFIX
    TIMESTAMP=$(date +"%Y%m%d%H%M")
    changelog_info=`head -1 debian.master/changelog`
    ORIG_VERSION=`echo $changelog_info | awk '{print $2}' | sed -r -e 's/^\(//;s/\)$//'`
    VERSION=${ORIG_VERSION}~${PREFIX}v${TIMESTAMP}
    SERIES=`echo $changelog_info | awk '{print $3}' | sed 's/;//' | sed 's/\-proposed//'`
    REMOTE_SRC_PATH=${REMOTE_GIT_REPOS}/ubuntu-$SERIES.git
    REMOTE_DEST_PATH=~/$PREFIX/ubuntu-$SERIES
}

function sanity_check() {
    # must specify a buildserver
    if [[ -z $BUILDSERVER ]]; then
        echo "Buildserver not specified."
        exit 1
    fi
}

function execute_remote() {
    echo $2
    echo "$BUILDSERVER: $1"
    ssh $BUILDSERVER $1
}

function execute_local() {
    echo $2
    echo "localhost: $1"
    $1
}

function remote_create() {
    cmd="
    cd ~;
    mkdir -p ~/$PREFIX;
    if [ ! -d $REMOTE_DEST_PATH ]; then
        git clone --reference ${REMOTE_GIT_REPOS}/linux.git $REMOTE_SRC_PATH $REMOTE_DEST_PATH;
        cd $REMOTE_DEST_PATH;
        git config add receive.denyCurrentBranch ignore;
    else
        cd $REMOTE_DEST_PATH;
        git fetch;
    fi
    "
    execute_remote "$cmd" "[updating remote repository]"

    cmd="
    git push -f $BUILDSERVER:$REMOTE_DEST_PATH $LOCAL_BRANCH:$REMOTE_BRANCH
    "
    execute_local "$cmd" "[pushing changes]"

    cmd="
    cd $REMOTE_DEST_PATH;
    git checkout -f $REMOTE_BRANCH;
    git reset --hard HEAD; git clean -xfd;
    rm -f debian/changelog;
    echo 'dch -b -v $VERSION -D $SERIES -c debian.master/changelog 'Test build for $PREFIX.''
        | tee --append build.log | schroot -c $SERIES-$ARCH;
    "
    execute_remote "$cmd" "[generating changelog]"
}

function remote_build() {
    cmd="
    cd $REMOTE_DEST_PATH;
    git clean -xfd;
    echo 'skipabi=true skipmodule=true fakeroot debian/rules clean;
          skipabi=true skipmodule=true debian/rules build-${FLAVOR};
          skipabi=true skipmodule=true fakeroot debian/rules binary-${FLAVOR} binary-headers ${DDEB}; 2>&1'
        | tee --append build.log | schroot -c ${SERIES}-${ARCH};
    rm -f ../*.patch;
    git format-patch -o .. origin/master;
    "
    execute_remote "$cmd" "[building kernel]"
}

# main
get_vars
sanity_check
dump_vars
remote_create
remote_build

