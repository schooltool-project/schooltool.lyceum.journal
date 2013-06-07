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
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#
"""
Evolve database to generation 4.

Move scores and attendance to scoresystems.
"""
import datetime
import pytz

from zope.app.generations.utility import findObjectsProviding
from zope.app.publication.zopepublication import ZopePublication
from zope.intid.interfaces import IIntIds
from zope.component import getUtility
from zope.component.hooks import getSite, setSite

from schooltool.app.interfaces import ISchoolToolApplication
from schooltool.app.interfaces import ISchoolToolCalendar
from schooltool.course.interfaces import ISectionContainer
from schooltool.schoolyear.interfaces import ISchoolYearContainer
from schooltool.lyceum.journal.journal import AttendanceRequirement
from schooltool.lyceum.journal.journal import GradeRequirement
from schooltool.term.interfaces import ITermContainer


def iterJournals(app):
    jc = app['schooltool.lyceum.journal']
    syc = ISchoolYearContainer(app)

    int_ids = getUtility(IIntIds)

    for sy in syc.values():
        terms = ITermContainer(sy)
        for term in terms.values():
            sections = ISectionContainer(term)
            for section in sections.values():
                section_id = str(int_ids.getId(section))
                journal = jc.get(section_id, None)
                if journal is not None:
                    yield journal


def findMeeting(calendar, date, meeting_id, guessmap):
    search_id = guessmap.get(meeting_id, meeting_id)
    try:
        return calendar.find(search_id)
    except KeyError:
        pass

    start = pytz.UTC.localize(datetime.datetime(
            date.year, date.month, date.day))
    end = pytz.UTC.localize(datetime.datetime(
            date.year, date.month, date.day) + datetime.timedelta(1))

    events = list(calendar.expand(start, end))
    for event in events:
        meeting_id = getattr(event, 'meeting_id')
        if meeting_id == search_id:
            return event

    # No meeting yet.  We've likely found a lost grade
    # Try asigning to the first unique
    used = set(guessmap.values())
    for event in events:
        if event.unique_id not in used:
            guessmap[search_id] = event.unique_id
            return event

    for event in calendar:
        if event.unique_id not in used:
            guessmap[search_id] = event.unique_id
            return event

    # Last resort, try using first meeting in the day
    if events:
        guessmap[search_id] = events[0].unique_id
        return events[0]

    return


def evolveJournal(app, journal):
    persons = app['persons']
    calendar = ISchoolToolCalendar(journal.section)
    meeting_guessmap = {}
    for key, grades in journal.__grade_data__.items():
        username, date = key
        student = persons.get(username)
        if student is None:
            continue
        for meeting_id, entries in grades:
            if isinstance(meeting_id, tuple):
                meeting_id = meeting_id[1]
            entries = list(entries)
            meeting = None
            last_requirement = None
            while entries:
                if meeting is None:
                    meeting = findMeeting(calendar, date, meeting_id, meeting_guessmap)
                if meeting is None:
                    raise Exception('No meeting %s found in calendar' % meeting_id)

                entry = entries.pop(0)
                if entry in ('n', 'p', 'N', 'P', 'a', 't', 'A', 'T'):
                    requirement = AttendanceRequirement(meeting)
                    journal.evaluate(student, requirement, entry, evaluator=None)
                    last_requirement = requirement
                elif entry:
                    requirement = GradeRequirement(meeting)
                    journal.evaluate(student, requirement, entry, evaluator=None)
                    last_requirement = requirement
                elif last_requirement is not None:
                    journal.evaluate(student, last_requirement, '', evaluator=None)
    del journal.__grade_data__

    # Also delete these two, because they've been unused for a long time now
    del journal.__attendance_data__
    del journal.__description_data__


def evolve(context):
    root = context.connection.root().get(ZopePublication.root_name, None)

    old_site = getSite()
    apps = findObjectsProviding(root, ISchoolToolApplication)
    for app in apps:
        setSite(app)
        journals = iterJournals(app)
        for journal in journals:
            evolveJournal(app, journal)

    setSite(old_site)

