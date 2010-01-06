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
import unittest
from pytz import utc
from datetime import datetime, date

from zope.app.testing import setup
from zope.component import provideAdapter
from zope.interface import implements
from zope.publisher.browser import TestRequest
from zope.testing import doctest
from zope.traversing.interfaces import IContainmentRoot
from zope.interface import directlyProvides


def doctest_SectionJournalJSView():
    """Tests for SectionJournalJSView.

        >>> from schooltool.lyceum.journal.browser.journal import SectionJournalJSView
        >>> view = SectionJournalJSView(object(), TestRequest())

    Test the JavaScript elements provided by grading_events method.

        >>> for event in view.grading_events():
        ...     print '%4s %s' % (event['grade_value'], event['js_condition'])
        'a'  event.which == 97 || event.which == 65
        't'  event.which == 116 || event.which == 84
        '1'  event.which == 49
        '2'  event.which == 50
        '3'  event.which == 51
        '4'  event.which == 52
        '5'  event.which == 53
        '6'  event.which == 54
        '7'  event.which == 55
        '8'  event.which == 56
        '9'  event.which == 57
        '10' event.which == 48

    """


def doctest_JournalCalendarEventViewlet():
    """Tests for JournalCalendarEventViewlet.

        >>> from schooltool.lyceum.journal.browser.journal import JournalCalendarEventViewlet
        >>> viewlet = JournalCalendarEventViewlet()

        >>> class ManagerStub(object):
        ...     pass
        >>> class EFDStub(object):
        ...     pass
        >>> class EventStub(object):
        ...     pass
        >>> manager = ManagerStub()
        >>> manager.event = EFDStub()
        >>> manager.event.context = EventStub()

    If the event is not adaptable to a journal, nothing is shown:

        >>> viewlet.manager = manager
        >>> viewlet.attendanceLink() is None
        True

    Though if it has a journal, you should get a URL for the journal
    with the event id passed as a parameter:

        >>> from zope.location.location import Location
        >>> from schooltool.timetable.interfaces import ITimetableCalendarEvent
        >>> from schooltool.lyceum.journal.interfaces import ISectionJournal
        >>> class JournalStub(Location):
        ...     __name__ = 'journal'

        >>> class TTEventStub(object):
        ...     implements(ITimetableCalendarEvent)
        ...     def __init__(self):
        ...         self.unique_id = "unique&id"
        ...     def __conform__(self, iface):
        ...         if iface == ISectionJournal:
        ...             journal = JournalStub()
        ...             journal.__parent__ = self
        ...             return journal

        >>> manager.event.context = TTEventStub()
        >>> viewlet.request = TestRequest()
        >>> directlyProvides(manager.event.context, IContainmentRoot)
        >>> viewlet.attendanceLink()
        'http://127.0.0.1/journal/index.html?event_id=unique%26id'

    """


def doctest_PersonGradesColumn_meetingDate():
    """Tests for PersonGradesColumn.meetingDate

    Let's set up an application and it's preferences:

        >>> from schooltool.app.interfaces import IApplicationPreferences
        >>> from schooltool.app.interfaces import ISchoolToolApplication
        >>> class PrefStub(object):
        ...     @property
        ...     def timezone(self):
        ...         return "Europe/Vilnius"

        >>> class STAppStub(dict):
        ...     def __init__(self, context):
        ...         pass
        ...     def __conform__(self, iface):
        ...         if iface == IApplicationPreferences:
        ...             return PrefStub()

        >>> provideAdapter(STAppStub, adapts=[None], provides=ISchoolToolApplication)

    And create a meeting:

        >>> class MeetingStub(object):
        ...     'Meeting Stub'
        >>> meeting = MeetingStub()
        >>> meeting.unique_id = "unique-id-2006-01-01"
        >>> meeting.dtstart = utc.localize(datetime(2006, 1, 1, 10, 15))

    Meeting date should be computed according to the timezone that is
    set in application preferences:

        >>> from schooltool.lyceum.journal.browser.journal import PersonGradesColumn
        >>> column = PersonGradesColumn(meeting, "journal")
        >>> column.meetingDate()
        datetime.date(2006, 1, 1)

    So if we shift it close ebough to the day boundary, we get the
    next day, because of the timezone difference:

        >>> meeting.dtstart = utc.localize(datetime(2006, 1, 1, 23, 15))
        >>> column.meetingDate()
        datetime.date(2006, 1, 2)

    """


def doctest_PersonGradesColumn_extra_parameters():
    """Tests for PersonGradesColumn.extra_parameters

    If there is not data in the request, extra parameter list is
    empty:

        >>> from schooltool.lyceum.journal.browser.journal import PersonGradesColumn
        >>> column = PersonGradesColumn("meeting", "journal")
        >>> request = TestRequest()
        >>> column.extra_parameters(request)
        []

    If we add TERM to the request, it will appear in the list of extra
    parameters:

        >>> request.form = {'TERM': '2006 Spring'}
        >>> column.extra_parameters(request)
        [('TERM', '2006 Spring')]

    As well as month:

        >>> request.form['month'] = 'July'
        >>> column.extra_parameters(request)
        [('TERM', '2006 Spring'),
         ('month', 'July')]

    Though parameters irrelevant to the person grades column will be
    ignored:

        >>> request.form['some-other-parameter'] = 'some-value'
        >>> column.extra_parameters(request)
        [('TERM', '2006 Spring'),
         ('month', 'July')]

    """


def doctest_PersonGradesColumn_journalUrl():
    """Tests for PersonGradesColumn.journalUrl

        >>> from schooltool.lyceum.journal.browser.journal import PersonGradesColumn
        >>> class SectionJournalStub(object):
        ...     implements(IContainmentRoot)
        ...     def __init__(self):
        ...         self.__name__ = "section-journal"
        ...         self.__parent__ = None

        >>> from schooltool.lyceum.journal.interfaces import ISectionJournal
        >>> class MeetingStub(object):
        ...     def __conform__(self, iface):
        ...         if iface == ISectionJournal:
        ...             return SectionJournalStub()

    Journal url is the url of the SectionJournal of the context
    meeting for this column:

        >>> meeting = MeetingStub()
        >>> column = PersonGradesColumn(meeting, SectionJournalStub())
        >>> request = TestRequest()
        >>> column.journalUrl(request)
        'http://127.0.0.1/section-journal'

    """


def doctest_PersonGradesColumn_renderHeader():
    """Tests for PersonGradesColumn.renderHeader

        >>> from schooltool.lyceum.journal.browser.journal import PersonGradesColumn
        >>> class MeetingStub(object):
        ...     pass
        >>> meeting = MeetingStub()
        >>> meeting.unique_id = 'unique-id-2006-01-01'
        >>> column = PersonGradesColumn(meeting, "journal")

        >>> class FormatterStub(object):
        ...     request = TestRequest()
        >>> formatter = FormatterStub()
        >>> column.meetingDate = lambda: date(2006, 1, 1)
        >>> column.today = lambda: date(2006, 1, 2)
        >>> column.journalUrl = lambda request: 'http://127.0.0.1/section-journal'
        >>> column.renderHeader(formatter)
        '<span class="select-column" title="2006-01-01"><a
           href="http://127.0.0.1/section-journal/index.html?event_id=unique-id-2006-01-01">01</a></span><input
              type="hidden" value="dW5pcXVlLWlkLTIwMDYtMDEtMDE%3D%0A" class="event_id" />'

        >>> column.selected = True
        >>> column.renderHeader(formatter)
        '<span class="select-column" title="2006-01-01">01</span><input
           type="hidden" value="dW5pcXVlLWlkLTIwMDYtMDEtMDE%3D%0A" class="event_id" />'

        >>> column.meetingDate = lambda: date(2006, 1, 2)
        >>> column.renderHeader(formatter)
        '<span class="select-column today" title="2006-01-02">02</span><input
           type="hidden" value="dW5pcXVlLWlkLTIwMDYtMDEtMDE%3D%0A" class="event_id" />'

    """


def doctest_PersonGradesColumn_renderCell_renderSelectedCell():
    """Tests for PersonGradesColumn.renderCell

        >>> from schooltool.lyceum.journal.browser.journal import PersonGradesColumn
        >>> class MeetingStub(object):
        ...     pass
        >>> has_meeting = True
        >>> class JournalStub(object):
        ...     def hasMeeting(self, student, meeting):
        ...         return has_meeting
        >>> meeting = MeetingStub()
        >>> meeting.__name__ = 'unique-id-2006-01-01'
        >>> column = PersonGradesColumn(meeting, JournalStub())
        >>> column.getCellValue = lambda person: "%s 5" % person.__name__

        >>> class FormatterStub(object):
        ...     request = TestRequest()
        >>> formatter = FormatterStub()

        >>> class PersonStub(object):
        ...     def __init__(self):
        ...         self.__name__ = "John"

    If there is a meeting for that date:

        >>> print column.renderCell(PersonStub(), formatter)
        <td>John 5</td>

        >>> column.selected = True
        >>> print column.renderCell(PersonStub(), formatter)
        <td class="selected-column"><input
               type="text" style="width: 1.4em"
               name="John.unique-id-2006-01-01" value="John 5" /></td>

        >>> column.selected = False
        >>> print column.renderSelectedCell(PersonStub(), formatter)
        <td class="selected-column"><input
              type="text" style="width: 1.4em"
              name="John.unique-id-2006-01-01" value="John 5" /></td>

    If there is no meeting:

        >>> column.getCellValue = lambda person: "X"
        >>> has_meeting = False
        >>> print column.renderCell(PersonStub(), formatter)
        <td>X</td>

        >>> column.selected = True
        >>> print column.renderCell(PersonStub(), formatter)
        <td>X</td>

        >>> column.selected = False
        >>> print column.renderSelectedCell(PersonStub(), formatter)
        <td>X</td>

    """


def doctest_SectionTermAverageGradesColumn_getGrades():
    """Tests for SectionTermAverageGradesColumn.getGrades

        >>> from schooltool.lyceum.journal.browser.journal import SectionTermAverageGradesColumn
        >>> class JournalStub(object):
        ...     def getGrade(self, person, meeting, default=None):
        ...         return meeting.grade or default
        >>> class TermStub(list):
        ...     __name__ = "2006-Spring"
        ...     def __init__(self):
        ...         self.append(date(2006, 1, 1))
        ...         self.append(date(2006, 1, 2))
        ...         self.append(date(2006, 1, 3))
        ...         self.append(date(2006, 1, 4))
        >>> journal = JournalStub()
        >>> term = TermStub()
        >>> column = SectionTermAverageGradesColumn(journal, term)
        >>> column.name
        '2006-Springaverage'
        >>> class PersonStub(object):
        ...     pass
        >>> item = PersonStub()
        >>> journal.recordedMeetings = lambda person: []
        >>> column.getGrades(item)
        []

        >>> class MeetingStub(object):
        ...     def __init__(self, datetime, grade=None):
        ...         self.dtstart = datetime
        ...         self.grade = grade
        >>> MS = MeetingStub
        >>> dt = datetime
        >>> journal.recordedMeetings = lambda person: [
        ...                                     MS(dt(2006, 1, 1, 10, 15), 'n'),
        ...                                     MS(dt(2006, 1, 2, 10, 15), '4'),
        ...                                     MS(dt(2006, 1, 3, 10, 15)),
        ...                                     MS(dt(2006, 1, 4, 10, 15), " "),
        ...                                     MS(dt(2006, 2, 1, 10, 15), '3')]
        >>> column.getGrades(item)
        ['n', '4']

    """


def doctest_SectionTermAverageGradesColumn_renderCell_renderHeader():
    """Tests for SectionTermAverageGradesColumn renderCell and renderHeader

        >>> from schooltool.lyceum.journal.browser.journal import SectionTermAverageGradesColumn
        >>> class TermStub(object):
        ...     __name__ = "2006-Spring"
        >>> column = SectionTermAverageGradesColumn("journal", TermStub())

        >>> column.getGrades = lambda person: ["1", "2", "n"]
        >>> column.renderCell("john", "formatter")
        '1.500'

        >>> class FormatterStub(object):
        ...     request = TestRequest()
        >>> column.renderHeader(FormatterStub())
        u'<span>Average</span>'

    """


def doctest_SectionTermAttendanceColumn_renderCell_renderHeader():
    """Tests for SectionTermAttendanceColumn renderCell and renderHeader

        >>> from schooltool.lyceum.journal.browser.journal import SectionTermAttendanceColumn
        >>> class TermStub(object):
        ...     __name__ = "2006-Spring"
        >>> column = SectionTermAttendanceColumn("journal", TermStub())

        >>> column.getGrades = lambda person: ["1", "2", "n"]
        >>> column.renderCell("john", "formatter")
        '1'

        >>> column.getGrades = lambda person: ["1", "n", "n", "N"]
        >>> column.renderCell("john", "formatter")
        '3'

        >>> class FormatterStub(object):
        ...     request = TestRequest()
        >>> column.renderHeader(FormatterStub())
        u'<span>Absences</span>'

    """

def doctest_StudentSelectionMixin():
    """Tests for StudentSelectionMixin.

        >>> from schooltool.lyceum.journal.browser.journal import StudentSelectionMixin

        >>> from schooltool.app.interfaces import IApplicationPreferences
        >>> from schooltool.app.interfaces import ISchoolToolApplication
        >>> class PrefStub(object):
        ...     @property
        ...     def timezone(self):
        ...         return "Europe/Vilnius"

        >>> class STAppStub(dict):
        ...     def __init__(self, context):
        ...         self['persons'] = {'stud1': '<John>', 'stud2': '<Bill>'}
        ...     def __conform__(self, iface):
        ...         if iface == IApplicationPreferences:
        ...             return PrefStub()

        >>> provideAdapter(STAppStub, adapts=[None], provides=ISchoolToolApplication)

    This mixin is intended for a view, so it has to have self.request.

        >>> mixin = StudentSelectionMixin()
        >>> mixin.request = {}

    No students are selected by default.

        >>> print mixin.selected_students
        None

        >>> mixin.selectStudents('table formatter')
        >>> print mixin.selected_students
        []

    If 'student' is set in the request, it gets selected.

        >>> mixin.request = {'student': 'stud2'}
        >>> mixin.selectStudents('table formatter')
        >>> print mixin.selected_students
        ['<Bill>']

    If an indexed table formatter is passed, selected students get indexed.

        >>> from schooltool.table.interfaces import IIndexedTableFormatter
        >>> class Formatter(object):
        ...     implements(IIndexedTableFormatter)
        ...     def indexItems(self, items):
        ...         return ['indexed %s' % i for i in items]

        >>> mixin.request = {'student': 'stud1'}
        >>> mixin.selectStudents(Formatter())
        >>> print mixin.selected_students
        ['indexed <John>']

    """


def doctest_LyceumSectionJournalView_getLegendItems():
    """Test for LyceumSectionJournalView.getLegendItems.

        >>> from schooltool.lyceum.journal.browser.journal import LyceumSectionJournalView

        >>> view = LyceumSectionJournalView(object(), TestRequest())

    List grade values, shortcut keys and descriptions for the grades.

        >>> for grade in view.getLegendItems():
        ...     print '%3s %6s %s' % (grade['value'], grade['keys'],
        ...                           grade['description'])
        a   a, A Absent
        t   t, T Tardy
        1      1
        2      2
        3      3
        4      4
        5      5
        6      6
        7      7
        8      8
        9      9
        10     0

    """


def doctest_LyceumSectionJournalView():
    """
    """


def doctest_JournalAbsoluteURL():
    """
    """


def doctest_JournalBreadcrumbs():
    """
    """


def doctest_SectionListView():
    """Test for the SectionListView

    SectionListView lists all the sections a person is teaching that
    are in the current term.

        >>> from schooltool.term.term import Term
        >>> from schooltool.term.tests import setUpDateManagerStub
        >>> term1 = Term("2001", date(2001, 1, 1), date(2001, 2, 1))
        >>> term2 = Term("2002", date(2002, 1, 1), date(2002, 2, 1))
        >>> setUpDateManagerStub(current_term=term1)

        >>> from zope.ucol.localeadapter import LocaleCollator
        >>> from zope.i18n.interfaces.locales import ICollator
        >>> from zope.component import provideAdapter
        >>> provideAdapter(LocaleCollator, adapts=[None], provides=ICollator)

        >>> from schooltool.lyceum.journal.browser.journal import SectionListView
        >>> view = SectionListView(None, TestRequest())

        >>> section_list = []
        >>> class InstructorStub(object):
        ...     def sections(self):
        ...         return section_list

        >>> terms = []
        >>> class TimetablesStub(object):
        ...     def __init__(self, terms):
        ...         self.terms = terms

        >>> from zope.traversing.interfaces import IContainmentRoot
        >>> class SectionStub(object):
        ...     implements(IContainmentRoot)
        ...     def __init__(self, name, terms):
        ...         self.terms = terms
        ...         self.__name__ = self.title = name
        ...     def __conform__(self, interface):
        ...         if interface == ITimetables:
        ...             return TimetablesStub(self.terms)

        >>> from schooltool.timetable.interfaces import ITimetables
        >>> from schooltool.course.interfaces import IInstructor
        >>> class TeacherStub(object):
        ...     def __conform__(self, interface):
        ...         if interface == IInstructor:
        ...             return InstructorStub()

    If the person is not related to any sections - it returns an empty
    list:

        >>> teacher = TeacherStub()
        >>> view.getSectionsForPerson(teacher)
        []

        >>> section_list = [SectionStub("section1", [term1]),
        ...                 SectionStub("section2", [term1, term2]),
        ...                 SectionStub("section3", [term2])]

    If there are sections associated with the teacher, only the
    sections in the current term will get returned:

        >>> view.getSectionsForPerson(teacher)
        [{'url': 'http://127.0.0.1/section1/journal/', 'title': 'section1'},
         {'url': 'http://127.0.0.1/section2/journal/', 'title': 'section2'}]

        >>> setUpDateManagerStub(current_term=term2)
        >>> view.getSectionsForPerson(teacher)
        [{'url': 'http://127.0.0.1/section2/journal/', 'title': 'section2'},
         {'url': 'http://127.0.0.1/section3/journal/', 'title': 'section3'}]

    If there is no current term - no sections will be returned:

        >>> setUpDateManagerStub(current_term=None)
        >>> view.getSectionsForPerson(teacher)
        []

    """


def setUp(test):
    setup.placelessSetUp()
    setup.setUpTraversal()


def tearDown(test):
    setup.placelessTearDown()


def test_suite():
    optionflags = doctest.NORMALIZE_WHITESPACE | doctest.ELLIPSIS
    return doctest.DocTestSuite(optionflags=optionflags,
                                setUp=setUp, tearDown=tearDown)


if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')
