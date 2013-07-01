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
Lyceum journal interfaces.
"""
import zope.schema
from zope.interface import Interface
from zope.interface import Attribute
from zope.location.interfaces import ILocation

from schooltool.requirement.interfaces import IScoreSystem

from schooltool.lyceum.journal import LyceumMessage as _


class IEvaluateRequirement(Interface):

    def evaluate(person, requirement, grade, evaluator=None, score_system=None):
        """Add evaluation of a requirement."""

    def getEvaluation(person, requirement, default=None):
        """Get evaluation of a requirement."""


class ISectionJournalData(IEvaluateRequirement):
    """A journal for a section."""

    section = Attribute("""Section this data belongs to.""")

    def setGrade(person, meeting, grade):
        """Set a grade for a person participating in this meeting."""

    def getGrade(person, meeting, default=None):
        """Retrieve a grade for a person and a meeting."""

    def setAbsence(person, meeting, explained=True, value=None):
        """Mark an absence as an explained or unexplained one."""

    def getAbsence(person, meeting, default=False):
        """Retrieve the status of an absence."""

    def gradedMeetings(person):
        """Returns a list of (meeting, grades) for a person."""

    def absentMeetings(person):
        """Returns a list of (meeting, absence) for a person."""


class ISectionJournal(ILocation):

    section = Attribute("Section this journal belongs to.")
    members = Attribute("List of students that belong to this section or any of the adjacent.")

    def setGrade(person, meeting, grade):
        """Set a grade for a person participating in this meeting."""

    def getGrade(person, meeting, default=None):
        """Retrieve a grade for a person and a meeting."""

    def setAbsence(person, meeting, explained=True):
        """Mark an absence as an explained or unexplained one."""

    def getAbsence(person, meeting, default=False):
        """Retrieve the status of an absence."""

    def meetings():
        """List all possible meetings for this section."""

    def gradedMeetings(person):
        """Returns a list of (meeting, grades) for a person."""

    def absentMeetings(person):
        """Returns a list of (meeting, absence) for a person."""

    def hasMeeting(person, meeting):
        """Returns true if person should participate in a given meeting."""

    def findMeeting(meeting_id):
        """Returns the meeting object for this meeting id.

        The meeting might belong to any of the adjacent sections so it
        goes through all their calendars to find the meeting.
        """


class IAttendanceScoreSystem(IScoreSystem):

    scores = zope.schema.List(
        title=u'All values',
        description=u'(score, label)',
        value_type=zope.schema.Tuple(),
        required=True)

    tag_absent = zope.schema.List(
        title=u'Absence scores',
        value_type=zope.schema.TextLine(),
        required=True)

    tag_tardy = zope.schema.List(
        title=u'Tardy scores',
        value_type=zope.schema.TextLine(),
        required=True)

    tag_excused = zope.schema.List(
        title=u'Excused scores',
        value_type=zope.schema.TextLine(),
        required=True)

    def isAbsent(score):
        pass

    def isTardy(score):
        pass

    def isExcused(score):
        pass


class IPersistentAttendanceScoreSystem(IAttendanceScoreSystem):

    hidden = zope.schema.Bool(
        title=u"Hidden Score System",
        required=False
        )


class IJournalScoresystemPreferences(Interface):

    grading_scoresystem = zope.schema.Choice(
        title=_("Grading scoresystem"),
        vocabulary="schooltool.lyceum.journal-grading-scoresystems",
        required=True)

    attendance_scoresystem = zope.schema.Choice(
        title=_("Atttendance scoresystem"),
        vocabulary="schooltool.lyceum.journal-attendance-scoresystems",
        required=True)


class IAvailableScoresystems(Interface):
    """A marker interface to get a list of available scoresystems."""
