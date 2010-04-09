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
"""
from BTrees.OOBTree import OOBTree
from persistent import Persistent

from zope.viewlet.viewlet import CSSViewlet
from zope.security.proxy import removeSecurityProxy
from zope.intid.interfaces import IIntIds
from zope.container.btree import BTreeContainer
from zope.cachedescriptors.property import Lazy
from zope.component import getUtility
from zope.component import adapter
from zope.component import adapts
from zope.interface import implementer
from zope.interface import implements
from zope.location.interfaces import ILocation

from schooltool.timetable.interfaces import ITimetableCalendarEvent
from schooltool.app.app import InitBase, StartUpBase
from schooltool.app.interfaces import ISchoolToolApplication
from schooltool.app.interfaces import ISchoolToolCalendar
from schooltool.course.interfaces import ILearner
from schooltool.course.interfaces import ISection
from schooltool.person.interfaces import IPerson

from schooltool.lyceum.journal.interfaces import ISectionJournal
from schooltool.lyceum.journal.interfaces import ISectionJournalData

ABSENT = 'n' #n means absent in lithuanian
TARDY = 'p' #p means tardy in lithuanian


def student_sections(students):
    sections = set()
    for student in students:
        for section in student.groups:
            if ISection.providedBy(section):
                sections.add(section)
    return sections


def adjacent_sections(section):
    courses = section.courses
    instructors = section.instructors
    sections = set()
    sections.add(section)
    members = [member for member in section.members
               if IPerson.providedBy(member)]
    for section in student_sections(members):
        section = removeSecurityProxy(section)
        for course in section.courses:
            if course in courses:
                for instructor in section.instructors:
                    if instructor in instructors:
                        sections.add(section)
                        break
    return sections


class LyceumJournalContainer(BTreeContainer):
    """A container for all the journals in the system."""


@adapter(ISectionJournalData)
@implementer(ISection)
def getSectionForSectionJournalData(jd):
    int_ids = getUtility(IIntIds)
    return int_ids.getObject(int(jd.__name__))


@adapter(ISectionJournal)
@implementer(ISection)
def getSectionForSectionJournal(sj):
    return sj.section


class SectionJournalData(Persistent):
    """A journal for a section."""
    implements(ISectionJournalData, ILocation)

    def __init__(self):
        self.__parent__ = None
        self.__name__ = None
        self.__grade_data__ = OOBTree()
        self.__description_data__ = OOBTree()
        self.__attendance_data__ = OOBTree()

    @property
    def section(self):
        return ISection(self)

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

    def setAbsence(self, person, meeting, explained=True):
        key = (person.__name__, meeting.unique_id)
        attendance = self.__attendance_data__.get(key, ())
        self.__attendance_data__[key] = (explained,) + attendance

    def getAbsence(self, person, meeting, default=False):
        key = (person.__name__, meeting.unique_id)
        attendance = self.__attendance_data__.get(key, ())
        if not attendance:
            return default
        return attendance[0]

    def getDescription(self, meeting):
        return self.__description_data__.get(meeting.unique_id)

    def setDescription(self, meeting, description):
        self.__description_data__[meeting.unique_id] = description

    def recordedMeetingIds(self, person):
        for person_name, meeting_id in self.__grade_data__.keys():
            if person_name == person.__name__:
                yield meeting_id

    def recordedMeetings(self, person):
        calendar = ISchoolToolCalendar(self.section)
        for meeting_id in self.recordedMeetingIds(person):
            try:
                yield calendar.find(meeting_id)
            except KeyError:
                pass


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

    def setAbsence(self, person, meeting, explained=True):
        section_journal_data = ISectionJournalData(meeting.owner)
        section_journal_data.setAbsence(person, meeting, explained)

    def getAbsence(self, person, meeting, default=False):
        section_journal_data = ISectionJournalData(meeting.owner)
        return section_journal_data.getAbsence(person, meeting, default)

    def setDescription(self, meeting, description):
        section_journal_data = ISectionJournalData(meeting.owner)
        return section_journal_data.setDescription(meeting, description)

    def getDescription(self, meeting):
        section_journal_data = ISectionJournalData(meeting.owner)
        return section_journal_data.getDescription(meeting)

    @Lazy
    def members(self):
        return [member for member in self.section.members
                if IPerson.providedBy(member)]

    @Lazy
    def adjacent_sections(self):
        """Sections in the same course that share members and at least one
        teacher with this section."""
        return adjacent_sections(self.section)

    @Lazy
    def meetings(self):
        """Ordered list of all meetings for this and adjacent sections."""
        calendars = [ISchoolToolCalendar(section)
                     for section in self.adjacent_sections]
        events = []
        for calendar in calendars:
            for event in calendar:
                if ITimetableCalendarEvent.providedBy(event):
                    events.append(event)
        return sorted(events)

    def recordedMeetings(self, person):
        """Ordered list of all recorded meetings for this person.

        For this and adjacent sections.
        """
        meetings = []
        for section in self.adjacent_sections:
            sd = ISectionJournalData(section)
            meetings.extend(sd.recordedMeetings(person))
        return sorted(meetings)

    def hasMeeting(self, person, meeting):
        return meeting.activity.owner in ILearner(person).sections()
        return person in meeting.activity.owner.members

    def findMeeting(self, meeting_id):
        calendars = [ISchoolToolCalendar(section)
                     for section in self.adjacent_sections]
        for calendar in calendars:
            try:
                return calendar.find(meeting_id)
            except KeyError:
                pass
        raise KeyError("Could not find a meeting.")


def getSectionJournalData(section):
    """Get the journal for the section."""
    app = ISchoolToolApplication(None)
    jc = app['schooltool.lyceum.journal']

    int_ids = getUtility(IIntIds)
    journal_id = str(int_ids.getId(section))

    journal = jc.get(journal_id, None)
    if journal is None:
        jc[journal_id] = journal = SectionJournalData()

    return journal


def getEventSectionJournal(event):
    """Get the section journal for a TimetableCalendarEvent."""
    section = event.activity.owner
    return ISectionJournal(section)


class JournalInit(InitBase):

    def __call__(self):
        self.app['schooltool.lyceum.journal'] = LyceumJournalContainer()


class JournalAppStartup(StartUpBase):
    def __call__(self):
        if 'schooltool.lyceum.journal' not in self.app:
            self.app['schooltool.lyceum.journal'] = LyceumJournalContainer()


JournalCSSViewlet = CSSViewlet("journal.css")
