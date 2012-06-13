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
Lyceum journal content classes.
"""
from BTrees.OOBTree import OOBTree
from decimal import Decimal
from persistent import Persistent

from zope.annotation.interfaces import IAnnotations
from zope.security.proxy import removeSecurityProxy
from zope.intid.interfaces import IIntIds
from zope.container.btree import BTreeContainer
from zope.cachedescriptors.property import Lazy
from zope.component import getUtility
from zope.component import adapter
from zope.component import adapts
from zope.interface import implementer
from zope.interface import implements
from zope.keyreference.interfaces import IKeyReference
from zope.location.interfaces import ILocation

from schooltool.app.app import InitBase, StartUpBase
from schooltool.app.interfaces import ISchoolToolApplication
from schooltool.app.interfaces import ISchoolToolCalendar
from schooltool.course.interfaces import ILearner
from schooltool.course.interfaces import ISection
from schooltool.person.interfaces import IPerson
from schooltool.requirement.interfaces import IEvaluations
from schooltool.requirement.evaluation import Evaluation
from schooltool.requirement.scoresystem import AbstractScoreSystem
from schooltool.requirement.scoresystem import GlobalRangedValuesScoreSystem
from schooltool.requirement.scoresystem import ScoreValidationError, UNSCORED
from schooltool.securitypolicy.crowds import ConfigurableCrowd
from schooltool.securitypolicy.crowds import AdministrationCrowd

from schooltool.lyceum.journal.interfaces import ISectionJournal
from schooltool.lyceum.journal.interfaces import ISectionJournalData
from schooltool.lyceum.journal import LyceumMessage as _

ABSENT = 'n' #n means absent in lithuanian
TARDY = 'p' #p means tardy in lithuanian

CURRENT_SECTION_TAUGHT_KEY = 'schooltool.gradebook.currentsectiontaught'


class JournalAbsenceScoreSystem(AbstractScoreSystem):

    values = ()

    def __init__(self, title, description=None,
                 values={'a': u'Absent', 't': u'Tardy'}):
        super(JournalAbsenceScoreSystem, self).__init__(title, description=description)
        self.values = tuple(values.items())

    def isValidScore(self, score):
        """See interfaces.IScoreSystem"""
        if score is UNSCORED:
            return True
        if not isinstance(score, (str, unicode)):
            return False
        if score.lower() in dict(self.values):
            return True
        return False

    def fromUnicode(self, rawScore):
        """See interfaces.IScoreSystem"""
        if not rawScore:
            return UNSCORED
        if not self.isValidScore(rawScore):
            raise ScoreValidationError(rawScore)
        return rawScore.strip().lower()


class GlobalAbsenceScoreSystem(JournalAbsenceScoreSystem):

    def __init__(self, name, *args, **kw):
        super(GlobalAbsenceScoreSystem, self).__init__(*args, **kw)
        self.__name__ = name

    def __reduce__(self):
        return self.__name__


class GlobalJournalRangedValuesScoreSystem(GlobalRangedValuesScoreSystem):
    pass


# The score system used in the old journal
TenPointScoreSystem = GlobalJournalRangedValuesScoreSystem(
    'TenPointScoreSystem',
    u'10 Points', u'10 Points Score System',
    min=Decimal(1), max=Decimal(10))


# Attendance score system
AbsenceScoreSystem = GlobalAbsenceScoreSystem(
    'AbsenceScoreSystem',
    u'Absences', u'Attendance Score System',
    values={ABSENT: _('Absent'), TARDY: _('Tardy')})


def getCurrentSectionTaught(person):
    ann = IAnnotations(removeSecurityProxy(person))
    if CURRENT_SECTION_TAUGHT_KEY not in ann:
        ann[CURRENT_SECTION_TAUGHT_KEY] = None
    else:
        section = ann[CURRENT_SECTION_TAUGHT_KEY]
        try:
            getSectionJournalData(section)
        except:
            ann[CURRENT_SECTION_TAUGHT_KEY] = None
    return ann[CURRENT_SECTION_TAUGHT_KEY]


def setCurrentSectionTaught(person, section):
    ann = IAnnotations(removeSecurityProxy(person))
    ann[CURRENT_SECTION_TAUGHT_KEY] = removeSecurityProxy(section)


def student_sections(students):
    sections = set()
    for student in students:
        for section in student.groups:
            if ISection.providedBy(section):
                sections.add(section)
    return sections


def adjacent_sections(section):
    courses = section.courses
    instructors = section.instructors
    sections = set()
    sections.add(section)
    members = [member for member in section.members
               if IPerson.providedBy(member)]
    for section in student_sections(members):
        section = removeSecurityProxy(section)
        for course in section.courses:
            if course in courses:
                for instructor in section.instructors:
                    if instructor in instructors:
                        sections.add(section)
                        break
    return sections


class LyceumJournalContainer(BTreeContainer):
    """A container for all the journals in the system."""


@adapter(ISectionJournalData)
@implementer(ISection)
def getSectionForSectionJournalData(jd):
    int_ids = getUtility(IIntIds)
    return int_ids.getObject(int(jd.__name__))


@adapter(ISectionJournal)
@implementer(ISection)
def getSectionForSectionJournal(sj):
    return sj.section


class MeetingRequirement(tuple):
    implements(IKeyReference)

    key_type_id  = 'schooltool.lyceum.journal.journal.MeetingRequirement'
    requirement_type = None
    score_system = None

    def __new__(cls, meeting):
        date = meeting.dtstart.date()
        meeting_id = meeting.meeting_id
        if meeting_id is None:
            meeting_id = meeting.unique_id
        try:
            calendar = meeting.__parent__
            target = calendar.__parent__
            target_ref = IKeyReference(target)
        except TypeError:
            target_ref = None
        return tuple.__new__(
            cls, (cls.requirement_type, date, meeting_id, target_ref))

    def __cmp__(self, other):
        if self.key_type_id == other.key_type_id:
            return cmp(tuple(self), tuple(other))
        return cmp(self.key_type_id, other.key_type_id)

    @property
    def date(self):
        return self[1]

    @property
    def meeting_id(self):
        return self[2]

    @property
    def target(self):
        """Return the grading target (for example, section)"""
        if self[3] is None:
            return None
        return self[3]()

    def __call__(self):
        return self


class GradeRequirement(MeetingRequirement):
    requirement_type = 'grade'
    score_system = TenPointScoreSystem


class AttendanceRequirement(MeetingRequirement):
    requirement_type = 'attendance'
    score_system = AbsenceScoreSystem


class SectionJournalData(Persistent):
    """A journal for a section."""
    implements(ISectionJournalData, ILocation)

    def __init__(self):
        self.__parent__ = None
        self.__name__ = None
        self.__grade_data__ = OOBTree()
        self.__description_data__ = OOBTree()
        self.__attendance_data__ = OOBTree()

    @property
    def section(self):
        return ISection(self)

    def getKeys(self, person, meeting):
        key = (person.__name__, meeting.dtstart.date())
        entry_id = meeting.meeting_id
        if entry_id is None:
            entry_id = meeting.unique_id
        return (key, entry_id)

    def evaluate(self, person, requirement, grade, evaluator=None, score_system=None):
        if score_system is None:
            score_system = requirement.score_system
        score = score_system.fromUnicode(grade)
        evaluations = removeSecurityProxy(IEvaluations(person))

        if requirement in evaluations:
            current = evaluations[requirement]
            if (current.value == score and
                current.evaluator == evaluator):
                return
        else:
            if score is UNSCORED:
                return

        eval = Evaluation(requirement, score_system, score, evaluator=evaluator)
        evaluations.addEvaluation(eval)

    def getEvaluation(self, person, requirement, default=None):
        evaluations = removeSecurityProxy(IEvaluations(person))
        score = evaluations.get(requirement)
        if score is None:
            return default
        return score

    def setGrade(self, person, meeting, grade, evaluator=None):
        requirement = GradeRequirement(removeSecurityProxy(meeting))
        self.evaluate(person, requirement, grade, evaluator=evaluator)

    def getGrade(self, person, meeting, default=None):
        requirement = GradeRequirement(removeSecurityProxy(meeting))
        score = self.getEvaluation(person, requirement, default=default)
        if score is not default:
            return score.value
        return default

    def setAbsence(self, person, meeting, explained=True, evaluator=None, value=ABSENT):
        requirement = AttendanceRequirement(removeSecurityProxy(meeting))
        # XXX: how to mark explained absences?  With score comments OFC
        #      so we need score comments now.
        self.evaluate(person, requirement, value, evaluator=evaluator)

    def getAbsence(self, person, meeting, default=''):
        requirement = AttendanceRequirement(removeSecurityProxy(meeting))
        score = self.getEvaluation(person, requirement, default=default)
        if score is default:
            return default
        return score.value

    def descriptionKey(self, meeting):
        date = meeting.dtstart.date()
        entry_id = meeting.meeting_id
        if entry_id is None:
            entry_id = meeting.unique_id
        return (date, entry_id)

    def recordedMeetings(self, person):
        result = []
        unique_meetings = set()
        calendar = ISchoolToolCalendar(self.section)
        sorted_events = sorted(calendar, key=lambda e: e.dtstart)
        evaluations = removeSecurityProxy(IEvaluations(person))
        for event in sorted_events:
            requirement = GradeRequirement(removeSecurityProxy(event))
            if (requirement in evaluations and
                event.meeting_id not in unique_meetings):
                result.append(event)
                unique_meetings.add(event.meeting_id)
        return result

    def gradedMeetings(self, person, requirement_factory=GradeRequirement):
        result = []
        unique_meetings = set()
        calendar = ISchoolToolCalendar(self.section)
        sorted_events = sorted(calendar, key=lambda e: e.dtstart)
        evaluations = removeSecurityProxy(IEvaluations(person))
        for event in sorted_events:
            requirement = requirement_factory(removeSecurityProxy(event))
            score = evaluations.get(requirement)
            if (requirement in evaluations and
                event.meeting_id not in unique_meetings):
                result.append((event, score))
                unique_meetings.add(event.meeting_id)
        return result

    def absentMeetings(self, person):
        return self.gradedMeetings(
            person, requirement_factory=AttendanceRequirement)


class SectionJournal(object):
    """Adapter that adapts a section to it's journal.

    Journal of a section might include grades from related sections as
    well.
    """

    implements(ISectionJournal)
    adapts(ISection)

    def __init__(self, context):
        self.__parent__ = context
        self.section = context
        self.__name__ = "journal"

    def setGrade(self, person, meeting, grade, evaluator=None):
        calendar = meeting.__parent__
        owner = calendar.__parent__
        section_journal_data = ISectionJournalData(owner)
        section_journal_data.setGrade(person, meeting, grade,
                                      evaluator=evaluator)

    def getGrade(self, person, meeting, default=None):
        calendar = meeting.__parent__
        owner = calendar.__parent__
        section_journal_data = ISectionJournalData(owner)
        return section_journal_data.getGrade(person, meeting, default)

    def setAbsence(self, person, meeting, explained=True, evaluator=None, value=ABSENT):
        calendar = meeting.__parent__
        owner = calendar.__parent__
        section_journal_data = ISectionJournalData(owner)
        section_journal_data.setAbsence(person, meeting, explained=explained,
                                        evaluator=evaluator, value=value)

    def getAbsence(self, person, meeting, default=''):
        calendar = meeting.__parent__
        owner = calendar.__parent__
        section_journal_data = ISectionJournalData(owner)
        return section_journal_data.getAbsence(person, meeting, default)

    def evaluate(self, person, requirement, grade, evaluator=None, score_system=None):
        section_journal_data = ISectionJournalData(requirement.target)
        return section_journal_data.evaluate(
            person, requirement, grade,
            evaluator=evaluator, score_system=score_system)

    def getEvaluation(self, person, requirement, default=None):
        section_journal_data = ISectionJournalData(requirement.target)
        return section_journal_data.getEvaluation(
            person, requirement, default=default)

    @Lazy
    def members(self):
        return [member for member in self.section.members
                if IPerson.providedBy(member)]

    @Lazy
    def adjacent_sections(self):
        """Sections in the same course that share members and at least one
        teacher with this section."""
        return adjacent_sections(removeSecurityProxy(self.section))

    @Lazy
    def meetings(self):
        """Ordered list of all meetings for this and adjacent sections with
           consecutive periods removed if the timetable is so configured."""
        events = []
        unique_meetings = set()
        calendars = [ISchoolToolCalendar(section)
                     for section in self.adjacent_sections]
        for calendar in calendars:
            sorted_events = sorted(calendar, key=lambda e: e.dtstart)
            for event in sorted_events:
                if event.meeting_id not in unique_meetings:
                    events.append(event)
                    unique_meetings.add(event.meeting_id)
        return sorted(events)

    def recordedMeetings(self, person):
        """Ordered list of all recorded meetings for this person.

        For this and adjacent sections.
        """
        meetings = []
        for section in self.adjacent_sections:
            sd = ISectionJournalData(section)
            meetings.extend(sd.recordedMeetings(person))
        return sorted(meetings)

    def gradedMeetings(self, person, requirement_factory=GradeRequirement):
        meetings = []
        for section in self.adjacent_sections:
            sd = ISectionJournalData(section)
            meetings.extend(sd.gradedMeetings(
                    person, requirement_factory=requirement_factory))
        return sorted(meetings)

    def absentMeetings(self, person):
        return self.gradedMeetings(person, requirement_factory=AttendanceRequirement)

    def hasMeeting(self, person, meeting):
        calendar = meeting.__parent__
        owner = calendar.__parent__
        return owner in ILearner(person).sections()

    def findMeeting(self, meeting_id):
        calendars = [ISchoolToolCalendar(section)
                     for section in self.adjacent_sections]
        for calendar in calendars:
            try:
                return calendar.find(meeting_id)
            except KeyError:
                pass
        raise KeyError("Could not find a meeting.")


def getSectionJournalData(section):
    """Get the journal for the section."""
    app = ISchoolToolApplication(None)
    jc = app['schooltool.lyceum.journal']

    int_ids = getUtility(IIntIds)
    section_id = str(int_ids.getId(section))

    journal = jc.get(section_id, None)
    if journal is None:
        jc[section_id] = journal = SectionJournalData()

    return journal


def getEventSectionJournal(event):
    """Get the section journal for a ScheduleCalendarEvent."""
    calendar = event.__parent__
    section = calendar.__parent__
    return ISectionJournal(section)


class JournalInit(InitBase):

    def __call__(self):
        self.app['schooltool.lyceum.journal'] = LyceumJournalContainer()


class JournalAppStartup(StartUpBase):
    def __call__(self):
        if 'schooltool.lyceum.journal' not in self.app:
            self.app['schooltool.lyceum.journal'] = LyceumJournalContainer()


class JournalEditorsCrowd(ConfigurableCrowd):

    setting_key = 'administration_can_grade_journal'

    def contains(self, principal):
        """Return the value of the related setting (True or False)."""
        return (AdministrationCrowd(self.context).contains(principal) and
                super(JournalEditorsCrowd, self).contains(principal))
