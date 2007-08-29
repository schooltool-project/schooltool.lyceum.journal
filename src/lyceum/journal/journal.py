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
Lyceum journal content classes.

$Id$

"""
from BTrees.OOBTree import OOBTree
from persistent import Persistent

from zope.app.container.btree import BTreeContainer
from zope.interface import implements
from zope.location.interfaces import ILocation
from zope.component import adapts

from schooltool.app.interfaces import ISchoolToolApplication
from schooltool.course.interfaces import ISection
from schooltool.app.app import InitBase

from lyceum.journal.interfaces import ISectionJournalData
from lyceum.journal.interfaces import ISectionJournal


class LyceumJournalContainer(BTreeContainer):
    """A container for all the journals in the system."""


class SectionJournalData(Persistent):
    """A journal for a section."""
    implements(ISectionJournalData, ILocation)

    def __init__(self):
        self.__parent__ = None
        self.__name__ = None
        self.__grade_data__ = OOBTree()

    @property
    def section(self):
        app = ISchoolToolApplication(None)
        sections = app['sections']
        return sections[self.__name__]

    def setGrade(self, person, meeting, grade):
        key = (person.__name__, meeting.unique_id)
        grades = self.__grade_data__.get(key, ())
        self.__grade_data__[key] = (grade,) + grades

    def getGrade(self, person, meeting, default=None):
        key = (person.__name__, meeting.unique_id)
        grades = self.__grade_data__.get(key, ())
        if not grades:
            return default
        return grades[0]


class SectionJournal(object):
    """Adapter that adapts a section to it's journal.

    Journal of a section might include grades from related sections as
    well.
    """

    implements(ISectionJournal)
    adapts(ISection)

    def __init__(self, context):
        self.__parent__ = context
        self.section = context
        self.__name__ = "journal"

    def setGrade(self, person, meeting, grade):
        section_journal_data = ISectionJournalData(meeting.owner)
        section_journal_data.setGrade(person, meeting, grade)

    def getGrade(self, person, meeting, default=None):
        section_journal_data = ISectionJournalData(meeting.owner)
        return section_journal_data.getGrade(person, meeting, default)


def getSectionJournalData(section):
    """Get the journal for the section."""
    app = ISchoolToolApplication(None)
    jc = app['lyceum.journal']
    journal = jc.get(section.__name__, None)
    if journal is None:
        jc[section.__name__] = journal = SectionJournalData()

    return journal


def getEventSectionJournal(event):
    """Get the section journal for a TimetableCalendarEvent."""
    section = event.activity.owner
    return ISectionJournal(section)


class JournalInit(InitBase):

    def __call__(self):
        self.app['lyceum.journal'] = LyceumJournalContainer()
