#
# SchoolTool - common information systems platform for school administration
# Copyright (c) 2007 Shuttleworth Foundation
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
Unit tests for schooltool.generations.evolve4
"""

import unittest

from zope.annotation.interfaces import IAnnotatable
from zope.testing import doctest
from zope.app.folder.folder import Folder
from zope.interface import implements

from schooltool.generations.tests import ContextStub
from schooltool.app.interfaces import ISchoolToolApplication


class AppStub(Folder):
    implements(ISchoolToolApplication, IAnnotatable)

    def __init__(self):
        super(AppStub, self).__init__()
        self['lyceum.journal'] = {}


def doctest_evolve():
    r"""Doctest for evolution to generation 4.

      >>> context = ContextStub()
      >>> context.root_folder['app'] = app = AppStub()

      >>> class SectionJournalDataStub(object):
      ...     def setDescription(self, meeting_id, description):
      ...         self.__description_data__[meeting_id] = description
      ...     def getDescription(self, meeting_id):
      ...         return self.__description_data__[meeting_id]

      >>> sd1 = app['lyceum.journal']['section1'] = SectionJournalDataStub()
      >>> sd2 =app['lyceum.journal']['section2'] = SectionJournalDataStub()

    Do the evolution:

      >>> from lyceum.generations.evolve4 import evolve
      >>> evolve(context)

    The storage for lesson descriptions now works:

      >>> sd1.setDescription('m1', "Will do that!")
      >>> sd1.getDescription('m1')
      'Will do that!'

    """


def test_suite():
    return doctest.DocTestSuite(optionflags=doctest.ELLIPSIS
                                |doctest.REPORT_ONLY_FIRST_FAILURE)

if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')
