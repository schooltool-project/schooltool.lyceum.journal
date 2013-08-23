#
# SchoolTool - common information systems platform for school administration
# Copyright (c) 2011 Shuttleworth Foundation
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
Selenium functional tests for schooltool.lyceum.journal
"""
import os
import unittest

from schooltool.common import parse_date
from schooltool.skin import flourish
from schooltool.testing.selenium import collect_ftests
from schooltool.testing.selenium import SeleniumLayer

dir = os.path.abspath(os.path.dirname(__file__))
filename = os.path.join(dir, 'stesting.zcml')

lyceum_journal_selenium_layer = SeleniumLayer(filename,
                                              __name__,
                                              'lyceum_journal_selenium_layer')


class DateManagementView(flourish.page.Page):

    def __call__(self):
        value = self.request.get('value')
        try:
            today = parse_date(value)
        except (ValueError,):
            return
        self.context.today = today


def test_suite():
    return collect_ftests(layer=lyceum_journal_selenium_layer)


if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')
