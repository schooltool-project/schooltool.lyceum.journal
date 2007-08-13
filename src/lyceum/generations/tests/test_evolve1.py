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
Unit tests for schooltool.generations.evolve1

$Id$
"""

import unittest

from zope.app.testing.setup import setUpAnnotations
from zope.annotation.interfaces import IAnnotatable
from zope.app.testing import setup
from zope.testing import doctest
from zope.interface import implements, directlyProvides
from zope.app.folder.folder import Folder
from zope.component.interfaces import IComponentLookup
from zope.app.intid.interfaces import IIntIds
from zope.app.catalog.interfaces import ICatalog
from schooltool.generations.tests.test_evolve17 import setUp, tearDown

from schooltool.generations.tests import ContextStub
from schooltool.app.interfaces import ISchoolToolApplication
from schooltool.demographics.person import Person


class AppStub(Folder):
    implements(ISchoolToolApplication, IAnnotatable)

    def __init__(self):
        super(AppStub, self).__init__()
        self['persons'] = {}

def doctest_evolve():
    r"""Doctest for evolution to generation 1.

      >>> context = ContextStub()
      >>> context.root_folder['app'] = app = AppStub()
      >>> dummy = setup.createSiteManager(app)
      >>> from lyceum.person.person import LyceumPerson
      >>> alpha = LyceumPerson('alpha', 'Alpha', 'Foo')
      >>> beta = LyceumPerson('alpha', 'Betha', 'Bar')
      >>> app['persons']['alpha'] = alpha
      >>> alpha.__name__ = 'alpha'
      >>> app['persons']['beta'] = beta
      >>> beta.__name__ = 'beta'

    Set the site:
      >>> from zope.app.component.hooks import setSite
      >>> setSite(app)

    Do the evolution:

      >>> from lyceum.generations.evolve1 import evolve
      >>> evolve(context)

    We expect the utilities to be installed:

      >>> from zope.component import getUtility
      >>> catalog = getUtility(ICatalog, 'lyceum.person')
      >>> ICatalog.providedBy(catalog)
      True

    We also expect things to be indexed. Let's check the indexes:

      >>> sorted(catalog['__name__'].documents_to_values.values())
      ['alpha', 'beta']
      >>> sorted(catalog['title'].documents_to_values.values())
      ['Bar Betha', 'Foo Alpha']

      >>> sorted(catalog['first_name'].documents_to_values.values())
      ['Alpha', 'Betha']

      >>> sorted(catalog['last_name'].documents_to_values.values())
      ['Bar', 'Foo']

    """

def test_suite():
    return doctest.DocTestSuite(setUp=setUp, tearDown=tearDown,
                                optionflags=doctest.ELLIPSIS
                                |doctest.REPORT_ONLY_FIRST_FAILURE)

if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')
