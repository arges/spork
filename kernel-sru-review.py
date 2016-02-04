#!/usr/bin/python
#
# Kernel SRU Review Tool
#
# Copyright (C) 2015, 2016 Chris J Arges <chris.j.arges@canonical.com>
#

from launchpadlib.launchpad import Launchpad
from termcolor import colored
import argparse
import pydoc
import subprocess
import sys
import time

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

    def __init__(self, args):
        self.launchpad = Launchpad.login_with("spork", "production", version="devel")
        self.ubuntu = self.launchpad.distributions["ubuntu"]
        self.workflow = self.launchpad.projects["kernel-sru-workflow"]
        self.me = self.launchpad.me
        team = self.launchpad.people["canonical-kernel-team"]
        self.ppa = team.getPPAByName(name="ppa")
        self.archive = self.ubuntu.main_archive
        self.args = args

    def ask(self, message):
        if self.args.yes:
            return True

        print colored(message,'red')
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

    def get_diff(self, package_name, version, series):
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
            if self.args.manual:
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

    def promote_kernel_set(self, bugnos):
        for bugno in bugnos:
            (packageset, series, version) = self.extract_fields_from_bug(bugno)

            # Check if package_set is valid
            if packageset not in self.package_map[series]:
                print("Invalid package set: %s" % packageset)
                exit(1)

            # Get variables
            distroseries = self.ubuntu.getSeries(name_or_version=series)
            packages = self.package_map[series][packageset]
            base_package = packages[0]

            # Ask for confirmation
            print("LP: #%s %s %s -> %s-proposed" % (bugno, packageset, version, series))
            if not self.ask("Accept into proposed? "):
                return

            # Copy everything over at once
            set_has_signed=False
            for package in packages:
                output = None
                cmd = ["copy-proposed-kernel", series, package]
                print("Calling: " + ' '.join(cmd))
                subprocess.Popen(cmd)

                if "signed" in package:
                    set_has_signed=True

            # Process UEFI stuff
            if set_has_signed:
                upload=None
                while True:
                    # Wait some time for UEFI binary to become available
                    upload = distroseries.getPackageUploads(status="Unapproved", \
                        name="%s_%s_amd64.tar.gz" % (base_package, version), exact_match=True)
                    if len(upload) > 1:
                        print("Something when wrong, UEFI binary not unique.")
                        exit(1)
                    elif len(upload) == 1:
                        break

                    print("Waiting for UEFI binary...")
                    time.sleep(10)

                upload[0].acceptFromQueue()
                print("Accepted UEFI binary!")

            print("Copied all packages")

    def release(self, bugnos):
        for bugno in bugnos:
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
            if security:
                cmd = ["sru-release", "--no-bugs", "--security", series]
            else:
                cmd = ["sru-release", "--no-bugs", series]

            cmd.extend(packages)
            print(" ".join(cmd))
            subprocess.Popen(cmd)

    def finish(self, bugnos, pocket="updates"):
        for bugno in bugnos:
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
        bugnos = []
        workflow_tasks = self.workflow.searchTasks()
        for task in workflow_tasks:
            for subtask in task.related_tasks:
              if "kernel-sru-workflow/promote-to-" in subtask.bug_target_name:
                  if subtask.status == 'Confirmed' or subtask.status == 'In Progress':

                      bugno = str(subtask.bug.id)
                      bugnos.append(bugno)
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

        print("Listed bugs: " + ' '.join(list(set(bugnos))))


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

def parse():
    parser = argparse.ArgumentParser(description='Kernel SRU Review Tool')
    parser.add_argument('--yes','-y', action='store_true')
    parser.add_argument('--verbose','-v', action='store_true')
    parser.add_argument('--manual','-m', action='store_true')
    subparsers = parser.add_subparsers(dest='command')
    review_parser = subparsers.add_parser('review')
    list_parser = subparsers.add_parser('list')
    promote_parser = subparsers.add_parser('promote')
    promote_parser.add_argument("bug_numbers", nargs='+', type=int)
    release_parser = subparsers.add_parser('release')
    release_parser.add_argument("bug_numbers", nargs='+', type=int)
    finish_parser = subparsers.add_parser('finish')
    finish_parser.add_argument("bug_numbers", nargs='+', type=int)
    finish_parser.add_argument("pocket", default="proposed")
    status_parser = subparsers.add_parser('status')
    status_parser.add_argument("pocket", default="proposed")
    args = parser.parse_args()
    return args

if __name__ == "__main__":
    args = parse()
    if args.command == "review":
        r = ReviewSRUKernel(args)
        r.list_sru_workflow(review=True)
    elif args.command == "promote":
        r = ReviewSRUKernel(args)
        r.promote_kernel_set(args.bug_numbers)
    elif args.command == "status":
        r = ReviewSRUKernel(args)
        r.status(args.pocket)
    elif args.command == "release":
        r = ReviewSRUKernel(args)
        r.release(args.bug_numbers)
    elif args.command == "finish":
        r = ReviewSRUKernel(args)
        r.finish(args.bug_numbers, args.pocket)
    elif args.command == "list":
        r = ReviewSRUKernel(args)
        r.list_sru_workflow()
