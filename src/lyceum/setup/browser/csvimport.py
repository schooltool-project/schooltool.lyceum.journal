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
"""
import csv

from zope.publisher.browser import BrowserView
from zope.app.pagetemplate.viewpagetemplatefile import ViewPageTemplateFile

from lyceum.setup.csvimport import LyceumGroupsAndStudents
from lyceum.setup.csvimport import (LyceumTeachers, LyceumSchoolTimetables,
                                    LyceumCourses, LyceumResources,
                                    LyceumScheduling, LyceumUpdateScheduling,
                                    LyceumTerms2006, LyceumTerms2007)


class LyceumCSVImportView(BrowserView):

    template = ViewPageTemplateFile('templates/csv_import.pt')

    def __call__(self):
        if 'IMPORT_STUDENTS' in self.request:
            students = list(csv.reader(self.request['students_csv'].readlines()))
            generator = LyceumGroupsAndStudents(students)
            generator.generate(self.context)

        if 'IMPORT_TIMETABLES' in self.request:
            term_id = self.request.get('TERM')
            timetables = []
            for weekday in range(5):
                timetables.append(list(csv.reader(self.request['weekday%s_csv' % weekday].readlines())))

            factories = [LyceumSchoolTimetables,
                         LyceumTeachers,
                         LyceumCourses,
                         LyceumResources,
                         LyceumScheduling]

            generators = [factory(term_id, timetables)
                          for factory in factories]

            for generator in generators:
                generator.generate(self.context)

        if 'UPDATE_TIMETABLES' in self.request:
            term_id = self.request.get('TERM')
            timetables = []
            for weekday in range(5):
                timetables.append(list(csv.reader(self.request['weekday%s_csv' % weekday].readlines())))
            generator = LyceumUpdateScheduling(term_id, timetables)
            generator.generate(self.context)

        if 'GENERATE_TERMS_2006' in self.request:
            generator = LyceumTerms2006()
            generator.generate(self.context)

        if 'GENERATE_TERMS_2007' in self.request:
            generator = LyceumTerms2007()
            generator.generate(self.context)

        return self.template()

    @property
    def terms(self):
        return sorted(self.context['terms'].values(),
                      key=lambda term: term.title)
