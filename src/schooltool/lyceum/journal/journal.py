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

    def getKeys(self, person, meeting):
        key = (person.__name__, meeting.dtstart.date())
        entry_id = meeting.meeting_id
        if entry_id is None:
            entry_id = meeting.unique_id
        return (key, entry_id)

    def setGrade(self, person, meeting, grade):
        key, eid = self.getKeys(person, meeting)
        entries = dict(self.__grade_data__.get(key, ()))
        entries[eid] = (grade, ) + entries.get(eid, ())
        self.__grade_data__[key] = tuple(sorted(entries.items()))

    def getGrade(self, person, meeting, default=None):
        key, eid = self.getKeys(person, meeting)
        entries = dict(self.__grade_data__.get(key, ()))
        if not entries or not entries.get(eid):
            return default
        return entries.get(eid)[0]

    def setAbsence(self, person, meeting, explained=True):
        key, eid = self.getKeys(person, meeting)
        entries = dict(self.__attendance_data__.get(key, ()))
        entries[eid] = (explained, ) + entries.get(eid, ())
        self.__attendance_data__[key] = tuple(sorted(entries.items()))

    def getAbsence(self, person, meeting, default=False):
        key, eid = self.getKeys(person, meeting)
        entries = dict(self.__attendance_data__.get(key, ()))
        if not entries or not entries.get(eid):
            return default
        return entries.get(eid)[0]

    def descriptionKey(self, meeting):
        date = meeting.dtstart.date()
        entry_id = meeting.meeting_id
        if entry_id is None:
            entry_id = meeting.unique_id
        return (date, entry_id)

    def getDescription(self, meeting):
        key = self.descriptionKey(meeting)
        return self.__description_data__.get(key)

    def setDescription(self, meeting, description):
        key = self.descriptionKey(meeting)
        self.__description_data__[key] = description

    def recordedMeetingIds(self, person):
        for key in self.__grade_data__.keys():
            person_name, date = key
            if person_name == person.__name__:
                for meeting_id, grades in self.__grade_data__[key]:
                    yield meeting_id

    def recordedMeetings(self, person):
        recorded_ids = set(self.recordedMeetingIds(person))
        calendar = ISchoolToolCalendar(self.section)
        for event in calendar:
            if event.meeting_id in recorded_ids:
                yield event


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
        calendar = meeting.__parent__
        owner = calendar.__parent__
        section_journal_data = ISectionJournalData(owner)
        section_journal_data.setGrade(person, meeting, grade)

    def getGrade(self, person, meeting, default=None):
        calendar = meeting.__parent__
        owner = calendar.__parent__
        section_journal_data = ISectionJournalData(owner)
        return section_journal_data.getGrade(person, meeting, default)

    def setAbsence(self, person, meeting, explained=True):
        calendar = meeting.__parent__
        owner = calendar.__parent__
        section_journal_data = ISectionJournalData(owner)
        section_journal_data.setAbsence(person, meeting, explained)

    def getAbsence(self, person, meeting, default=False):
        calendar = meeting.__parent__
        owner = calendar.__parent__
        section_journal_data = ISectionJournalData(owner)
        return section_journal_data.getAbsence(person, meeting, default)

    def setDescription(self, meeting, description):
        calendar = meeting.__parent__
        owner = calendar.__parent__
        section_journal_data = ISectionJournalData(owner)
        return section_journal_data.setDescription(meeting, description)

    def getDescription(self, meeting):
        calendar = meeting.__parent__
        owner = calendar.__parent__
        section_journal_data = ISectionJournalData(owner)
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
        """Ordered list of all meetings for this and adjacent sections with
           consecutive periods removed if the timetable is so configured."""
        events = []
        unique_meetings = set()
        calendars = [ISchoolToolCalendar(section)
                     for section in self.adjacent_sections]
        for calendar in calendars:
            sorted_events = sorted(calendar, key=lambda e: e.dtstart)
            for event in sorted_events:
                if event.meeting_id not in unique_meetings:
                    events.append(event)
                    unique_meetings.add(event.meeting_id)
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
        calendar = meeting.__parent__
        owner = calendar.__parent__
        return owner in ILearner(person).sections()

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
    """Get the section journal for a ScheduleCalendarEvent."""
    calendar = event.__parent__
    section = calendar.__parent__
    return ISectionJournal(section)


class JournalInit(InitBase):

    def __call__(self):
        self.app['schooltool.lyceum.journal'] = LyceumJournalContainer()


class JournalAppStartup(StartUpBase):
    def __call__(self):
        if 'schooltool.lyceum.journal' not in self.app:
            self.app['schooltool.lyceum.journal'] = LyceumJournalContainer()


JournalCSSViewlet = CSSViewlet("journal.css")
