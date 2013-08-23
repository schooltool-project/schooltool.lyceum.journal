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
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
"""
Tests for generation scripts.
"""
import datetime

from persistent.interfaces import IPersistent

from zope.keyreference.interfaces import IKeyReference
from zope.app.publication.zopepublication import ZopePublication
from zope.app.testing.setup import setUpAnnotations
from zope.component import provideAdapter, provideUtility
from zope.interface import implements

from schooltool.app.app import SchoolToolApplication
from schooltool.term.interfaces import IDateManager


class ContextStub(object):
    """Stub for the context argument passed to evolve scripts.

        >>> from zope.app.generations.utility import getRootFolder
        >>> context = ContextStub()
        >>> getRootFolder(context) is context.root_folder
        True
    """

    class ConnectionStub(object):
        def __init__(self, root_folder):
            self.root_folder = root_folder
        def root(self):
            return {ZopePublication.root_name: self.root_folder}

    def __init__(self):
        self.root_folder = SchoolToolApplication()
        self.connection = self.ConnectionStub(self.root_folder)


_d = {}

class StupidKeyReference(object):
    implements(IKeyReference)
    key_type_id = 'StupidKeyReference'
    def __init__(self, ob):
        global _d
        self.id = id(ob)
        _d[self.id] = ob
    def __call__(self):
        return _d[self.id]
    def __hash__(self):
        return self.id
    def __cmp__(self, other):
        return cmp(hash(self), hash(other))


class DateManagerStub(object):
    implements(IDateManager)

    def __init__(self):
        self.current_term = None
        self.today = datetime.date(2011, 1, 23)


def provideAdapters():
    setUpAnnotations()
    provideAdapter(StupidKeyReference, [IPersistent], IKeyReference)


def provideUtilities():
    provideUtility(DateManagerStub(), IDateManager, '')

