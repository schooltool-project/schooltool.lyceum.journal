#
# SchoolTool - common information systems platform for school administration
# Copyright (c) 2005 Shuttleworth Foundation
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
Functional tests for schooltool.level.

$Id: test_all.py 2922 2005-02-22 19:04:44Z mg $
"""
import unittest
from zope.testing import doctest
from zope.app.testing.functional import FunctionalDocFileSuite

from schooltool.testing import analyze
from schooltool.testing.functional import load_ftesting_zcml
from schooltool.testing.functional import collect_ftests


def test_suite():
    load_ftesting_zcml()
    optionflags = (doctest.ELLIPSIS | doctest.REPORT_NDIFF |
                   doctest.NORMALIZE_WHITESPACE |
                   doctest.REPORT_ONLY_FIRST_FAILURE)
    return FunctionalDocFileSuite(
        'README.txt', optionflags=optionflags,
        globs={'analyze': analyze})

if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')
