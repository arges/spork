#!/usr/bin/python
#
# get-linux-deb-url - get linux related package URLs from launchpad
#
# Copyright (C) 2015, 2016 Chris J Arges <chris.j.arges@canonical.com>
#

import sys
import subprocess
import urllib2
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

        self.version = version
        self.flavor = "generic"
        self.abi = '.'.join(version.split('.')[0:3])

    def get_binaries(self, source_name, source_version, filename_filter):
        pub_sources = self.main_archive.getPublishedSources(
            distro_series=self.series,
            source_name=source_name,
            version=source_version, exact_match=True)
        if not pub_sources:
            print "%s %s not found." % (source_version, self.arch)
            exit(1)

        # Filter through URLs and create a flat list.
        ret = []
        for pub_source in pub_sources:
            urls = pub_source.binaryFileUrls()
            ret = ret + filter(lambda k: filename_filter in k, urls)

        # Just return the first element.
        return ret

    def check_url(self, url):
        try:
            urllib2.urlopen(url).headers.getheader('Content-Length')
        except urllib2.HTTPError:
            print("404 error checking url: " + url)
            return False
        return True

    def get_build_log_gcc_version(self):
        binary_name="linux-image-%s-generic" % self.abi
        binaries = self.main_archive.getPublishedBinaries(
            binary_name=binary_name, distro_arch_series=self.archseries,
            version=self.version, exact_match=True)
        build_log_url = binaries[0].build.build_log_url
        p1 = subprocess.Popen(["wget", "-qO-", build_log_url],
            stdout=subprocess.PIPE)
        p2 = subprocess.Popen(["zgrep", "Toolchain package versions"],
            stdin=p1.stdout, stdout=subprocess.PIPE)
        p1.stdout.close()
        package_versions = p2.communicate()[0]
        p2.stdout.close()
        gcc_package = filter(lambda x: 'gcc' in x, package_versions.split(' '))
        return gcc_package[0].split('_')[1]

    def get_gcc_version(self):
        # Try to get version from build log
        gcc_version = self.get_build_log_gcc_version()
        if gcc_version:
            return gcc_version

        # Use vmlinuz strings to get gcc version
        kernel_url = self.get_kernel_packages().split(' ')[0]
        cmd = "wget -q %s -O /tmp/deb && dpkg --fsys-tarfile /tmp/deb | " \
               % (kernel_url) + \
              "tar xOf - ./boot/vmlinuz-%s-%s > /tmp/vmlinuz ; " \
               % (self.abi, self.flavor) + \
              "strings /tmp/vmlinuz | grep 'gcc version' | cut -d '(' -f 4 | " + \
              "awk '{ print $2 }' | tr -d ')'"

        p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
        version = p.stdout.readlines()[0].strip()

        if not version:
            # Worst case we'll need to download the ddeb to get the version.
            debug_url = self.get_kernel_debug_package()
            cmd = "wget -q %s -O /tmp/ddeb && dpkg --fsys-tarfile /tmp/ddeb | " \
                   % (debug_url) + \
                   "tar xOf - ./usr/lib/debug/boot/vmlinux-%s-%s > /tmp/vmlinux; " \
                   % (self.abi, self.flavor) + \
	           "readelf -p .comment /tmp/vmlinux | grep GCC | tr -s ' ' | " + \
                   " cut -d ' ' -f6 | tr -d ')'"

            p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
            version = p.stdout.readlines()[0].strip()

        return version

    def get_gcc_package(self):
        # Grab gcc version from linux image
        version = self.get_gcc_version()

        # Find that source package upload and binaries produced by it.
        # TODO: ensure this works on other gcc- versions
        package = 'gcc-' + version.split('.')[0]
        filename = package + "_%s_%s.deb" % (version, self.arch)
        url = self.get_binaries(package, version, filename)[0]

        return url

    def get_kernel_packages(self):
        filenames = [ "linux-image-%s-generic_%s_%s.deb" % \
                 (self.abi, self.version, self.arch), \
                 "linux-image-extra-%s-generic_%s_%s.deb" % \
                 (self.abi, self.version, self.arch) ]

        urls = []
        urls.append(self.get_binaries('linux', self.version, filenames[0])[0])
        if not self.check_url(urls[0]):
            return None

        urls.append(self.get_binaries('linux', self.version, filenames[1])[0])
        if not self.check_url(urls[1]):
            return None

        return(' '.join(urls))

    def get_kernel_debug_package(self):
        filename = "linux-image-%s-generic-dbgsym_%s_%s.ddeb" % \
                   (self.abi, self.version, self.arch)

	try:
            url = self.get_binaries('linux', self.version, filename)[0]
            if url and self.check_url(url):
                return(url)
        except:
            print("Couldn't find debug package.")

        return None

if __name__ == "__main__":
    if len(sys.argv) != 5:
        print("Usage: %s <version> <series> <arch> " % sys.argv[0] + \
              "<type:kernel,debug,gcc,gcc_version>")
        exit(1)

    VERSION = sys.argv[1]
    SERIES = sys.argv[2]
    ARCH = sys.argv[3]
    QUERY_TYPE = sys.argv[4]

    q = GetPackageLaunchpadURLQuery(ARCH, VERSION, SERIES)

    if QUERY_TYPE == 'debug':
        print q.get_kernel_debug_package()
    elif QUERY_TYPE == 'kernel':
        print q.get_kernel_packages()
    elif QUERY_TYPE == 'gcc':
        print q.get_gcc_package()
    elif QUERY_TYPE == 'gcc_version':
        print q.get_gcc_version()
    else:
        print "Invalid set argument."
        exit(1)

    exit(0)
