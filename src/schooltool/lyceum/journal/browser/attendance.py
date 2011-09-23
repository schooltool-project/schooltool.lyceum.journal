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
Lyceum attendance views.
"""
from zope.browserpage.viewpagetemplatefile import ViewPageTemplateFile
from zope.cachedescriptors.property import CachedProperty
from zope.component import getUtility
from zope.component import queryMultiAdapter
from zope.i18n import translate
from zope.interface import implements
from zope.formlib.widget import quoteattr
from zope.cachedescriptors.property import Lazy
from zc.table.interfaces import IColumn

from schooltool.app.interfaces import ISchoolToolApplication
from schooltool.app.interfaces import ISchoolToolCalendar
from schooltool.common import parse_date
from schooltool.course.interfaces import ILearner
from schooltool.table.interfaces import ITableFormatter
from schooltool.term.interfaces import ITermContainer
from schooltool.term.interfaces import IDateManager

from schooltool.lyceum.journal.browser.interfaces import IIndependentColumn
from schooltool.lyceum.journal.browser.interfaces import ISelectableColumn
from schooltool.lyceum.journal.browser.journal import LyceumSectionJournalView
from schooltool.lyceum.journal.browser.table import viewURL
from schooltool.lyceum.journal.browser.table import SelectableRowTableFormatter
from schooltool.lyceum.journal.browser.table import SelectStudentCellFormatter
from schooltool.lyceum.journal.browser.journal import StudentSelectionMixin
from schooltool.lyceum.journal.interfaces import ISectionJournal

from schooltool.lyceum.journal import LyceumMessage as _


class AttendanceTableFormatter(SelectableRowTableFormatter):

    def renderSelectedCells(self, item):
        cells = ''.join([self.renderSelectedCell(item, col)
                         for col in self.visible_columns[1:]])
        return "<td>%s</td>%s" % (_("Explained:"), cells)

    def renderSelectedCell(self, item, column):
        sc = ISelectableColumn(column, None)
        if sc:
            return sc.renderSelectedCell(item, self)
        return '    <td%s></td>\n' % self._getCSSClass('td')

    def renderSelectedRow(self, item):
        row = self._renderRow(item)

        klass = self.cssClasses.get('tr', '')
        if klass:
            klass += ' '
        return row + '  <tr class=%s>\n%s  </tr>\n' % (
            quoteattr(klass + self.row_classes[self.row % 2]),
            self.renderSelectedCells(item))


class AttendanceSelectStudentCellFormatter(SelectStudentCellFormatter):

    def __call__(self, value, item, formatter):
        request = formatter.request
        parameters = [('student', item.__name__)] + self.extra_parameters(request)
        url = viewURL(self.context, request,
                      name='attendance.html',
                      parameters=parameters)
        return '<a href="%s">%s</a>' % (url, value)


class AttendanceColumn(object):

    implements(ISelectableColumn, IIndependentColumn)

    def __init__(self, group, date, meetings):
        self.meetings = meetings
        self.date = date
        self.group = group
        self.name = date.strftime("%y-%m-%d")

    def renderCell(self, student, formatter):
        absences = 0
        for meeting in self.meetings:
            journal = ISectionJournal(meeting)
            if journal.getGrade(student, meeting, default="") == "n":
                absences += 1
        if absences == 0:
            return '<td></td>'
        else:
            return '<td style="background-color: #FFDDDD;">%s</td>' % absences

    def extra_parameters(self, request):
        parameters = []
        for info in ['TERM', 'month', 'student']:
            if info in request:
                parameters.append((info, request[info]))
        return parameters

    def renderHeader(self, formatter):
        header = self.date.strftime("%d")

        parameters = [('date', self.date)] + self.extra_parameters(formatter.request)
        url = viewURL(self.group, formatter.request,
                      name='attendance.html',
                      parameters=parameters)
        header = '<a href="%s">%s</a>' % (url, header)

        return '<span title="%s">%s</span>' % (
            self.date.strftime("%Y-%m-%d"), header)

    def renderSelectedCell(self, student, formatter):
        absences = 0
        for meeting in self.meetings:
            journal = ISectionJournal(meeting)
            if journal.getGrade(student, meeting, default="") == "n":
                absences += 1

        name = student.__name__ + "." + self.date.strftime("%Y-%m-%d")
        value = True
        for meeting in self.meetings:
            calendar = meeting.__parent__
            owner = calendar.__parent__
            if student in owner.members:
                value = value and ISectionJournal(meeting).getAbsence(student, meeting)

        if absences == 0:
            return '<td></td>'
        else:
            cell_content = '<input type="checkbox" name="%s" %s />' % (name, value and 'checked="checked"' or '')
            if value:
                cell_content += '<input type="hidden" name="%s.marker" value="checked"/>' % name
            return '<td style="background-color: #FFDDDD;">%s</td>' % cell_content


class AttendanceTotalColumn(object):

    implements(IColumn, IIndependentColumn)

    def __init__(self, days):
        self.days = days
        self.name = "total"

    def renderCell(self, student, formatter):
        absences = 0
        for date, meetings in self.days.items():
            for meeting in meetings:
                journal = ISectionJournal(meeting)
                if journal.getGrade(student, meeting, default="") == "n":
                    absences += 1
        if absences == 0:
            return '<td></td>'
        else:
            return '<td>%s</td>' % str(absences)

    def renderHeader(self, formatter):
        return '<span>%s</span>' % translate(_("Total"), context=formatter.request)


class PeriodAttendanceColumn(object):

    implements(ISelectableColumn, IIndependentColumn)

    def __init__(self, meeting_id, meetings):
        self.meetings = meetings
        self.name = meeting_id

    def renderCell(self, student, formatter):
        absences = []
        for meeting in self.meetings:
            journal = ISectionJournal(meeting)
            if journal.getGrade(student, meeting, default="") == "n":
                absences.append(meeting)
        if absences == []:
            return '<td></td>'
        else:
            calendar = meeting.__parent__
            owner = calendar.__parent__
            absence_titles = [translate(owner.label, context=formatter.request)
                              for meeting in absences]
            return '<td style="background-color: #FFDDDD;">n</td>'

    def renderSelectedCell(self, student, formatter):
        absences = []
        for meeting in self.meetings:
            journal = ISectionJournal(meeting)
            if journal.getGrade(student, meeting, default="") == "n":
                absences.append(meeting)
        if absences == []:
            return '<td></td>'
        else:
            name = student.__name__ + "." + self.name
            value = False
            calendar = meeting.__parent__
            owner = calendar.__parent__
            for meeting in self.meetings:
                if student in owner.members:
                    value = value or ISectionJournal(meeting).getAbsence(student, meeting)
            absence_titles = [translate(owner.label, context=formatter.request)
                              for meeting in absences]
            cell_content = '<input type="checkbox" name="%s" %s />' % (name, value and 'checked="checked"' or '')
            if value:
                cell_content += '<input type="hidden" name="%s.marker" value="checked"/>' % name
            return '<td style="background-color: #FFDDDD;">%s</td>' % cell_content

    def renderHeader(self, formatter):
        return '<span>%s</span>' % self.name


class GroupAttendanceView(LyceumSectionJournalView, StudentSelectionMixin):
    """A view for a section journal."""

    template = ViewPageTemplateFile("templates/attendance.pt")

    @property
    def scheduled_terms(self):
        terms = ITermContainer(self.context)
        return sorted(terms.values(), key=lambda t: t.last)

    def monthsInSelectedTerm(self):
        month = -1
        for date, meetings in sorted(self.allDays.items()):
            if (date in self.getSelectedTerm() and
                date.month != month):
                yield date.month
                month = date.month

    def _setAbsence(self, student, meeting, id):
        calendar = meeting.__parent__
        owner = calendar.__parent__
        marker = id + ".marker"
        if id in self.request:
            if student in owner.members:
                ISectionJournal(meeting).setAbsence(student, meeting,
                                                    explained=True)
        elif marker in self.request:
            if student in owner.members:
                ISectionJournal(meeting).setAbsence(student, meeting,
                                                    explained=False)

    def updateDayAttendance(self, student):
        for meeting in self.allDays[self.selectedDate()]:
            id = student.__name__ + "." + meeting.meeting_id
            self._setAbsence(student, meeting, id)

    def updateMonthAttendance(self, student):
        for date, meetings in self.days():
            id = student.__name__ + "." + date.strftime("%Y-%m-%d")
            for meeting in meetings:
                self._setAbsence(student, meeting, id)

    def updateAttendance(self):
        student_id = self.request.get('student', None)
        student = None
        if student_id:
            app = ISchoolToolApplication(None)
            student = app['persons'].get(student_id)
        if student:
            if self.selectedDate():
                self.updateDayAttendance(student)
            else:
                self.updateMonthAttendance(student)

    def __call__(self):
        if 'UPDATE_SUBMIT' in self.request:
            self.updateAttendance()
        app = ISchoolToolApplication(None)
        person_container = app['persons']
        self.attendance_table = queryMultiAdapter((person_container, self.request),
                                                  ITableFormatter)
        self.selectStudents(self.attendance_table)
        self.attendance_table.setUp(items=self.context.members,
                                    formatters=[AttendanceSelectStudentCellFormatter(self.context)] * 2,
                                    columns_after=self.attendanceColumns(),
                                    batch_size=0,
                                    table_formatter=self.createAttendanceTableFormatter)
        return self.template()

    def createAttendanceTableFormatter(self, *args, **kwargs):
        kwargs['selected_items'] = self.selected_students
        return AttendanceTableFormatter(*args, **kwargs)

    @CachedProperty
    def allDays(self):
        students = list(self.context.members)
        sections = set()
        for person in students:
            for section in ILearner(person).sections():
                sections.add(section)
        calendars = [ISchoolToolCalendar(section)
                     for section in list(sections)]
        days = {}
        for calendar in calendars:
            for event in calendar:
                date = event.dtstart.date()
                days.setdefault(date, [])
                days[date].append(event)
        return days

    def days(self):
        for date, meetings in sorted(self.allDays.items()):
            if date.month == self.active_month:
                yield (date, meetings)

    def attendanceColumns(self):
        columns = []
        if self.selectedDate():
            for date, meetings in self.days():
                if date == self.selectedDate():
                    meetings = sorted(meetings)
                    periods = []
                    period = []
                    meeting_id = meetings[0].meeting_id
                    for meeting in meetings:
                        if meeting_id == meeting.meeting_id:
                            period.append(meeting)
                        else:
                            periods.append((meeting_id, period))
                            meeting_id = meeting.meeting_id
                            period = [meeting]
                    if period:
                        periods.append((meeting_id, period))
                    for meeting_id, meetings in periods:
                        columns.append(PeriodAttendanceColumn(meeting_id, meetings))
        else:
            for date, meetings in self.days():
                columns.append(AttendanceColumn(self.context, date, meetings))
            columns.append(AttendanceTotalColumn(self.allDays))
        return columns

    def getSelectedTerm(self):
        terms = ITermContainer(self.context)
        term_id = self.request.get('TERM', None)
        if term_id:
            term = terms[term_id]
            if term in self.scheduled_terms:
                return term

        return self.getCurrentTerm()

    def monthURL(self, month_id):
        parameters = [('month', month_id)] + self.extra_parameters(self.request)
        return viewURL(self.context, self.request,
                       name='attendance.html',
                       parameters=parameters)

    def selectedDate(self):
        str_date = self.request.get('date', None)
        if str_date:
            return parse_date(str_date)
        return None

    def getCurrentTerm(self):
        date = self.selectedDate()
        if not date:
            date = getUtility(IDateManager).today
        for term in self.scheduled_terms:
            if date in term:
                return term
        # should return last term closest to the selectedDate()
        return self.scheduled_terms[-1]

    @Lazy
    def active_month(self):
        available_months = list(self.monthsInSelectedTerm())
        if 'month' in self.request:
            month = int(self.request['month'])
            if month in available_months:
                return month

        term = self.getSelectedTerm()
        date = self.selectedDate()
        if not date:
            date = getUtility(IDateManager).today

        if term.first <= date <= term.last:
            month = date.month
            if month in available_months:
                return month

        if not available_months:
            return None

        return available_months[-1]
