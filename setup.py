#!/usr/bin/env python
#
# SchoolTool - common information systems platform for school administration
# Copyright (c) 2005-2011 Shuttleworth Foundation,
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
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
"""
SchoolTool Lyceum Journal setup script.
"""

import os
from setuptools import setup, find_packages

if os.path.exists("version.txt"):
    version = open("version.txt").read().strip()
else:
    version = open("version.txt.in").read().strip()

def read(*rnames):
    text = open(os.path.join(os.path.dirname(__file__), *rnames)).read()
    return text

setup(
    name="schooltool.lyceum.journal",
    description="Attendance and class participation plugin for SchoolTool",
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
    classifiers=["Development Status :: 5 - Production/Stable",
    "Environment :: Web Environment",
    "Intended Audience :: End Users/Desktop",
    "License :: OSI Approved :: GNU General Public License (GPL)",
    "Operating System :: OS Independent",
    "Programming Language :: Python",
    "Programming Language :: Python :: 2.5",
    "Programming Language :: Python :: 2.6",
    "Programming Language :: Python :: 2.7",
    "Programming Language :: Zope",
    "Topic :: Education"],
    package_dir={'': 'src'},
    namespace_packages=["schooltool", "schooltool.lyceum"],
    packages=find_packages('src'),
    install_requires=['schooltool>=2.2',
                      'pytz',
                      'setuptools',
                      'zc.table',
                      'ZODB3',
                      'zope.browserpage>=3.10.1',
                      'zope.cachedescriptors',
                      'zope.component',
                      'zope.container',
                      'zope.exceptions',
                      'zope.formlib>=4',
                      'zope.i18n',
                      'zope.i18nmessageid',
                      'zope.interface',
                      'zope.intid',
                      'zope.location',
                      'zope.publisher',
                      'zope.security',
                      'zope.traversing',
                      'zope.viewlet'],
    extras_require={'test': ['zope.app.testing',
                             'zope.testing',
                             'zope.ucol',
                             'schooltool.devtools>=0.6',
                             'selenium']},
    include_package_data=True,
    zip_safe=False,
    entry_points="""
        [z3c.autoinclude.plugin]
        target = schooltool
        """,
    )
