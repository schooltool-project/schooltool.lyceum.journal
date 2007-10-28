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

from zope.app.testing import setup
from zope.interface import implements
from zope.publisher.browser import TestRequest
from zope.testing import doctest


def doctest_SelectStudentCellFormatter():
    """Tests for SelectStudentCellFormatter.

        >>> from lyceum.journal.browser.table import SelectStudentCellFormatter
        >>> formatter = SelectStudentCellFormatter(None)
        >>> request = TestRequest()

    SelectStudentCellFormatter takes some parameters from the request,
    and adds them to the url that has the person displayed in the row
    selected:

        >>> request.form = {'event_id': "some-event-id",
        ...                 'month': "july"}
        >>> formatter.extra_parameters(request)
        [('event_id', 'some-event-id'),
         ('month', 'july')]

    Parameters that are not relevant to the state of the view get
    ignored:

        >>> request.form = {'event_id': "some-event-id",
        ...                 'month': "july",
        ...                 'some-thing-else': 'is-ignored'}
        >>> formatter.extra_parameters(request)
        [('event_id', 'some-event-id'),
         ('month', 'july')]

    The formatter renders the url of the journal, and adds student
    parameter set to the __name__ of the student that is being
    rendered:

        >>> class TableFormatterStub(object):
        ...     pass
        >>> table_formatter = TableFormatterStub()
        >>> table_formatter.request = request
        >>> class PersonStub(object):
        ...     __name__ = "john"
        >>> item = PersonStub()
        >>> formatter("John", item, table_formatter)
        '<a href="http://127.0.0.1/index.html?student=john&event_id=some-event-id&month=july">John</a>'

    """


def doctest_SelectableRowTableFormatter():
    r"""Tests for SelectableRowTableFormatter.

    SelectableRowTableFormatter is a special table formatter that
    allows you to select items, and have rows for these items
    displayed in some special way when rendering the table.

        >>> from lyceum.journal.browser.table import SelectableRowTableFormatter
        >>> request = TestRequest()
        >>> class ColumnStub(object):
        ...     def renderCell(self, item, formatter):
        ...         return "I am %s" % item

    It still works with simple columns that have no way to get
    selected:

        >>> columns = [ColumnStub()]
        >>> formatter = SelectableRowTableFormatter("context", request, [],
        ...                                         selected_items=["Pete"],
        ...                                         columns=columns)
        >>> formatter.row = 0
        >>> print formatter.renderRow("John")
        <tr class="odd">
          <td>
            I am John
          </td>
        </tr>

    As this table formatter inherits from AlternatingRowFormatter the
    next row is "even":

        >>> print formatter.renderRow("Pete")
        <tr class="even">
          <td>
            I am Pete
          </td>
        </tr>

    If column implements ISelectableColumn, and the row being rendered
    is for a selected item - cells will be rendered in a special way:

        >>> from lyceum.journal.browser.interfaces import ISelectableColumn
        >>> class SelectableColumnStub(ColumnStub):
        ...     implements(ISelectableColumn)
        ...     def renderSelectedCell(self, item, formatter):
        ...         return "I am Selected %s" % item

    John is not selected:

        >>> columns[0] = SelectableColumnStub()
        >>> print formatter.renderRow("John")
        <tr class="odd">
          <td>
            I am John
          </td>
        </tr>

    But Pete is:

        >>> print formatter.renderRow("Pete")
        <tr class="even">
          <td>
            I am Selected Pete
          </td>
        </tr>

    Another type of columns is IIndependentColumn, "independent"
    columns render their own TD tags, so they can style themselves any
    way they want:

        >>> from lyceum.journal.browser.interfaces import IIndependentColumn
        >>> class IndependentColumnStub(ColumnStub):
        ...     implements(IIndependentColumn)
        ...     def renderCell(self, item, formatter):
        ...         return '<td class="special">\nI am %s\n</td>' % item

        >>> columns[0] = IndependentColumnStub()
        >>> print formatter.renderRow("John")
        <tr class="odd">
          <td class="special">
            I am John
          </td>
        </tr>

    The column did not implement ISelectableColumn, so Pete is
    rendered the same way as John was:

        >>> print formatter.renderRow("Pete")
        <tr class="even">
          <td class="special">
            I am Pete
          </td>
        </tr>

    Columns can implement both interfaces ISelectableColumn and
    IIndependentColumn at the same time, so they will render their own
    TD tags, and get displayed differently when the row is selected:

        >>> class SelectableIndependentColumn(IndependentColumnStub):
        ...     implements(ISelectableColumn)
        ...     def renderSelectedCell(self, item, formatter):
        ...         return '<td class="selected">\nI am %s\n</td>' % item
        >>> columns[0] = SelectableIndependentColumn()
        >>> print formatter.renderRow("John")
        <tr class="odd">
          <td class="special">
            I am John
          </td>
        </tr>

    The TD for Pete gets it's class set to "selected":

        >>> print formatter.renderRow("Pete")
        <tr class="even">
          <td class="selected">
            I am Pete
          </td>
        </tr>

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
