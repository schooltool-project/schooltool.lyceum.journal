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
Evolve database to generation 1.

Remove LyceumTermDataContainer from app root.
"""

from zope.app.generations.utility import findObjectsProviding
from zope.app.publication.zopepublication import ZopePublication
from zope.component.hooks import getSite, setSite

from schooltool.app.interfaces import ISchoolToolApplication


TERM_GRADES_KEY = 'schooltool.lyceum.journal.term_grades'


def evolve(context):
    root = context.connection.root().get(ZopePublication.root_name, None)

    old_site = getSite()
    apps = findObjectsProviding(root, ISchoolToolApplication)
    for app in apps:
        setSite(app)
        if TERM_GRADES_KEY in app:
            del app[TERM_GRADES_KEY]

    setSite(old_site)

