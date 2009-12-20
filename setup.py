#!/usr/bin/env python
#
# SchoolTool - common information systems platform for school administration
# Copyright (c) 2005    Shuttleworth Foundation,
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#
"""
SchoolTool Lyceum Journal setup script.
"""

import os, sys
from setuptools import setup, find_packages
from distutils import log
from distutils.util import newer
from distutils.spawn import find_executable

from glob import glob

def compile_translations(domain):
    "Compile *.po files to *.mo files"
    locales_dir = 'src/%s/locales' % (domain.replace('.', '/'))
    for po in glob('%s/*.po' % locales_dir):
        lang = os.path.basename(po)[:-3]
        mo = "%s/%s/LC_MESSAGES/%s.mo" % (locales_dir, lang, domain)
        if newer(po, mo):
            log.info('Compile: %s -> %s' % (po, mo))
            messages_dir = os.path.dirname(mo)
            if not os.path.isdir(messages_dir):
                os.makedirs(messages_dir)
            os.system('msgfmt -o %s %s' % (mo, po))

if len(sys.argv) > 1 and sys.argv[1] in ('build', 'install'):
    if not find_executable('msgfmt'):
        log.warn("GNU gettext msgfmt utility not found!")
        log.warn("Skip compiling po files.")
    else:
        compile_translations('schooltool.lyceum.journal')

if len(sys.argv) > 1 and sys.argv[1] == 'clean':
    for mo in glob('src/schooltool/lyceum/journal/locales/*/LC_MESSAGES/*.mo'):
        os.unlink(mo)
        os.removedirs(os.path.dirname(mo))

if os.path.exists("version.txt"):
    version = open("version.txt").read().strip()
else:
    version = open("version.txt.in").read().strip()

def read(*rnames):
    text = open(os.path.join(os.path.dirname(__file__), *rnames)).read()
    return text

setup(
    name="schooltool.lyceum.journal",
    description="An attendance and class participation journal",
    long_description=(
        read('README.txt')
        + '\n\n' +
        read('CHANGES.txt')
        ),
    version=version,
    url='http://www.schooltool.org',
    license="GPL",
    maintainer="SchoolTool Developers",
    maintainer_email="schooltool-developers@lists.launchpad.net",
    platforms=["any"],
    classifiers=["Development Status :: 4 - Beta",
    "Environment :: Web Environment",
    "Intended Audience :: End Users/Desktop",
    "License :: OSI Approved :: GNU General Public License (GPL)",
    "Operating System :: OS Independent",
    "Programming Language :: Python",
    "Programming Language :: Zope",
    "Topic :: Education",
    "Topic :: Office/Business :: Scheduling"],
    package_dir={'': 'src'},
    namespace_packages=["schooltool", "schooltool.lyceum"],
    packages=find_packages('src'),
    install_requires=['schooltool>1.2.0',
                      'setuptools'],
    tests_require=['zope.testing'],
    dependency_links=['http://ftp.schooltool.org/schooltool/1.2/'],
    include_package_data=True,
    zip_safe=False,
    entry_points="""
        [z3c.autoinclude.plugin]
        target = schooltool
        """,
    )
