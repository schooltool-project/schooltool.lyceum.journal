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
Lyceum student journal views.
"""
import urllib

from zope.browserpage.viewpagetemplatefile import ViewPageTemplateFile
from zope.component import queryMultiAdapter
from zope.i18n import translate
from zope.interface import implements
from zope.traversing.browser.absoluteurl import absoluteURL

from zc.table.interfaces import IColumn

from schooltool.term.interfaces import ITermContainer
from schooltool.table.interfaces import ITableFormatter
from schooltool.course.interfaces import ICourseContainer
from schooltool.course.interfaces import ILearner

from schooltool.lyceum.journal.browser.journal import LyceumSectionJournalView
from schooltool.lyceum.journal.interfaces import ISectionJournalData
from schooltool.lyceum.journal.interfaces import ITermGradingData
from schooltool.lyceum.journal import LyceumMessage as _


class CourseGradesColumn(object):
    implements(IColumn)

    def __init__(self, date, student, courses):
        self.date = date
        self.name = date.strftime("%d")
        self.student = student
        self.courses = courses

    def renderCell(self, course, formatter):
        grades = []
        for section in self.courses[course.__name__]:
            journal = ISectionJournalData(section)
            for meeting in journal.recordedMeetings(self.student):
                if meeting.dtstart.date() == self.date:
                    grade = journal.getGrade(self.student, meeting, default=None)
                    if (grade is not None) and (grade != ""):
                        grades.append(grade)

        return ", ".join(grades)

    def renderHeader(self, formatter):
        return '<span title="%s">%s</span>' % (
            self.date.strftime("%Y-%m-%d"), self.date.strftime("%d"))


class CourseTermAverageGradesColumn(object):

    def __init__(self, term, student, courses):
        self.term = term
        self.name = term.__name__ + "average"
        self.courses = courses
        self.student = student

    def courseGrades(self, course):
        grades = []
        for section in self.courses[course.__name__]:
            journal = ISectionJournalData(section)
            for meeting in journal.recordedMeetings(self.student):
                if meeting.dtstart.date() in self.term:
                    grade = journal.getGrade(self.student, meeting, default=None)
                    if (grade is not None) and (grade != ""):
                        grades.append(grade)
        int_grades = []
        for grade in grades:
            try:
                grade = int(grade)
            except ValueError:
                continue
            int_grades.append(grade)
        return int_grades

    def renderCell(self, course, formatter):
        tgd = ITermGradingData(self.student)
        if tgd.getGrade(course, self.term, None) is not None:
            return "<strong>%s</strong>" % tgd.getGrade(course, self.term)

        grades = self.courseGrades(course)
        if grades:
            return "%.3f" % (sum(grades) / float(len(grades)))

        return ""

    def renderHeader(self, formatter):
        return '<span>%s</span>' % translate(_("Average"),
                                             context=formatter.request)


class LyceumStudentJournalView(LyceumSectionJournalView):
    """A view for a student journal."""

    template = ViewPageTemplateFile("templates/student_journal.pt")

    def __init__(self, context, request):
        self.context, self.request = context, request
        self.courses = set()
        learner = ILearner(self.context)
        for section in learner.sections():
            for course in section.courses:
                self.courses.add(course)

    def __call__(self):
        term = self.getSelectedTerm()
        course_container = ICourseContainer(term)
        self.gradebook = queryMultiAdapter((course_container, self.request),
                                           ITableFormatter)
        self.gradebook.setUp(items=self.courses,
                             columns_after=self.gradeColumns(),
                             batch_size=0)
        return self.template()

    def allMeetings(self):
        for date in self.getSelectedTerm():
            yield date

    def meetings(self):
        for meeting in self.allMeetings():
            if meeting.month == self.active_month:
                yield meeting

    def gradeColumns(self):
        columns = []

        learner = ILearner(self.context)
        courses = {}
        for section in learner.sections():
            for course in section.courses:
                courses.setdefault(course.__name__, [])
                courses[course.__name__].append(section)

        for meeting in self.meetings():
            columns.append(CourseGradesColumn(meeting, self.context, courses))
        columns.append(CourseTermAverageGradesColumn(self.getSelectedTerm(),
                                                     self.context, courses))
        return columns

    @property
    def scheduled_terms(self):
        terms = ITermContainer(self.context)
        scheduled_terms = list(terms.values())
        return sorted(scheduled_terms, key=lambda t: t.last)

    def monthsInSelectedTerm(self):
        month = -1
        for meeting in self.allMeetings():
            if meeting.month != month:
                yield meeting.month
                month = meeting.month

    def monthURL(self, month_id):
        url = absoluteURL(self.context, self.request)
        url = "%s/gradebook.html?%s" % (
            url,
            urllib.urlencode([('month', month_id)] +
                             self.extra_parameters(self.request)))
        return url
