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

$Id$
"""
import unittest

from zope.component import provideAdapter
from zope.app.testing import setup
from zope.testing import doctest


def doctest_SectionJournalData():
    """Tests for SectionJournalData

        >>> from lyceum.journal.journal import SectionJournalData
        >>> journal = SectionJournalData()

    Journals don't really work on their own, as they find out which
    section they belong to by their __name__:

        >>> journal.__name__ = 'some_section'

        >>> class SectionStub(object):
        ...     pass
        >>> section = SectionStub()

        >>> class STAppStub(dict):
        ...     def __init__(self, context):
        ...         self['sections'] = {'some_section': section}

        >>> from schooltool.app.interfaces import ISchoolToolApplication
        >>> provideAdapter(STAppStub, adapts=[None], provides=ISchoolToolApplication)

        >>> journal.section is section
        True

    Grades can be added for every person/meeting pair:

        >>> class PersonStub(object):
        ...     def __init__(self, name):
        ...         self.__name__ = name

        >>> class MeetingStub(object):
        ...     def __init__(self, uid):
        ...         self.unique_id = uid

        >>> person1 = PersonStub('john')
        >>> person2 = PersonStub('pete')

        >>> meeting = MeetingStub('some-unique-id')

        >>> journal.setGrade(person1, meeting, "5")

    And are read that way too:

        >>> journal.getGrade(person1, meeting)
        '5'

    If there is no grade present in that position, you get None:

        >>> journal.getGrade(person2, meeting) is None
        True

    Unless default is provided:

        >>> journal.getGrade(person2, meeting, default="")
        ''

    """


def doctest_getSectionJournalData():
    """Tests for getSectionJournalData

        >>> from lyceum.journal.journal import getSectionJournalData

        >>> from zope.app.container.btree import BTreeContainer
        >>> journal_container = BTreeContainer()
        >>> class STAppStub(dict):
        ...     def __init__(self, context):
        ...         self['lyceum.journal'] = journal_container

        >>> from schooltool.app.interfaces import ISchoolToolApplication
        >>> provideAdapter(STAppStub, adapts=[None], provides=ISchoolToolApplication)

        >>> class SectionStub(object):
        ...     def __init__(self, name):
        ...         self.__name__ = name

        >>> section = SectionStub('some_section')

    Initially the journal container is empty, but if we try to get a
    journal for a section, a SectionJournalData objecgt is created:

        >>> journal = getSectionJournalData(section)
        >>> journal
        <lyceum.journal.journal.SectionJournalData object at ...>

        >>> journal.__name__
        u'some_section'

        >>> journal_container[section.__name__] is journal
        True

    If we try to get the journal for the second time, we get the same
    journal instance:

        >>> getSectionJournalData(section) is journal
        True

    """


def doctest_SectionJournal():
    """Tests for SectionJournal adapter:

        >>> from lyceum.journal.journal import SectionJournal
        >>> section = object()
        >>> sj = SectionJournal(section)
        >>> sj.section is section
        True

    The section you pass as an argument is set as a section attribute
    for the journal.

        >>> class SectionDataStub(object):
        ...     data = {}
        ...     def setGrade(self, person, meeting, value):
        ...         self.data[person, meeting] = value
        ...     def getGrade(self, person, meeting, default):
        ...         return self.data.get((person, meeting), default)
        >>> section_data = SectionDataStub()

        >>> class SectionStub(object):
        ...     def __conform__(self, iface):
        ...         return section_data

        >>> class MeetingStub(object):
        ...     owner = SectionStub()
        >>> meeting = MeetingStub()

    The grades are stored in the section journal data of the section
    that "owns" the meeting:

        >>> sj.setGrade("john", meeting, 9)

        >>> sj.getGrade("john", meeting, default=0)
        9

    If there is no value set, the default is returned:

        >>> sj.getGrade("pete", meeting, default=0)
        0

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
