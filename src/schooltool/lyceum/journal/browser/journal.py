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
import xlwt
from StringIO import StringIO

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
from zope.traversing.browser.absoluteurl import absoluteURL
from zope.component import getUtility

from zc.table.column import GetterColumn
from zc.table.interfaces import IColumn
from zope.cachedescriptors.property import Lazy

from schooltool.skin import flourish
from schooltool.basicperson.interfaces import IDemographics
from schooltool.course.interfaces import ILearner, IInstructor
from schooltool.common.inlinept import InlineViewPageTemplate
from schooltool.export import export
from schooltool.person.interfaces import IPerson
from schooltool.app.browser.cal import month_names
from schooltool.app.interfaces import IApplicationPreferences
from schooltool.app.interfaces import ISchoolToolApplication
from schooltool.app.interfaces import ISchoolToolCalendar
from schooltool.report.browser.report import RequestReportDownloadDialog
from schooltool.requirement.scoresystem import UNSCORED
from schooltool.term.interfaces import ITerm
from schooltool.term.interfaces import ITermContainer
from schooltool.term.interfaces import IDateManager
from schooltool.table.interfaces import ITableFormatter, IIndexedTableFormatter
from schooltool.timetable.interfaces import IScheduleContainer
from schooltool.schoolyear.interfaces import ISchoolYear

from schooltool.lyceum.journal.journal import (ABSENT, TARDY,
    getCurrentSectionTaught, setCurrentSectionTaught)
from schooltool.lyceum.journal.journal import GradeRequirement
from schooltool.lyceum.journal.journal import AttendanceRequirement
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


JournalCSSViewlet = CSSViewlet("journal.css")


def getEvaluator(request):
    user = IPerson(request.principal, None)
    if user is None:
        return None
    return user.__name__


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
                score is not UNSCORED):
                grades.append(score.value)
        return grades

    def getAbsences(self, person):
        """Get the grades for the person."""
        grades = []
        for meeting, score in self.journal.absentMeetings(person):
            if (meeting.dtstart.date() in self.term and
                score is not UNSCORED):
                grades.append(score.value)
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
        for grade in self.getAbsences(person):
            if (grade.strip().lower() == ABSENT):
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
        for grade in self.getAbsences(person):
            if (grade.strip().lower() == TARDY):
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

    def allMeetings(self):
        term = removeSecurityProxy(self.selected_term)
        if not term:
            return ()

        # maybe expand would be better in here
        by_uid = dict([(removeSecurityProxy(e).unique_id, e)
                       for e in self.context.meetings])

        insecure_events = [removeSecurityProxy(e)
                           for e in by_uid.values()]
        insecure_events[:] = filter(lambda e: e.dtstart.date() in term,
                                    insecure_events)
        meetings = [by_uid[e.unique_id] for e in sorted(insecure_events)]
        return meetings

    @Lazy
    def all_meetings(self):
        return self.allMeetings()

    def meetings(self):
        for event in self.all_meetings:
            insecure_event = removeSecurityProxy(event)
            if insecure_event.dtstart.date().month == self.active_month:
                yield event

    def members(self):
        members = list(self.context.members)
        collator = ICollator(self.request.locale)
        members.sort(key=lambda a: collator.key(
                removeSecurityProxy(a).first_name))
        members.sort(key=lambda a: collator.key(
                removeSecurityProxy(a).last_name))
        return members

    def updateGradebook(self):
        members = self.members()
        evaluator = getEvaluator(self.request)
        for meeting in self.meetings():
            for person in members:
                cell_id = "%s.%s" % (person.__name__, meeting.__name__)
                cell_value = self.request.get(cell_id, None)
                if cell_value is not None:
                    cell_value = ATTENDANCE_TRANSLATION_TO_DATA.get(cell_value, cell_value)
                    self.context.setGrade(person, meeting, cell_value, evaluator=evaluator)

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
            # XXX: what about time zones?
            if insecure_meeting.dtstart.date().month != month:
                yield insecure_meeting.dtstart.date().month
                month = insecure_meeting.dtstart.date().month

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
            if insecure_meeting.dtstart.date().month == selected_month:
                return insecure_meeting.dtstart.year

    @Lazy
    def active_month(self):
        available_months = list(self.selected_months)
        if 'month' in self.request:
            month = int(self.request['month'])
            if month in available_months:
                return month

        term = self.selected_term
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
        evaluator = getEvaluator(self.request)
        self.context.setGrade(person, meeting, grade, evaluator=evaluator)
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

        if 'UPDATE_SUBMIT' in self.request:
            self.updateGradebook()

        app = ISchoolToolApplication(None)
        self.tzinfo = pytz.timezone(IApplicationPreferences(app).timezone)

    @Lazy
    def activities(self):
        result = []
        for meeting in self.meetings:
            info = {
                'hash': meeting.__name__,
                'cssClass': 'scorable',
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
            if insecure_event.dtstart.date().month == self.active_month:
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
        result = []
        unique_meetings = set()
        term = self.selected_term
        calendar = ISchoolToolCalendar(self.context.section)
        events = [e for e in calendar if e.dtstart.date() in term]
        sorted_events = sorted(events, key=lambda e: e.dtstart)
        for event in sorted_events:
            if event.dtstart.date() not in term:
                continue
            requirement = self.makeRequirement(event)
            score = removeSecurityProxy(self.context.getEvaluation(
                    person, requirement, default=UNSCORED))
            if (event.meeting_id not in unique_meetings and
                score is not UNSCORED):
                result.append(score)
                unique_meetings.add(event.meeting_id)
        return result


class FlourishLyceumSectionJournalGrades(FlourishLyceumSectionJournalBase):

    @property
    def title(self):
        if self.render_journal:
            return _('Enter Grades')
        else:
            if self.no_timetable:
                return _('Section is not scheduled')
            else:
                return _('No periods assigned for this section')

    def makeRequirement(self, meeting):
        return GradeRequirement(meeting)

    def updateGradebook(self):
        evaluator = getEvaluator(self.request)
        members = self.members()
        for meeting in self.meetings:
            for person in members:
                cell_id = "%s_%s" % (meeting.__name__, person.__name__)
                cell_value = self.request.get(cell_id, None)
                if cell_value is not None:
                    requirement = self.makeRequirement(removeSecurityProxy(meeting))
                    self.context.evaluate(person, requirement, cell_value,
                                          evaluator=evaluator)

    def table(self):
        result = []
        collator = ICollator(self.request.locale)
        for person in self.members():
            grades = []
            for meeting in self.meetings:
                insecure_meeting = removeSecurityProxy(meeting)
                requirement = self.makeRequirement(insecure_meeting)
                score = self.context.getEvaluation(person, requirement, default=UNSCORED)
                grade = score.value
                value = ATTENDANCE_DATA_TO_TRANSLATION.get(grade, grade)
                grade_data = {
                    'id': '%s_%s' % (meeting.__name__, person.__name__),
                    'sortKey': meeting.__name__,
                    'value': value,
                    'editable': True,
                    }
                grades.append(grade_data)
            if flourish.canView(person):
                person = removeSecurityProxy(person)
            result.append(
                {'student': {'title': person.title,
                             'id': person.username,
                             'sortKey': collator.key(person.title),
                             'url': absoluteURL(person, self.request)},
                 'grades': grades,
                 'average': self.average(person),
                })
        self.sortBy = self.request.get('sort_by')
        return sorted(result, key=self.sortKey)

    def sortKey(self, row):
        if self.sortBy == 'student':
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
                try:
                    grade = int(grade)
                except (ValueError,):
                    return (2, row['student']['sortKey'])
                return (0, grade, row['student']['sortKey'])
            else:
                return (1, row['student']['sortKey'])

    def average(self, person):
        grades = []
        scores = self.getScores(person)
        for score in scores:
            try:
                # XXX: ints!
                grade = int(score.value)
            except ValueError:
                continue
            except TypeError:
                import pdb; pdb.set_trace()
                scores = self.getScores(person)
            grades.append(grade)
        if not grades:
            return _('N/A')
        else:
            return "%.1f" % (sum(grades) / float(len(grades)))


class FlourishLyceumSectionJournalAttendance(FlourishLyceumSectionJournalBase):

    @property
    def title(self):
        if self.render_journal:
            return _('Enter Attendance')
        else:
            if self.no_timetable:
                return _('Section is not scheduled')
            else:
                return _('No periods assigned for this section')

    def makeRequirement(self, meeting):
        return AttendanceRequirement(meeting)

    def table(self):
        result = []
        collator = ICollator(self.request.locale)
        for person in self.members():
            grades = []
            for meeting in self.meetings:
                insecure_meeting = removeSecurityProxy(meeting)
                grade = self.context.getAbsence(person,
                                                insecure_meeting,
                                                default='')
                value = ATTENDANCE_DATA_TO_TRANSLATION.get(grade, grade)
                grade_data = {
                    'id': '%s_%s' % (meeting.__name__, person.__name__),
                    'sortKey': meeting.__name__,
                    'value': value,
                    'editable': True,
                    }
                grades.append(grade_data)
            if flourish.canView(person):
                person = removeSecurityProxy(person)
            result.append(
                {'student': {'title': person.title,
                             'id': person.username,
                             'sortKey': collator.key(person.title),
                             'url': absoluteURL(person, self.request)},
                 'grades': grades,
                 'absences': self.absences(person),
                 'tardies': self.tardies(person),
                })
        self.sortBy = self.request.get('sort_by')
        return sorted(result, key=self.sortKey)

    def sortKey(self, row):
        if self.sortBy == 'student':
            return row['student']['sortKey']
        elif self.sortBy == 'absences':
            return (int(row['absences']), row['student']['sortKey'])
        elif self.sortBy == 'tardies':
            return (int(row['tardies']), row['student']['sortKey'])
        else:
            grades = dict([(grade['sortKey'], grade['value'])
                          for grade in row['grades']])
            if self.sortBy in grades:
                grade = grades.get(self.sortBy)
                try:
                    grade = int(grade)
                except (ValueError,):
                    grade = ATTENDANCE_TRANSLATION_TO_DATA.get(grade)
                    if grade == ABSENT:
                        return (1, row['student']['sortKey'])
                    elif grade == TARDY:
                        return (2, row['student']['sortKey'])
                    else:
                        return (3, row['student']['sortKey'])
                return (0, grade, row['student']['sortKey'])
            else:
                return (1, row['student']['sortKey'])

    def absences(self, person):
        absences = 0
        for score in self.getScores(person):
            if (score.value == ABSENT):
                absences += 1
        if absences == 0:
            return "0"
        else:
            return str(absences)

    def tardies(self, person):
        tardies = 0
        for score in self.getScores(person):
            if (score.value == TARDY):
                tardies += 1

        if tardies == 0:
            return "0"
        else:
            return str(tardies)

    def updateGradebook(self):
        evaluator = getEvaluator(self.request)
        members = self.members()
        for meeting in self.meetings:
            for person in members:
                cell_id = "%s_%s" % (meeting.__name__, person.__name__)
                cell_value = self.request.get(cell_id, None)
                if cell_value is not None:
                    cell_value = ATTENDANCE_TRANSLATION_TO_DATA.get(cell_value,
                                                                    cell_value)
                    requirement = self.makeRequirement(removeSecurityProxy(meeting))
                    self.context.evaluate(person, requirement, cell_value,
                                          evaluator=evaluator)

    def validate_score(self, activity_id=None, score=None):
        if score is None:
            score = self.request.get('score')
        score = ATTENDANCE_TRANSLATION_TO_DATA.get(score, score)
        return FlourishLyceumSectionJournalBase.validate_score(
            self, activity_id=activity_id, score=score)


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

    def render(self):
        url = absoluteURL(self.context, self.request)
        person = IPerson(self.request.principal, None)
        if person is not None:
            section = getCurrentSectionTaught(person)
            if section is None:
                sections = list(IInstructor(person).sections())
                if sections:
                    section = sections[0]
            if section is not None:
                url = absoluteURL(section, self.request) + '/journal'
        self.request.response.redirect(url)


class FlourishJournalActionsLinks(flourish.page.RefineLinksViewlet):
    """Journal action links viewlet."""


class FlourishJournalHelpViewlet(flourish.page.ModalFormLinkViewlet):

    @property
    def dialog_title(self):
        title = _(u'Journal Help')
        return translate(title, context=self.request)


class FlourishJournalHelpView(flourish.form.Dialog):

    def updateDialog(self):
        # XXX: fix the width of dialog content in css
        if self.ajax_settings['dialog'] != 'close':
            self.ajax_settings['dialog']['width'] = 144 + 16

    def initDialog(self):
        self.ajax_settings['dialog'] = {
            'autoOpen': True,
            'modal': False,
            'resizable': False,
            'draggable': True,
            'position': ['center','middle'],
            'width': 'auto',
            }

    def getLegendItems(self):
        for grade in journal_grades():
            yield {'keys': u', '.join(grade['keys']),
                   'value': grade['value'],
                   'description': grade['legend']}


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
            url = absoluteURL(self.context, self.request)
            result['header'] = info['longTitle']
            result['options'] = [
                {
                    'label': self.translate(_('Fill down')),
                    'url': '#',
                    'css_class': 'filldown',
                    },
                {
                    'label': self.translate(_('Sort by')),
                    'url': '%s?sort_by=%s' % (url, info['hash']),
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
                url = absoluteURL(student, self.request)
                result['header'] = student.title
                result['options'] = [
                    {
                        'label': self.translate(_('Student')),
                        'url': url,
                        }
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

    def __call__(self):
        result = {
            'header': self.translate(_('Name')),
            'options': [
                {
                    'label': self.translate(_('Sort by')),
                    'url': '?sort_by=student',
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


class FlourishRequestJournalExportView(RequestReportDownloadDialog):

    def nextURL(self):
        return absoluteURL(self.context, self.request) + '/export.xls'


class DateHeader(export.Header):

    @property
    def style(self):
        result = super(DateHeader, self).style.copy()
        result['format_str'] = 'YYYY-MM-DD'
        return result


# XXX: TODO PLZ
class FlourishJournalExportView(export.ExcelExportView,
                                FlourishLyceumSectionJournalGrades):

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

    def print_grades(self, ws):
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

    def export_month_worksheets(self, wb):
        for month_id in self.selected_months:
            self._active_month = month_id
            title = self.monthTitle(month_id)
            ws = wb.add_sheet(title)
            self.print_headers(ws)
            self.print_grades(ws)

    def __call__(self):
        app = ISchoolToolApplication(None)
        self.persons = app['persons']
        self.tzinfo = pytz.timezone(IApplicationPreferences(app).timezone)
        wb = xlwt.Workbook()
        self.export_month_worksheets(wb)
        datafile = StringIO()
        wb.save(datafile)
        data = datafile.getvalue()
        self.setUpHeaders(data)
        return data

    @property
    def active_month(self):
        return self._active_month

    @property
    def meetings(self):
        result = []
        for event in self.all_meetings:
            insecure_event = removeSecurityProxy(event)
            if insecure_event.dtstart.date().month == self.active_month:
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


class JournalModes(flourish.page.RefineLinksViewlet):
    pass


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

    def items(self):
        journal_url = absoluteURL(self.context, self.request)
        result = []
        result.append({
                'id': 'journal-mode-grades',
                'label': _('Grades'),
                'url': journal_url,
                'selected': self.manager.view.__name__ == 'index.html',
                })
        result.append({
                'id': 'journal-mode-attendance',
                'label': _('Attendance'),
                'url': journal_url + '/attendance.html',
                'selected': self.manager.view.__name__ == 'attendance.html',
                })
        return result

    def render(self, *args, **kw):
        return self.template(*args, **kw)
