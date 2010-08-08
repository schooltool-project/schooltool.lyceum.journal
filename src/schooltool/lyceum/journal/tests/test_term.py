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
import unittest, doctest

from zope.component import provideAdapter
from zope.app.testing import setup


def doctest_TermGradingData():
    """Tests for TermGradingData.

        >>> from schooltool.lyceum.journal.term import TermGradingData
        >>> grading_data = TermGradingData()

    Term Grading Data does not really work on it's own, as it find out which
    person it belongs to by its __name__:

        >>> grading_data.__name__ = 'some_person'


        >>> class PersonStub(object):
        ...     def __init__(self, name):
        ...         self.__name__ = name
        >>> person = PersonStub('some_person')

        >>> class STAppStub(dict):
        ...     def __init__(self, context):
        ...         self['persons'] = {'some_person': person}

        >>> from schooltool.app.interfaces import ISchoolToolApplication
        >>> provideAdapter(STAppStub, adapts=[None], provides=ISchoolToolApplication)

        >>> grading_data.person is person
        True

    Grades can be added for every course/term pair:


        >>> class TermStub(object):
        ...     def __init__(self, name):
        ...         self.__name__ = name

        >>> class CourseStub(object):
        ...     def __init__(self, name):
        ...         self.__name__ = name

        >>> course1 = CourseStub('john')
        >>> course2 = CourseStub('pete')

        >>> term = TermStub('2007-fall')

        >>> grading_data.setGrade(course1, term, "5")

    And are read that way too:

        >>> grading_data.getGrade(course1, term)
        '5'

    If there is no grade present in that position, you get None:

        >>> grading_data.getGrade(course2, term) is None
        True

    Unless default is provided:

        >>> grading_data.getGrade(course2, term, default="")
        ''

    """


def doctest_getPersonTermGradingData():
    """Tests for getPersonTermGradingData.

        >>> from schooltool.lyceum.journal.term import getPersonTermGradingData

        >>> from zope.container.btree import BTreeContainer
        >>> term_grade_container = BTreeContainer()
        >>> class STAppStub(dict):
        ...     def __init__(self, context):
        ...         self['schooltool.lyceum.journal.term_grades'] = term_grade_container

        >>> from schooltool.app.interfaces import ISchoolToolApplication
        >>> provideAdapter(STAppStub, adapts=[None], provides=ISchoolToolApplication)

        >>> class PersonStub(object):
        ...     def __init__(self, name):
        ...         self.__name__ = name

        >>> person = PersonStub('john')

    Initially the term grade data container is empty, but if we try to
    get a journal for a section, a PersonTermGradingData objecgt is
    created:

        >>> grading_data = getPersonTermGradingData(person)
        >>> grading_data
        <schooltool.lyceum.journal.term.TermGradingData object at ...>

        >>> grading_data.__name__
        u'john'

        >>> term_grade_container[person.__name__] is grading_data
        True

    If we try to get the grading data for the second time, we get the
    same TermGradingData instance:

        >>> getPersonTermGradingData(person) is grading_data
        True

    """


def setUp(test):
    setup.placelessSetUp()


def tearDown(test):
    setup.placelessTearDown()


def test_suite():
    optionflags = doctest.NORMALIZE_WHITESPACE | doctest.ELLIPSIS
    return doctest.DocTestSuite(optionflags=optionflags,
                                setUp=setUp, tearDown=tearDown)


if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')
