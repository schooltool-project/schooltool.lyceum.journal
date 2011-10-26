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
Evolve recorded meeting keys to a new format.

Evolution caused by timetable remake.
"""
import pytz
import re
from datetime import datetime

from zope.app.generations.utility import findObjectsProviding
from zope.app.publication.zopepublication import ZopePublication
from zope.component.hooks import getSite, setSite
from zope.component import getUtility
from zope.intid.interfaces import IIntIds

from schooltool.app.interfaces import ISchoolToolApplication
from schooltool.app.interfaces import ISchoolToolCalendar
from schooltool.term.interfaces import ITerm


meeting_pattern = re.compile(
    '(?P<hashed_id>-?\d+)-(?P<timetable_path>.+)@(?P<socket_getfqdn>.+)')


def makeEventMap(section):
    event_map = {}
    activity_title = ''.join(
        [course.title for course in section.courses])
    calendar = ISchoolToolCalendar(section)
    for event in calendar:
        schedule = getattr(event, 'schedule', None)
        if schedule is None:
            continue
        hashed_id = unicode(hash(
                (activity_title, event.dtstart, event.duration)))
        event_map[hashed_id] = event
    return event_map


def extractMeetingEventKey(section, meeting_key):
    parts = meeting_pattern.match(meeting_key).groupdict()
    split_path = filter(None, parts['timetable_path'].strip().split('/'))

    app_key, term_intid, section_id, timetables, tt_id = split_path

    assert app_key == 'schooltool.course.section', app_key
    assert term_intid == section.__parent__.__name__, '%s != %s' % (
        term_intid, section.__parent__.__name__)
    assert section_id == section.__name__, '%s != %s' % (
        section_id, section.__name__)
    assert timetables == 'timetables', timetables

    return unicode(parts['hashed_id'])


class MisplacedMeeting(object):
    meeting_id = None

    def __init__(self, dtstart, unique_id, meeting_id=None):
        self.dtstart = dtstart
        self.unique_id = unique_id
        self.meeting_id = meeting_id

    def __reduce__(self, proto=None):
        raise TypeError("Not picklable")
    __reduce_ex__ = __reduce__


def evolveRecords(section, records, default_date, event_map):
    records_by_event = {}

    for record_key, record in records.items():
        username, meeting_key = record_key
        old_key = extractMeetingEventKey(section, meeting_key)
        event = event_map.get(old_key)
        if event is None:
            event = event_map.get(meeting_key)
        if event is None:
            event = MisplacedMeeting(default_date, record_key)
        if event in records_by_event:
            # An edge case when two events for the section have
            # identical times (a schedule conflict, generated
            # from two different timetables) and both of them
            # had a record.
            event = MisplacedMeeting(
                event.dtstart, event.unique_id,
                meeting_id=event.meeting_id)
        records_by_event[event] = username, record

    records.clear()
    for event, (username, record) in records_by_event.items():
        key = (username, event.dtstart.date())
        entries = dict(records.get(key, ()))
        entry_id = event.meeting_id
        if entry_id is None:
            entry_id = event.unique_id
        entries[entry_id] = record
        records[key] = tuple(sorted(entries.items()))


def evolveDescriptions(section, descriptions, event_map):
    new_descriptions = {}

    for meeting_key, description in descriptions.items():
        old_key = extractMeetingEventKey(section, meeting_key)
        event = event_map.get(old_key)
        if event is None:
            continue

        date = event.dtstart.date()
        entry_id = event.meeting_id
        if entry_id is None:
            entry_id = event.unique_id
        new_descriptions[(date, entry_id)] = description

    descriptions.clear()

    for key, description in new_descriptions.items():
        descriptions[key] = description


def evolveSectionJournal(section, journal):
    event_map = makeEventMap(section)

    first = ITerm(section).first
    default_date = datetime(first.year, first.month, first.day)

    evolveRecords(section, journal.__grade_data__,
                  default_date, event_map)

    evolveRecords(section, journal.__attendance_data__,
                  default_date, event_map)

    evolveDescriptions(section, journal.__description_data__,
                       event_map)


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
