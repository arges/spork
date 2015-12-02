#!/usr/bin/python
#
# Kernel SRU Review Tool
#
# Copyright (C) 2015 Chris J Arges <chris.j.arges@canonical.com>
#

from launchpadlib.launchpad import Launchpad
import pydoc
import subprocess
import sys
import time
from termcolor import colored

class ReviewSRUKernel:

    package_map = {
        "precise": {
            "linux": [ "linux", "linux-meta", "linux-backports-modules-3.2.0" ],
            "linux-armadaxp" : [ "linux-armadaxp", "linux-meta-armadaxp" ],
            "linux-lts-trusty" : [ "linux-lts-trusty", "linux-meta-lts-trusty",
                                   "linux-signed-lts-trusty" ],
            "linux-ti-omap4" : [ "linux-ti-omap4", "linux-meta-ti-omap4" ],
         },
        "trusty": {
            "linux": [ "linux", "linux-meta", "linux-signed" ],
            "linux-keystone" : [ "linux-keystone", "linux-meta-keystone" ],
            "linux-lts-utopic" : [ "linux-lts-utopic", "linux-meta-lts-utopic",
                                   "linux-signed-lts-utopic" ],
            "linux-lts-vivid" : [ "linux-lts-vivid", "linux-meta-lts-vivid",
                                  "linux-signed-lts-vivid" ],
            "linux-lts-wily" : [ "linux-lts-wily", "linux-meta-lts-wily",
                                  "linux-signed-lts-wily" ],
         },
         "vivid" : {
            "linux": [ "linux", "linux-meta", "linux-signed" ],
         },
         "wily" : {
            "linux": [ "linux", "linux-meta", "linux-signed" ],
            "linux-raspi2": [ "linux-raspi2", "linux-meta-raspi2" ],
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

    def set_bug_state(self, bugno, status, pocket='proposed'):
        bug = self.launchpad.bugs[bugno]
        for task in bug.bug_tasks:
              if task.bug_target_name == "kernel-sru-workflow/promote-to-%s" % pocket:
                  if task.status in ["Confirmed", "In Progress"]:
                      task.status = status
                      task.assignee = self.me
                      task.lp_save()

    def add_bug_message(self, bugno, subject, message):
        bug = self.launchpad.bugs[bugno]
        bug.newMessage(subject=subject, content=message)
        bug.lp_save()

    def get_diff(self, package_name, version, series, manual=True):
        distroseries = self.ubuntu.getSeries(name_or_version=series)
        new_source = self.ppa.getPublishedSources(source_name=package_name,
            version=version, distro_series=distroseries, exact_match=True, status='Published')[0]
        if not new_source:
            print "Couldn't find sources!"
            exit(1)

        # Attempt to download launchpad generated diff
        try:
            # TODO: improve logic here. Throw an exception to get into the
            # manual diff creation block.
            if manual:
                raise Exception()

            # Download whatever launchpad gives us.
            url = new_source.packageDiffUrl(to_version=version)
        except:
            # Try to construct diff manually.
            # We diff against Updates, but in the rare case that this is
            # the first SRU, we'll need to diff against the Release pocket.
            print "Launchpad diff pending, constructing diff manually."
            try:
                old_source = self.archive.getPublishedSources(
                    source_name=package_name, distro_series=distroseries,
                    pocket='Updates', status='Published',  exact_match=True)[0]
            except:
                old_source = self.archive.getPublishedSources(
                    source_name=package_name, distro_series=distroseries,
                    pocket='Release', status='Published',  exact_match=True)[0]
            old_dsc = [ f for f in old_source.sourceFileUrls() if f.endswith('.dsc') ][0]
            new_dsc = [ f for f in new_source.sourceFileUrls() if f.endswith('.dsc') ][0]
            old_filename = old_dsc.split('/')[-1]
            new_filename = new_dsc.split('/')[-1]
            subprocess.call(["mkdir","-p","temp"])
            subprocess.call(["dget", "-q", "-u", old_dsc], cwd='temp')
            subprocess.call(["dget", "-q", "-u", new_dsc], cwd='temp')
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
        pydoc.pipepager(text, "view -c 'set syntax=diff' -")

    def status(self, pocket):
        if pocket != 'proposed' and pocket != 'updates':
            print "Invalid pocket"
            exit(1)

        for series in self.package_map:
            for packageset in self.package_map[series]:
                packages = ' '.join(self.package_map[series][packageset])
                cmd = "rmadison -a source %s | grep %s-%s" % ( packages, series, pocket )
                try:
                    output = subprocess.check_output([cmd], shell=True).split('\n')
                    for line in output:
                        s = line.split('|')
                        print colored(s[0].rstrip(),'yellow').ljust(42) + " " + colored(s[1].rstrip(), 'green').ljust(32) + " " + s[2].rstrip()
                except: pass

    def promote_kernel_set(self, package_set, series):

        print("Not working yet.")
        exit(1)

        version = 0

        # Check if package_set is valid
        if package_set not in self.package_map[series]:
            print("Invalid package set")
            exit(1)

        # Get variables
        distroseries = self.ubuntu.getSeries(name_or_version=series)
        packages = self.package_map[series][package_set]
        print packages

        # Copy anything that isn't signed first
        set_has_signed=False
        for package in packages:
            if "signed" not in package:
                subprocess.Popen(["copy-proposed-kernel", series, package])
            else:
                set_has_signed=True

        # If there were no signed kernel then we are done
        if not set_has_signed:
            return

        # Otherwise wait for uefi upload
        upload=None
        while True:
            # Wait some time for UEFI binary to become available
            time.sleep(10)

            # TODO detect the correct name here
            upload = distroseries.getPackageUploads(status="Unapproved",
                name="linux", version=version, exact_match=True)[0]
            if upload:
                break

            print("Waiting for UEFI binary...")
        print("Accepted UEFI binary!")

        # Otherwise except the upload.
        upload.acceptFromQueue()

        # Wait for linux/linux-meta to land in -proposed
        output = None
        while True:
            # Wait some time for linux / linux-meta to be published
            time.sleep(60)
            cmd = "rmadison -a source %s | grep %s-%s | grep %s" % ( 'linux', series, 'proposed', version )
            try:
                output = subprocess.check_output([cmd], shell=True)
                print output
                break
            except:
                pass

            print("Waiting for %s %s %s to be published" % ( 'linux linux-meta', series, version ))

        print("%s %s %s is published!" % ( 'linux linux-meta', series, version ))

        # Copy in linux-signed
        subprocess.Popen(["copy-proposed-kernel", series, "linux-signed"])

        # Wait and approve linux-signed new package
        upload=None
        while True:
            # Wait some time for linux-signed to become available
            time.sleep(30)
            upload = distroseries.getPackageUploads(status="New",
                name="linux-signed", version=version, exact_match=True)[0]
            if upload:
                break
            print("Waiting for linux-signed new package...")
        print("Accepted linux-signed new package!")

        upload.acceptFromQueue()

    def release(self, bugno, package_set, series):
        # Assign yourself to both updates, security
        self.set_bug_state(bugno, "In Progress", "updates")
        self.set_bug_state(bugno, "In Progress", "security")

        # Release the kernel!
        packages = self.package_map[series][package_set]
        cmd = ["sru-release", "--no-bugs", "--security", series]
        cmd.extend(packages)
        print(" ".join(cmd))
        subprocess.Popen(cmd)

    def finish(self, bugno, package_set, series, pocket="updates"):

        # Get status
        status = ""
        packages = ' '.join(self.package_map[series][package_set])
        cmd = "rmadison -a source %s | grep %s-%s" % ( packages, series, pocket)
        try:
            status = subprocess.check_output([cmd], shell=True).rstrip("\n\r")
        except:
            print("Error getting status")
            exit(1)

        text = "Promoted to %s:\n%s" % (pocket.capitalize(), status)
        print text

        # Look good?
        print("Does this look correct? "),
        answer = raw_input().lower()
        if answer in ('y','yes'):
            # Set bug states to Fix Released
            if pocket == "updates":
                self.set_bug_state(bugno, "Fix Released", "updates")
                self.set_bug_state(bugno, "Fix Released", "security")
            else:
                self.set_bug_state(bugno, "Fix Released", "proposed")

            # Set bug message
            self.add_bug_message(bugno, "Promoted to " + pocket.capitalize(), status)


    def list_ppa_packages(self, series, packageset):
        distroseries = self.ubuntu.getSeries(name_or_version=series)
        packages = self.package_map[series][packageset]

        package_versions = []
        for package in packages:
            new_source = self.ppa.getPublishedSources(source_name=package,
                status='Published', distro_series=distroseries, exact_match=True)[0]
            version = str(new_source.source_package_version)
            print "\t" + colored(str(package), 'white', attrs=['underline']) + " " + colored(version, 'green')
            package_versions.append((package, version))

        return package_versions

    def list_sru_workflow(self, review=False):
        workflow_tasks = self.workflow.searchTasks()
        for task in workflow_tasks:
            for subtask in task.related_tasks:
              if "kernel-sru-workflow/promote-to-" in subtask.bug_target_name:
                  if subtask.status == 'Confirmed' or subtask.status == 'In Progress':
                      bugno = str(subtask.bug.id)
                      status = str(subtask.status)
                      title = str(subtask.title)
                      task_type = str(title.split(' ')[6]).replace(':','').replace('"','').replace('promote-to-','->')
                      assignee = str(subtask.assignee.name)
                      packageset = str(title.split(' ')[7]).replace(':','').replace('"','')

                      # get series
                      series = '???'
                      tags = subtask.bug.tags
                      for tag in tags:
                          if tag in self.package_map.keys():
                              series = tag
                              break

                      # set colors
                      status_color = 'green' if status == 'In Progress' else 'red'
                      assignee_color = 'green' if assignee == 'arges' else 'red'

                      print colored("LP: #" + bugno, 'white',attrs=['bold','underline']) + " " + \
                          colored(status, status_color) + " " + \
                          colored(assignee, assignee_color) + " " + colored(task_type, 'green') + " " + \
                          colored(series, 'yellow') + " " + colored(packageset, 'yellow')

                      # list all source packages and versions
                      package_versions = self.list_ppa_packages(series, packageset)

                      # Check for review mode.
                      if review:
                          # Check if this is a proposed issue
                          if "kernel-sru-workflow/promote-to-proposed" in subtask.bug_target_name:
                              # Ask if we should review it?
                              print('Review this bug? '),
                              answer = raw_input().lower()
                              if answer in ('y','yes'):
                                  if status != 'In Progress' and assignee != 'arges':
                                      print('Assigning...')
                                      self.set_bug_state(bugno, "In Progress")
                                      print("%s assigned and set to: %s" %( bugno, "In Progress" ))
                                  print('Reviewing...')
                                  for package_version in package_versions:
                                      package = package_version[0]
                                      version = package_version[1]
                                      diff = self.get_diff(package, version, series)
                                      r.display_diff(diff)


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
        print("Usage:")
        print("       review")
        print("       promote <package-set> <series>")
        print("       release <bugno> <package> <series>")
        print("       finish <bugno> <package> <series> <pocket>")
        print("       status <pocket>")
        print("       list")
        exit(1)

if __name__ == "__main__":

    if len(sys.argv) <= 1:
        usage()

    elif sys.argv[1] == "review":
        r = ReviewSRUKernel()
        r.list_sru_workflow(review=True)
    elif sys.argv[1] == "promote":
        if len(sys.argv) != 4:
            usage()
        SET = sys.argv[2]
        SERIES = sys.argv[3]
        r = ReviewSRUKernel()
        r.promote_kernel_set(SET, SERIES)
    elif sys.argv[1] == "status":
        if len(sys.argv) != 3:
            usage()
        POCKET = sys.argv[2]
        r = ReviewSRUKernel()
        r.status(POCKET)
    elif sys.argv[1] == "release":
        if len(sys.argv) != 5:
            usage()
        BUGNO = sys.argv[2]
        SET = sys.argv[3]
        SERIES = sys.argv[4]
        r = ReviewSRUKernel()
        r.release(BUGNO, SET, SERIES)
    elif sys.argv[1] == "finish":
        if len(sys.argv) != 6:
            usage()
        BUGNO = sys.argv[2]
        SET = sys.argv[3]
        SERIES = sys.argv[4]
        POCKET = sys.argv[5]
        r = ReviewSRUKernel()
        r.finish(BUGNO, SET, SERIES, POCKET)
    elif sys.argv[1] == "list":
        r = ReviewSRUKernel()
        r.list_sru_workflow()
    else:
        usage()

