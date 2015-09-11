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

class ReviewSRUKernel:

    package_map = {
        "precise": {
            "linux": [ "linux", "linux-meta", "linux-backports-modules-3.2.0" ],
            "linux-armadaxp" : [ "linux-armadaxp", "linux-meta-armadaxp" ],
            "linux-lts-trusty" : [ "linux-lts-trusty", "linux-meta-lts-trusty",
                                   "linux-signed-lts-trusty" ],
            "linux-ti-omap4" : [ "linux-ti-omap4", "linux-ti-omap4-meta" ],
         },
        "trusty": {
            "linux": [ "linux", "linux-meta", "linux-signed" ],
            "linux-keystone" : [ "linux-keystone", "linux-meta-keystone" ],
            "linux-lts-utopic" : [ "linux-lts-utopic", "linux-meta-lts-utopic",
                                   "linux-signed-lts-utopic" ],
            "linux-lts-vivid" : [ "linux-lts-vivid", "linux-meta-lts-vivid",
                                  "linux-signed-lts-vivid" ],
         },
         "vivid" : {
            "linux": [ "linux", "linux-meta", "linux-signed" ],
         }
    }

    def __init__(self):
        self.launchpad = Launchpad.login_with("spork", "production", version="devel")
        self.ubuntu = self.launchpad.distributions["ubuntu"]
        self.workflow = self.launchpad.projects["kernel-sru-workflow"]
        self.me = self.launchpad.me
        team = self.launchpad.people["canonical-kernel-team"]
        self.ppa = team.getPPAByName(name="ppa")
        self.archive = self.ubuntu.main_archive

    def set_bug_state(self, bugno, status):
        bug = self.launchpad.bugs[bugno]
        for task in bug.bug_tasks:
              if task.bug_target_name == "kernel-sru-workflow/promote-to-proposed":
                  task.status = status
                  task.assignee = self.me
                  task.lp_save()

    def review_packageset(self, packageset, version, series):
        packages = self.package_map[series][packageset]
        for package in packages:
            version_fixed = version.replace("-",".") if 'meta' in package else version
            print version_fixed
            url = self.get_diff(package, version_fixed, series)
            self.display_diff(url)

    def get_diff(self, package_name, version, series):
        distroseries = self.ubuntu.getSeries(name_or_version=series)
        new_source = self.ppa.getPublishedSources(source_name=package_name,
            version=version, distro_series=distroseries, exact_match=True)[0]
        if not new_source:
            print "Couldn't find sources!"
            exit(1)

        # Attempt to download launchpad generated diff
        try:
            url = new_source.packageDiffUrl(to_version=version)
        except:
            # Try to construct diff manually
            print "Launchpad diff pending, constructing diff manually."
            old_source = self.archive.getPublishedSources(
                source_name=package_name, distro_series=distroseries,
                pocket='Updates', status='Published',  exact_match=True)[0]
            old_dsc = [ f for f in old_source.sourceFileUrls() if f.endswith('.dsc') ][0]
            new_dsc = [ f for f in new_source.sourceFileUrls() if f.endswith('.dsc') ][0]
            old_filename = old_dsc.split('/')[-1]
            new_filename = new_dsc.split('/')[-1]
            subprocess.call(["mkdir","temp"])
            subprocess.call(["dget", "-u", old_dsc], cwd='temp')
            subprocess.call(["dget", "-u", new_dsc], cwd='temp')
            p1 = subprocess.Popen(["debdiff",
                "%s" % old_filename, "%s" % new_filename],
                stdout=subprocess.PIPE, cwd='temp')
            p2 = subprocess.Popen(["filterdiff -x '*/abi/*'"],
                stdin=p1.stdout, stdout=subprocess.PIPE, shell=True, cwd='temp')
            p1.stdout.close()
            output = p2.communicate()[0]
            return output

        # Download and filter diff
        p1 = subprocess.Popen(["wget", "-qO-", url], stdout=subprocess.PIPE)
        p2 = subprocess.Popen(["zcat | filterdiff -x '*/abi/*'"],
            stdin=p1.stdout, stdout=subprocess.PIPE, shell=True)
        p1.stdout.close()
        output = p2.communicate()[0]

        return output

    def display_diff(self, text):
        pydoc.pipepager(text, "view -")

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
        # FIXME: actually finish this...

        exit(1)
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

    def sanity_check(self):
        print("sanity check")
        # all bugs public?
        # all bugs targeted correctly?
        # changes file looks correct
        #   diff.gz => {linux}
        #   tar.gz => {linux-meta,linux-signed}
        # check diff size < 7MB (WARNING)
        # no swp or random binary files
        # no large amounts of removed files

def usage():
        print("Usage: take <bugno>")
        print("       review <package> <version> <series>")
        print("       promote <package> <version> <series>")
        print("       status <pocket>")

if __name__ == "__main__":

    if len(sys.argv) <= 2:
        usage()
        exit(1)

    if sys.argv[1] == "take":
        if len(sys.argv) != 3:
            usage()
        BUGNO = sys.argv[2]
        r = ReviewSRUKernel()
        r.set_bug_state(BUGNO, "In Progress")
        print("%s assigned and set to: %s" %( BUGNO, "In Progress" ))
    elif sys.argv[1] == "review":
        if len(sys.argv) != 5:
            usage()
        PACKAGE = sys.argv[2]
        VERSION = sys.argv[3]
        SERIES = sys.argv[4]
        r = ReviewSRUKernel()
        diff = r.get_diff(PACKAGE, VERSION, SERIES)
        r.display_diff(diff)
    elif sys.argv[1] == "promote":
        if len(sys.argv) != 5:
            usage()
        PACKAGE = sys.argv[2]
        VERSION = sys.argv[3]
        SERIES = sys.argv[4]
        r = ReviewSRUKernel()
        r.promote_kernel(PACKAGE, VERSION, SERIES)
    elif sys.argv[1] == "status":
        if len(sys.argv) != 3:
            usage()
        POCKET = sys.argv[2]
        r = ReviewSRUKernel()
        r.status(POCKET)
    else:
        print("Invalid command")

