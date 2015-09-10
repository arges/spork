#!/usr/bin/python
#
# Kernel SRU Review Tool
#
# Copyright (C) 2015 Chris J Arges <chris.j.arges@canonical.com>
#

import sys
import subprocess
from launchpadlib.launchpad import Launchpad
import pydoc

"""

TODO

high-level commands
-------------------

list
promote <bug number>
release <bug number>

functions needed
----------------

sanity_check
  all bugs public?
  all bugs targeted correctly?
  changes file looks correct
    diff.gz for linux
    tar.gz for linux-meta
    tar.gz for linux-signed
  check diff size < 7MB (WARNING)
  no swp or random binary files

promote_kernel
  issue sru commands to promote kernel
  output commands

  copy-proposed-kernel vivid linux
  copy-proposed-kernel vivid linux-meta
  wait for uefi binary in unapproved and accept
  wait for linux/linux-meta to get into proposed
  copy-proposed-kernel vivid linux-signed
  wait for linux-signed in new and accept
  ensure everything is in -proposed within timeout

"""

class ReviewSRUKernel:
    def __init__(self):
        self.launchpad = Launchpad.login_with("spork", "production")
        self.ubuntu = self.launchpad.distributions["ubuntu"]
        self.workflow = self.launchpad.projects["kernel-sru-workflow"]

        self.me = self.launchpad.people["arges"]
        team = self.launchpad.people["canonical-kernel-team"]
        self.ppa = team.getPPAByName(name="ppa")

    def set_bug_state(self, bugno, assignee, status):
        bug = self.launchpad.bugs[bugno]
        for task in bug.bug_tasks:
              if task.bug_target_name == "kernel-sru-workflow/promote-to-proposed":
                  task.status = status
                  task.assignee = self.launchpad.people[assignee]
                  task.lp_save()

    def get_diff(self, package_name, version, series):
        distroseries = self.ubuntu.getSeries(name_or_version=series)
        pub_sources = self.ppa.getPublishedSources(source_name=package_name,
            version=version, distro_series=distroseries, exact_match=True)
        if not pub_sources:
            print "Couldn't find sources!"
            exit(1)

        return pub_sources[0].packageDiffUrl(to_version=version)

    def display_diff(self, url):
        p1 = subprocess.Popen(["wget", "-qO-", url], stdout=subprocess.PIPE)
        p2 = subprocess.Popen(["zcat | filterdiff -x '*/abi/*'"],
            stdin=p1.stdout, stdout=subprocess.PIPE, shell=True)
        p1.stdout.close()
        output = p2.communicate()[0]
        pydoc.pipepager(output, "view -")

if __name__ == "__main__":

    if len(sys.argv) != 5:
        print("Usage:	%s bug <bugno> <assignee> <status>" % sys.argv[0])
        print("	%s review <package> <version> <series>" % sys.argv[0])
        exit(1)

    if sys.argv[1] == "bug":
        BUGNO = sys.argv[2]
        ASSIGNEE = sys.argv[3]
        STATUS = sys.argv[4]
        r = ReviewSRUKernel()
        r.set_bug_state(BUGNO, ASSIGNEE, STATUS)
        print("%s set to %s and assigned %s" %( BUGNO, ASSIGNEE, STATUS ))
    elif sys.argv[1] == "review":
        PACKAGE = sys.argv[2]
        VERSION = sys.argv[3]
        SERIES = sys.argv[4]
        r = ReviewSRUKernel()
        url = r.get_diff(PACKAGE, VERSION, SERIES)
        r.display_diff(url)
    else:
        print("Invalid command")

