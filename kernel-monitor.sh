#!/bin/bash

monitor() {

  POCKET=$1

  # normal linux uploads for all releases
  rmadison -a source linux linux-meta linux-signed | grep ${POCKET}

  # precise linux release
  rmadison -a source linux linux-meta linux-backports-modules-3.2.0 | grep precise-${POCKET}

  # special linux packages
  rmadison -a source linux-keystone linux-meta-keystone | grep trusty-${POCKET}
  rmadison -a source linux-armadaxp linux-meta-armadaxp | grep precise-${POCKET}
  rmadison -a source linux-ti-omap4 linux-meta-ti-omap4 | grep precise-${POCKET}

  # backport packages
  rmadison -a source linux-lts-trusty linux-meta-lts-trusty linux-signed-lts-trusty | grep precise-${POCKET}
  rmadison -a source linux-lts-utopic linux-meta-lts-utopic linux-signed-lts-utopic | grep trusty-${POCKET}

}

monitor $1
