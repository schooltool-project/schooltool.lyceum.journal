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
from zope.app.pagetemplate.viewpagetemplatefile import ViewPageTemplateFile
from zope.component import getMultiAdapter
from zope.i18n import translate

from zc.table.column import Column

from schooltool.app.interfaces import ISchoolToolApplication
from schooltool.table.interfaces import ITableFormatter

from lyceum import LyceumMessage as _
from lyceum.journal.browser.journal import GradeClassColumn
from lyceum.journal.browser.journal import LyceumJournalView
from lyceum.journal.interfaces import ITermGradingData


class SectionTermGradingColumn(Column):

    def __init__(self, journal, term):
        self.term = term
        self.name = term.__name__ + "term_grade"
        self.journal = journal

    def renderCell(self, person, formatter):
        name = person.__name__
        courses = list(self.journal.section.courses)
        assert len(courses) == 1
        course = courses[0]
        tgd = ITermGradingData(person)
        value = tgd.getGrade(course, self.term, default="")
        return '<input type="text" name="%s" value="%s" style="width: 1.4em" />' % (name, value)

    def renderHeader(self, formatter):
        return '<span>%s</span>' % translate(_("Term Grade"), context=formatter.request)


class TermView(LyceumJournalView):

    template = ViewPageTemplateFile("templates/term.pt")

    def updateGradebook(self):
        courses = list(self.context.section.courses)
        assert len(courses) == 1
        course = courses[0]

        term = self.getSelectedTerm()

        for person in self.members():
            if person.__name__ in self.request:
                ITermGradingData(person).setGrade(course, term,
                                                  self.request[person.__name__])

    def __call__(self):
        if 'UPDATE_SUBMIT' in self.request:
            self.updateGradebook()

        app = ISchoolToolApplication(None)
        person_container = app['persons']
        self.gradebook = getMultiAdapter((person_container, self.request),
                                         ITableFormatter)
        self.gradebook.setUp(items=self.members(),
                             columns_before=[GradeClassColumn(title=_('Grade'),
                                                              name='grade')],
                             columns_after=self.gradeColumns(),
                             batch_size=0)
        return self.template()

    def gradeColumns(self):
        return [SectionTermGradingColumn(self.context,
                                         self.getSelectedTerm())]
