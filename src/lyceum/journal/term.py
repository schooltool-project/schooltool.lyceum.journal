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
Lyceum term grade content classes.

$Id$

"""
from BTrees.OOBTree import OOBTree
from persistent import Persistent

from zope.app.container.btree import BTreeContainer
from zope.interface import implements
from zope.location.interfaces import ILocation

from schooltool.app.interfaces import ISchoolToolApplication
from schooltool.app.app import InitBase

from lyceum.journal.interfaces import ITermGradingData


class LyceumTermDataContainer(BTreeContainer):
    """Container for person term grading data."""


class TermGradingData(Persistent):

    implements(ITermGradingData, ILocation)

    def __init__(self):
        self.__parent__ = None
        self.__name__ = None
        self.__data__ = OOBTree()

    @property
    def person(self):
        app = ISchoolToolApplication(None)
        persons = app['persons']
        return persons[self.__name__]

    def setGrade(self, course, term, grade):
        key = (course.__name__, term.__name__)
        self.__data__[key] = grade

    def getGrade(self, course, term, default=None):
        key = (course.__name__, term.__name__)
        return self.__data__.get(key, default)


def getPersonTermGradingData(person):
    app = ISchoolToolApplication(None)
    tc = app['lyceum.term_grades']

    # write on read
    tgd = tc.get(person.__name__, None)
    if tgd is None:
        tc[person.__name__] = tgd = TermGradingData()

    return tgd


class TermGradingDataInit(InitBase):

    def __call__(self):
        self.app['lyceum.term_grades'] = LyceumTermDataContainer()
