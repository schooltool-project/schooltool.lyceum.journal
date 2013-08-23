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
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
"""
Lyceum journal content classes.
"""
from BTrees.OOBTree import OOBTree
from decimal import Decimal
from persistent import Persistent

import zope.schema
import zope.schema.interfaces
import zope.schema.vocabulary
import z3c.form.widget
from zope.annotation.interfaces import IAnnotations
from zope.security.proxy import removeSecurityProxy
from zope.intid.interfaces import IIntIds
from zope.container.btree import BTreeContainer
from zope.container.interfaces import INameChooser
from zope.cachedescriptors.property import Lazy
from zope.component import getUtility
from zope.component import adapter
from zope.component import adapts
from zope.component import queryMultiAdapter
from zope.interface import implementer
from zope.interface import implements
from zope.interface import Interface
from zope.keyreference.interfaces import IKeyReference
from zope.location.interfaces import ILocation

from schooltool.app.app import InitBase, StartUpBase
from schooltool.app.interfaces import ISchoolToolApplication
from schooltool.app.interfaces import ISchoolToolCalendar
from schooltool.course.interfaces import ILearner
from schooltool.course.interfaces import IInstructor
from schooltool.course.interfaces import ISection
from schooltool.export.export import XLSReportTask
from schooltool.person.interfaces import IPerson
from schooltool.requirement.interfaces import ICustomScoreSystem
from schooltool.requirement.interfaces import IEvaluations
from schooltool.requirement.evaluation import Evaluation
from schooltool.requirement.scoresystem import AbstractScoreSystem
from schooltool.requirement.scoresystem import GlobalRangedValuesScoreSystem
from schooltool.requirement.scoresystem import CustomScoreSystem
from schooltool.requirement.scoresystem import ScoreValidationError, UNSCORED
from schooltool.requirement.interfaces import IScoreSystemContainer
from schooltool.securitypolicy.crowds import ConfigurableCrowd
from schooltool.securitypolicy.crowds import ClerksCrowd

from schooltool.lyceum.journal.interfaces import IJournalScoreSystemPreferences
from schooltool.lyceum.journal.interfaces import IAttendanceScoreSystem
from schooltool.lyceum.journal.interfaces import IPersistentAttendanceScoreSystem
from schooltool.lyceum.journal.interfaces import IEvaluateRequirement
from schooltool.lyceum.journal.interfaces import ISectionJournal
from schooltool.lyceum.journal.interfaces import ISectionJournalData
from schooltool.lyceum.journal.interfaces import IAvailableScoreSystems
from schooltool.lyceum.journal import LyceumMessage as _

ABSENT = 'n' #n means absent in lithuanian
TARDY = 'p' #p means tardy in lithuanian

CURRENT_SECTION_TAUGHT_KEY = 'schooltool.gradebook.currentsectiontaught'
CURRENT_JOURNAL_MODE_KEY = 'schooltool.gradebook.currentjournalmode'


class AttendanceScoreSystem(AbstractScoreSystem):
    implements(IAttendanceScoreSystem)

    scores = ()
    tag_absent = ()
    tag_tardy = ()
    tag_excused = ()

    def __init__(self, title, description=None, **kw):
        super(AttendanceScoreSystem, self).__init__(title, description=description)
        self.initDefaults(**kw)

    def initDefaults(self, **kw):
        if 'scores' not in kw:
            self.scores = (('a', 'Absent'),
                           ('t', 'Tardy'),
                           ('ae', 'Absent (excused)'),
                           ('te', 'Tardy (excused)'))
            self.tag_absent = 'a', 'ae',
            self.tag_tardy = 't', 'te',
            self.tag_excused = 'ae', 'te',
        else:
            self.scores = tuple(kw['scores'].items())
            for attr in ('tag_absent', 'tag_tardy', 'tag_excused'):
                setattr(self, attr, tuple(kw.get(attr, ())))

    def isValidScore(self, score):
        """See interfaces.IScoreSystem"""
        if score is UNSCORED:
            return True
        if not isinstance(score, (str, unicode)):
            return False
        if score.lower() in dict(self.scores):
            return True
        return False

    def fromUnicode(self, rawScore):
        """See interfaces.IScoreSystem"""
        if not rawScore:
            return UNSCORED
        if not self.isValidScore(rawScore):
            raise ScoreValidationError(rawScore)
        return rawScore.strip().lower()

    def isTardy(self, score):
        if (score is None or
            score is UNSCORED or
            score.value is UNSCORED):
            return False
        return score.value in self.tag_tardy

    def isAbsent(self, score):
        if (score is None or
            score is UNSCORED or
            score.value is UNSCORED):
            return False
        return score.value in self.tag_absent

    def isExcused(self, score):
        if (score is None or
            score is UNSCORED or
            score.value is UNSCORED):
            return False
        return score.value in self.tag_excused


class PersistentAttendanceScoreSystem(AttendanceScoreSystem, Persistent):
    implements(IPersistentAttendanceScoreSystem)

    hidden = False


class GlobalAbsenceScoreSystem(AttendanceScoreSystem):

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
    u'Absences', u'Attendance Score System')


def getInstructorSections(person):
    return list(IInstructor(person).sections())


def getCurrentSectionTaught(person):
    ann = IAnnotations(removeSecurityProxy(person))
    if CURRENT_SECTION_TAUGHT_KEY not in ann:
        ann[CURRENT_SECTION_TAUGHT_KEY] = None
    else:
        section = ann[CURRENT_SECTION_TAUGHT_KEY]
        if section not in getInstructorSections(person):
            return None
        try:
            getSectionJournalData(section)
        except:
            ann[CURRENT_SECTION_TAUGHT_KEY] = None
    return ann[CURRENT_SECTION_TAUGHT_KEY]


def setCurrentSectionTaught(person, section):
    ann = IAnnotations(removeSecurityProxy(person))
    if section in getInstructorSections(person):
        ann[CURRENT_SECTION_TAUGHT_KEY] = removeSecurityProxy(section)


def getCurrentJournalMode(person):
    ann = IAnnotations(removeSecurityProxy(person))
    if CURRENT_JOURNAL_MODE_KEY not in ann:
        ann[CURRENT_JOURNAL_MODE_KEY] = None
    return ann.get(CURRENT_JOURNAL_MODE_KEY, None)


def setCurrentJournalMode(person, mode):
    ann = IAnnotations(removeSecurityProxy(person))
    ann[CURRENT_JOURNAL_MODE_KEY] = mode


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


class EvaluateGeneric(object):
    implements(IEvaluateRequirement)

    def __init__(self, target):
        self.context = target

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


class MeetingRequirement(tuple):
    implements(IKeyReference)

    key_type_id  = 'schooltool.lyceum.journal.journal.MeetingRequirement'
    requirement_type = None
    score_system = None

    def __new__(cls, meeting, score_system=None):
        params = cls.getMeetingParams(meeting)
        inst = tuple.__new__(cls, params)
        if score_system is not None:
            inst.score_system = score_system
        return inst

    @classmethod
    def getMeetingParams(cls, meeting):
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
        return (cls.requirement_type, date, meeting_id, target_ref)

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


class SchoolMeetingRequirement(MeetingRequirement):
    implements(IKeyReference)

    key_type_id  = 'schooltool.lyceum.journal.journal.SchoolMeetingRequirement'

    @classmethod
    def getMeetingParams(cls, meeting):
        date = meeting.dtstart.date()
        target_ref = IKeyReference(ISchoolToolApplication(None))
        return (cls.requirement_type, date, None, target_ref)


class GradeRequirement(MeetingRequirement):
    requirement_type = 'grade'
    score_system = TenPointScoreSystem


class AttendanceRequirement(MeetingRequirement):
    requirement_type = 'attendance'
    score_system = AbsenceScoreSystem


class HomeroomRequirement(SchoolMeetingRequirement):
    requirement_type = 'homeroom'
    score_system = AbsenceScoreSystem


class SectionJournalData(Persistent):
    """A journal for a section."""
    implements(ISectionJournalData, ILocation)

    def __init__(self):
        self.__parent__ = None
        self.__name__ = None

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

    @Lazy
    def members(self):
        return [member for member in self.section.members
                if IPerson.providedBy(member)]

    @Lazy
    def meetings(self):
        """Ordered list of all meetings for this section with
           consecutive periods removed if the timetable is so configured."""
        events = []
        unique_meetings = set()
        calendar = ISchoolToolCalendar(removeSecurityProxy(self.section))
        sorted_events = sorted(calendar, key=lambda e: e.dtstart)
        for event in sorted_events:
            if event.meeting_id not in unique_meetings:
                events.append(event)
                unique_meetings.add(event.meeting_id)
        return sorted(events)

    def recordedMeetings(self, person):
        """Ordered list of all recorded meetings for this person.

        For this section.
        """
        sd = ISectionJournalData(removeSecurityProxy(self.section))
        meetings = sd.recordedMeetings(person)
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
        calendar = ISchoolToolCalendar(removeSecurityProxy(self.section))
        meeting = calendar.find(meeting_id)
        return meeting


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
        return (ClerksCrowd(self.context).contains(principal) and
                super(JournalEditorsCrowd, self).contains(principal))


class JournalXLSReportTask(XLSReportTask):

    @property
    def context(self):
        section = XLSReportTask.context.fget(self)
        journal = ISectionJournal(section)
        return journal

    @context.setter
    def context(self, value):
        section = ISection(value)
        XLSReportTask.context.fset(self, section)


@adapter(MeetingRequirement)
@implementer(IEvaluateRequirement)
def getEvaluateRequirementForMeetingRequirement(requirement):
    return IEvaluateRequirement(requirement.target)


@adapter(ISection)
@implementer(IEvaluateRequirement)
def getEvaluateRequirementForSection(section):
    return ISectionJournalData(section)


class ScoreSystemPreferences(Persistent):
    implements(IJournalScoreSystemPreferences)

    grading_scoresystem = None
    attendance_scoresystem = None


@adapter(Interface)
@implementer(IJournalScoreSystemPreferences)
def getScoreSystemPreferences(jd):
    app = ISchoolToolApplication(None)
    ssp = app['schooltool.lyceum.journal-ss-prefs']
    return ssp


class JournalScoreSystemsStartup(StartUpBase):

    def updateGradingSS(self, prefs):
        if prefs.grading_scoresystem is not None:
            return
        app = ISchoolToolApplication(None)
        ssc = IScoreSystemContainer(app)
        tenPointScoreSystem = CustomScoreSystem(
            u'10 Points', u'10 Points Score System',
            scores=[(unicode(i), u'', Decimal(i), Decimal((i-1)*10))
                    for i in range(1, 11)],
            bestScore='10',
            minPassingScore='4')
        chooser = INameChooser(ssc)
        name = chooser.chooseName('ten_points', tenPointScoreSystem)
        ssc[name] = tenPointScoreSystem
        prefs.grading_scoresystem = tenPointScoreSystem

    def updateAttendanceSS(self, prefs):
        if prefs.attendance_scoresystem is not None:
            return
        app = ISchoolToolApplication(None)
        ssc = IScoreSystemContainer(app)
        attendanceScoreSystem = None
        for ss in ssc.values():
            if (IAttendanceScoreSystem.providedBy(ss) and
                not ss.hidden):
                attendanceScoreSystem = ss
                break
        if attendanceScoreSystem is None:
            attendanceScoreSystem = PersistentAttendanceScoreSystem('Attendance')
            chooser = INameChooser(ssc)
            name = chooser.chooseName(attendanceScoreSystem.title, attendanceScoreSystem)
            ssc[name] = attendanceScoreSystem
        prefs.attendance_scoresystem = attendanceScoreSystem

    def updatePreferences(self, prefs):
        self.updateGradingSS(prefs)
        self.updateAttendanceSS(prefs)

    def __call__(self):
        if 'schooltool.lyceum.journal-ss-prefs' not in self.app:
            prefs = ScoreSystemPreferences()
            self.app['schooltool.lyceum.journal-ss-prefs'] = prefs
        else:
            prefs = self.app['schooltool.lyceum.journal-ss-prefs']
        self.updatePreferences(prefs)


@adapter(Interface)
@implementer(IAvailableScoreSystems)
def getJournalGradingScoreSystems(context):
    app = ISchoolToolApplication(None)
    ssc = IScoreSystemContainer(app)
    result = [
        ss for ss in ssc.values()
        if (ICustomScoreSystem.providedBy(ss) and
            not ss.hidden)]
    return result


@adapter(Interface)
@implementer(IAvailableScoreSystems)
def getJournalAttendanceScoreSystems(context):
    app = ISchoolToolApplication(None)
    ssc = IScoreSystemContainer(app)
    result = [
        ss for ss in ssc.values()
        if (IPersistentAttendanceScoreSystem.providedBy(ss) and
            not ss.hidden)]
    return result


class JournalGradingScoreSystemChoices(zope.schema.vocabulary.SimpleVocabulary):
    implements(zope.schema.interfaces.IContextSourceBinder)

    def __init__(self, context):
        self.context = context
        terms = self.createTerms()
        zope.schema.vocabulary.SimpleVocabulary.__init__(self, terms)

    def getScoreSystems(self):
        scoresystems = list(queryMultiAdapter(
                (self.context, ),
                IAvailableScoreSystems,
                name="grading",
                default=[],
                ))
        return scoresystems

    def createTerms(self):
        result = []
        result.append(self.createTerm(
                None,
                z3c.form.widget.SequenceWidget.noValueToken,
                _("Select a scoresystem"),
                ))
        scoresystems = self.getScoreSystems()
        for scoresystem in scoresystems:
            title = scoresystem.title
            token = scoresystem.__name__
            token=unicode(token).encode('punycode')
            result.append(self.createTerm(scoresystem, token, title))
        return result


class JournalAttendanceScoreSystemChoices(JournalGradingScoreSystemChoices):

    def getScoreSystems(self):
        scoresystems = list(queryMultiAdapter(
                (self.context, ),
                IAvailableScoreSystems,
                name="attendance",
                default=[],
                ))
        return scoresystems


def journalgradingchoicesfactory():
    return JournalGradingScoreSystemChoices


def journalattendancechoicesfactory():
    return JournalAttendanceScoreSystemChoices
