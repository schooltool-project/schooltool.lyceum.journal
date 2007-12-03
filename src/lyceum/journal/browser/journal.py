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
Lyceum journal views.
"""
import pytz
import urllib
import base64
from datetime import datetime

from zope.exceptions.interfaces import UserError
from zope.publisher.browser import BrowserView
from zope.app import zapi
from zope.app.pagetemplate.viewpagetemplatefile import ViewPageTemplateFile
from zope.component import queryMultiAdapter
from zope.i18n import translate
from zope.i18n.interfaces.locales import ICollator
from zope.interface import implements
from zope.traversing.browser.absoluteurl import absoluteURL

from zc.table.column import GetterColumn
from zc.table.interfaces import IColumn
from zope.cachedescriptors.property import Lazy

from schooltool.app.browser.cal import month_names
from schooltool.app.interfaces import IApplicationPreferences
from schooltool.app.interfaces import ISchoolToolApplication
from schooltool.table.interfaces import ITableFormatter
from schooltool.table.table import LocaleAwareGetterColumn
from schooltool.timetable.interfaces import ITimetableCalendarEvent
from schooltool.timetable.interfaces import ITimetables
from schooltool.traverser.traverser import AdapterTraverserPlugin

from lyceum.journal.interfaces import ISectionJournal
from lyceum.journal.browser.interfaces import IIndependentColumn
from lyceum.journal.browser.interfaces import ISelectableColumn
from lyceum.journal.browser.table import SelectStudentCellFormatter
from lyceum.journal.browser.table import SelectableRowTableFormatter
from lyceum import LyceumMessage as _


def today():
    app = ISchoolToolApplication(None)
    tzinfo = pytz.timezone(IApplicationPreferences(app).timezone)
    dt = pytz.utc.localize(datetime.utcnow())
    return dt.astimezone(tzinfo).date()


class JournalCalendarEventViewlet(object):
    """Viewlet for section meeting calendar events.

    Adds an Attendance link to all section meeting events.
    """

    def attendanceLink(self):
        """Construct the URL for the attendance form for a section meeting.

        Returns None if the calendar event is not a section meeting event.
        """
        event_for_display = self.manager.event
        calendar_event = event_for_display.context
        journal = ISectionJournal(calendar_event, None)
        if journal:
            return '%s/index.html?event_id=%s' % (
                zapi.absoluteURL(journal, self.request),
                urllib.quote(event_for_display.context.unique_id.encode('utf-8')))


class GradeClassColumn(LocaleAwareGetterColumn):

    def getter(self, item, formatter):
        groups = ISchoolToolApplication(None)['groups']
        if item.gradeclass is not None:
            return groups[item.gradeclass].title
        return ""


class StudentNumberColumn(GetterColumn):

    def getter(self, item, formatter):
        person_name = '<input type="hidden" value="%s" class="person_id" />' % (
            urllib.quote(item.__name__))

        return str(formatter.row) + person_name

    def renderHeader(self, formatter):
        return '<span>%s</span>' % translate(_("Nr."),
                                             context=formatter.request)


class PersonGradesColumn(object):
    implements(IColumn, ISelectableColumn, IIndependentColumn)

    def __init__(self, meeting, journal, selected=False):
        self.meeting = meeting
        self.selected = selected
        self.journal = journal

    def today(self):
        return today()

    @property
    def name(self):
        return self.meeting.unique_id

    def meetingDate(self):
        app = ISchoolToolApplication(None)
        tzinfo = pytz.timezone(IApplicationPreferences(app).timezone)
        date = self.meeting.dtstart.astimezone(tzinfo).date()
        return date

    def extra_parameters(self, request):
        parameters = []
        for info in ['TERM', 'month', 'student']:
            if info in request:
                parameters.append((info, request[info].encode('utf-8')))
        return parameters

    def journalUrl(self, request):
        return absoluteURL(self.journal, request)

    def renderHeader(self, formatter):
        meetingDate = self.meetingDate()
        header = meetingDate.strftime("%d")

        today_class = ""
        if meetingDate == self.today():
            today_class = ' today'

        if not self.selected:
            url = "%s/index.html?%s" % (
                self.journalUrl(formatter.request),
                urllib.urlencode([('event_id', self.meeting.unique_id.encode('utf-8'))] +
                                 self.extra_parameters(formatter.request)))
            header = '<a href="%s">%s</a>' % (url, header)

        span = '<span class="select-column%s" title="%s">%s</span>' % (
            today_class, meetingDate.strftime("%Y-%m-%d"), header)
        event_id = '<input type="hidden" value="%s" class="event_id" />' % (
            urllib.quote(base64.encodestring(self.meeting.unique_id.encode('utf-8'))))
        return span + event_id

    def getCellValue(self, item):
        if self.hasMeeting(item):
            return self.journal.getGrade(item, self.meeting, default="")
        return "X"

    def hasMeeting(self, item):
        return self.journal.hasMeeting(item, self.meeting)

    def template(self, item, selected):
        value = self.getCellValue(item)
        name = "%s.%s" % (item.__name__, self.meeting.__name__)

        if not selected:
            return "<td>%s</td>" % str(value)
        else:
            klass = ' class="selected-column"'
            input = """<td%(class)s><input type="text" style="width: 1.4em"
                                           name="%(name)s"
                                           value="%(value)s" /></td>"""
            return input % {'class': klass, 'name':name, 'value':value}

    def renderSelectedCell(self, item, formatter):
        selected = self.hasMeeting(item)
        return self.template(item, selected)

    def renderCell(self, item, formatter):
        selected = self.selected and self.hasMeeting(item)
        return self.template(item, selected)


class SectionTermAverageGradesColumn(object):
    implements(IColumn)

    def __init__(self, journal, term):
        self.term = term
        self.name = term.__name__ + "average"
        self.journal = journal

    def getGrades(self, person):
        grades = []
        for meeting in self.journal.recordedMeetings(person):
            if meeting.dtstart.date() in self.term:
                grade = self.journal.getGrade(person, meeting, default=None)
                if (grade is not None) and (grade.strip() != ""):
                    grades.append(grade)
        return grades

    def renderCell(self, person, formatter):
        grades = []
        for grade in self.getGrades(person):
            try:
                grade = int(grade)
            except ValueError:
                continue
            grades.append(grade)
        if not grades:
            return ""
        else:
            return "%.3f" % (sum(grades) / float(len(grades)))

    def renderHeader(self, formatter):
        return '<span>%s</span>' % translate(_("Average"),
                                             context=formatter.request)


class SectionTermAttendanceColumn(SectionTermAverageGradesColumn):

    def __init__(self, journal, term):
        self.term = term
        self.name = term.__name__ + "attendance"
        self.journal = journal

    def renderCell(self, person, formatter):
        absences = 0
        for grade in self.getGrades(person):
            if (grade.strip().lower() == "n"):
                absences += 1

        if absences == 0:
            return ""
        else:
            return str(absences)

    def renderHeader(self, formatter):
        return '<span>%s</span>' % translate(_("Attendance"),
                                             context=formatter.request)


class LyceumSectionJournalView(object):

    template = ViewPageTemplateFile("templates/journal.pt")

    def __init__(self, context, request):
        self.context, self.request = context, request

    def __call__(self):
        if 'UPDATE_SUBMIT' in self.request:
            self.updateGradebook()

        app = ISchoolToolApplication(None)
        person_container = app['persons']
        self.gradebook = queryMultiAdapter((person_container, self.request),
                                           ITableFormatter)

        columns_before = [StudentNumberColumn(title=_('Nr'), name='nr')]

        all_classes = set()
        for member in self.members():
            all_classes.add(member.gradeclass)

        if len(all_classes) > 1:
            columns_before.append(GradeClassColumn(title=_('Class'), name='class'))

        self.gradebook.setUp(items=self.members(),
                             formatters=[SelectStudentCellFormatter(self.context)] * 2,
                             columns_before=columns_before,
                             columns_after=self.gradeColumns(),
                             table_formatter=self.formatterFactory,
                             batch_size=0)
        return self.template()

    def formatterFactory(self, *args, **kwargs):
        students = []
        if 'student' in self.request:
            student_id = self.request['student']
            app = ISchoolToolApplication(None)
            student = app['persons'].get(student_id)
            if student:
                students = [student]
        kwargs['selected_items'] = students
        return SelectableRowTableFormatter(*args, **kwargs)

    def allMeetings(self):
        term = self.getSelectedTerm()
        events = []
        # maybe expand would be better in here
        for event in self.context.meetings:
            if (ITimetableCalendarEvent.providedBy(event) and
                event.dtstart.date() in term):
                events.append(event)
        return sorted(events)

    def meetings(self):
        for event in self.allMeetings():
            if event.dtstart.date().month == self.active_month:
                yield event

    def members(self):
        members = list(self.context.members)
        collator = ICollator(self.request.locale)
        members.sort(key=lambda a: collator.key(a.first_name))
        members.sort(key=lambda a: collator.key(a.last_name))
        return members

    def updateGradebook(self):
        members = self.members()
        for meeting in self.meetings():
            for person in members:
                meeting_id = meeting.unique_id
                cell_id = "%s.%s" % (person.__name__, meeting.__name__)
                cell_value = self.request.get(cell_id, None)
                if cell_value is not None:
                    self.context.setGrade(person, meeting, cell_value)

    def gradeColumns(self):
        columns = []
        selected_meeting = self.selectedEvent()
        for meeting in self.meetings():
            selected = selected_meeting and selected_meeting == meeting
            columns.append(PersonGradesColumn(meeting, self.context,
                                              selected=selected))
        columns.append(SectionTermAverageGradesColumn(self.context,
                                                      self.getSelectedTerm()))
        columns.append(SectionTermAttendanceColumn(self.context,
                                                   self.getSelectedTerm()))
        return columns

    def getSelectedTerm(self):
        terms = ISchoolToolApplication(None)['terms']
        term_id = self.request.get('TERM', None)
        if term_id:
            term = terms[term_id]
            if term in self.scheduled_terms:
                return term

        return self.getCurrentTerm()

    def selectedEvent(self):
        event_id = self.request.get('event_id', None)
        if event_id is not None:
            try:
                return self.context.findMeeting(event_id)
            except KeyError:
                pass

    def selectedDate(self):
        event = self.selectedEvent()
        if event:
            app = ISchoolToolApplication(None)
            tzinfo = pytz.timezone(IApplicationPreferences(app).timezone)
            date = event.dtstart.astimezone(tzinfo).date()
            return date
        else:
            return today()

    def getCurrentTerm(self):
        event = self.selectedEvent()
        if event:
            terms = ISchoolToolApplication(None)['terms']
            term_id, schema_id = event.activity.timetable.__name__.split(".")
            return terms[term_id]
        return self.scheduled_terms[-1]

    @property
    def scheduled_terms(self):
        scheduled_terms = []
        terms = ISchoolToolApplication(None)['terms']
        tt = ITimetables(self.context.section).timetables
        for key in tt.keys():
            term_id, schema_id = key.split(".")
            scheduled_terms.append(terms[term_id])
        scheduled_terms.sort(key=lambda term: term.last)
        return scheduled_terms

    def monthsInSelectedTerm(self):
        month = -1
        for meeting in self.allMeetings():
            if meeting.dtstart.date().month != month:
                yield meeting.dtstart.date().month
                month = meeting.dtstart.date().month

    def monthTitle(self, number):
        return month_names[number]

    def monthURL(self, month_id):
        url = absoluteURL(self.context, self.request)
        url = "%s/index.html?%s" % (
            url,
            urllib.urlencode([('month', month_id)] +
                             self.extra_parameters(self.request)))
        return url

    @Lazy
    def active_year(self):
        event = self.selectedEvent()
        if event:
            return event.dtstart.year

        available_months = list(self.monthsInSelectedTerm())
        selected_month = None
        if 'month' in self.request:
            month = int(self.request['month'])
            if month in available_months:
                selected_month = month

        if not selected_month:
            selected_month = available_months[0]

        for meeting in self.allMeetings():
            if meeting.dtstart.date().month == selected_month:
                return meeting.dtstart.year

    @Lazy
    def active_month(self):
        available_months = list(self.monthsInSelectedTerm())
        if 'month' in self.request:
            month = int(self.request['month'])
            if month in available_months:
                return month

        term = self.getSelectedTerm()
        date = self.selectedDate()
        if term.first <= date <= term.last:
            month = date.month
            if month in available_months:
                return month

        return available_months[0]

    def extra_parameters(self, request):
        parameters = []
        for info in ['TERM', 'student']:
            if info in request:
                parameters.append((info, request[info].encode('utf-8')))
        return parameters


class SectionJournalAjaxView(BrowserView):

    def __call__(self):
        person_id = self.request['person_id']
        app = ISchoolToolApplication(None)
        person = app['persons'].get(person_id)
        if not person:
            raise UserError('Person was invalid!')
        meeting = self.context.findMeeting(base64.decodestring(urllib.unquote(self.request['event_id'])).decode("utf-8"))
        self.context.setGrade(person, meeting, self.request['grade']);
        return ""


LyceumJournalTraverserPlugin = AdapterTraverserPlugin(
    'journal', ISectionJournal)
