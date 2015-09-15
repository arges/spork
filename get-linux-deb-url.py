#!/usr/bin/python
#
# get-linux-deb-url.py
#
# Copyright (C) 2015 Chris J Arges <chris.j.arges@canonical.com>
#

import sys
import subprocess
from launchpadlib.launchpad import Launchpad

class GetPackageLaunchpadURLQuery:
    build = None

    def __init__(self, arch, version, series):
        launchpad = Launchpad.login_anonymously('spork', 'production')
        ubuntu = launchpad.distributions["ubuntu"]

        self.main_archive = ubuntu.main_archive

        team = launchpad.people["canonical-kernel-team"]
        self.ppa = team.getPPAByName(name="ppa")

        self.arch = arch
        self.series = ubuntu.getSeries(name_or_version=series)
        self.archseries = self.series.getDistroArchSeries(archtag=self.arch)

        self.build = self.get_build(version)

        self.version = version
        self.abi = '.'.join(version.split('.')[0:3])


    def get_build(self, version):
        """ get build object for binary package from any appropriate archive """
        abi = '.'.join(version.split(".")[:3])
        binary_name="linux-image-%s-generic" % abi

        binaries = self.main_archive.getPublishedBinaries(
	    binary_name=binary_name, distro_arch_series=self.archseries,
            version=version, exact_match=True)
        if not binaries:
            binaries = self.ppa.getPublishedBinaries(
	        binary_name=binary_name, distro_arch_series=self.archseries,
                version=version, exact_match=True)
            if not binaries:
                print "%s %s not found." % (version, self.arch)
                exit(1)

        return binaries[0].build

    def get_base_url(self):
        return("%s/+files" % self.build.web_link)

    def get_dep_build(self, binary_name, version):
        return self.main_archive.getPublishedBinaries(
	    binary_name=binary_name, distro_arch_series=self.archseries,
            version=version, exact_match=True)

    def get_dep_packages(self):
        """ This function could probably be re-written. """
        build_log_url = self.build.build_log_url
        p1 = subprocess.Popen(["wget", "-qO-", build_log_url],
            stdout=subprocess.PIPE)
        p2 = subprocess.Popen(["zgrep", "Package versions"],
            stdin=p1.stdout, stdout=subprocess.PIPE)
        p1.stdout.close()
        package_versions = p2.communicate()[0].split(' ')
        p2.stdout.close()
        dep_package_versions = []
        for package in package_versions:
            if not 'Package' in package and not 'versions:' in package:
                dep_package_versions.append(package)

        # For each dep_package_version look it up and return the launchpad URL
        dep_package_urls = []
        for package in dep_package_versions:
            (binary_name, version) = package.split('_')
            try:
                build = self.get_dep_build(binary_name, version)[0].build
            except:
                continue

            arch = build.arch_tag
            f = lambda ver : version.split(':')[1] if ':' in version else version
            deb = "%s_%s_%s.deb" % (binary_name, f(version), arch)
            dep_package_urls.append("%s/+files/%s" % (build, deb))

        return ' '.join(dep_package_urls)

    def get_kernel_packages(self, base_url):
        return(' '.join([ "%s/linux-image-%s-generic_%s_%s.deb" %
                 (base_url, self.abi, self.version, self.arch),
                 "%s/linux-image-extra-%s-generic_%s_%s.deb" %
                 (base_url, self.abi, self.version, self.arch)
               ]))

    def get_kernel_debug_package(self, base_url):
        return("%s/linux-image-%s-generic-dbgsym_%s_%s.ddeb" %
               (base_url, self.abi, self.version, self.arch))

if __name__ == "__main__":
    if len(sys.argv) != 5:
        print("Usage: %s <version> <series> <arch> <set:kernel,debug,dep>" % sys.argv[0])
        exit(1)

    VERSION = sys.argv[1]
    SERIES = sys.argv[2]
    ARCH = sys.argv[3]
    PACKAGE_SET = sys.argv[4]

    q = GetPackageLaunchpadURLQuery(ARCH, VERSION, SERIES)
    base_url = q.get_base_url()

    if PACKAGE_SET == 'debug':
        print q.get_kernel_debug_package(base_url)
    elif PACKAGE_SET == 'kernel':
        print q.get_kernel_packages(base_url)
    elif PACKAGE_SET == 'dep':
        print q.get_dep_packages()
    else:
        print "Invalid set argument."
        exit(1)

    exit(0)
