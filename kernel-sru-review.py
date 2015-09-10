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

"""

class ReviewSRUKernel:

    package_map = {
        "precise": {
            "linux": [ "linux", "linux-meta", "linux-backports-modules-3.2.0" ],
            "linux-armadaxp" : [ "linux-armadaxp", "linux-armadaxp-meta" ],
            "linux-lts-trusty" : [ "linux-lts-trusty", "linux-lts-trusty-meta", "linux-lts-trusty-signed" ],
            "linux-ti-omap4" : [ "linux-ti-omap4", "linux-ti-omap4-meta" ],
         },
        "trusty": {
            "linux": [ "linux", "linux-meta", "linux-signed" ],
            "linux-keystone" : [ "linux-keystone", "linux-keystone-meta" ],
            "linux-lts-utopic" : [ "linux-lts-utopic", "linux-lts-utopic-meta", "linux-lts-utopic-signed" ],
            "linux-lts-vivid" : [ "linux-lts-vivid", "linux-lts-vivid-meta", "linux-lts-vivid-signed" ],
         },
         "vivid" : {
            "linux": [ "linux", "linux-meta", "linux-signed" ],
         }
    }

    def __init__(self):
        self.launchpad = Launchpad.login_with("spork", "production", version="devel")
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

    def status(self, pocket):
        if pocket != 'proposed' and pocket != 'updates':
            print "Invalid pocket"
            exit(1)

        for series in self.package_map:
            for packageset in self.package_map[series]:
                packages = ' '.join(self.package_map[series][packageset])
                cmd = "rmadison -a source %s | grep %s-%s" % ( packages, series, pocket )
                try:
                    output = subprocess.check_output([cmd], shell=True)
                    print output
                except: pass

    def promote_kernel(self, version, series, name):
        # Sanity check first

        distroseries = self.ubuntu.getSeries(name_or_version=series)

        subprocess.Popen(["copy-proposed-kernel", series, "linux"])
        subprocess.Popen(["copy-proposed-kernel", series, "linux-meta"])

        # Wait and approve uefi upload
	upload = distroseries.getPackageUploads(status="Unapproved",
            name="linux", version=version, exact_match=True)[0]
        upload.acceptFromQueue()

        # Wait for linux/linux-meta to land in -proposed

        # Copy in linux-signed
        subprocess.Popen(["copy-proposed-kernel", series, "linux-signed"])

        # Wait and approve linux-signed new package
	upload = distroseries.getPackageUploads(status="New",
            name="linux-signed", version=version, exact_match=True)[0]
        upload.acceptFromQueue()

        # Check that everything is correct


def usage():
        print("Usage: bug <bugno> <assignee> <status>")
        print("       review <package> <version> <series>")
        print("       status <pocket>")


if __name__ == "__main__":

    if len(sys.argv) < 2:
        usage()
        exit(1)

    if sys.argv[1] == "bug":
        if len(sys.argv) != 5:
            usage()
        BUGNO = sys.argv[2]
        ASSIGNEE = sys.argv[3]
        STATUS = sys.argv[4]
        r = ReviewSRUKernel()
        r.set_bug_state(BUGNO, ASSIGNEE, STATUS)
        print("%s set to %s and assigned %s" %( BUGNO, ASSIGNEE, STATUS ))
    elif sys.argv[1] == "review":
        if len(sys.argv) != 5:
            usage()
        PACKAGE = sys.argv[2]
        VERSION = sys.argv[3]
        SERIES = sys.argv[4]
        r = ReviewSRUKernel()
        url = r.get_diff(PACKAGE, VERSION, SERIES)
        r.display_diff(url)
    elif sys.argv[1] == "status":
        if len(sys.argv) != 3:
            usage()
        POCKET = sys.argv[2]
        r = ReviewSRUKernel()
        r.status(POCKET)
    else:
        print("Invalid command")

