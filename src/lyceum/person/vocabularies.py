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
Sources and vocabularies for form fields.

$Id$

"""
from zope.interface import implements

from schooltool.app.interfaces import ISchoolToolApplication
from schooltool.person.interfaces import IPerson
from schooltool.group.interfaces import IGroup

from lyceum.person.interfaces import IGroupSource
from lyceum.person.interfaces import ILyceumPersonSource


class GradeClassSource(object):
    implements(IGroupSource)

    def __init__(self, context):
        self.context = context

    def __len__(self):
        len(self.context.groups)

    def __contains__(self, value):
        return True

    def __iter__(self):
        if IPerson.providedBy(self.context):
            groups = [group.__name__
                      for group in self.context.groups
                      if IGroup.providedBy(group)]
        else:
            groups = list(ISchoolToolApplication(None)['groups'])

        for group in sorted(groups):
            yield group

def gradeClassVocabularyFactory():
    return GradeClassSource


class AdvisorSource(object):
    implements(ILyceumPersonSource)

    def __init__(self, context):
        self.context = context

    def __contains__(self, value):
        return True

    def __len__(self):
        len(self.context.groups)

    def __iter__(self):
        app = ISchoolToolApplication(None)
        persons = app['groups']['teachers'].members
        for person in sorted(persons, key=lambda p: p.__name__):
            yield person

def advisorVocabularyFactory():
    return AdvisorSource
