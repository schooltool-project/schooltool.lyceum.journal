#
# - common information systems platform for school administration
# Copyright (c) 2013 Shuttleworth Foundation
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
Move grades from overlapped journal schedules to respective journals.
"""
from zope.app.generations.utility import findObjectsProviding
from zope.app.publication.zopepublication import ZopePublication
from zope.component.hooks import getSite, setSite
from zope.component import getUtility
from zope.intid.interfaces import IIntIds

from schooltool.app.interfaces import ISchoolToolApplication
from schooltool.app.interfaces import ISchoolToolCalendar
from schooltool.course.interfaces import ISection
from schooltool.person.interfaces import IPerson
from schooltool.lyceum.journal.interfaces import ISectionJournalData
from schooltool.term.interfaces import ITerm


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
        for course in section.courses:
            if course in courses:
                for instructor in section.instructors:
                    if instructor in instructors:
                        sections.add(section)
                        break
    return sections


def collect_meeting_ids(section):
    calendar = ISchoolToolCalendar(section)
    unique_meeting_ids = set()
    for event in sorted(calendar, key=lambda e: e.dtstart):
        entry_id = event.meeting_id
        if entry_id is None:
            entry_id = event.unique_id
        if entry_id not in unique_meeting_ids:
            unique_meeting_ids.add(entry_id)
    return unique_meeting_ids


def collect_student_names(section):
    return set([person.__name__ for person in section.members])


def evolveSectionJournal(section, journal):
    adjacent_journals = sorted([
        (ITerm(adj_sec).first,
         ISectionJournalData(adj_sec),
         collect_meeting_ids(adj_sec),
         collect_student_names(adj_sec))
        for adj_sec in adjacent_sections(section)
        if ITerm(adj_sec).first > ITerm(section).first
        ])

    for key in journal.__grade_data__:
        person_name, grade_date = key
        for adj_date, adj_journal, adj_eids, adj_students in reversed(adjacent_journals):
            if adj_date > grade_date:
                continue # journal starts later then grade recorded

            if person_name not in adj_students:
                continue # person is not attending this section

            # process day records
            recorded_entries = list(journal.__grade_data__.get(key, ()))
            for eid, entries in recorded_entries:
                # is the move possible for this grade?
                if eid not in adj_eids:
                    continue
                journal.__grade_data__[key] = tuple([
                        (k, v)
                        for k, v in journal.__grade_data__[key]
                        if k != eid])
                adj_journal.__grade_data__[key] = tuple(sorted(
                        [(k, v)
                         for k, v in adj_journal.__grade_data__.get(key, ())
                         if k != eid] +
                        [(eid, entries)]
                        ))


def evolveJournals(app):
    container = app['schooltool.lyceum.journal']
    int_ids = getUtility(IIntIds)

    for section_id, journal in container.items():
        section = int_ids.queryObject(int(section_id))
        if section:
            evolveSectionJournal(section, journal)
        else:
            # Section was deleted, delete journal data for it
            del container[section_id]


def evolve(context):
    root = context.connection.root().get(ZopePublication.root_name, None)
    old_site = getSite()

    apps = findObjectsProviding(root, ISchoolToolApplication)
    for app in apps:
        setSite(app)
        if 'schooltool.lyceum.journal' in app:
            evolveJournals(app)

    setSite(old_site)
