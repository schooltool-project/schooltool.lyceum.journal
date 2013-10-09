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
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
"""
Lyceum journal views.
"""
import calendar
import pytz
import urllib
import base64
import xlwt
import datetime
import dateutil

from zope.security.proxy import removeSecurityProxy
from zope.security import checkPermission
from zope.proxy import sameProxiedObjects
from zope.viewlet.interfaces import IViewlet
from zope.viewlet.viewlet import CSSViewlet
from zope.exceptions.interfaces import UserError
from zope.publisher.browser import BrowserView
from zope.browserpage.viewpagetemplatefile import ViewPageTemplateFile
from zope.formlib.widget import quoteattr
from zope.component import queryMultiAdapter
from zope.i18n import translate
from zope.i18n.interfaces.locales import ICollator
from zope.interface import implements
from zope.intid.interfaces import IIntIds
from zope.traversing.browser.absoluteurl import absoluteURL
from zope.cachedescriptors.property import Lazy
from zope.component import getUtility
from zope.container.interfaces import INameChooser

import z3c.form.field
import z3c.form.form
import z3c.form.button
from zc.table.column import GetterColumn
from zc.table.interfaces import IColumn

from schooltool.skin import flourish
from schooltool import table
from schooltool.basicperson.interfaces import IDemographics
from schooltool.course.interfaces import ILearner, IInstructor
from schooltool.common.inlinept import InlineViewPageTemplate
from schooltool.common import SchoolToolMessage as s_
from schooltool.export import export
from schooltool.person.interfaces import IPerson
from schooltool.person.interfaces import IPersonFactory
from schooltool.app.browser.cal import month_names
from schooltool.app.interfaces import IApplicationPreferences
from schooltool.app.interfaces import ISchoolToolApplication
from schooltool.app.interfaces import ISchoolToolCalendar
from schooltool.app.relationships import Instruction
from schooltool.course.interfaces import ISection
from schooltool.export.export import RequestXLSReportDialog
from schooltool.task.progress import normalized_progress
from schooltool.group.interfaces import IGroupContainer
from schooltool.course.interfaces import ISectionContainer
from schooltool.requirement.scoresystem import ScoreValidationError
from schooltool.requirement.scoresystem import UNSCORED
from schooltool.requirement.interfaces import IEvaluations
from schooltool.term.interfaces import ITerm
from schooltool.term.interfaces import ITermContainer
from schooltool.term.interfaces import IDateManager
from schooltool.table.interfaces import ITableFormatter, IIndexedTableFormatter
from schooltool.timetable.interfaces import IScheduleContainer
from schooltool.timetable.calendar import ScheduleCalendarEvent
from schooltool.schoolyear.interfaces import ISchoolYearContainer
from schooltool.schoolyear.interfaces import ISchoolYear
from schooltool.securitypolicy.crowds import inCrowd

from schooltool.lyceum.journal.journal import getCurrentSectionTaught
from schooltool.lyceum.journal.journal import setCurrentSectionTaught
from schooltool.lyceum.journal.journal import getCurrentJournalMode
from schooltool.lyceum.journal.journal import setCurrentJournalMode
from schooltool.lyceum.journal.journal import JournalXLSReportTask
from schooltool.lyceum.journal.journal import PersistentAttendanceScoreSystem
from schooltool.lyceum.journal.journal import GradeRequirement
from schooltool.lyceum.journal.journal import AttendanceRequirement
from schooltool.lyceum.journal.journal import HomeroomRequirement
from schooltool.lyceum.journal.interfaces import IAttendanceScoreSystem
from schooltool.lyceum.journal.interfaces import IEvaluateRequirement
from schooltool.lyceum.journal.interfaces import ISectionJournal
from schooltool.lyceum.journal.interfaces import ISectionJournalData
from schooltool.lyceum.journal.interfaces import IJournalScoreSystemPreferences
from schooltool.lyceum.journal.browser.interfaces import IIndependentColumn
from schooltool.lyceum.journal.browser.interfaces import ISelectableColumn
from schooltool.lyceum.journal.browser.table import SelectStudentCellFormatter
from schooltool.lyceum.journal.browser.table import SelectableRowTableFormatter
from schooltool.lyceum.journal import LyceumMessage as _


JournalCSSViewlet = CSSViewlet("journal.css")


def getEvaluator(request):
    user = IPerson(request.principal, None)
    if user is None:
        return None
    return user.__name__


def makeSchoolAttendanceMeeting(date):
    uid = '%s' % date.isoformat()
    dt = datetime.datetime(date.year, date.month, date.day)
    meeting = ScheduleCalendarEvent(dt, datetime.timedelta(1), '', unique_id=uid)
    return meeting


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


class FlourishJournalCalendarEventViewlet(JournalCalendarEventViewlet):

    def attendanceLink(self):
        """Construct the URL for the attendance form for a section meeting.

        Returns None if the calendar event is not a section meeting event.
        """
        event_for_display = self.manager.event
        calendar_event = event_for_display.context
        journal = ISectionJournal(calendar_event, None)
        if journal and checkPermission('schooltool.view', journal):
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
        for meeting, score in self.journal.gradedMeetings(person):
            # This is not a correct way, as this looses score system info
            if (meeting.dtstart.date() in self.term and
                score.value is not UNSCORED):
                grades.append(score)
        return grades

    def getAbsences(self, person):
        """Get the grades for the person."""
        grades = []
        for meeting, score in self.journal.absentMeetings(person):
            if (meeting.dtstart.date() in self.term and
                score.value is not UNSCORED):
                grades.append(score)
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
                if self.meeting.period is not None:
                    short_title = self.meeting.period.title[:3]
                else:
                    short_title = ''
                period = '<br />' + short_title
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
            grade = self.journal.getAbsence(item, self.meeting, default="")
            grade = self.journal.getGrade(item, self.meeting, grade)
            if grade is UNSCORED:
                grade = ''
            return grade
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
        for score in self.getGrades(person):
            grade = score.value
            if grade is UNSCORED:
                continue
            grades.append(grade)
        if not grades:
            return ""
        else:
            return ",".join(["%s" % grade for grade in grades])

    def renderHeader(self, formatter):
        return '<span>%s</span>' % translate(_("Scores"),
                                             context=formatter.request)

class SectionTermAverageGradesColumn(GradesColumn):
    implements(IColumn)

    def __init__(self, journal, term):
        self.term = term
        self.name = term.__name__ + "average"
        self.journal = journal

    def renderCell(self, person, formatter):
        grades = []
        for score in self.getGrades(person):
            grade = score.value
            if grade is UNSCORED:
                continue
            try:
                grade = score.scoreSystem.getNumericalValue(grade)
            except KeyError:
                continue
            grades.append(grade)
        if not grades:
            return ""
        else:
            return "%.3f" % (float(sum(grades)) / float(len(grades)))

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
        for score in self.getAbsences(person):
            if (IAttendanceScoreSystem.providedBy(score.scoreSystem) and
                score.scoreSystem.isAbsent(score)):
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
        for score in self.getAbsences(person):
            if (IAttendanceScoreSystem.providedBy(score.scoreSystem) and
                score.scoreSystem.isTardy(score)):
                tardies += 1
        if tardies == 0:
            return ""
        else:
            return str(tardies)

    def renderHeader(self, formatter):
        return '<span>%s</span>' % translate(_("Tardies"),
                                             context=formatter.request)

class SectionTermExcusedColumn(GradesColumn):
    implements(IColumn)

    def __init__(self, journal, term):
        self.term = term
        self.name = term.__name__ + "excused"
        self.journal = journal

    def renderCell(self, person, formatter):
        excusable = 0
        excused = 0
        for score in self.getAbsences(person):
            if (score.value is UNSCORED or
                not IAttendanceScoreSystem.providedBy(score.scoreSystem)):
                continue
            ss = score.scoreSystem
            if (ss.isAbsent(score) or
                ss.isTardy(score) or
                ss.isExcused(score)):
                excusable += 1
            if ss.isExcused(score):
                excused += 1
        if excusable == 0:
            return ""
        else:
            return "%d / %d" % (excusable, excused)

    def renderHeader(self, formatter):
        return '<span>%s</span>' % translate(_("Excused"),
                                             context=formatter.request)

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
        schedules = IScheduleContainer(self.context.section)
        if not schedules:
            return self.no_timetable_template()

        meetings = self.all_meetings
        if not meetings:
            return self.no_periods_template()

        if 'UPDATE_SUBMIT' in self.request:
            self.updateGradebook()

        app = ISchoolToolApplication(None)
        person_container = app['persons']
        self.gradebook = queryMultiAdapter((person_container, self.request),
                                           ITableFormatter)

        self.selectStudents(self.gradebook)

        columns_before = [StudentNumberColumn(title=_('Nr.'), name='nr')]

        self.gradebook.setUp(items=self.members(),
                             formatters=[SelectStudentCellFormatter(self.context)] * 2,
                             columns_before=columns_before,
                             columns_after=self.gradeColumns(),
                             table_formatter=self.formatterFactory,
                             batch_size=0)

        return self.template()

    @Lazy
    def timezone(self):
        prefs = IApplicationPreferences(ISchoolToolApplication(None))
        return pytz.timezone(prefs.timezone)

    def encodedSelectedEventId(self):
        event = self.selectedEvent()
        if event:
            return urllib.quote(base64.encodestring(event.unique_id.encode('utf-8')))

    def formatterFactory(self, *args, **kwargs):
        kwargs['selected_items'] = self.selected_students
        return SelectableRowTableFormatter(*args, **kwargs)

    def isJournalMeeting(self, term, meeting):
        return meeting.dtstart.date() in term

    def allMeetings(self):
        term = removeSecurityProxy(self.selected_term)
        if not term:
            return ()

        # maybe expand would be better in here
        by_uid = dict([(removeSecurityProxy(e).unique_id, e)
                       for e in self.context.meetings])

        insecure_events = [removeSecurityProxy(e)
                           for e in by_uid.values()]
        insecure_events[:] = filter(lambda e: self.isJournalMeeting(term, e),
                                    insecure_events)
        meetings = [by_uid[e.unique_id] for e in sorted(insecure_events)]
        return meetings

    @Lazy
    def all_meetings(self):
        return self.allMeetings()

    def meetings(self):
        for event in self.all_meetings:
            insecure_event = removeSecurityProxy(event)
            meeting_start = insecure_event.dtstart.astimezone(self.timezone)
            if meeting_start.month == self.active_month:
                yield event

    def members(self):
        collator = ICollator(self.request.locale)
        factory = getUtility(IPersonFactory)
        sorting_key = lambda x: factory.getSortingKey(x, collator)
        return sorted(self.context.members, key=sorting_key)

    def updateGradebook(self):
        members = self.members()
        evaluator = getEvaluator(self.request)
        for meeting in self.meetings():
            for person in members:
                cell_id = "%s.%s" % (person.__name__, meeting.__name__)
                cell_value = self.request.get(cell_id, None)
                if cell_value is not None:
                    try:
                        self.context.setGrade(
                            person, meeting, cell_value, evaluator=evaluator)
                    except ScoreValidationError:
                        self.context.setAbsence(
                            person, meeting, evaluator=evaluator, value=cell_value)

    def gradeColumns(self):
        columns = []
        selected_meeting = self.selectedEvent()
        for meeting in self.meetings():
            # Arguably anyone who can look at this journal
            # should be able to look at meeting grades
            insecure_meeting = removeSecurityProxy(meeting)
            selected = selected_meeting and selected_meeting == insecure_meeting
            columns.append(PersonGradesColumn(insecure_meeting, self.context,
                                              selected=selected))
        columns.append(SectionTermAverageGradesColumn(self.context,
                                                      self.selected_term))
        columns.append(SectionTermAttendanceColumn(self.context,
                                                   self.selected_term))
        columns.append(SectionTermTardiesColumn(self.context,
                                                self.selected_term))
        columns.append(SectionTermExcusedColumn(self.context,
                                                self.selected_term))
        return columns

    def getSelectedTerm(self):
        terms = ITermContainer(self.context)
        term_id = self.request.get('TERM', None)
        if term_id and term_id in terms:
            term = terms[term_id]
            if term in self.scheduled_terms:
                return term

        return self.getCurrentTerm()

    @Lazy
    def selected_term(self):
        return self.getSelectedTerm()

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
            calendar = event.__parent__
            owner = calendar.__parent__
            term = ITerm(owner)
            return term
        return self.scheduled_terms[-1]

    @property
    def scheduled_terms(self):
        linked_sections = self.context.section.linked_sections
        linked_sections = [section for section in linked_sections
                           if IScheduleContainer(section)]
        terms = [ITerm(section) for section in linked_sections]
        return sorted(terms, key=lambda term: term.last)

    def monthsInSelectedTerm(self):
        month = -1
        for meeting in self.all_meetings:
            insecure_meeting = removeSecurityProxy(meeting)
            meeting_start = insecure_meeting.dtstart.astimezone(self.timezone)
            if meeting_start.month != month:
                yield meeting_start.month
                month = meeting_start.month

    @Lazy
    def selected_months(self):
        return list(self.monthsInSelectedTerm())

    def monthTitle(self, number):
        return translate(month_names[number], context=self.request)

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

        available_months = list(self.selected_months)
        selected_month = None
        if 'month' in self.request:
            month = int(self.request['month'])
            if month in available_months:
                selected_month = month

        if not selected_month:
            selected_month = available_months[0]

        for meeting in self.all_meetings:
            insecure_meeting = removeSecurityProxy(meeting)
            meeting_start = insecure_meeting.dtstart.astimezone(self.timezone)
            if meeting_start.month == selected_month:
                return meeting_start.year

    @Lazy
    def active_month(self):
        available_months = list(self.selected_months)
        if 'month' in self.request:
            month = int(self.request['month'])
            if month in available_months:
                return month

        term = self.selected_term
        date = self.selectedDate()
        if (term is not None and
            term.first <= date <= term.last):
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
        evaluator = getEvaluator(self.request)
        try:
            self.context.setGrade(person, meeting, grade, evaluator=evaluator)
        except ScoreValidationError:
            pass
        try:
            self.context.setAbsence(person, meeting, evaluator=evaluator, value=grade)
        except ScoreValidationError:
            pass

        return ""


class SectionListView(BrowserView):

    def getSectionsForPerson(self, person):
        current_term = getUtility(IDateManager).current_term
        sections = IInstructor(person).sections()
        results = []
        for section in sections:
            term = ITerm(section)
            if sameProxiedObjects(current_term, term):
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
    def enabled(self):
        person = self.person
        if person is None:
            return False
        if inCrowd(self.request.principal, 'clerks',
                   context=self.context):
            return True
        taught_sections = list(self.getSectionsForPerson(person))
        learner_sections = list(ILearner(person).sections())
        return taught_sections or learner_sections

    @property
    def url(self):
        if self.person is None:
            return ''
        base_url = absoluteURL(self.person, self.request)
        return '%s/journal.html' % base_url

    def getSectionsForPerson(self, person):
        return list(IInstructor(person).sections())


class StudentGradebookTabViewlet(object):
    implements(IViewlet)

    def enabled(self):
        person = IPerson(self.request.principal, None)
        if not person:
            return False
        return bool(list(ILearner(person).sections()))


class FlourishLyceumSectionJournalBase(flourish.page.WideContainerPage,
                                       LyceumSectionJournalView):
    no_timetable = False
    no_periods = False
    render_journal = True
    journal_mode = None

    no_periods_text = _("No periods have been assigned in timetables of this section.")

    def __init__(self, *args, **kw):
        self._grade_cache = {}
        super(FlourishLyceumSectionJournalBase, self).__init__(*args, **kw)

    @property
    def page_class(self):
        if self.render_journal:
            return 'page grid'
        else:
            return 'page'

    @property
    def has_header(self):
        return not self.render_journal

    def monthURL(self, month_id):
        url = absoluteURL(self, self.request)
        url = "%s?%s" % (
            url,
            urllib.urlencode([('month', month_id)] +
                             self.extra_parameters(self.request)))
        return url

    def update(self):
        schedules = IScheduleContainer(self.context.section)
        if not schedules:
            self.no_timetable = True
            self.render_journal = False
            return

        meetings = self.all_meetings
        if not meetings:
            self.no_periods = True
            self.render_journal = False
            return

        person = IPerson(self.request.principal, None)
        if person is not None:
            setCurrentSectionTaught(person, self.context.section)

        self.updateJournalMode()
        if 'UPDATE_SUBMIT' in self.request:
            self.updateGradebook()

        app = ISchoolToolApplication(None)
        self.tzinfo = pytz.timezone(IApplicationPreferences(app).timezone)

    @Lazy
    def activities(self):
        result = []
        scores = None
        ss = self.getDefaultScoreSystem()
        if ss is not None:
            scores = self.getJSONScores(ss)
        for meeting in self.meetings:
            info = {
                'hash': meeting.__name__,
                'cssClass': 'scorable',
                'scores': scores,
                }
            insecure_meeting = removeSecurityProxy(meeting)
            meetingDate = insecure_meeting.dtstart.astimezone(self.tzinfo).date()
            info['shortTitle'] = meetingDate.strftime("%d")
            info['longTitle'] = meetingDate.strftime("%Y-%m-%d")
            try:
                if meeting.period is not None:
                    short_title = meeting.period.title[:3]
                else:
                    short_title = ''
                period = short_title
                if period[-1] == ':':
                    period = period[:-1]
            except:
                period = ''
            info['period'] = period
            result.append(info)
        return result

    def getDefaultScoreSystem(self):
        return None

    def makeRequirement(self, meeting):
        return None

    def getSelectedTerm(self):
        term = ITerm(self.context.section)
        if term in self.scheduled_terms:
            return term

    def breakJSString(self, origstr):
        newstr = unicode(origstr)
        newstr = newstr.replace('\n', '')
        newstr = newstr.replace('\r', '')
        newstr = "\\'".join(newstr.split("'"))
        newstr = '\\"'.join(newstr.split('"'))
        return newstr

    def scorableActivities(self):
        return self.activities

    @property
    def warningText(self):
        return _('You have some changes that have not been saved.  Click OK to save now or CANCEL to continue without saving.')

    @Lazy
    def meetings(self):
        result = []
        for event in self.all_meetings:
            insecure_event = removeSecurityProxy(event)
            meeting_start = insecure_event.dtstart.astimezone(self.timezone)
            if meeting_start.month == self.active_month:
                result.append(event)
        return result

    def validate_score(self, activity_id=None, score=None):
        """Intended to be used from AJAX calls."""
        if score is None:
            score = self.request.get('score')
        if activity_id is None:
            activity_id = self.request.get('activity_id')
        result = {'is_valid': True,
                  'is_extracredit': False}

        meeting = None
        meetings = dict([(meeting.__name__, meeting)
                         for meeting in self.context.meetings])
        if activity_id is not None and activity_id in meetings:
            meeting = meetings[activity_id]
        if (meeting is not None and
            score and score.strip()):
            requirement = self.makeRequirement(meeting)
            if requirement is not None:
                result['is_valid'] = requirement.score_system.isValidScore(score)

        response = self.request.response
        response.setHeader('Content-Type', 'application/json')
        encoder = flourish.tal.JSONEncoder()
        json = encoder.encode(result)
        return json

    def getScores(self, person):
        if person in self._grade_cache:
            return list(self._grade_cache[person])
        self._grade_cache[person] = result = []
        unique_meetings = set()
        term = self.selected_term
        calendar = ISchoolToolCalendar(self.context.section)
        events = [e for e in calendar if e.dtstart.date() in term]
        sorted_events = sorted(events, key=lambda e: e.dtstart)
        unproxied_person = removeSecurityProxy(person)
        for event in sorted_events:
            if event.dtstart.date() not in term:
                continue
            unproxied_event = removeSecurityProxy(event)
            requirement = self.makeRequirement(unproxied_event)
            score = IEvaluateRequirement(requirement).getEvaluation(
                    unproxied_person, requirement, default=UNSCORED)
            if (event.meeting_id not in unique_meetings and
                score is not UNSCORED):
                result.append(score)
                unique_meetings.add(event.meeting_id)
        return result

    def getGrade(self, person, meeting):
        requirement = self.makeRequirement(meeting)
        score = IEvaluateRequirement(requirement).getEvaluation(
            person, requirement, default=UNSCORED)
        if score is UNSCORED:
            return None
        grade = score.value
        if grade is UNSCORED:
            return None
        return score.value

    def getHint(self, person, meeting):
        # grade hint is homeroom attendance by default
        period = getattr(meeting, 'period', None)
        if period is None:
            return None
        if period.activity_type != 'homeroom':
            return None
        requirement = HomeroomRequirement(meeting)
        score = IEvaluateRequirement(requirement).getEvaluation(
            person, requirement, default=UNSCORED)
        if (score is UNSCORED or
            score.value is UNSCORED):
            return None
        return score.value

    def updateJournalMode(self):
        if self.journal_mode is None:
            return
        person = IPerson(self.request.principal, None)
        if person is None:
            return
        mode = getCurrentJournalMode(person) or ''
        if mode == self.journal_mode:
            return
        setCurrentJournalMode(person, self.journal_mode)

    @Lazy
    def name_sorting_columns(self):
        return getUtility(IPersonFactory).columns()


class FlourishLyceumSectionJournalGrades(FlourishLyceumSectionJournalBase):

    journal_mode = 'journal-mode-grades'

    @property
    def title(self):
        if self.render_journal:
            return _('Enter Scores')
        else:
            if self.no_timetable:
                return _('Section is not scheduled')
            else:
                return _('No periods assigned for this section')

    def getDefaultScoreSystem(self):
        prefs = IJournalScoreSystemPreferences(self.context)
        ss = prefs.grading_scoresystem
        if ss is not None:
            return ss
        return GradeRequirement.score_system

    def makeRequirement(self, meeting):
        ss = self.getDefaultScoreSystem()
        return GradeRequirement(meeting, ss)

    def updateGradebook(self):
        evaluator = getEvaluator(self.request)
        members = self.members()
        for meeting in self.meetings:
            for person in members:
                cell_id = "%s_%s" % (meeting.__name__, person.__name__)
                cell_value = self.request.get(cell_id, None)
                if cell_value is not None:
                    requirement = self.makeRequirement(removeSecurityProxy(meeting))
                    try:
                        IEvaluateRequirement(requirement).evaluate(
                            person, requirement, cell_value,
                            evaluator=evaluator)
                    except ScoreValidationError:
                        pass
                    except:
                        IEvaluateRequirement(requirement).evaluate(
                            person, requirement, cell_value,
                            evaluator=evaluator)

    def table(self):
        result = []
        collator = ICollator(self.request.locale)
        factory = getUtility(IPersonFactory)
        self.sortBy = self.request.get('sort_by')
        if self.sortBy == 'last_name':
            sorting_key = lambda x: (collator.key(x.last_name),
                                     collator.key(x.first_name))
        elif self.sortBy == 'first_name':
            sorting_key = lambda x: (collator.key(x.first_name),
                                     collator.key(x.last_name))
        else:
            sorting_key = lambda x: factory.getSortingKey(x, collator)
        for person in self.members():
            grades = []
            for meeting in self.meetings:
                insecure_meeting = removeSecurityProxy(meeting)
                grade = self.getGrade(person, insecure_meeting) or ''
                hint = self.getHint(person, insecure_meeting) or ''
                grade_data = {
                    'id': '%s_%s' % (meeting.__name__, person.__name__),
                    'sortKey': meeting.__name__,
                    'value': grade,
                    'hint': hint,
                    'editable': True,
                    }
                grades.append(grade_data)
            if flourish.canView(person):
                person = removeSecurityProxy(person)
            result.append(
                {'student': {'title': person.title,
                             'first_name': person.first_name,
                             'last_name': person.last_name,
                             'id': person.username,
                             'sortKey': sorting_key(person),
                             'url': absoluteURL(person, self.request)},
                 'grades': grades,
                 'has_hints': any([g['hint'] for g in grades]),
                 'average': self.average(person),
                })
        return sorted(result, key=self.sortKey)

    def sortKey(self, row):
        if self.sortBy in ('student', 'first_name', 'last_name'):
            return row['student']['sortKey']
        elif self.sortBy == 'average':
            try:
                return (float(row['average']), row['student']['sortKey'])
            except (ValueError,):
                return ('', row['student']['sortKey'])
        else:
            grades = dict([(grade['sortKey'], grade['value'])
                          for grade in row['grades']])
            if self.sortBy in grades:
                grade = grades.get(self.sortBy)
                if grade:
                    return (0, grade, row['student']['sortKey'])
        return (1, row['student']['sortKey'])

    def average(self, person):
        grades = []
        scores = self.getScores(person)
        for score in scores:
            if score.value is UNSCORED:
                continue
            try:
                grade = score.scoreSystem.getNumericalValue(score.value)
            except KeyError:
                continue
            grades.append(grade)
        if not grades:
            return _('N/A')
        else:
            return "%.1f" % (float(sum(grades)) / float(len(grades)))

    def getJSONScores(self, scoresystem):
        encoder = flourish.tal.JSONEncoder()
        result = []
        for label, abbr, value, percent in scoresystem.scores:
            title = translate(label, context=self.request)
            if abbr:
                title += ': %s' % abbr
            result.append({
                'label': title,
                'value': label,
            })
        json = encoder.encode(result)
        return json


class FlourishLyceumSectionJournalAttendance(FlourishLyceumSectionJournalBase):

    journal_mode = 'journal-mode-attendance'

    @property
    def title(self):
        if self.render_journal:
            return _('Enter Attendance')
        else:
            if self.no_timetable:
                return _('Section is not scheduled')
            else:
                return _('No periods assigned for this section')

    def getDefaultScoreSystem(self):
        prefs = IJournalScoreSystemPreferences(self.context)
        ss = prefs.attendance_scoresystem
        if ss is not None:
            return ss
        return AttendanceRequirement.score_system

    def makeRequirement(self, meeting):
        ss = self.getDefaultScoreSystem()
        return AttendanceRequirement(meeting, ss)

    def getJSONScores(self, scoresystem):
        encoder = flourish.tal.JSONEncoder()
        result = []
        for label, abbr in scoresystem.scores:
            title = translate(label, context=self.request)
            if abbr:
                title += ': %s' % abbr
            result.append({
                'label': title,
                'value': label,
            })
        json = encoder.encode(result)
        return json

    def table(self):
        result = []
        collator = ICollator(self.request.locale)
        factory = getUtility(IPersonFactory)
        self.sortBy = self.request.get('sort_by')
        if self.sortBy == 'last_name':
            sorting_key = lambda x: (collator.key(x.last_name),
                                     collator.key(x.first_name))
        elif self.sortBy == 'first_name':
            sorting_key = lambda x: (collator.key(x.first_name),
                                     collator.key(x.last_name))
        else:
            sorting_key = lambda x: factory.getSortingKey(x, collator)
        for person in self.members():
            grades = []
            for meeting in self.meetings:
                insecure_meeting = removeSecurityProxy(meeting)
                attendance = self.getGrade(person, insecure_meeting) or ''
                hint = self.getHint(person, insecure_meeting) or ''
                grade_data = {
                    'id': '%s_%s' % (meeting.__name__, person.__name__),
                    'sortKey': meeting.__name__,
                    'value': attendance,
                    'hint': hint,
                    'editable': True,
                    }
                grades.append(grade_data)
            if flourish.canView(person):
                person = removeSecurityProxy(person)
            excused, excusable = self.excused(person)
            result.append(
                {'student': {'title': person.title,
                             'first_name': person.first_name,
                             'last_name': person.last_name,
                             'id': person.username,
                             'sortKey': sorting_key(person),
                             'url': absoluteURL(person, self.request)},
                 'grades': grades,
                 'absences': self.absences(person),
                 'tardies': self.tardies(person),
                 'excused': (
                        '%s / %s' % (excused, excusable)
                        if excusable
                        else ''),
                 'unexcused': excused - excusable if excusable else 1,
                 'has_hints': any([g['hint'] for g in grades]),
                })
        return sorted(result, key=self.sortKey)

    def sortKey(self, row):
        if self.sortBy in ('student', 'first_name', 'last_name'):
            return row['student']['sortKey']
        elif self.sortBy == 'absences':
            return (int(row['absences']), row['student']['sortKey'])
        elif self.sortBy == 'tardies':
            return (int(row['tardies']), row['student']['sortKey'])
        elif self.sortBy == 'excused':
            return (row['unexcused'], row['student']['sortKey'])
        else:
            grades = dict([(grade['sortKey'], grade['value'])
                          for grade in row['grades']])
            if self.sortBy in grades:
                grade = grades.get(self.sortBy)
                if grade:
                    return (0, grade, row['student']['sortKey'])
        return (1, row['student']['sortKey'])

    def absences(self, person):
        absences = 0
        for score in self.getScores(person):
            if (score.value is not UNSCORED and
                IAttendanceScoreSystem.providedBy(score.scoreSystem) and
                score.scoreSystem.isAbsent(score)):
                absences += 1
        if absences == 0:
            return "0"
        else:
            return str(absences)

    def tardies(self, person):
        tardies = 0
        for score in self.getScores(person):
            if (score.value is not UNSCORED and
                IAttendanceScoreSystem.providedBy(score.scoreSystem) and
                score.scoreSystem.isTardy(score)):
                tardies += 1
        if tardies == 0:
            return "0"
        else:
            return str(tardies)

    def excused(self, person):
        excusable = 0
        excused = 0
        for score in self.getScores(person):
            if (score.value is UNSCORED or
                not IAttendanceScoreSystem.providedBy(score.scoreSystem)):
                continue
            ss = score.scoreSystem
            if (ss.isAbsent(score) or
                ss.isTardy(score) or
                ss.isExcused(score)):
                excusable += 1
            if ss.isExcused(score):
                excused += 1
        if not excusable:
            return 0, 0
        return excused, excusable

    def updateGradebook(self):
        evaluator = getEvaluator(self.request)
        members = self.members()
        for meeting in self.meetings:
            for person in members:
                cell_id = "%s_%s" % (meeting.__name__, person.__name__)
                cell_value = self.request.get(cell_id, None)
                if cell_value is not None:
                    requirement = self.makeRequirement(removeSecurityProxy(meeting))
                    try:
                        IEvaluateRequirement(requirement).evaluate(
                            person, requirement, cell_value,
                            evaluator=evaluator)
                    except ScoreValidationError:
                        pass

    def validate_score(self, activity_id=None, score=None):
        if score is None:
            score = self.request.get('score')
        return FlourishLyceumSectionJournalBase.validate_score(
            self, activity_id=activity_id, score=score)


class FlourishSectionHomeroomAttendance(FlourishLyceumSectionJournalAttendance):

    journal_mode = 'journal-mode-homeroom'

    no_periods_text = _("This section is not scheduled for any homeroom periods.")

    def getHint(self, person, meeting):
        return None

    def isJournalMeeting(self, term, meeting):
        if not FlourishLyceumSectionJournalAttendance.isJournalMeeting(self, term, meeting):
            return False
        period = getattr(meeting, 'period', None)
        if period is None:
            return False
        if period.activity_type == 'homeroom':
            return True
        return False

    def getDefaultScoreSystem(self):
        prefs = IJournalScoreSystemPreferences(self.context)
        ss = prefs.attendance_scoresystem
        if ss is not None:
            return ss
        return HomeroomRequirement.score_system

    def makeRequirement(self, meeting):
        ss = self.getDefaultScoreSystem()
        return HomeroomRequirement(meeting, ss)


class JournalTertiaryNavigationManager(flourish.page.TertiaryNavigationManager):

    template = ViewPageTemplateFile('templates/f_journal_tertiary_nav.pt')

    @Lazy
    def items(self):
        result = []
        for month_id in self.view.selected_months:
            url = self.view.monthURL(month_id)
            title = self.view.monthTitle(month_id)
            result.append({
                'class': month_id == self.view.active_month and 'active' or None,
                'viewlet': u'<a href="%s" title="%s">%s</a>' % (url, title, title),
                })
        return result


class FlourishJournalNavigationViewletBase(flourish.viewlet.Viewlet):

    @property
    def person(self):
        return IPerson(self.request.principal)

    def render(self, *args, **kw):
        return self.template(*args, **kw)

    def getUserSections(self):
        return list(IInstructor(self.person).sections())

    @Lazy
    def user_sections(self):
        return self.getUserSections()


class TeacherNavigationViewletBase(flourish.page.RefineLinksViewlet):

    @property
    def person(self):
        return IPerson(self.request.principal)

    @property
    def section(self):
        return self.context.section

    def render(self, *args, **kw):
        if self.person in self.section.instructors:
            return super(TeacherNavigationViewletBase,
                         self).render(*args, **kw)


class FlourishJournalYearNavigation(TeacherNavigationViewletBase):
    """Journal year navigation viewlet."""


class FlourishJournalYearNavigationViewlet(FlourishJournalNavigationViewletBase):
    template = InlineViewPageTemplate('''
    <select name="currentYear" class="navigator"
            tal:define="years view/getYears"
            tal:condition="years"
            onchange="ST.redirect($(this).context.value)">
      <option tal:repeat="year years"
              tal:attributes="value year/section_url;
                              selected year/selected"
              tal:content="year/title" />
    </select>
    ''')

    def getYears(self):
        currentSection = self.context.section
        currentYear = ISchoolYear(ITerm(currentSection))
        years = []
        for section in self.user_sections:
            year = ISchoolYear(ITerm(section))
            if year not in years:
                years.append(year)
        return [{'title': year.title,
                 'section_url': self.getSectionURL(year),
                 'selected': year is currentYear and 'selected' or None}
                for year in sorted(years, key=lambda x:x.first)]

    def getSectionURL(self, year):
        result = None
        for section in self.user_sections:
            term = ITerm(section)
            if ISchoolYear(term).__name__ == year.__name__:
               result = section
               break
        url = '%s/journal' % absoluteURL(result, self.request)
        return url


class FlourishJournalTermNavigation(TeacherNavigationViewletBase):
    """Journal term navigation viewlet."""


class FlourishJournalTermNavigationViewlet(FlourishJournalNavigationViewletBase):
    template = InlineViewPageTemplate('''
    <select name="currentTerm" class="navigator"
            tal:define="terms view/getTerms"
            tal:condition="terms"
            onchange="ST.redirect($(this).context.value)">
      <option tal:repeat="term terms"
              tal:attributes="value term/section_url;
                              selected term/selected"
              tal:content="term/title" />
    </select>
    ''')

    def getTerms(self):
        currentSection = self.context.section
        currentTerm = ITerm(currentSection)
        currentYear = ISchoolYear(currentTerm)
        terms = []
        for section in self.user_sections:
            term = ITerm(section)
            if ISchoolYear(term) == currentYear and term not in terms:
                terms.append(term)
        return [{'title': term.title,
                 'section_url': self.getSectionURL(term),
                 'selected': term is currentTerm and 'selected' or None}
                for term in sorted(terms, key=lambda x:x.first)]

    def getCourse(self, section):
        try:
            return list(section.courses)[0]
        except (IndexError,):
            return None

    def getSectionURL(self, term):
        result = None
        currentSection = self.context.section
        currentCourse = self.getCourse(currentSection)
        for section in self.user_sections:
            if term == ITerm(section):
                if currentCourse == self.getCourse(section):
                    result = section
                    break
                elif result is None:
                    result = section
        url = '%s/journal' % absoluteURL(result, self.request)
        return url


class FlourishJournalSectionNavigation(TeacherNavigationViewletBase):
    """Journal section navigation viewlet."""


class FlourishJournalSectionNavigationViewlet(FlourishJournalNavigationViewletBase):
    template = InlineViewPageTemplate('''
    <select name="currentSection" class="navigator"
            tal:define="sections view/getSections"
            tal:condition="sections"
            onchange="ST.redirect($(this).context.value)">
      <option tal:repeat="section sections"
	      tal:attributes="value section/url;
			      selected section/selected;"
	      tal:content="section/title" />
    </select>
    ''')

    def getSections(self):
        result = []
        currentSection = self.context.section
        currentTerm = ITerm(currentSection)
        for section in self.user_sections:
            term = ITerm(section)
            if term != currentTerm:
                continue
            result.append({
                'url': '%s/journal' % absoluteURL(section, self.request),
                'title': section.title,
                'selected': section == currentSection and 'selected' or None,
                })
        return result


class FlourishJournalRedirectView(flourish.page.Page):

    @Lazy
    def person(self):
        person = IPerson(self.request.principal, None)
        return person

    def getModeUrl(self):
        content = self.providers.get('lyceum-journal-modes')
        if content is None:
            return
        modes = content.modes
        if not modes:
            return
        url = modes[0]['url']
        current = getCurrentJournalMode(self.person) or ''
        if not current:
            return url
        for mode in content.modes:
            if mode['id'] == current:
                return mode['url']
        return url

    def getSchoolYearUrl(self):
        sections = list(ILearner(self.person).sections())
        if sections:
            current_term = getUtility(IDateManager).current_term
            if current_term is not None:
                schoolyear = ISchoolYear(current_term)
                url = (absoluteURL(schoolyear, self.request) +
                       '/myjournal.html')
                return url

    def render(self):
        url = self.getModeUrl()
        if not url:
            url = self.getSchoolYearUrl()
        if not url:
            self.request.response.redirect(
                absoluteURL(self.context, self.request))
        else:
            self.request.response.redirect(url)


class FlourishJournalActionsLinks(flourish.page.RefineLinksViewlet):
    """Journal action links viewlet."""


class FlourishJournalHelpLinks(flourish.page.RefineLinksViewlet):
    """Journal help links viewlet."""


class FlourishJournalHelpViewlet(flourish.page.ModalFormLinkViewlet):

    @property
    def url(self):
        return "%s/%s" % (absoluteURL(self.view, self.request),
                          self.link)

    @property
    def dialog_title(self):
        title = _(u'Journal Help')
        return translate(title, context=self.request)


class FlourishJournalHelpView(flourish.form.Dialog):

    template = InlineViewPageTemplate('''
        <tal:block define="scoresystem view/context/getDefaultScoreSystem"
                   condition="scoresystem"
                   content="structure scoresystem/schooltool:content/legend" />
    ''')

    def updateDialog(self):
        # XXX: fix the width of dialog content in css
        if self.ajax_settings['dialog'] != 'close':
            self.ajax_settings['dialog']['width'] = 192 + 16

    def initDialog(self):
        self.ajax_settings['dialog'] = {
            'autoOpen': True,
            'modal': False,
            'resizable': False,
            'draggable': True,
            'position': ['center','middle'],
            'width': 'auto',
            }


class AbsenceScoreSystemLegend(flourish.content.ContentProvider):

    title = _('Attendance')

    def getLegendItems(self):
        score_system = self.context
        for grade, title in score_system.scores:
            meaning = []
            if grade in score_system.tag_absent:
                meaning.append(translate(_('Absent'), context=self.request))
            if grade in score_system.tag_tardy:
                meaning.append(translate(_('Tardy'), context=self.request))
            if not meaning:
                meaning.append(translate(_('Present'), context=self.request))
            if grade in score_system.tag_excused:
                meaning.append(translate(_('Excused'), context=self.request))
            yield {'value': grade,
                   'description': title,
                   'meaning': ', '.join(meaning)
                   }


class CustomScoreSystemLegend(flourish.content.ContentProvider):

    @property
    def scoresystem(self):
        return self.context

    def getGrades(self):
        result = []
        scoresystem = self.scoresystem
        scores = sorted(scoresystem.scores, key=lambda s: s[3])
        for score, abbr, val, percent in scores:
            result.append({
                'value': score,
                'points': val,
                'passing': scoresystem.isPassingScore(score),
                })
        return result


class SectionJournalLinkViewlet(flourish.page.LinkViewlet):

    @Lazy
    def journal(self):
        journal = ISectionJournal(self.context, None)
        return journal

    @property
    def url(self):
        journal = self.journal
        if journal is None:
            return None
        return absoluteURL(journal, self.request)

    @property
    def enabled(self):
        if not super(SectionJournalLinkViewlet, self).enabled:
            return False
        journal = self.journal
        if journal is None:
            return None
        can_view = flourish.canView(journal)
        return can_view


class FlourishActivityPopupMenuView(flourish.content.ContentProvider):

    def __init__(self, view, request):
        flourish.content.ContentProvider.__init__(self, view.context, request, view)

    def translate(self, message):
        return translate(message, context=self.request)

    def __call__(self):
        result = {}
        app = ISchoolToolApplication(None)
        tzinfo = pytz.timezone(IApplicationPreferences(app).timezone)
        activity_id = self.request.get('activity_id')
        meetings = dict([(meeting.__name__, meeting)
                         for meeting in self.context.meetings])

        if activity_id is not None and activity_id in meetings:
            meeting = meetings[activity_id]
            meetingDate = meeting.dtstart.astimezone(tzinfo).date()
            info = {
                'longTitle': meetingDate.strftime("%Y-%m-%d"),
                'hash': activity_id,
                }
            url = absoluteURL(self.view, self.request)
            result['header'] = info['longTitle']
            result['options'] = [
                {
                    'label': self.translate(_('Fill down')),
                    'url': '#',
                    'css_class': 'filldown',
                    },
                {
                    'label': self.translate(_('Sort by')),
                    'url': '%s?sort_by=%s&month=%s' % (
                        url, info['hash'], meetingDate.month),
                    }
                ]
        response = self.request.response
        response.setHeader('Content-Type', 'application/json')
        encoder = flourish.tal.JSONEncoder()
        json = encoder.encode(result)
        return json


class FlourishStudentPopupMenuView(flourish.content.ContentProvider):

    def __init__(self, view, request):
        flourish.content.ContentProvider.__init__(self, view.context, request, view)

    def translate(self, message):
        return translate(message, context=self.request)

    def __call__(self):
        result = {}
        student_id = self.request.get('student_id')
        if student_id is not None:
            app = ISchoolToolApplication(None)
            student = app['persons'].get(student_id)
            if student is not None and student in self.context.members:
                journal_url = absoluteURL(self.view, self.request)
                student_url = absoluteURL(student, self.request)
                result['header'] = student.title
                result['options'] = [
                    {
                        'label': self.translate(_('Student')),
                        'url': student_url,
                        },
                    {
                        'label': self.translate(_('History')),
                        'url': '%s/score_history?student_id=%s&month=%s' % (
                            journal_url, student_id, self.view.active_month),
                        },
                    ]
        response = self.request.response
        response.setHeader('Content-Type', 'application/json')
        encoder = flourish.tal.JSONEncoder()
        json = encoder.encode(result)
        return json


class FlourishNamePopupMenuView(flourish.content.ContentProvider):

    def __init__(self, view, request):
        flourish.content.ContentProvider.__init__(self, view.context, request, view)

    def translate(self, message):
        return translate(message, context=self.request)

    @Lazy
    def name_sorting_columns(self):
        return getUtility(IPersonFactory).columns()

    def __call__(self):
        column_id = self.request.get('column_id')
        for column in self.name_sorting_columns:
            if column.name == column_id:
                break
        result = {
            'header': self.translate(column.title),
            'options': [
                {
                    'label': self.translate(_('Sort by')),
                    'url': '?sort_by=%s' % column_id,
                    }
                ],
            }
        response = self.request.response
        response.setHeader('Content-Type', 'application/json')
        encoder = flourish.tal.JSONEncoder()
        json = encoder.encode(result)
        return json


class FlourishTotalPopupMenuView(flourish.content.ContentProvider):

    def __init__(self, view, request):
        flourish.content.ContentProvider.__init__(self, view.context, request, view)

    titles = {
        'total': _('Total'),
        'average': _('Ave.'),
        'tardies': _('Trd.'),
        'absences': _('Abs.'),
        'excused': _('Exc.'),
        }

    def translate(self, message):
        return translate(message, context=self.request)

    def __call__(self):
        result = {}
        column_id = self.request.get('column_id')
        if column_id in self.titles:
            result['header'] = self.translate(self.titles[column_id])
            result['options'] = [
                {
                    'label': self.translate(_('Sort by')),
                    'url': '?sort_by=%s' % column_id,
                    },
                ]
        response = self.request.response
        response.setHeader('Content-Type', 'application/json')
        encoder = flourish.tal.JSONEncoder()
        json = encoder.encode(result)
        return json


class FlourishRequestJournalExportGrades(RequestXLSReportDialog):

    report_builder = 'grades.xls'
    task_factory = JournalXLSReportTask


class FlourishRequestJournalExportAttendance(RequestXLSReportDialog):

    report_builder = 'attendance.xls'
    task_factory = JournalXLSReportTask


class DateHeader(export.Header):

    @property
    def style(self):
        result = super(DateHeader, self).style.copy()
        result['format_str'] = 'YYYY-MM-DD'
        return result


class FlourishJournalExportBase(export.ExcelExportView):

    def print_headers(self, ws):
        row_1_headers = [export.Header(label)
                         for label in ['ID', 'First name', 'Last name']]
        row_2_headers = [export.Header('') for i in range(3)]
        for activity_info in self.activities:
            row_1_headers.append(DateHeader(activity_info['date']))
            row_2_headers.append(export.Header(activity_info['period']))
        for col, header in enumerate(row_1_headers):
            self.write(ws, 0, col, header.data, **header.style)
        for col, header in enumerate(row_2_headers):
            self.write(ws, 1, col, header.data, **header.style)

    def studentSortKey(self, value):
        student = self.persons[value['student']['id']]
        return IDemographics(student).get('ID', '')

    def print_grades(self, ws, nmonth, total_months):
        starting_row = 2
        table = sorted(self.table(), key=lambda x:self.studentSortKey)
        for i, row in enumerate(table):
            student = self.persons[row['student']['id']]
            cells = [export.Text(IDemographics(student).get('ID', '')),
                     export.Text(student.first_name),
                     export.Text(student.last_name)]
            for grade in row['grades']:
                value = grade['value']
                cells.append(export.Text(value))
            for col, cell in enumerate(cells):
                self.write(ws, starting_row+i, col, cell.data, **cell.style)
            self.progress('journal', normalized_progress(
                    nmonth, total_months,
                    i, len(table),
                    ))

    def export_month_worksheets(self, wb):
        months = list(self.selected_months)
        for nm, month_id in enumerate(months):
             self._active_month = month_id
             title = self.monthTitle(month_id)
             ws = wb.add_sheet(title)
             self.print_headers(ws)
             self.print_grades(ws, nm, len(months))
             self.progress('journal', normalized_progress(
                     nm, len(months),
                     ))
        self.finish('journal')

    def addImporters(self, progress):
        self.task_progress.add(
            'journal',
            title=_('Journal'), progress=0.0)

    def __call__(self):
        self.makeProgress()
        self.task_progress.title = _("Exporting")
        self.addImporters(self.task_progress)
        app = ISchoolToolApplication(None)
        self.persons = app['persons']
        self.tzinfo = pytz.timezone(IApplicationPreferences(app).timezone)
        workbook = xlwt.Workbook()
        self.export_month_worksheets(workbook)
        return workbook

    @property
    def active_month(self):
        return self._active_month

    @property
    def meetings(self):
        result = []
        for event in self.all_meetings:
            insecure_event = removeSecurityProxy(event)
            meeting_start = insecure_event.dtstart.astimezone(self.tzinfo)
            if meeting_start.month == self.active_month:
                result.append(event)
        return result

    @property
    def activities(self):
        result = []
        for meeting in self.meetings:
            info = {}
            insecure_meeting = removeSecurityProxy(meeting)
            meetingDate = insecure_meeting.dtstart.astimezone(self.tzinfo).date()
            info['date'] = meetingDate
            try:
                if meeting.period is not None:
                    short_title = meeting.period.title
                else:
                    short_title = ''
                period = short_title
                if period[-1] == ':':
                    period = period[:-1]
            except:
                period = ''
            info['period'] = period
            result.append(info)
        return result


class FlourishJournalExportGrades(FlourishJournalExportBase,
                                  FlourishLyceumSectionJournalGrades):

    @property
    def base_filename(self):
        section = ISection(self.context)
        filename = '%s journal scores' % section.title
        filename = filename.replace(' ', '_')
        return filename



class FlourishJournalExportAttendance(FlourishJournalExportBase,
                                      FlourishLyceumSectionJournalAttendance):

    @property
    def base_filename(self):
        section = ISection(self.context)
        filename = '%s attendance' % section.title
        filename = filename.replace(' ', '_')
        return filename


class JournalModes(flourish.page.RefineLinksViewlet):
    pass


def getSectionJournalModes(person, section, request):
    journal_url = absoluteURL(section, request) + '/journal'

    result = []
    result.append({
            'id': 'journal-mode-attendance',
            'label': _('Attendance'),
            'url': journal_url,
            })

    takes_day_attendance = True
    journal = ISectionJournal(section)
    homerooms = queryMultiAdapter(
        (journal, request), name='homeroom.html')
    if (homerooms is None or
        not homerooms.all_meetings):
        takes_day_attendance = False
    if takes_day_attendance:
        result.append({
                'id': 'journal-mode-homeroom',
                'label': _('Homeroom'),
                'url': journal_url + '/homeroom.html',
                })

    result.append({
            'id': 'journal-mode-grades',
            'label': _('Scores'),
            'url': journal_url + '/grades.html',
            })
    return result


class JournalModeContent(flourish.content.ContentProvider):

    @Lazy
    def person(self):
        person = IPerson(self.request.principal, None)
        return person

    @Lazy
    def section(self):
        person = self.person
        if person is None:
            return None
        section = getCurrentSectionTaught(person)
        if section is None:
            sections = list(IInstructor(person).sections())
            if not sections:
                return None
            section = sections[0]
        return section

    def getSchoolModes(self):
        if not inCrowd(self.request.principal, 'clerks', context=self.context):
            return []
        app = ISchoolToolApplication(None)
        persons = app['persons']
        persons_url = absoluteURL(persons, self.request)
        result = []
        result.append({
                'id': 'journal-mode-school-attendance',
                'label': _('School Attendance'),
                'url': persons_url + '/attendance.html',
                })
        return result

    def getSectionModes(self):
        section = self.section
        if section is None:
            return []
        person = self.person
        if person is None:
            return []
        result = getSectionJournalModes(person, section, self.request)
        return result

    @Lazy
    def modes(self):
        result = []
        result.extend(self.getSchoolModes())
        result.extend(self.getSectionModes())
        return result

    def render(self):
        return ''


class JournalModeSelector(flourish.viewlet.Viewlet):

    list_class = 'filter'

    template = InlineViewPageTemplate('''
        <ul tal:attributes="class view/list_class"
            tal:condition="view/items">
          <li tal:repeat="item view/items">
            <input type="radio"
                   onclick="ST.redirect($(this).context.value)"
                   tal:attributes="value item/url;
                                   id item/id;
                                   checked item/selected;" />
            <label tal:content="item/label"
                   tal:attributes="for item/id" />
          </li>
        </ul>
    ''')

    @Lazy
    def items(self):
        content = self.manager.view.providers.get('lyceum-journal-modes')
        if not content:
            return []

        current = getCurrentJournalMode(IPerson(self.request.principal, None)) or ''
        result = list(content.modes)
        for mode in result:
            mode['selected'] = bool(mode['id'] == current)
        return result

    def render(self, *args, **kw):
        if len(self.items) < 2:
            return ''
        return self.template(*args, **kw)



class SubPage(flourish.content.ContentProvider,
              flourish.page.Page):

    update = flourish.page.Page.update
    render = flourish.page.Page.render
    __call__ = flourish.page.Page.__call__

    def __init__(self, context, request):
        view = context
        flourish.content.ContentProvider.__init__(
            self, view.context, request, view)


class SectionJournalGradeHistory(SubPage):

    @property
    def title(self):
        section = self.context.section
        return section.title

    @Lazy
    def student(self):
        student_id = self.request.get('student_id')
        if student_id is None:
            return None
        app = ISchoolToolApplication(None)
        student = app['persons'].get(student_id)
        return student

    @property
    def meetings(self):
        calendar = ISchoolToolCalendar(self.context.section)
        sorted_events = sorted(calendar, key=lambda e: e.dtstart)
        return sorted_events

    @property
    def timezone(self):
        app = ISchoolToolApplication(None)
        return pytz.timezone(IApplicationPreferences(app).timezone)

    @property
    def timeformat(self):
        app = ISchoolToolApplication(None)
        prefs = IApplicationPreferences(app)
        return prefs.timeformat

    def formatScoreValue(self, requirement, score):
        if (score is None or score.value is UNSCORED):
            return ''
        return score.value

    def table(self):
        if self.student is None:
            return []

        persons = ISchoolToolApplication(None)['persons']
        evaluations = removeSecurityProxy(IEvaluations(self.student))
        result = []

        meetings = self.meetings
        timezone = self.timezone
        timeformat = self.timeformat

        for meeting in meetings:
            requirement = self.view.makeRequirement(removeSecurityProxy(meeting))
            scores = list(evaluations.getHistory(requirement))
            current = evaluations.get(requirement)
            if (scores or current is not None):
                scores.append(current)
            if not scores:
                continue
            scores.reverse()
            meeting_time = meeting.dtstart.astimezone(timezone)
            activity = {
                'date': meeting_time.date(),
                'time': meeting_time.time().strftime(timeformat),
                'period': '',
                'grades': [],
                }
            if meeting.period is not None:
                activity['period'] = meeting.period.title

            for score in scores:
                record = {'date': '',
                          'time': '',
                          'value': '',
                          'evaluator': None}
                record['value'] = self.formatScoreValue(requirement, score)

                if score is not None:
                    if score.evaluator:
                        record['evaluator'] = persons.get(score.evaluator)

                    if (getattr(score, 'time', None) is not None):
                        time_utc = pytz.utc.localize(score.time)
                        time = time_utc.astimezone(timezone)
                        record['date'] = time.date()
                        record['time'] = time.strftime(timeformat)

                activity['grades'].append(record)

            result.append(activity)

        return result

    @property
    def done_url(self):
        month = None
        try:
            month = int(self.request.get('month'))
        except TypeError:
            pass
        except ValueError:
            pass
        if month is not None:
            return self.view.monthURL(month)
        return absoluteURL(self.view, self.request)


class SectionJournalAttendanceHistory(SectionJournalGradeHistory):

    def formatScoreValue(self, requirement, score):
        if (score is None or score.value is UNSCORED):
            return ''
        grade = score.value
        if IAttendanceScoreSystem.providedBy(requirement.score_system):
            description = dict(requirement.score_system.scores).get(grade, u'')
        else:
            description = ''
        result = ' - '.join([translate(i, context=self.request)
                             for i in (grade, description)])
        return result


class FlourishSchoolYearMyJournalView(flourish.page.Page):

    @property
    def subtitle(self):
        return self.context.title

    @property
    def person(self):
        return IPerson(self.request.principal, None)

    @property
    def sections(self):
        if self.person is None:
            return []
        result = []
        for section in ILearner(self.person).sections():
            term = ITerm(section)
            if ISchoolYear(term) != self.context:
                continue
            result.append([term.first, section.title, term, section])
        return [(term, section)
                 for first, title, term, section in sorted(result)]

    def getEventGrades(self, section):
        person = self.person
        if person is None:
            return
        section_journal_data = ISectionJournalData(section)
        for event in ISchoolToolCalendar(section):
            grade = section_journal_data.getGrade(person, event)
            if not grade:
                continue
            yield event, grade

    def getEventAttendanceScores(self, section):
        person = self.person
        if person is None:
            return
        evaluations = removeSecurityProxy(IEvaluations(person))
        for event in ISchoolToolCalendar(section):
            requirement = AttendanceRequirement(removeSecurityProxy(event))
            score = evaluations.get(requirement)
            if not score:
                continue
            yield event, score

    def collectAttendance(self, attr):
        days = {}
        for term, section in self.sections:
            for event, score in self.getEventAttendanceScores(section):
                if (not IAttendanceScoreSystem.providedBy(score.scoreSystem) or
                    not getattr(score.scoreSystem, attr)(score)):
                    continue
                days.setdefault(event.dtstart.date(), []).append(
                    (event.dtstart, event.period.title))
        result = []
        for day, periods in sorted(days.items()):
            result.append({
                'day': day,
                'period': ', '.join([period for dt, period in sorted(periods)]),
                })
        return result

    @property
    def absences(self):
        result = self.collectAttendance('isAbsent')
        return result

    @property
    def tardies(self):
        result = self.collectAttendance('isTardy')
        return result

    @property
    def participation(self):
        result = []
        for term, section in self.sections:
            average, count = 0, 0
            for event, grade in self.getEventGrades(section):
                if grade is None:
                    continue
                try:
                    grade = int(grade)
                except ValueError:
                    continue
                average += grade
                count += 1
            if not count:
                continue
            average /= float(count)
            result.append({
                'term': term.title,
                'section': section.title,
                'average': '%.1f' % average,
                })
        return result


class FlourishSchoolAttendanceView(flourish.page.Page):
    content_template = InlineViewPageTemplate('''
      <div>
        <tal:block content="structure context/schooltool:content/ajax/table" />
      </div>
    ''')

    container_class = 'container widecontainer'

    @Lazy
    def year(self):
        year = self.request.get('year', '').strip()
        if year:
            try:
                year = int(year)
            except ValueError:
                pass
        if not year:
            dateman = getUtility(IDateManager)
            year = dateman.today.year
        return year

    @Lazy
    def month(self):
        month = self.request.get('month', '').strip()
        if month:
            try:
                month = int(month)
            except ValueError:
                pass
        if not month:
            dateman = getUtility(IDateManager)
            month = dateman.today.month
        return month

    @Lazy
    def schoolyears(self):
        years = []
        for term in self.terms:
            year = term.__parent__
            if year not in years:
                years.append(year)
        return years

    @Lazy
    def terms(self):
        terms = ITermContainer(None, {})
        selected = set()
        year = self.year
        month = self.month
        for day in filter(None, calendar.Calendar().itermonthdays(year, month)):
            date = datetime.date(year, month, day)
            for term in terms.values():
                if date in term and term not in selected:
                    selected.add(term)
        return sorted(selected, key=lambda term: term.first)

    @Lazy
    def group(self):
        params = self.request.get('group', '').strip().split('.')
        if len(params) != 2:
            return None
        year_id, group_id = params
        if year_id not in [year.__name__ for year in self.schoolyears]:
            return None
        app = ISchoolToolApplication(None)
        year = ISchoolYearContainer(app).get(year_id)
        if year is None:
            return None
        group = IGroupContainer(year).get(group_id)
        return group

    @Lazy
    def instructor(self):
        username = self.request.get('instructor', '').strip()
        app = ISchoolToolApplication(None)
        return app['persons'].get(username)

    def updateJournalMode(self):
        person = IPerson(self.request.principal, None)
        if person is None:
            return
        mode = getCurrentJournalMode(person) or ''
        if mode == 'journal-mode-school-attendance':
            return
        setCurrentJournalMode(person, 'journal-mode-school-attendance')

    def update(self):
        self.updateJournalMode()
        super(FlourishSchoolAttendanceView, self).update()

    @Lazy
    def name_sorting_columns(self):
        return getUtility(IPersonFactory).columns()


class AttendanceFilter(table.ajax.IndexedTableFilter):

    def instructorSections(self, instructor, terms):
        sections = set()
        for section in Instruction.query(instructor=self.view.instructor):
            term = ITerm(section)
            if term not in terms:
                continue
            sections.add(section)
        return sections

    def termSections(self, terms):
        sections = set()
        for term in self.view.terms:
            container = ISectionContainer(term)
            for section in container.values():
                if section not in sections:
                    sections.add(section)
        return sections

    def availableSections(self):
        instructor = self.view.instructor
        terms = set([removeSecurityProxy(term) for term in self.view.terms])
        if instructor:
            sections = self.instructorSections(instructor, terms)
            return sections
        if terms:
            sections = self.termSections(terms)
            return sections
        return None

    @Lazy
    def section_student_ids(self):
        sections = self.availableSections()
        if sections is None:
            return None
        int_ids = getUtility(IIntIds)
        ids = {}
        for section in sections:
            unsecure_section = removeSecurityProxy(section)
            for person in unsecure_section.members:
                if person in ids:
                    continue
                intid = int_ids.queryId(person, None)
                if intid is None:
                    continue
                ids[person] = intid
        return set(ids.values())

    def filterBySection(self, items):
        available_ids = self.section_student_ids
        if available_ids is None:
            return items
        return [item for item in items if item['id'] in available_ids]

    def filterByGroup(self, items):
        if not self.view.group:
            return items
        int_ids = getUtility(IIntIds)
        group_person_ids = set([
                int_ids.queryId(person)
                for person in self.view.group.members
                ])
        items = [item for item in items
                 if item['id'] in group_person_ids]
        return items

    def filter(self, items):
        items = self.filterBySection(items)
        items = self.filterByGroup(items)
        if self.ignoreRequest:
            return items
        return table.ajax.IndexedTableFilter.filter(self, items)


class AttendanceTable(table.ajax.IndexedTable):

    no_default_url_cell_formatter = True
    form_class = 'grid-form'
    form_id = 'grid-form'

    def columns(self):
        return getUtility(IPersonFactory).columns()

    def sortOn(self):
        return getUtility(IPersonFactory).sortOn()


class AttendanceTableTable(flourish.viewlet.Viewlet):

    template = flourish.templates.HTMLFile('templates/f_school_attendance.pt')

    persons = None

    def extractItems(self):
        formatter = self.manager.makeFormatter()
        self.persons = [
            table.catalog.unindex(item)
            for item in formatter.getItems()
            ]

    def render(self, *args, **kw):
        self.extractItems()
        return self.template()

    @Lazy
    def batch(self):
        params = {'start': None,
                  'size': None,
                  'postfix': self.manager.__name__}
        batch = self.manager.get('batch')
        if batch is not None:
            params['start'] = getattr(batch, 'start', None)
            params['size'] = getattr(batch, 'size', None)
        return params


class FlourishSchoolAttendanceGradebook(flourish.content.ContentProvider,
                                        FlourishSectionHomeroomAttendance):

    no_periods_text = _("There are no school days this month.")

    def __init__(self, context, request, view):
        flourish.content.ContentProvider.__init__(self, context, request, view)
        FlourishSectionHomeroomAttendance.__init__(self, context, request)

    def update(self):
        app = ISchoolToolApplication(None)
        self.tzinfo = pytz.timezone(IApplicationPreferences(app).timezone)
        meetings = self.all_meetings
        if not meetings:
            self.no_periods = True
            self.render_journal = False
            return

        self.updateJournalMode()
        if 'UPDATE_SUBMIT' in self.request:
            self.updateGradebook()

    def getSelectedTerm(self):
        return None

    @Lazy
    def selected_terms(self):
        table = self.view
        return table.view.terms

    @property
    def selected_year(self):
        table = self.view
        return table.view.year

    @property
    def selected_month(self):
        table = self.view
        return table.view.month

    def members(self):
        return self.view.persons

    def allMeetings(self):
        terms = removeSecurityProxy(self.selected_terms)
        if not terms:
            return ()

        year = self.selected_year
        month = self.selected_month

        dates = [self.tzinfo.localize(datetime.datetime(year, month, day))
                 for day in calendar.Calendar().itermonthdays(year, month)
                 if day]

        meetings = []

        for dt in dates:
            date = dt.date()
            for term in terms:
                if date in term and term.isSchoolday(date):
                    # meeting duration is not precise - some days are not 24 hours long
                    meetings.append(makeSchoolAttendanceMeeting(dt))
        return meetings

    def getScores(self, person):
        if person in self._grade_cache:
            return list(self._grade_cache[person])
        self._grade_cache[person] = result = []
        unique_meetings = set()
        terms = self.selected_terms
        events = list(self.all_meetings)
        sorted_events = sorted(events, key=lambda e: e.dtstart)
        unproxied_person = removeSecurityProxy(person)
        for event in sorted_events:
            date = event.dtstart.date()
            if not any([date in term for term in terms]):
                continue
            unproxied_event = removeSecurityProxy(event)
            requirement = self.makeRequirement(unproxied_event)
            score = IEvaluateRequirement(requirement).getEvaluation(
                    unproxied_person, requirement, default=UNSCORED)
            if (event.meeting_id not in unique_meetings and
                score is not UNSCORED):
                result.append(score)
                unique_meetings.add(event.meeting_id)
        return result


class FlourishAttendanceValidateScoreView(flourish.ajax.AJAXPart):

    def render(self):
        if not self.fromPublication:
            return ''
        data = self.validate_score()
        json = self.setJSONResponse(data)
        return json

    @property
    def requirement(self):
        activity_id = self.request.get('activity_id')
        if activity_id is None:
            return None
        dts = base64.decodestring(activity_id.strip())
        try:
            dt = dateutil.parser.parse(dts)
        except ValueError:
            return None
        meeting = makeSchoolAttendanceMeeting(dt)
        requirement = HomeroomRequirement(meeting)
        return requirement

    def validate_score(self):
        score = self.request.get('score')
        result = {'is_valid': True,
                  'is_extracredit': False}
        requirement = self.requirement
        if requirement is None:
            result['is_valid'] = False
        else:
            result['is_valid'] = requirement.score_system.isValidScore(score)
        return result


class RefineFormManager(flourish.page.ContentViewletManager):
    template = flourish.templates.Inline("""
        <form method="get">
          <tal:block repeat="viewlet view/viewlets">
            <div class="content"
                 tal:define="rendered viewlet;
                             stripped rendered/strip|nothing"
                 tal:condition="stripped"
                 tal:content="structure stripped">
            </div>
          </tal:block>
        </form>
    """)


class OptionalViewlet(flourish.viewlet.Viewlet):

    enabled = True

    def render(self, *args, **kw):
        if not self.enabled:
            return ''
        return self.template(*args, **kw)


class FlourishSchoolAttendanceDateNavigation(flourish.page.RefineLinksViewlet):
    """School attendance date navigation viewlet."""


class FlourishSchoolAttendanceYearMonthPicker(OptionalViewlet):
    template = InlineViewPageTemplate('''
    <select name="year" class="navigator"
            tal:define="years view/years"
            tal:condition="years"
            onchange="$(this).closest('form').submit()">
      <option tal:repeat="year years"
              tal:attributes="value year/value;
                              selected year/selected"
              tal:content="year/title" />
    </select>
    <select name="month" class="navigator"
            tal:define="months view/months"
            tal:condition="months"
            onchange="$(this).closest('form').submit()">
      <option tal:repeat="month months"
              tal:attributes="value month/value;
                              selected month/selected"
              tal:content="month/title" />
    </select>
    ''')

    def years(self):
        this_year = self.view.year
        terms = ITermContainer(None)
        min_year = min([this_year] +
                       [term.first.year for term in terms.values() if term.first])
        max_year = max([this_year] +
                       [term.last.year for term in terms.values() if term.last])
        years = [{'selected': year == this_year,
                  'title': str(year),
                  'value': str(year)}
                 for year in range(min_year, max_year+1)]
        return years

    def months(self):
        this_month = self.view.month

        months = [{'selected': month == this_month,
                   'title': title,
                   'value': str(month)}
                  for month, title in month_names.items()]
        return months

    def terms(self):
        return self.view.terms


class FlourishSchoolAttendanceTermNavigation(flourish.page.RefineLinksViewlet):
    """School attendance date navigation viewlet."""


class FlourishSchoolAttendanceCurrentTerm(OptionalViewlet):
    template = InlineViewPageTemplate('''
    <ul tal:repeat="term view/view/terms">
      <li i18n:translate="">
        School year
        <tal:block i18n:name="schoolyear" content="term/__parent__/@@title" />,
        term <tal:block i18n:name="term" content="term/@@title" />.
      </li>
    </ul>
    ''')

    @property
    def enabled(self):
        return bool(self.view.terms)


class FlourishSchoolAttendanceGroupNavigation(flourish.page.RefineLinksViewlet):
    """School attendance date navigation viewlet."""


class FlourishSchoolAttendanceGroupPicker(OptionalViewlet):
    template = InlineViewPageTemplate('''
    <select name="group" class="navigator"
            onchange="$(this).closest('form').submit()">
      <option i18n:translate="" value="">Everybody</option>
      <tal:block repeat="year view/groups_by_year">
        <option disabled="disabled"
                class="separator"
                tal:content="year/title" />
        <option tal:repeat="group year/groups"
                tal:attributes="value group/value;
                                selected group/selected"
                tal:content="group/title" />
      </tal:block>
    </select>
    ''')

    @property
    def enabled(self):
        return any([len(year['groups']) for year in self.groups_by_year])

    @Lazy
    def groups_by_year(self):
        result = []
        selected_group = self.view.group
        selected_key = None
        if self.view.group:
            selected_key = '%s.%s' % (
                ISchoolYear(selected_group.__parent__).__name__,
                selected_group.__name__)

        collator = ICollator(self.request.locale)
        for year in self.view.schoolyears:
            key = lambda g: '%s.%s' % (year.__name__, g.__name__)
            groups = sorted(IGroupContainer(year).values(),
                            key=lambda g: collator.key(g.title))
            result.append({
                'title': year.title,
                'groups': [
                    {'title': group.title,
                     'value': key(group),
                     'selected': key(group) == selected_key}
                    for group in groups],
                })
        return result


class FlourishSchoolAttendanceInstructorNavigation(flourish.page.RefineLinksViewlet):
    """School attendance date navigation viewlet."""


class FlourishSchoolAttendanceInstructorPicker(OptionalViewlet):
    template = InlineViewPageTemplate('''
    <select name="instructor" class="navigator"
            onchange="$(this).closest('form').submit()">
      <option i18n:translate="" value="">All instructors</option>
      <option tal:repeat="instructor view/instructors"
              tal:attributes="value instructor/value;
                              selected instructor/selected"
              tal:content="instructor/title" />
    </select>
    ''')

    @property
    def enabled(self):
        return len(self.instructors)

    @Lazy
    def instructors(self):
        instructors = set()
        selected_instructor = self.view.instructor
        selected_username = selected_instructor and selected_instructor.__name__

        for term in self.view.terms:
            sections = ISectionContainer(term)
            for section in sections.values():
                if len(section.members):
                    instructors.update(section.instructors)

        collator = ICollator(self.request.locale)
        factory = getUtility(IPersonFactory)
        sorting_key = lambda x: factory.getSortingKey(x, collator)
        instructors = sorted(instructors, key=sorting_key)

        result = [
            {'title': instructor.title,
             'value': instructor.__name__,
             'selected': instructor.__name__ == selected_username,
             }
            for instructor in instructors]
        return result


class SSValidationError(Exception):

    message = None

    def __init__(self, msg):
        self.message = msg
        Exception.__init__(self)


class FlourishAttendanceScoreSystemAddView(BrowserView):
    """A view for adding a custom score system"""

    def update(self):
        self.message = ''
        if 'form-submitted' in self.request:
            if 'CANCEL' in self.request:
                self.request.response.redirect(self.nextURL())

            try:
                self.validateForm()
            except SSValidationError, e:
                self.message = e.message
                return

            if 'UPDATE_SUBMIT' in self.request:
                try:
                    self.validateScores()
                except SSValidationError, e:
                    self.message = e.message
                    return
                target = PersistentAttendanceScoreSystem(self.validTitle)
                self.updateScoreSystem(target)
                self.addScoreSystem(target)
                self.request.response.redirect(self.nextURL())

    def addScoreSystem(self, target):
        chooser = INameChooser(self.context)
        name = chooser.chooseName(target.title, target)
        self.context[name] = target

    def nextURL(self):
        return absoluteURL(self.context, self.request)

    def scores(self):
        rownum = 1
        results = []
        for value, title, absence, excused in self.getRequestScores():
            results.append(self.buildScoreRow(rownum, value, title, absence, excused))
            rownum += 1
        results.append(self.buildScoreRow(rownum, '', '', '', ''))
        return results

    def buildScoreRow(self, rownum, value, title, absence, excused):
        return {
            'value_name': 'value' + unicode(rownum),
            'value': value,
            'title_name': 'title' + unicode(rownum),
            'title_value': title,
            'absence_name': 'absence' + unicode(rownum),
            'present': not absence and 'selected',
            'absent': absence == 'a' and 'selected',
            'tardy': absence == 't' and 'selected',
            'excused_name': 'excused' + unicode(rownum),
            'excused': excused and 'checked',
            }

    def getRequestScores(self):
        rownum = 0
        results = []
        while True:
            rownum += 1
            value_name = 'value' + unicode(rownum)
            title_name = 'title' + unicode(rownum)
            absence_name = 'absence' + unicode(rownum)
            excused_name = 'excused' + unicode(rownum)
            if value_name not in self.request:
                break
            if not len(self.request[value_name]):
                continue
            results.append((self.request[value_name],
                            self.request[title_name],
                            self.request[absence_name],
                            bool(self.request.get(excused_name))))
        return results

    def validateForm(self):
        title = self.request.get('title', '').strip()
        if not len(title):
            raise SSValidationError(_('The title field must not be empty'))
        self.validTitle = title

        scores = []
        for value, title, absence, excused in self.getRequestScores():
            value = value.strip().lower()
            title = title.strip()
            scores.append([value, title, absence, excused])
        self.validScores = scores

    def validateScores(self):
        if len(self.validScores) < 1:
            raise SSValidationError(_('A score system must have at least one value.'))

        all_values = set()
        all_titles = set()
        for value, title, absence, excused in self.validScores:
            if value in all_values:
                raise SSValidationError(_('Duplicate value: ${value}',
                                          mapping={'value': value}))
            all_values.add(value)
            if not title.strip():
                raise SSValidationError(_('Title required for: ${value}',
                                          mapping={'value': value}))
            if title in all_titles:
                raise SSValidationError(_('Duplicate title: ${title}',
                                          mapping={'title': title}))
            all_titles.add(title)

    def updateScoreSystem(self, target):
        target.scores = tuple([(s[0], s[1]) for s in self.validScores])
        target.tag_absent = tuple([s[0] for s in self.validScores if s[2] == 'a'])
        target.tag_tardy = tuple([s[0] for s in self.validScores if s[2] == 't'])
        target.tag_excused = tuple([s[0] for s in self.validScores if s[3]])


class FlourishAttendanceScoreSystemView(BrowserView):
    """A view for adding a custom score system"""

    @property
    def subtitle(self):
        return self.scoresystem.title

    @property
    def scoresystem(self):
        return self.context

    def scores(self):
        scoresystem = self.scoresystem
        results = []
        for score in self.context.scores:
            tags = []
            value = score[0]
            if value in scoresystem.tag_absent:
                tags.append(_('Absent'))
            if value in scoresystem.tag_tardy:
                tags.append(_('Tardy'))
            if not tags:
                tags.append(_('Present'))
            if value in scoresystem.tag_excused:
                tags.append(_('Excused'))
            tags = ', '.join([translate(t, self.request)
                              for t in tags])
            results.append({
                    'value': score[0],
                    'description': score[1],
                    'tags': tags,
                    })
        return results

    def done_link(self):
        return absoluteURL(self.context.__parent__, self.request)


class EditDefaultJournalScoreSystems(flourish.form.Form, z3c.form.form.EditForm):

    fields = z3c.form.field.Fields(IJournalScoreSystemPreferences)

    legend = _('Customize')

    def updateActions(self):
        super(EditDefaultJournalScoreSystems, self).updateActions()
        self.actions['apply'].addClass('button-ok')
        self.actions['cancel'].addClass('button-cancel')

    @z3c.form.button.buttonAndHandler(s_('Done'), name="apply")
    def handle_apply_action(self, action):
        super(EditDefaultJournalScoreSystems,self).handleApply.func(self, action)
        if (self.status == self.successMessage or
            self.status == self.noChangesMessage):
            self.request.response.redirect(self.nextURL())

    @z3c.form.button.buttonAndHandler(s_('Cancel'))
    def handle_cancel_action(self, action):
        self.request.response.redirect(self.nextURL())

    def nextURL(self):
        return absoluteURL(self.context, self.request)

    def getContent(self):
        app = ISchoolToolApplication(None)
        prefs = IJournalScoreSystemPreferences(app)
        return prefs
