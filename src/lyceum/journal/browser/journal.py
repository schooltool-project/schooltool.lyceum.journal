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

$Id$

"""
import pytz
import urllib
from datetime import datetime

from zope.app import zapi
from zope.app.pagetemplate.viewpagetemplatefile import ViewPageTemplateFile
from zope.pagetemplate.pagetemplatefile import PageTemplateFile
from zope.component import queryMultiAdapter
from zope.i18n import translate
from zope.i18n.interfaces.locales import ICollator
from zope.interface import implements
from zope.traversing.browser.absoluteurl import absoluteURL

from zc.table.interfaces import IColumn
from zope.cachedescriptors.property import Lazy

from schooltool.app.browser.cal import month_names
from schooltool.app.interfaces import IApplicationPreferences
from schooltool.app.interfaces import ISchoolToolApplication
from schooltool.app.interfaces import ISchoolToolCalendar
from schooltool.person.interfaces import IPerson
from schooltool.table.interfaces import ITableFormatter
from schooltool.table.table import LocaleAwareGetterColumn
from schooltool.timetable.interfaces import ITimetableCalendarEvent
from schooltool.timetable.interfaces import ITimetables
from schooltool.traverser.traverser import AdapterTraverserPlugin

from lyceum.journal.interfaces import ISectionJournal
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
                urllib.quote(event_for_display.context.unique_id))


class GradeClassColumn(LocaleAwareGetterColumn):

    def getter(self, item, formatter):
        groups = ISchoolToolApplication(None)['groups']
        if item.gradeclass is not None:
            return groups[item.gradeclass].title
        return ""


class PersonGradesColumn(object):
    implements(IColumn)

    template = PageTemplateFile("templates/journal_grade_column.pt")

    def __init__(self, meeting, selected=False):
        self.meeting = meeting
        self.selected = selected

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
        for info in ['TERM', 'month']:
            if info in request:
                parameters.append((info, request[info]))
        return parameters

    def journalUrl(self, request):
        journal = ISectionJournal(self.meeting)
        return absoluteURL(journal, request)

    def renderHeader(self, formatter):
        meetingDate = self.meetingDate()
        header = meetingDate.strftime("%d")

        klass = ""
        if meetingDate == self.today():
            klass = 'class="today" '

        if not self.selected:
            url = "%s/index.html?%s" % (
                self.journalUrl(formatter.request),
                urllib.urlencode([('event_id', self.meeting.unique_id)] +
                                 self.extra_parameters(formatter.request)))
            header = '<a href="%s">%s</a>' % (url, header)

        return '<span %stitle="%s">%s</span>' % (
            klass, meetingDate.strftime("%Y-%m-%d"), header)

    def getCellValue(self, item):
        journal = ISectionJournal(self.meeting)
        return journal.getGrade(item, self.meeting, default="")

    def renderCell(self, item, formatter):
        value = self.getCellValue(item)
        name = "%s.%s" % (item.__name__, self.meeting.__name__)
        return self.template(value=value,
                             selected=self.selected,
                             name=name)


class SectionTermAverageGradesColumn(object):
    implements(IColumn)

    def __init__(self, journal, term):
        self.term = term
        self.name = term.__name__ + "average"
        self.journal = journal

    def getGrades(self, person):
        grades = []
        for meeting in self.journal.meetings():
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


class LyceumJournalView(object):

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
        self.gradebook.setUp(items=self.members(),
                             formatters=[SelectStudentCellFormatter(self.context)] * 2,
                             columns_before=[GradeClassColumn(title=_('Grade'), name='grade')],
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
        calendar = ISchoolToolCalendar(self.context.section)
        events = []
        # maybe expand would be better in here
        for event in calendar:
            if (ITimetableCalendarEvent.providedBy(event) and
                event.dtstart.date() in term):
                events.append(event)
        return sorted(events)

    def meetings(self):
        for event in self.allMeetings():
            if event.dtstart.date().month == self.active_month:
                yield event

    def members(self):
        members = [member for member in self.context.section.members
                   if IPerson.providedBy(member)]
        collator = ICollator(self.request.locale)
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
        for meeting in self.meetings():
            app = ISchoolToolApplication(None)
            tzinfo = pytz.timezone(IApplicationPreferences(app).timezone)
            meeting_date = meeting.dtstart.astimezone(tzinfo).date()
            selected = (meeting_date == self.selectedDate())
            columns.append(PersonGradesColumn(meeting, selected=selected))
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

    def selectedDate(self):
        event_id = self.request.get('event_id', None)
        if event_id is not None:
            calendar = ISchoolToolCalendar(self.context.section)
            event = calendar.find(event_id)
            app = ISchoolToolApplication(None)
            tzinfo = pytz.timezone(IApplicationPreferences(app).timezone)
            if event:
                date = event.dtstart.astimezone(tzinfo).date()
                return date

        return today()

    def getCurrentTerm(self):
        date = self.selectedDate()
        for term in self.scheduled_terms:
            if date in term:
                return term
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

    @property
    def section(self):
        return self.context.section

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
    def active_month(self):
        available_months = list(self.monthsInSelectedTerm())
        if 'month' in self.request:
            month = int(self.request['month'])
            if month in available_months:
                return month

        month = self.selectedDate().month
        if month in available_months:
            return month

        return available_months[0]

    def extra_parameters(self, request):
        parameters = []
        for info in ['TERM']:
            if info in request:
                parameters.append((info, request[info]))
        return parameters


LyceumJournalTraverserPlugin = AdapterTraverserPlugin(
    'journal', ISectionJournal)
