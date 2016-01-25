#!/usr/bin/python
#
# get-linux-deb-url.py
#
# Copyright (C) 2015 Chris J Arges <chris.j.arges@canonical.com>
#

import sys
import subprocess
import urllib2
from HTMLParser import HTMLParser
from launchpadlib.launchpad import Launchpad

class LaunchpadWebpageDDEBParser(HTMLParser):
    found = False
    done = False

    def handle_starttag(self, tag, attrs):
        if tag == 'div':
            for attr in attrs:
                if attr == ('id', 'downloadable-files'):
                    self.found = True

        if self.found and tag == 'a':
            for attr in attrs:
                if attr[0] == 'href':
                     self.url = attr[1]
                     self.done = True

    def handle_endtag(self, tag):
        self.found = False

    def get_url(self):
        return self.url

class GetPackageLaunchpadURLQuery:
    build = None

    def __init__(self, arch, version, series, flavor='generic'):
        self.arch = arch
        self.series = series
        self.version = version
        self.abi = '.'.join(version.split('.')[0:3])
        self.flavor = flavor

    def scrape_kernel_file(self, source_pkg_name):
        url = "https://launchpad.net/ubuntu/" + str(self.series) + "/" + \
              str(self.arch) + "/" + source_pkg_name + "/" + str(self.version)
        html = urllib2.urlopen(url).read()
        parser = LaunchpadWebpageDDEBParser()
        parser.feed(html)
        return parser.get_url()

    def test_file(self, url):
        try:
            urllib2.urlopen(url).headers.getheader('Content-Length')
        except urllib2.HTTPError:
            print("404 error testing if %s exists.", url)
            return False
        return True

    def get_kernel_debug_package(self):
        source_pkg_name = "linux-image-%s-generic-dbgsym" % (self.abi)
        url = self.scrape_kernel_file(source_pkg_name)
        if self.test_file(url):
            return(url)

    def get_kernel_packages(self):
        urls = []

        source_pkg_name = "linux-image-%s-generic" % (self.abi)
        url = self.scrape_kernel_file(source_pkg_name)
        if self.test_file(url):
            urls.append(url)

        source_pkg_name = "linux-image-extra-%s-generic" % (self.abi)
        url = self.scrape_kernel_file(source_pkg_name)
        if self.test_file(url):
            urls.append(url)

        return urls

if __name__ == "__main__":
    if len(sys.argv) != 5:
        print("Usage: %s <version> <series> <arch> <set:kernel,debug>" % sys.argv[0])
        exit(1)

    VERSION = sys.argv[1]
    SERIES = sys.argv[2]
    ARCH = sys.argv[3]
    PACKAGE_SET = sys.argv[4]

    q = GetPackageLaunchpadURLQuery(ARCH, VERSION, SERIES)

    if PACKAGE_SET == 'debug':
        print q.get_kernel_debug_package()
    elif PACKAGE_SET == 'kernel':
        print q.get_kernel_packages()
    else:
        print "Invalid set argument."
        exit(1)

    exit(0)
