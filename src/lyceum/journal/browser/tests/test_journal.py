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

$Id$
"""
import unittest
from pytz import timezone
from pytz import utc
from datetime import datetime, date

from zope.app.testing import setup
from zope.component import provideAdapter
from zope.interface import implements
from zope.publisher.browser import TestRequest
from zope.testing import doctest
from zope.traversing.interfaces import IContainmentRoot
from zope.interface import directlyProvides
from zope.traversing.interfaces import IContainmentRoot


def doctest_today():
    """Test for today.

    Today returns the date of today, according to the application
    prefered timezone:

        >>> from lyceum.journal.browser.journal import today
        >>> from schooltool.app.interfaces import IApplicationPreferences
        >>> tz_name = "Europe/Vilnius"
        >>> class PrefStub(object):
        ...     @property
        ...     def timezone(self):
        ...         return tz_name

        >>> class STAppStub(dict):
        ...     def __init__(self, context):
        ...         pass
        ...     def __conform__(self, iface):
        ...         if iface == IApplicationPreferences:
        ...             return PrefStub()

        >>> from schooltool.app.interfaces import ISchoolToolApplication
        >>> provideAdapter(STAppStub, adapts=[None], provides=ISchoolToolApplication)

        >>> current_time = timezone('UTC').localize(datetime.utcnow())

        >>> tz_name = 'Pacific/Midway'
        >>> tz = timezone(tz_name)
        >>> today_date = current_time.astimezone(tz).date()
        >>> today() == today_date
        True

        >>> tz_name = 'Pacific/Funafuti'
        >>> tz = timezone('Pacific/Funafuti')
        >>> today_date = current_time.astimezone(tz).date()
        >>> today() == today_date
        True

    """


def doctest_JournalCalendarEventViewlet():
    """Tests for JournalCalendarEventViewlet.

        >>> from lyceum.journal.browser.journal import JournalCalendarEventViewlet
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

        >>> from schooltool.timetable.interfaces import ITimetableCalendarEvent
        >>> from lyceum.journal.interfaces import ISectionJournal
        >>> class JournalStub(object):
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

        >>> from lyceum.journal.browser.journal import PersonGradesColumn
        >>> column = PersonGradesColumn(meeting)
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

        >>> from lyceum.journal.browser.journal import PersonGradesColumn
        >>> column = PersonGradesColumn("meeting")
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

        >>> from lyceum.journal.browser.journal import PersonGradesColumn
        >>> class SectionJournalStub(object):
        ...     implements(IContainmentRoot)
        ...     def __init__(self):
        ...         self.__name__ = "section-journal"
        ...         self.__parent__ = None

        >>> from lyceum.journal.interfaces import ISectionJournal
        >>> class MeetingStub(object):
        ...     def __conform__(self, iface):
        ...         if iface == ISectionJournal:
        ...             return SectionJournalStub()

    Journal url is the url of the SectionJournal of the context
    meeting for this column:

        >>> meeting = MeetingStub()
        >>> column = PersonGradesColumn(meeting)
        >>> request = TestRequest()
        >>> column.journalUrl(request)
        'http://127.0.0.1/section-journal'

    """

def doctest_PersonGradesColumn_renderHeader():
    """Tests for PersonGradesColumn.renderHeader

        >>> from lyceum.journal.browser.journal import PersonGradesColumn
        >>> class MeetingStub(object):
        ...     pass
        >>> meeting = MeetingStub()
        >>> meeting.unique_id = 'unique-id-2006-01-01'
        >>> column = PersonGradesColumn(meeting)

        >>> class FormatterStub(object):
        ...     request = TestRequest()
        >>> formatter = FormatterStub()
        >>> column.meetingDate = lambda: date(2006, 1, 1)
        >>> column.today = lambda: date(2006, 1, 2)
        >>> column.journalUrl = lambda request: 'http://127.0.0.1/section-journal'
        >>> column.renderHeader(formatter)
        '<span title="2006-01-01"><a href="http://127.0.0.1/section-journal/index.html?event_id=unique-id-2006-01-01">01</a></span>'

        >>> column.selected = True
        >>> column.renderHeader(formatter)
        '<span title="2006-01-01">01</span>'

        >>> column.meetingDate = lambda: date(2006, 1, 2)
        >>> column.renderHeader(formatter)
        '<span class="today" title="2006-01-02">02</span>'

    """


def doctest_PersonGradesColumn_renderCell():
    """Tests for PersonGradesColumn.renderCell

        >>> from lyceum.journal.browser.journal import PersonGradesColumn
        >>> class MeetingStub(object):
        ...     pass
        >>> meeting = MeetingStub()
        >>> meeting.__name__ = 'unique-id-2006-01-01'
        >>> column = PersonGradesColumn(meeting)
        >>> column.getCellValue = lambda person: "%s 5" % person.__name__

        >>> class FormatterStub(object):
        ...     request = TestRequest()
        >>> formatter = FormatterStub()

        >>> class PersonStub(object):
        ...     def __init__(self):
        ...         self.__name__ = "John"

        >>> print column.renderCell(PersonStub(), formatter)
        John 5

        >>> column.selected = True
        >>> print column.renderCell(PersonStub(), formatter)
        <input type="text" style="width: 1.4em"
               name="John.unique-id-2006-01-01" value="John 5" />

    """

def doctest_SectionTermAverageGradesColumn_getGrades():
    """Tests for SectionTermAverageGradesColumn.getGrades

        >>> from lyceum.journal.browser.journal import SectionTermAverageGradesColumn
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
        >>> journal.meetings = lambda: []
        >>> column.getGrades(item)
        []

        >>> class MeetingStub(object):
        ...     def __init__(self, datetime, grade=None):
        ...         self.dtstart = datetime
        ...         self.grade = grade
        >>> journal.meetings = lambda: [MeetingStub(datetime(2006, 1, 1, 10, 15), 'n'),
        ...                             MeetingStub(datetime(2006, 1, 2, 10, 15), '4'),
        ...                             MeetingStub(datetime(2006, 1, 3, 10, 15)),
        ...                             MeetingStub(datetime(2006, 1, 4, 10, 15), " "),
        ...                             MeetingStub(datetime(2006, 2, 1, 10, 15), '3')]
        >>> column.getGrades(item)
        ['n', '4']

    """


def doctest_SectionTermAverageGradesColumn_renderCell_renderHeader():
    """Tests for SectionTermAverageGradesColumn renderCell and renderHeader

        >>> from lyceum.journal.browser.journal import SectionTermAverageGradesColumn
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

        >>> from lyceum.journal.browser.journal import SectionTermAttendanceColumn
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
        u'<span>Attendance</span>'

    """


def doctest_LyceumJournalView():
    """
    """


def doctest_JournalAbsoluteURL():
    """
    """


def doctest_JournalBreadcrumbs():
    """
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
