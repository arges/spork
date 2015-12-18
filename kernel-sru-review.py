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

    def ask(self, message):
        print(message)
        answer = raw_input().lower()
        if answer in ('y','yes'):
            return True
        return False

    def set_bug_state(self, bugno, status, pocket='proposed'):
        bug = self.launchpad.bugs[bugno]
        for task in bug.bug_tasks:
              if task.bug_target_name == "kernel-sru-workflow/promote-to-%s" % pocket:
                  if task.status in ["Confirmed", "In Progress"]:
                      task.status = status
                      task.assignee = self.me
                      task.lp_save()

    def get_bug_state(self, bugno, workflow_task):
        bug = self.launchpad.bugs[bugno]
        for task in bug.bug_tasks:
              if task.bug_target_name == "kernel-sru-workflow/%s" % workflow_task:
                  return task.status
        return None

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

    def promote_kernel_set(self, bugno):

        (packageset, series, version) = self.extract_fields_from_bug(bugno)

        # Check if package_set is valid
        if packageset not in self.package_map[series]:
            print("Invalid package set: %s" % packageset)
            exit(1)

        # Get variables
        distroseries = self.ubuntu.getSeries(name_or_version=series)
        packages = self.package_map[series][packageset]
        print packages
        base_package = packages[0]


        # Copy everything over at once
        set_has_signed=False
        for package in packages:
            subprocess.Popen(["copy-proposed-kernel", series, package])
            if "signed" in package:
                set_has_signed=True

        # If there were no signed kernel then we are done
        if not set_has_signed:
            print("Copied all packages")
            return

        # Otherwise wait for uefi upload
        upload=None
        print version
        while True:
            # Wait some time for UEFI binary to become available

            # TODO detect the correct name here
            try:
                uploads = distroseries.getPackageUploads(status="Unapproved",
                    name="%s_%s" % (base_package, version))[0]
                for u in uploads:
                    print u
                print("do it manually")
                exit(1)
                break
            except:
                time.sleep(10)
                print("Waiting for UEFI binary...")

        upload.acceptFromQueue()
        print("Accepted UEFI binary!")
        print("Now wait a while...")
        exit(1)

        # Wait for linux/linux-meta to land in -proposed
        output = None
        while True:
            # Wait some time for linux / linux-meta to be published
            time.sleep(60)
            cmd = "rmadison -a source %s | grep %s-%s | grep %s" % ( base_package, series, 'proposed', version )
            try:
                output = subprocess.check_output([cmd], shell=True)
                print output
                break
            except:
                pass

            print("Waiting for %s %s %s to be published" % ( base_package, series, version ))

        print("%s %s %s is published!" % ( base_package, series, version ))

        print("Now re-try the signed build, and accept the new binary.")

        """
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
        """


    def release(self, bugno):
        (packageset, series, version) = self.extract_fields_from_bug(bugno)

        # Check if security needs to be updated
        security = True
        if self.get_bug_state(bugno, "Security-signoff") == "Invalid":
            security = False

        # Ask for confirmation
        print("LP: #%s %s %s -> %s-updates" % (bugno, packageset, version, series))
        if not self.ask("Release into updates? "):
            return

        # Assign to updates/security if necessary
        self.set_bug_state(bugno, "In Progress", "updates")
        if security:
            self.set_bug_state(bugno, "In Progress", "security")

        # Release the kernel!
        packages = self.package_map[series][packageset]
        cmd = ["sru-release", "--no-bugs", "--security", series]
        cmd.extend(packages)
        print(" ".join(cmd))
        subprocess.Popen(cmd)

    def finish(self, bugno, pocket="updates"):

        # Determine information.
        (packageset, series, version) = self.extract_fields_from_bug(bugno)

        # TODO: Check if any packages are not published

        # Get status
        status = ""
        packages = ' '.join(self.package_map[series][packageset])
        cmd = "rmadison -a source %s | grep %s-%s" % ( packages, series, pocket)
        try:
            status = subprocess.check_output([cmd], shell=True).rstrip("\n\r")
        except:
            print("Error getting status")
            exit(1)

        text = "Promoted to %s:\n%s" % (pocket.capitalize(), status)
        print text

        # Look good?
        if self.ask("Does this look correct? "):
            # Set bug states to Fix Released
            if pocket == "updates":
                self.set_bug_state(bugno, "Fix Released", "updates")
                self.set_bug_state(bugno, "Fix Released", "security")
            else:
                self.set_bug_state(bugno, "Fix Released", "proposed")

            # Set bug message
            self.add_bug_message(bugno, "Promoted to " + pocket.capitalize(), status)

        # Print output message
        wording = "released" if pocket == "updates" else "promoted"
        print("* LP: #%s - %s %s %s to %s-%s" % (bugno, wording, packageset, version, series, pocket))

    def list_ppa_packages(self, series, packageset, version):
        distroseries = self.ubuntu.getSeries(name_or_version=series)
        packages = self.package_map[series][packageset]
        abi = '.'.join(version.split('.')[:3])

        package_versions = []
        for package in packages:
	    sources = self.ppa.getPublishedSources(source_name=package,
                distro_series=distroseries)

            # Match version with source and correct status depending on package
            found_match = False
            for source in sources:
                source_version = str(source.source_package_version)
                source_status = str(source.status)
                if source_status in ['Published', 'Superseded']:
                    if '-meta' in package:
                        if abi.replace('-','.') in source_version:
                            found_match = True
                            break
                    else:
                        if version in source_version:
                            found_match = True
                            break
            if not found_match:
                print("Couldn't find %s %s %s in the PPA" % (packageset, series, abi))

            print "\t" + colored(str(package), 'white', attrs=['underline']) + " " + colored(source_version, 'green')
            package_versions.append((package, source_version))

        return package_versions

    def extract_fields_from_bug(self, bugno):
        bug = self.launchpad.bugs[bugno]
        title = bug.title

        packageset = str(title.split(' ')[0]).replace(':','').replace('"','')
        version = str(title.split(' ')[1])
        (series,) = set(bug.tags).intersection(self.package_map.keys())
        return (packageset, series, version)

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
                      (packageset, series, version) = self.extract_fields_from_bug(bugno)

                      # set colors
                      status_color = 'green' if status == 'In Progress' else 'red'
                      assignee_color = 'green' if assignee == 'arges' else 'red'

                      print colored("LP: #" + bugno, 'white',attrs=['bold','underline']) + " " + \
                          colored(status, status_color) + " " + \
                          colored(assignee, assignee_color) + " " + colored(task_type, 'green') + " " + \
                          colored(series, 'yellow') + " " + colored(packageset, 'yellow')

                      # list all source packages and versions
                      package_versions = self.list_ppa_packages(series, packageset, version)

                      # Check for review mode.
                      if review:
                          # Check if this is a proposed issue
                          if "kernel-sru-workflow/promote-to-proposed" in subtask.bug_target_name:
                              if self.ask('Review this bug? '):
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
        print("       promote <bugno>")
        print("       release <bugno>")
        print("       finish <bugno> <pocket>")
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
        if len(sys.argv) != 3:
            usage()
        BUGNO = sys.argv[2]
        r = ReviewSRUKernel()
        r.promote_kernel_set(BUGNO)
    elif sys.argv[1] == "status":
        if len(sys.argv) != 3:
            usage()
        POCKET = sys.argv[2]
        r = ReviewSRUKernel()
        r.status(POCKET)
    elif sys.argv[1] == "release":
        if len(sys.argv) != 3:
            usage()
        BUGNO = sys.argv[2]
        r = ReviewSRUKernel()
        r.release(BUGNO)
    elif sys.argv[1] == "finish":
        if len(sys.argv) != 4:
            usage()
        BUGNO = sys.argv[2]
        POCKET = sys.argv[3]
        r = ReviewSRUKernel()
        r.finish(BUGNO, POCKET)
    elif sys.argv[1] == "list":
        r = ReviewSRUKernel()
        r.list_sru_workflow()
    else:
        usage()

