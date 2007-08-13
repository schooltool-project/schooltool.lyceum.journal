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
Lyceum advisor relationship.

$Id$

"""
from zope.component import adapts
from zope.interface import implements

from schooltool.relationship.uri import URIObject
from schooltool.relationship.relationship import RelationshipSchema
from schooltool.relationship.interfaces import IRelationshipLinks

from lyceum.person.interfaces import ILyceumPerson
from lyceum.person.interfaces import IAdvisor
from lyceum.person.interfaces import IStudent


URIAdvising = URIObject('http://schooltool.org/ns/lyceum/advising',
                        'Advising', 'The advising relationship.')
URIStudent = URIObject('http://schooltool.org/ns/lyceum/advising/student',
                       'Student', 'An advising relationship student role.')
URIAdvisor = URIObject('http://schooltool.org/ns/lyceum/advising/advisor',
                       'Advisor', 'An advising relationship advisor role.')

Advising = RelationshipSchema(URIAdvising,
                              advisor=URIAdvisor,
                              student=URIStudent)


class PersonAdvisorAdapter(object):
    adapts(ILyceumPerson)
    implements(IAdvisor)

    def __init__(self, context):
        self.context = context

    @property
    def students(self):
        relationships = IRelationshipLinks(self.context)
        return relationships.getTargetsByRole(URIStudent, URIAdvising)

    def addStudent(self, student):
        Advising(student=student, advisor=self.context)

    def removeStudent(self, student):
        Advising.unlink(student=student, advisor=self.context)


class PersonStudentAdapter(object):
    adapts(ILyceumPerson)
    implements(IStudent)

    def __init__(self, context):
        self.context = context

    @property
    def advisor(self):
        relationships = IRelationshipLinks(self.context)
        advisors = relationships.getTargetsByRole(URIAdvisor, URIAdvising)
        assert len(advisors) < 2
        advisors.append(None)
        return advisors[0]
