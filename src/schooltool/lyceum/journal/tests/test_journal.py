#
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
Unit tests for lyceum journal.
"""
import unittest, doctest
import datetime

from zope.component import adapter
from zope.component import provideAdapter
from zope.app.testing import setup
from zope.interface import implementer
from zope.interface import implements

from schooltool.course.interfaces import ISection
from schooltool.lyceum.journal.interfaces import ISectionJournalData


def doctest_SectionJournalData():
    """Tests for SectionJournalData

        >>> from schooltool.lyceum.journal.journal import SectionJournalData
        >>> journal = SectionJournalData()

        >>> class SectionStub(object):
        ...     pass
        >>> section = SectionStub()

        >>> @adapter(ISectionJournalData)
        ... @implementer(ISection)
        ... def getSection(jd):
        ...     return section


    Grades can be added for every person/meeting pair:

        >>> class PersonStub(object):
        ...     def __init__(self, name):
        ...         self.__name__ = name

        >>> class MeetingStub(object):
        ...     def __init__(self, uid, meeting_id=None,
        ...                  date=datetime.date(2011, 05, 05)):
        ...         self.dtstart = datetime.datetime(
        ...             date.year, date.month, date.day)
        ...         self.unique_id = uid
        ...         self.meeting_id = meeting_id

        >>> person1 = PersonStub('john')
        >>> person2 = PersonStub('pete')

        >>> meeting = MeetingStub('some-unique-id')

        >>> journal.setGrade(person1, meeting, "5")

    And are read that way too:

        >>> journal.getGrade(person1, meeting)
        '5'

    If there is no grade present in that position, you get None:

        >>> journal.getGrade(person2, meeting) is None
        True

    Unless default is provided:

        >>> journal.getGrade(person2, meeting, default="")
        ''

    Absences work in a very simmilar way:

        >>> journal.setAbsence(person1, meeting)

    If value was not provided, it defaults to True:

        >>> journal.getAbsence(person1, meeting)
        True

    Absences are treated as unexplained by default:

        >>> journal.getAbsence(person2, meeting)
        False

    Unless default is provided:

        >>> journal.getAbsence(person2, meeting, default=True)
        True

    Meetings can be shared:

        >>> meeting2 = MeetingStub('double-1', meeting_id='double-meeting')
        >>> meeting3 = MeetingStub('double-2', meeting_id='double-meeting')

        >>> print journal.getGrade(person1, meeting)
        5

        >>> print journal.getGrade(person1, meeting2)
        None

        >>> print journal.getGrade(person1, meeting3)
        None

        >>> journal.setGrade(person1, meeting2, "7")

        >>> print journal.getGrade(person1, meeting3)
        7

        >>> print journal.getGrade(person1, meeting)
        5

    """


def doctest_getSectionJournalData():
    """Tests for getSectionJournalData

        >>> from schooltool.lyceum.journal.journal import getSectionJournalData

        >>> from zope.container.btree import BTreeContainer
        >>> journal_container = BTreeContainer()
        >>> class STAppStub(dict):
        ...     def __init__(self, context):
        ...         self['schooltool.lyceum.journal'] = journal_container

        >>> from schooltool.app.interfaces import ISchoolToolApplication
        >>> provideAdapter(STAppStub, adapts=[None], provides=ISchoolToolApplication)

        >>> from zope.intid.interfaces import IIntIds
        >>> from zope.component import provideUtility
        >>> class FakeIntID(object):
        ...     implements(IIntIds)
        ...     def getId(self, object):
        ...         return id(object)
        >>> provideUtility(FakeIntID())

        >>> class SectionStub(object):
        ...     def __init__(self, name):
        ...         self.__name__ = name

        >>> section = SectionStub('some_section')

    Initially the journal container is empty, but if we try to get a
    journal for a section, a SectionJournalData objecgt is created:

        >>> journal = getSectionJournalData(section)
        >>> journal
        <schooltool.lyceum.journal.journal.SectionJournalData object at ...>

        >>> journal.__name__ == str(id(section))
        True

        >>> journal_container[str(id(section))] is journal
        True

    If we try to get the journal for the second time, we get the same
    journal instance:

        >>> getSectionJournalData(section) is journal
        True

    """


def doctest_SectionJournal():
    """Tests for SectionJournal adapter:

        >>> from schooltool.lyceum.journal.journal import SectionJournal
        >>> section = object()
        >>> sj = SectionJournal(section)
        >>> sj.section is section
        True

    The section you pass as an argument is set as a section attribute
    for the journal.

        >>> class SectionDataStub(object):
        ...     grade_data = {}
        ...     absence_data = {}
        ...     def setGrade(self, person, meeting, value):
        ...         self.grade_data[person, meeting] = value
        ...     def getGrade(self, person, meeting, default):
        ...         return self.grade_data.get((person, meeting), default)
        ...     def setAbsence(self, person, meeting, value):
        ...         self.absence_data[person, meeting] = value
        ...     def getAbsence(self, person, meeting, default):
        ...         return self.absence_data.get((person, meeting), default)
        >>> section_data = SectionDataStub()

        >>> class SectionStub(object):
        ...     def __conform__(self, iface):
        ...         return section_data

        >>> class CalendarStub(object):
        ...     def __init__(self, section):
        ...         self.__parent__ = section

        >>> class MeetingStub(object):
        ...     __parent__ = CalendarStub(SectionStub())
        >>> meeting = MeetingStub()

    The grades are stored in the section journal data of the section
    that "owns" the meeting:

        >>> sj.setGrade("john", meeting, 9)

        >>> sj.getGrade("john", meeting, default=0)
        9

    If there is no value set, the default is returned:

        >>> sj.getGrade("pete", meeting, default=0)
        0

    Absence information belongs in the journal data of the section too:

        >>> sj.setAbsence("john", meeting, True)

        >>> sj.getAbsence("john", meeting)
        True

    """


def doctest_SectionJournal_adjacent_sections():
    """Tests for SectionJournal.adjacent_sections:

        >>> from schooltool.lyceum.journal.journal import SectionJournal
        >>> from schooltool.course.interfaces import ISection
        >>> class SectionStub(object):
        ...     implements(ISection)
        ...     def __init__(self, name):
        ...         self.name = name
        ...     def __repr__(self):
        ...         return "<Section %s>" % self.name
        ...     def __cmp__(self, other):
        ...         return cmp(self.name, other.name)
        ...     courses = []
        ...     members = []
        ...     instructors = []
        >>> section = SectionStub("Math 1a")
        >>> section.courses = ["math"]
        >>> sj = SectionJournal(section)
        >>> sorted(sj.adjacent_sections)
        [<Section Math 1a>]

        >>> from schooltool.person.interfaces import IPerson
        >>> class PersonStub(object):
        ...     implements(IPerson)
        ...     groups = []
        >>> john = PersonStub()
        >>> pete = PersonStub()
        >>> teacher = PersonStub()
        >>> section.members = [john, pete, "something-else"]
        >>> section.instructors = [teacher]
        >>> sj = SectionJournal(section)
        >>> sorted(sj.adjacent_sections)
        [<Section Math 1a>]

        >>> sj = SectionJournal(section)
        >>> section2 = SectionStub("Math 1a A")
        >>> john.groups = [section2, "something-else"]
        >>> sorted(sj.adjacent_sections)
        [<Section Math 1a>]

        >>> sj = SectionJournal(section)
        >>> section2.courses = ["math"]
        >>> section2.instructors = [teacher]
        >>> sorted(sj.adjacent_sections)
        [<Section Math 1a>, <Section Math 1a A>]

        >>> sj = SectionJournal(section)
        >>> section2.courses = ["math", "history"]
        >>> section.courses = ["math", "history"]
        >>> sorted(sj.adjacent_sections)
        [<Section Math 1a>, <Section Math 1a A>]

        >>> sj = SectionJournal(section)
        >>> section3 = SectionStub("Math 1a B")
        >>> section3.courses = ["math"]
        >>> section3.instructors = [teacher]
        >>> pete.groups = [section3]
        >>> sorted(sj.adjacent_sections)
        [<Section Math 1a>, <Section Math 1a A>, <Section Math 1a B>]

    """


def doctest_SectionJournal_findMeeting():
    """Test for SectionJournal.findMeeting

        >>> from schooltool.lyceum.journal.journal import SectionJournal
        >>> from schooltool.app.interfaces import ISchoolToolCalendar
        >>> class SectionStub(object):
        ...     def __conform__(self, iface):
        ...         if iface == ISchoolToolCalendar:
        ...             return self.calendar
        >>> class CalendarStub(object):
        ...     events = []
        ...     def find(self, event_id):
        ...         if event_id in self.events:
        ...             return "<Event uid=%s>" % event_id
        ...         else:
        ...             raise KeyError("Event not found!")
        >>> section1 = SectionStub()
        >>> section1.calendar = CalendarStub()
        >>> section1.calendar.events = ["section-meeting"]
        >>> sj = SectionJournal(section1)
        >>> sj.adjacent_sections = [section1]

    If there is no such meeting, a key error is raised:

        >>> sj.findMeeting("some-meeting-id")
        Traceback (most recent call last):
        ...
        KeyError: 'Could not find a meeting.'

    But if we are looking for a meeting that belongs to the calendar
    of the context section, we should get it:

        >>> sj.findMeeting("section-meeting")
        '<Event uid=section-meeting>'

    If meeting belongs to some other section that is adjacent, we
    should still get it's instance:

        >>> section2 = SectionStub()
        >>> section2.calendar = CalendarStub()
        >>> section2.calendar.events = ["section2-meeting"]
        >>> sj.adjacent_sections = [section1, section2]

        >>> sj.findMeeting("section2-meeting")
        '<Event uid=section2-meeting>'

    """


def setUp(test):
    setup.placelessSetUp()


def tearDown(test):
    setup.placelessTearDown()


def test_suite():
    optionflags = doctest.NORMALIZE_WHITESPACE | doctest.ELLIPSIS
    return doctest.DocTestSuite(optionflags=optionflags,
                                setUp=setUp, tearDown=tearDown)


if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')
