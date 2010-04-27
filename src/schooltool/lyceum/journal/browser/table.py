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
Common code for journal view table display.
"""
import urllib

from zope.app.form.browser.widget import quoteattr
from zope.interface import implementer
from zope.component import adapter
from zope.traversing.browser.absoluteurl import absoluteURL
from zc.table import table

from schooltool.table.interfaces import IIndexedColumn
from schooltool.table.catalog import makeIndexedColumn
from schooltool.table.catalog import RenderUnindexingMixin, unindex
from schooltool.lyceum.journal.browser.interfaces import IIndependentColumn
from schooltool.lyceum.journal.browser.interfaces import ISelectableColumn


class SelectStudentCellFormatter(object):

    extra_info = ['event_id', 'month', 'date', 'TERM']

    def __init__(self, context):
        self.context = context

    def extra_parameters(self, request):
        parameters = []
        for info in self.extra_info:
            if info in request:
                parameters.append((info, request[info].encode('utf-8')))
        return parameters

    def __call__(self, value, item, formatter):
        request = formatter.request
        url = absoluteURL(self.context, request)
        url = "%s/index.html?%s" % (
            url,
            urllib.urlencode([('student', item.__name__.encode('utf-8'))] +
                             self.extra_parameters(request)))
        return '<a class="select-row" href="%s">%s</a>' % (url, value)


class SelectableRowTableFormatter(table.FormFullFormatter):

    def __init__(self, *args, **kwargs):
        self.selected_items = kwargs.pop("selected_items", [])
        super(SelectableRowTableFormatter, self).__init__(*args, **kwargs)

    def renderCell(self, item, column):
        sc = IIndependentColumn(column, None)
        if sc:
            return self.getCell(item, column)
        return super(SelectableRowTableFormatter, self).renderCell(item, column)

    def renderSelectedCells(self, item):
        return ''.join([self.renderSelectedCell(item, col)
                        for col in self.visible_columns])

    def renderSelectedCell(self, item, column):
        sc = ISelectableColumn(column, None)
        if sc:
            ic = IIndependentColumn(sc, None)
            if ic:
                return sc.renderSelectedCell(item, self)
            else:
                return '    <td%s>\n%s  </td>\n' % (
                    self._getCSSClass('td'), sc.renderSelectedCell(item, self))
        return self.renderCell(item, column)

    def _renderRow(self, item):
        return super(SelectableRowTableFormatter, self).renderRow(item)

    def renderSelectedRow(self, item):
        self.row += 1
        klass = self.cssClasses.get('tr', '')
        if klass:
            klass += ' '
        return '  <tr class=%s>\n%s  </tr>\n' % (
            quoteattr(klass + self.row_classes[self.row % 2]),
            self.renderSelectedCells(item))

    def renderRow(self, item):
        if item in self.selected_items:
            return self.renderSelectedRow(item)
        return self._renderRow(item)


def viewURL(context, request, name, parameters=[]):
    url = absoluteURL(context, request)
    return "%s/%s?%s" % (url, name, urllib.urlencode(parameters))


class SelectableColumnUnindexingMixin(object):
    def renderSelectedCell(self, indexed_item, formatter):
        return super(SelectableColumnUnindexingMixin, self).renderSelectedCell(
            unindex(indexed_item), formatter)


@adapter(ISelectableColumn)
@implementer(IIndexedColumn)
def getIndexedSelectableColumn(column):
    column = makeIndexedColumn(
        [RenderUnindexingMixin, SelectableColumnUnindexingMixin], column)
    return column
