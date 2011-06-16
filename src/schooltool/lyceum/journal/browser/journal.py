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

from zope.security.proxy import removeSecurityProxy
from zope.viewlet.interfaces import IViewlet
from zope.exceptions.interfaces import UserError
from zope.publisher.browser import BrowserView
from zope.browserpage.viewpagetemplatefile import ViewPageTemplateFile
from zope.app.form.browser.widget import quoteattr
from zope.component import queryMultiAdapter
from zope.i18n import translate
from zope.i18n.interfaces.locales import ICollator
from zope.interface import implements
from zope.traversing.browser.absoluteurl import absoluteURL
from zope.component import getUtility

from zc.table.column import GetterColumn
from zc.table.interfaces import IColumn
from zope.cachedescriptors.property import Lazy

import schooltool.skin.flourish.page
from schooltool.course.interfaces import ILearner, IInstructor
from schooltool.person.interfaces import IPerson
from schooltool.app.browser.cal import month_names
from schooltool.app.interfaces import IApplicationPreferences
from schooltool.app.interfaces import ISchoolToolApplication
from schooltool.skin import flourish
from schooltool.term.interfaces import ITermContainer
from schooltool.term.interfaces import IDateManager
from schooltool.table.interfaces import ITableFormatter, IIndexedTableFormatter
from schooltool.timetable.interfaces import ITimetableCalendarEvent
from schooltool.timetable.interfaces import ITimetables

from schooltool.lyceum.journal.journal import ABSENT, TARDY
from schooltool.lyceum.journal.interfaces import ISectionJournal
from schooltool.lyceum.journal.browser.interfaces import IIndependentColumn
from schooltool.lyceum.journal.browser.interfaces import ISelectableColumn
from schooltool.lyceum.journal.browser.table import SelectStudentCellFormatter
from schooltool.lyceum.journal.browser.table import SelectableRowTableFormatter
from schooltool.lyceum.journal import LyceumMessage as _


# set up translation from data base data to locale representation and back
ABSENT_LETTER = translate(_(u"Single letter that represents an absent mark for a student",
                           default='a'))
TARDY_LETTER = translate(_(u"Single letter that represents an tardy mark for a student",
                          default='t'))

ATTENDANCE_DATA_TO_TRANSLATION = {ABSENT: ABSENT_LETTER,
                                  TARDY:  TARDY_LETTER}
ATTENDANCE_TRANSLATION_TO_DATA = {ABSENT_LETTER: ABSENT,
                                  TARDY_LETTER:  TARDY}


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
                absoluteURL(journal, self.request),
                urllib.quote(event_for_display.context.unique_id.encode('utf-8')))


class StudentNumberColumn(GetterColumn):

    def getter(self, item, formatter):
        return formatter.row

    def renderCell(self, item, formatter):
        value = self.getter(item, formatter)
        cell = u'%d<input type="hidden" value=%s class="person_id" />' % (
            value, quoteattr(item.__name__))
        return cell

    def renderHeader(self, formatter):
        return '<span>%s</span>' % translate(_("Nr."),
                                             context=formatter.request)

class GradesColumn(object):
    def getGrades(self, person):
        """Get the grades for the person."""
        grades = []
        for meeting in self.journal.recordedMeetings(person):
            if meeting.dtstart.date() in self.term:
                grade = self.journal.getGrade(person, meeting, default=None)
                if (grade is not None) and (grade.strip() != ""):
                    grades.append(grade)
        return grades


class PersonGradesColumn(GradesColumn):
    implements(ISelectableColumn, IIndependentColumn)

    def __init__(self, meeting, journal, selected=False):
        self.meeting = meeting
        self.selected = selected
        self.journal = journal

    def today(self):
        return getUtility(IDateManager).today

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
            try:
                period = '<br />' + self.meeting.period_id[:3]
                if period[-1] == ':':
                    period = period[:-1]
            except:
                period = ''
            header = '<a href="%s">%s%s</a>' % (url, header, period)

        span = '<span class="select-column%s" title="%s">%s</span>' % (
            today_class, meetingDate.strftime("%Y-%m-%d"), header)
        event_id = '<input type="hidden" value="%s" class="event_id" />' % (
            urllib.quote(base64.encodestring(self.meeting.unique_id.encode('utf-8'))))
        return span + event_id

    def getCellValue(self, item):
        if self.hasMeeting(item):
            grade = self.journal.getGrade(item, self.meeting, default="")
            return ATTENDANCE_DATA_TO_TRANSLATION.get(grade, grade)
        return "X"

    def hasMeeting(self, item):
        return self.journal.hasMeeting(item, self.meeting)

    def template(self, item, selected):
        value = self.getCellValue(item)
        name = "%s.%s" % (item.__name__, self.meeting.__name__)

        if not selected:
            return "<td>%s</td>" % value
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


class SectionTermGradesColumn(GradesColumn):
    implements(IColumn)

    def __init__(self, journal, term):
        self.term = term
        self.name = term.__name__ + "grades"
        self.journal = journal

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
            return ",".join(["%s" % grade for grade in grades])

    def renderHeader(self, formatter):
        return '<span>%s</span>' % translate(_("Grades"),
                                             context=formatter.request)

class SectionTermAverageGradesColumn(GradesColumn):
    implements(IColumn)

    def __init__(self, journal, term):
        self.term = term
        self.name = term.__name__ + "average"
        self.journal = journal

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


class SectionTermAttendanceColumn(GradesColumn):
    implements(IColumn)

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
        return '<span>%s</span>' % translate(_("Absences"),
                                             context=formatter.request)


class SectionTermTardiesColumn(GradesColumn):
    implements(IColumn)

    def __init__(self, journal, term):
        self.term = term
        self.name = term.__name__ + "tardies"
        self.journal = journal

    def renderCell(self, person, formatter):
        tardies = 0
        for grade in self.getGrades(person):
            if (grade.strip().lower() == "p"):
                tardies += 1

        if tardies == 0:
            return ""
        else:
            return str(tardies)

    def renderHeader(self, formatter):
        return '<span>%s</span>' % translate(_("Tardies"),
                                             context=formatter.request)

def journal_grades():
    grades = [
        {'keys': [ABSENT_LETTER.lower(), ABSENT_LETTER.upper()],
         'value': ABSENT_LETTER,
         'legend': _('Absent')},
        {'keys': [TARDY_LETTER.lower(), TARDY_LETTER.upper()],
         'value': TARDY_LETTER,
         'legend': _('Tardy')}]
    for i in range(9):
        grades.append({'keys': [chr(i + ord('1'))],
                       'value': unicode(i+1),
                       'legend': u''})
    grades.append({'keys': ['0'],
                   'value': u'10',
                   'legend': u''})
    return grades


class SectionJournalJSView(BrowserView):

    def grading_events(self):
        for grade in journal_grades():
            event_check = ' || '.join([
                'event.which == %d' % ord(key)
                for key in grade['keys']])
            yield {'js_condition': event_check,
                   'grade_value': "'%s'" % grade['value']}


class StudentSelectionMixin(object):

    selected_students = None

    def selectStudents(self, table_formatter):
        self.selected_students = []
        if 'student' in self.request:
            student_id = self.request['student']
            app = ISchoolToolApplication(None)
            student = app['persons'].get(student_id)
            self.selected_students = [student]

        if IIndexedTableFormatter.providedBy(table_formatter):
            self.selected_students = table_formatter.indexItems(
                self.selected_students)


class LyceumSectionJournalView(StudentSelectionMixin):

    template = ViewPageTemplateFile("templates/journal.pt")
    no_timetable_template = ViewPageTemplateFile("templates/no_timetable_journal.pt")
    no_periods_template = ViewPageTemplateFile("templates/no_periods_journal.pt")

    def __init__(self, context, request):
        self.context, self.request = context, request

    def __call__(self):
        if not ITimetables(self.context.section).terms:
            return self.no_timetable_template()

        meetings = self.allMeetings()
        if not meetings:
            return self.no_periods_template()

        if 'UPDATE_SUBMIT' in self.request:
            self.updateGradebook()

        app = ISchoolToolApplication(None)
        person_container = app['persons']
        self.gradebook = queryMultiAdapter((person_container, self.request),
                                           ITableFormatter)

        self.selectStudents(self.gradebook)

        columns_before = [StudentNumberColumn(title=_('Nr'), name='nr')]

        self.gradebook.setUp(items=self.members(),
                             formatters=[SelectStudentCellFormatter(self.context)] * 2,
                             columns_before=columns_before,
                             columns_after=self.gradeColumns(),
                             table_formatter=self.formatterFactory,
                             batch_size=0)

        return self.template()

    def getLegendItems(self):
        for grade in journal_grades():
            yield {'keys': u', '.join(grade['keys']),
                   'value': grade['value'],
                   'description': grade['legend']}

    def encodedSelectedEventId(self):
        event = self.selectedEvent()
        if event:
            return urllib.quote(base64.encodestring(event.unique_id.encode('utf-8')))

    def formatterFactory(self, *args, **kwargs):
        kwargs['selected_items'] = self.selected_students
        return SelectableRowTableFormatter(*args, **kwargs)

    def timetables(self):
        tt = ITimetables(self.context.section).timetables
        return sorted(tt.values(), key=lambda tt: tt.term.last)

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
                cell_id = "%s.%s" % (person.__name__, meeting.__name__)
                cell_value = self.request.get(cell_id, None)
                if cell_value is not None:
                    cell_value = ATTENDANCE_TRANSLATION_TO_DATA.get(cell_value, cell_value)
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
        columns.append(SectionTermTardiesColumn(self.context,
                                                self.getSelectedTerm()))
        return columns

    def getSelectedTerm(self):
        terms = ITermContainer(self.context)
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
            return getUtility(IDateManager).today

    def getCurrentTerm(self):
        event = self.selectedEvent()
        if event:
            return event.activity.timetable.term
        return self.scheduled_terms[-1]

    @property
    def scheduled_terms(self):
        scheduled_terms = []
        terms = ITermContainer(self.context)
        tt = ITimetables(self.context.section).timetables
        for tt in tt.values():
            scheduled_terms.append(tt.term)
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
        grade = self.request['grade']
        grade = ATTENDANCE_TRANSLATION_TO_DATA.get(grade, grade)
        self.context.setGrade(person, meeting, grade);
        return ""


class SectionListView(BrowserView):

    def getSectionsForPerson(self, person):
        current_term = getUtility(IDateManager).current_term
        sections = IInstructor(person).sections()
        results = []
        for section in sections:
            if current_term in ITimetables(section).terms:
                url = "%s/journal/" % absoluteURL(section, self.request)
                results.append({'title': removeSecurityProxy(section).title,
                                'url': url})

        collator = ICollator(self.request.locale)
        results.sort(key=lambda s: collator.key(s['title']))
        return results


class TeacherJournalView(SectionListView):
    """A view that lists all the sections teacher is teaching to.

    The links go to the journals of these sections and only sections
    in the current term are displayed.
    """

    def getSections(self):
        return self.getSectionsForPerson(self.context)


class TeacherJournalTabViewlet(SectionListView):
    implements(IViewlet)

    def enabled(self):
        person = IPerson(self.request.principal, None)
        if not person:
            return False
        return bool(list(self.getSectionsForPerson(person)))


class JournalNavViewlet(flourish.page.LinkViewlet, SectionListView):

    @property
    def person(self):
        return IPerson(self.request.principal, None)

    @property
    def title(self):
        person = self.person
        if person is None:
            return ''
        taught_sections = list(self.getSectionsForPerson(person))
        learner_sections = list(ILearner(person).sections())
        if not (taught_sections or learner_sections):
            return ''
        return _('Journal')

    @property
    def url(self):
        if self.person is None:
            return ''
        base_url = absoluteURL(self.person, self.request)
        return '%s/gradebook.html' % base_url


class StudentGradebookTabViewlet(object):
    implements(IViewlet)

    def enabled(self):
        person = IPerson(self.request.principal, None)
        if not person:
            return False
        return bool(list(ILearner(person).sections()))
