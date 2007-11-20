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
Upgrade SchoolTool to generation 6.

Fix capitalization in names of persons with more than one name.
"""
from zope.app.generations.utility import findObjectsProviding
from zope.app.publication.zopepublication import ZopePublication

from schooltool.person.interfaces import IPerson
from schooltool.app.interfaces import ISchoolToolCalendar
from schooltool.app.interfaces import ISchoolToolApplication


def evolve(context):
    root = context.connection.root()[ZopePublication.root_name]
    for app in findObjectsProviding(root, ISchoolToolApplication):
        sections = app['sections']
        for section in sections.values():
            calendar = ISchoolToolCalendar(section)
            for member in section.members:
                if IPerson.providedBy(member):
                    if calendar not in member.overlaid_calendars:
                        member.overlaid_calendars.add(calendar)
