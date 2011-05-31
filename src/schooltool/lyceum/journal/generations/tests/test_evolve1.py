#
# SchoolTool - common information systems platform for school administration
# Copyright (c) 2011 Shuttleworth Foundation
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
Unit tests for schooltool.lyceum.journal.generations.evolve1
"""

import unittest, doctest

from zope.app.generations.utility import getRootFolder
from zope.app.testing import setup
from zope.site import LocalSiteManager

from schooltool.lyceum.journal.generations.tests import (
    ContextStub, provideAdapters, provideUtilities)
from schooltool.lyceum.journal.generations.evolve1 import (evolve,
    TERM_GRADES_KEY)


def doctest_evolve1():
    """Evolution to generation 1.

    First, we'll set up the app object:

        >>> context = ContextStub()
        >>> app = getRootFolder(context)
        >>> sm = LocalSiteManager(app)
        >>> app.setSiteManager(sm)

    We'll set up our test with data that will be effected by running the
    evolve script:

        >>> app[TERM_GRADES_KEY] = {}

    Finally, we'll run the evolve script, testing the effected values before and
    after:

        >>> TERM_GRADES_KEY in app
        True

        >>> evolve(context)

        >>> TERM_GRADES_KEY in app
        False

    """


def setUp(test):
    setup.placefulSetUp()
    setup.setUpTraversal()
    provideAdapters()
    provideUtilities()


def tearDown(test):
    setup.placefulTearDown()


def test_suite():
    optionflags = (doctest.ELLIPSIS |
                   doctest.NORMALIZE_WHITESPACE)
    return doctest.DocTestSuite(setUp=setUp, tearDown=tearDown,
                                optionflags=optionflags)


if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')

