#
# SchoolTool - common information systems platform for school administration
# Copyright (c) 2005 Shuttleworth Foundation
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
Lyceum person csv import views.

$Id$
"""
from zope.publisher.browser import BrowserView
from zope.app.pagetemplate.viewpagetemplatefile import ViewPageTemplateFile

from lyceum.csvimport import LyceumGroupsAndStudents
from lyceum.csvimport import (LyceumTeachers, LyceumSchoolTimetables,
                              LyceumCourses, LyceumResources, LyceumScheduling,
                              LyceumTerms)


class LyceumCSVImportView(BrowserView):

    template = ViewPageTemplateFile('templates/csv_import.pt')

    def __call__(self):
        if 'IMPORT' in self.request:
            generators = [LyceumSchoolTimetables(),
                          LyceumTerms(),
                          LyceumGroupsAndStudents(),
                          LyceumTeachers(),
                          LyceumCourses(),
                          LyceumResources(),
                          LyceumScheduling(),
                          ]
            for generator in generators:
                generator.generate(self.context)
        return self.template()
