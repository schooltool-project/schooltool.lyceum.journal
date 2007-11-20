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
Unit tests for lyceum.generations.evolve6
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
        self['sections'] = {}


def doctest_evolve():
    r"""Doctest for evolution to generation 6.

      >>> context = ContextStub()
      >>> context.root_folder['app'] = app = AppStub()

      >>> class CalendarStub(object):
      ...     def __init__(self, title):
      ...         self.title = title

      >>> from schooltool.app.interfaces import ISchoolToolCalendar
      >>> class SectionStub(object):
      ...     members = []
      ...     def __init__(self, title):
      ...         self.title = title
      ...         self.calendar = CalendarStub(title)
      ...     def __conform__(self, iface):
      ...         if iface == ISchoolToolCalendar:
      ...             return self.calendar

      >>> class CalendarOverlayStub(object):
      ...     def __init__(self, title, calendars):
      ...         self.title = title
      ...         self.calendars = calendars
      ...     def add(self, calendar):
      ...         print "Adding %s calendar to %s overlays" % (calendar.title, self.title)
      ...     def __contains__(self, calendar):
      ...         return calendar in self.calendars

      >>> from schooltool.person.interfaces import IPerson
      >>> class PersonStub(object):
      ...     implements(IPerson)
      ...     def __init__(self, title, calendars):
      ...         self.overlaid_calendars = CalendarOverlayStub(title, calendars)

    We have 2 sections - History and English:

      >>> app['sections']['history'] = history = SectionStub("History")
      >>> app['sections']['english'] = english = SectionStub("English")

    We have Pete and John, Pete already has History calendar in his
    overlays:

      >>> pete = PersonStub("Pete", [history.calendar])
      >>> john = PersonStub("John", [])

    Both Pete and John are in the History section, but only Pete is in
    the English section:

      >>> history.members = [pete, john]
      >>> english.members = [pete]

    Let's evolve now:

      >>> from lyceum.generations.evolve6 import evolve
      >>> evolve(context)
      Adding English calendar to Pete overlays
      Adding History calendar to John overlays

    As we can see only the overays that were missing were added back.

    """


def test_suite():
    return doctest.DocTestSuite(optionflags=doctest.ELLIPSIS
                                |doctest.REPORT_ONLY_FIRST_FAILURE)

if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')
