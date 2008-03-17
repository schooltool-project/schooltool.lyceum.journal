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
from pytz import timezone
from pytz import utc
from datetime import datetime

from zope.app.testing import setup
from zope.component import provideAdapter
from zope.interface import directlyProvides
from zope.interface import implements
from zope.publisher.browser import TestRequest
from zope.publisher.interfaces.browser import IBrowserRequest
from zope.testing import doctest
from zope.traversing.interfaces import IContainmentRoot


def doctest_SectionTermGradingColumn():
    """Tests for SectionTermGradingColumn.

        >>> from schooltool.lyceum.journal.browser.term import SectionTermGradingColumn
        >>> class TermStub(object):
        ...     __name__ = "2005-fall"
        >>> class SectionStub(object):
        ...     courses = ["History"]
        >>> class JournalStub(object):
        ...     section = SectionStub()
        >>> journal = JournalStub()
        >>> term = TermStub()
        >>> column = SectionTermGradingColumn(journal, term)

        >>> class FormatterStub(object):
        ...     request = TestRequest()
        >>> formatter = FormatterStub()

    Header just states what info is being displayed in this column:

        >>> column.renderHeader(formatter)
        u'<span>Term Grade</span>'

    To render an actual cell we will need a person that has a storage
    for his grading data:

        >>> from schooltool.lyceum.journal.interfaces import ITermGradingData
        >>> grading_data = {}
        >>> class TermGradingData(object):
        ...     def getGrade(self, course, term, default=None):
        ...         return grading_data.get((course, term.__name__), default)
        >>> class PersonStub(object):
        ...     __name__ = "john"
        ...     def __conform__(self, iface):
        ...         if iface == ITermGradingData:
        ...             return TermGradingData()
        >>> person = PersonStub()

    If there are no grades, an empty input box is dislpayed:

        >>> column.renderCell(person, formatter)
        '<input type="text" name="john" value="" style="width: 1.4em" />'

    Let's add a grade in that cell:

        >>> grading_data[("History", "2005-fall")] = "5"

    And see it displayed in the input cell:

        >>> column.renderCell(person, formatter)
        '<input type="text" name="john" value="5" style="width: 1.4em" />'

    """


def doctest_TermView():
    """Tests for the TermView.

        >>> from schooltool.lyceum.journal.browser.term import TermView
        >>> request = TestRequest()
        >>> view = TermView("JournalStub", request)
        >>> view.members = lambda: ["members"]
        >>> view.gradeColumns = lambda: ["Term Column"]
        >>> view.template = lambda: "<Term grading view>"

    If no buttons were clicked (we are just looking at the view), no
    actions are performed, just the gradebook table gets set up:

        >>> class AppStub(dict):
        ...     def __init__(self, context):
        ...         self['persons'] = "Person Container"
        >>> from schooltool.app.interfaces import ISchoolToolApplication
        >>> provideAdapter(AppStub, adapts=[None], provides=ISchoolToolApplication)
        >>> from schooltool.table.table import SchoolToolTableFormatter
        >>> provideAdapter(SchoolToolTableFormatter, adapts=[None, IBrowserRequest])
        >>> view()
        '<Term grading view>'

    Gradebook attrribute now is storing the table formatter:

        >>> view.gradebook
        <schooltool.table.table.SchoolToolTableFormatter object at ...>

    Section members and default columns are passed to the formatter:

        >>> view.gradebook._items
        ['members']
        >>> view.gradebook._columns
        [<schooltool.lyceum.journal.browser.journal.StudentNumberColumn object at ...>,
         <schooltool.lyceum.journal.browser.journal.GradeClassColumn object at ...>,
         <zc.table.column.GetterColumn object at ...>,
         'Term Column']

    If you click update, updateGradebook method get's called:

        >>> request.form['UPDATE_SUBMIT'] = 'Update'
        >>> def updateGradebook():
        ...     print "Wrote grades!"
        >>> view.updateGradebook = updateGradebook
        >>> result = view()
        Wrote grades!

    """


def doctest_TermView_updateGradebook():
    """Tests for TermView.updateGradebook

        >>> class SectionStub(object):
        ...     courses = ["History"]

        >>> class JournalStub(object):
        ...     section = SectionStub()

        >>> class GradingDataStub(object):
        ...     def __init__(self, student):
        ...         self.student = student
        ...     def setGrade(self, course, term, value):
        ...         print "Grading %s for term: %s and course %s by %s" % (
        ...             self.student, term, course, value)

        >>> from schooltool.lyceum.journal.interfaces import ITermGradingData
        >>> class PersonStub(object):
        ...     def __init__(self, name):
        ...         self.__name__ = name
        ...     def __conform__(self, iface):
        ...         if iface == ITermGradingData:
        ...             return GradingDataStub(self.__name__)

        >>> journal = JournalStub()
        >>> request = TestRequest()
        >>> from schooltool.lyceum.journal.browser.term import TermView
        >>> view = TermView(journal, request)
        >>> view.getSelectedTerm = lambda: "2007-Fall"
        >>> view.members = lambda: map(PersonStub, ["john", "pete"])

    If there are no grades in the request, nothing is done:

        >>> view.updateGradebook()

    Let's grade some students:

        >>> request.form['john'] = "5"
        >>> view.updateGradebook()
        Grading john for term: 2007-Fall and course History by 5

        >>> request.form['john'] = "6"
        >>> request.form['pete'] = "9"
        >>> view.updateGradebook()
        Grading john for term: 2007-Fall and course History by 6
        Grading pete for term: 2007-Fall and course History by 9

    If student is not a member of the course, he is not graded:

        >>> request.form['alex'] = "9"
        >>> view.updateGradebook()
        Grading john for term: 2007-Fall and course History by 6
        Grading pete for term: 2007-Fall and course History by 9

    """


def doctest_TermView_gradeColumns():
    """Tests for TermView.gradeColumns

        >>> from schooltool.lyceum.journal.browser.term import TermView
        >>> view = TermView("Journal", TestRequest())
        >>> class TermStub(object):
        ...     __name__ = "2007-fall"
        >>> view.getSelectedTerm = lambda: TermStub()
        >>> columns = view.gradeColumns()
        >>> columns
        [<schooltool.lyceum.journal.browser.journal.SectionTermGradesColumn object at ...>,
         <schooltool.lyceum.journal.browser.journal.SectionTermAverageGradesColumn object at ...>,
         <schooltool.lyceum.journal.browser.journal.SectionTermAttendanceColumn object at ...>,
         <schooltool.lyceum.journal.browser.term.SectionTermGradingColumn object at ...>]

        >>> columns[0].journal
        'Journal'
        >>> columns[0].term.__name__
        '2007-fall'

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
