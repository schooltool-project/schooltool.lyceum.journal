#
# SchoolTool - common information systems platform for school administration
# Copyright (c) 2003 Shuttleworth Foundation
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
Unit tests for the schooltool.timetable module.

$Id$
"""
import calendar
import unittest
from sets import Set
from pprint import pformat
from datetime import date, time, timedelta, datetime
from persistence import Persistent

from zope.interface.verify import verifyObject
from zope.interface import implements
from schooltool.tests.helpers import diff, sorted
from schooltool.tests.utils import RegistriesSetupMixin
from schooltool.tests.utils import EventServiceTestMixin
from schooltool.tests.utils import LocatableEventTargetMixin
from schooltool.interfaces import ISchooldayModel
from schooltool.interfaces import ILocation
from schooltool.facet import FacetedMixin
from schooltool.timetable import TimetabledMixin
from schooltool.relationship import RelatableMixin


class TestTimetable(unittest.TestCase):

    def test_interface(self):
        from schooltool.timetable import Timetable
        from schooltool.interfaces import ITimetable, ITimetableWrite
        from schooltool.interfaces import ILocation

        t = Timetable(('1', '2'))
        verifyObject(ITimetable, t)
        verifyObject(ITimetableWrite, t)
        verifyObject(ILocation, t)

    def test_keys(self):
        from schooltool.timetable import Timetable
        days = ('Mo', 'Tu', 'We', 'Th', 'Fr')
        t = Timetable(days)
        self.assertEqual(t.keys(), list(days))

    def test_getitem_setitem(self):
        from schooltool.timetable import Timetable
        from schooltool.interfaces import ITimetableDay

        days = ('Mo', 'Tu', 'We', 'Th', 'Fr')
        t = Timetable(days)
        self.assertRaises(KeyError, t.__getitem__, "Mo")
        self.assertRaises(KeyError, t.__getitem__, "What!?")

        class DayStub:
            implements(ITimetableDay)

        self.assertRaises(TypeError, t.__setitem__, "Mo", object())
        self.assertRaises(ValueError, t.__setitem__, "Mon", DayStub())
        monday = DayStub()
        t["Mo"] = monday
        self.assertEqual(t["Mo"], monday)

    def test_items(self):
        from schooltool.timetable import Timetable
        from schooltool.interfaces import ITimetableDay

        days = ('Mo', 'Tu', 'We', 'Th', 'Fr')
        t = Timetable(days)

        class DayStub:
            implements(ITimetableDay)

        monday = DayStub()
        t["Mo"] = monday
        self.assertEqual(t.items(),
                         [("Mo", monday), ("Tu", None), ("We", None),
                          ("Th", None), ("Fr", None)])
        tuesday = DayStub()
        t["Tu"] = tuesday
        self.assertEqual(t.items(),
                         [("Mo", monday), ("Tu", tuesday), ("We", None),
                          ("Th", None), ("Fr", None)])

    def createTimetable(self):
        from schooltool.timetable import Timetable, TimetableDay
        days = ('A', 'B')
        periods = ('Green', 'Blue')
        tt = Timetable(days)
        tt["A"] = TimetableDay(periods)
        tt["B"] = TimetableDay(periods)
        return tt

    def test_clear(self):
        from schooltool.timetable import TimetableActivity
        tt = self.createTimetable()
        english = TimetableActivity("English")
        math = TimetableActivity("Math")
        bio = TimetableActivity("Biology")
        tt["A"].add("Green", english)
        tt["A"].add("Blue", math)
        tt["B"].add("Green", bio)

        tt.clear()

        empty_tt = self.createTimetable()
        self.assertEqual(tt, empty_tt)

    def test_update(self):
        from schooltool.timetable import Timetable, TimetableDay
        from schooltool.timetable import TimetableActivity

        tt = self.createTimetable()
        english = TimetableActivity("English")
        math = TimetableActivity("Math")
        bio = TimetableActivity("Biology")
        tt["A"].add("Green", english)
        tt["A"].add("Blue", math)
        tt["B"].add("Green", bio)

        tt2 = self.createTimetable()
        french = TimetableActivity("French")
        math2 = TimetableActivity("Math 2")
        geo = TimetableActivity("Geography")
        tt2["A"].add("Green", french)
        tt2["A"].add("Blue", math2)
        tt2["B"].add("Blue", geo)

        tt.update(tt2)

        items = [(p, Set(i)) for p, i in tt["A"].items()]
        self.assertEqual(items, [("Green", Set([english, french])),
                                 ("Blue", Set([math, math2]))])

        items = [(p, Set(i)) for p, i in tt["B"].items()]
        self.assertEqual(items, [("Green", Set([bio])),
                                 ("Blue", Set([geo]))])

        tt3 = Timetable(("A", ))
        tt3["A"] = TimetableDay(('Green', 'Blue'))
        self.assertRaises(ValueError, tt.update, tt3)

    def test_cloneEmpty(self):
        from schooltool.timetable import TimetableActivity

        tt = self.createTimetable()
        english = TimetableActivity("English")
        math = TimetableActivity("Math")
        bio = TimetableActivity("Biology")
        tt["A"].add("Green", english)
        tt["A"].add("Blue", math)
        tt["B"].add("Green", bio)
        tt.model = object()

        tt2 = tt.cloneEmpty()
        self.assert_(tt2 is not tt)
        self.assertEquals(tt.day_ids, tt2.day_ids)
        self.assert_(tt.model is tt2.model)
        for day_id in tt2.day_ids:
            day = tt[day_id]
            day2 = tt2[day_id]
            self.assert_(day is not day2)
            self.assertEquals(day.periods, day2.periods)
            for period in day2.periods:
                self.assertEquals(list(day2[period]), [])

    def testComparison(self):
        from schooltool.timetable import TimetableActivity

        model = object()
        tt = self.createTimetable()
        english = TimetableActivity("English")
        math = TimetableActivity("Math")
        bio = TimetableActivity("Biology")
        tt["A"].add("Green", english)
        tt["A"].add("Blue", math)
        tt["B"].add("Green", bio)

        self.assertEquals(tt, tt)
        self.assertNotEquals(tt, None)

        tt2 = self.createTimetable()
        self.assertNotEquals(tt, tt2)

        tt2["A"].add("Green", english)
        tt2["A"].add("Blue", math)
        tt2["B"].add("Green", bio)
        self.assertEquals(tt, tt2)
        tt2.model = model
        self.assertNotEquals(tt, tt2)
        tt.model = model
        self.assertEquals(tt, tt2)

        tt2["B"].remove("Green", bio)
        self.assertNotEquals(tt, tt2)


class TestTimetableDay(unittest.TestCase):

    def test_interface(self):
        from schooltool.timetable import TimetableDay
        from schooltool.interfaces import ITimetableDay, ITimetableDayWrite

        td = TimetableDay()
        verifyObject(ITimetableDay, td)
        verifyObject(ITimetableDayWrite, td)

    def test_keys(self):
        from schooltool.timetable import TimetableDay
        from schooltool.interfaces import ITimetableActivity

        class ActivityStub:
            implements(ITimetableActivity)

        periods = ('1', '2', '3', '4', '5')
        td = TimetableDay(periods)
        self.assertEqual(td.keys(), [])
        td.add("5", ActivityStub())
        td.add("1", ActivityStub())
        td.add("3", ActivityStub())
        td.add("2", ActivityStub())
        self.assertEqual(td.keys(), ['1', '2', '3', '5'])

    def testComparison(self):
        from schooltool.timetable import TimetableDay
        from schooltool.interfaces import ITimetableActivity

        class ActivityStub:
            implements(ITimetableActivity)

        periods = ('A', 'B')
        td1 = TimetableDay(periods)
        td2 = TimetableDay(periods)
        self.assertEquals(td1, td2)
        self.assertNotEquals(td1, None)
        self.failIf(td1 != td2)

        a1 = ActivityStub()
        td1.add("A", a1)
        self.assertNotEquals(td1, td2)
        td2.add("A", a1)
        self.assertEquals(td1, td2)

        td3 = TimetableDay(('C', 'D'))
        self.assertNotEquals(td1, td3)

    def test_getitem_add_items_clear_remove(self):
        from schooltool.timetable import TimetableDay
        from schooltool.interfaces import ITimetableActivity

        periods = ('1', '2', '3', '4')
        td = TimetableDay(periods)
        self.assertRaises(KeyError, td.__getitem__, "Mo")
        self.assertEqual(len(list(td["1"])), 0)
        self.assert_(hasattr(td["1"], 'next'), "not an iterator")

        class ActivityStub:
            implements(ITimetableActivity)

        self.assertRaises(TypeError, td.add, "1", object())
        math = ActivityStub()
        self.assertRaises(ValueError, td.add, "Mo", math)
        td.add("1", math)
        self.assertEqual(list(td["1"]), [math])

        result = [(p, Set(i)) for p, i in td.items()]

        self.assertEqual(result, [('1', Set([math])), ('2', Set([])),
                                  ('3', Set([])), ('4', Set([]))])
        english = ActivityStub()
        td.add("2", english)
        result = [(p, Set(i)) for p, i in td.items()]
        self.assertEqual(result, [('1', Set([math])), ('2', Set([english])),
                                  ('3', Set([])), ('4', Set([]))])


        # test clear()
        self.assertEqual(Set(td["2"]), Set([english]))
        self.assertRaises(ValueError, td.clear, "Mo")
        td.clear("2")
        self.assertRaises(ValueError, td.clear, "foo")
        self.assertEqual(Set(td["2"]), Set([]))

        # test remove()
        td.add("1", english)
        result = [(p, Set(i)) for p, i in td.items()]
        self.assertEqual(result, [('1', Set([english, math])),
                                  ('2', Set([])), ('3', Set([])),
                                  ('4', Set([]))])
        td.remove("1", math)
        self.assertRaises(KeyError, td.remove, "1", math)
        result = [(p, Set(i)) for p, i in td.items()]
        self.assertEqual(result, [('1', Set([english])),
                                  ('2', Set([])), ('3', Set([])),
                                  ('4', Set([]))])


class TestTimetableActivity(unittest.TestCase):

    def test(self):
        from schooltool.timetable import TimetableActivity
        from schooltool.interfaces import ITimetableActivity

        owner = object()
        ta = TimetableActivity("Dancing", owner)
        verifyObject(ITimetableActivity, ta)
        self.assertEqual(ta.title, "Dancing")

        class FakeThing:
            title = "Dancing"
        fake_thing = FakeThing()
        tb = TimetableActivity("Dancing", owner)
        tc = TimetableActivity("Fencing", owner)
        td = TimetableActivity("Dancing", object())

        # __eq__
        self.assertEqual(ta, ta)
        self.assertEqual(ta, tb)
        self.assertNotEqual(ta, tc)
        self.assertNotEqual(ta, td)
        self.assertNotEqual(ta, fake_thing)

        # __ne__
        self.failIf(ta != ta)
        self.failIf(ta != tb)
        self.assert_(ta != tc)
        self.assert_(ta != td)
        self.assert_(ta != fake_thing)

        # __hash__
        self.assertEqual(hash(ta), hash(tb))
        self.assertNotEqual(hash(ta), hash(tc))
        self.assertNotEqual(hash(ta), hash(td))

        def try_to_assign_title():
            ta.title = "xyzzy"
        def try_to_assign_owner():
            ta.owner = "xyzzy"
        self.assertRaises(AttributeError, try_to_assign_title)
        self.assertRaises(AttributeError, try_to_assign_owner)
        self.assertEquals(ta.title, "Dancing")


class TestTimetablingPersistence(unittest.TestCase):
    """A functional test for timetables persistence."""

    def setUp(self):
        from zodb.db import DB
        from zodb.storage.mapping import MappingStorage
        self.db = DB(MappingStorage())
        self.datamgr = self.db.open()

    def test(self):
        from schooltool.timetable import Timetable, TimetableDay
        from schooltool.timetable import TimetableActivity
        from transaction import get_transaction
        tt = Timetable(('A', 'B'))
        self.datamgr.root()['tt'] = tt
        get_transaction().commit()

        periods = ('Green', 'Blue')
        tt["A"] = TimetableDay(periods)
        tt["B"] = TimetableDay(periods)
        get_transaction().commit()

        try:
            datamgr = self.db.open()
            tt2 = datamgr.root()['tt']
            self.assert_(tt2["A"].periods, periods)
            self.assert_(tt2["B"].periods, periods)
        finally:
            get_transaction().abort()
            datamgr.close()

        tt["A"].add("Green", TimetableActivity("English"))
        tt["A"].add("Blue", TimetableActivity("Math"))
        tt["B"].add("Green", TimetableActivity("Biology"))
        tt["B"].add("Blue", TimetableActivity("Geography"))
        get_transaction().commit()

        ## TimetableActivities are not persistent
        # geo = tt["B"]["Blue"].next()
        # geo.title = "Advanced geography"
        # get_transaction().commit()

        self.assertEqual(len(list(tt["A"]["Green"])), 1)
        self.assertEqual(len(list(tt["A"]["Blue"])), 1)
        self.assertEqual(len(list(tt["B"]["Green"])), 1)
        self.assertEqual(len(list(tt["B"]["Blue"])), 1)

        try:
            datamgr = self.db.open()
            tt3 = datamgr.root()['tt']
            self.assertEqual(len(list(tt3["A"]["Green"])), 1)
            self.assertEqual(len(list(tt3["A"]["Blue"])), 1)
            self.assertEqual(len(list(tt3["B"]["Green"])), 1)
            self.assertEqual(len(list(tt3["B"]["Blue"])), 1)
            last = tt3["B"]["Blue"].next()
            # self.assertEqual(last.title, "Advanced geography")
            self.assertEqual(last.title, "Geography")
        finally:
            get_transaction().abort()
            datamgr.close()


class TestSchooldayPeriod(unittest.TestCase):

    def test(self):
        from schooltool.timetable import SchooldayPeriod
        from schooltool.interfaces import ISchooldayPeriod

        ev = SchooldayPeriod("1", time(9, 00), timedelta(minutes=45))
        verifyObject(ISchooldayPeriod, ev)
        self.assertEqual(ev.title, "1")
        self.assertEqual(ev.tstart, time(9,0))
        self.assertEqual(ev.duration, timedelta(seconds=2700))

    def test_eq(self):
        from schooltool.timetable import SchooldayPeriod
        self.assertEqual(
            SchooldayPeriod("1", time(9, 00), timedelta(minutes=45)),
            SchooldayPeriod("1", time(9, 00), timedelta(minutes=45)))
        self.assertEqual(
            hash(SchooldayPeriod("1", time(9, 0), timedelta(minutes=45))),
            hash(SchooldayPeriod("1", time(9, 0), timedelta(minutes=45))))
        self.assertNotEqual(
            SchooldayPeriod("1", time(9, 00), timedelta(minutes=45)),
            SchooldayPeriod("2", time(9, 00), timedelta(minutes=45)))
        self.assertNotEqual(
            SchooldayPeriod("1", time(9, 00), timedelta(minutes=45)),
            SchooldayPeriod("1", time(9, 01), timedelta(minutes=45)))
        self.assertNotEqual(
            SchooldayPeriod("1", time(9, 00), timedelta(minutes=45)),
            SchooldayPeriod("1", time(9, 00), timedelta(minutes=90)))
        self.assertNotEqual(
            SchooldayPeriod("1", time(9, 00), timedelta(minutes=45)),
            object())


class TestSchooldayTemplate(unittest.TestCase):

    def test_interface(self):
        from schooltool.timetable import SchooldayTemplate
        from schooltool.interfaces import ISchooldayTemplate
        from schooltool.interfaces import ISchooldayTemplateWrite

        tmpl = SchooldayTemplate()
        verifyObject(ISchooldayTemplate, tmpl)
        verifyObject(ISchooldayTemplateWrite, tmpl)

    def test_add_remove_iter(self):
        from schooltool.timetable import SchooldayTemplate, SchooldayPeriod
        from schooltool.interfaces import ISchooldayPeriod

        tmpl = SchooldayTemplate()
        self.assertEqual(list(iter(tmpl)), [])
        self.assertRaises(TypeError, tmpl.add, object())

        lesson1 = SchooldayPeriod("1", time(9, 0), timedelta(minutes=45))
        lesson2 = SchooldayPeriod("2", time(10, 0), timedelta(minutes=45))

        tmpl.add(lesson1)
        self.assertEqual(list(iter(tmpl)), [lesson1])

        # Adding the same thing again.
        tmpl.add(lesson1)
        self.assertEqual(list(iter(tmpl)), [lesson1])

        tmpl.add(lesson2)
        self.assertEqual(len(list(iter(tmpl))), 2)
        tmpl.remove(lesson1)
        self.assertEqual(list(iter(tmpl)), [lesson2])

    def test_eq(self):
        from schooltool.timetable import SchooldayTemplate, SchooldayPeriod
        from schooltool.interfaces import ISchooldayPeriod

        tmpl = SchooldayTemplate()
        tmpl.add(SchooldayPeriod("1", time(9, 0), timedelta(minutes=45)))
        tmpl.add(SchooldayPeriod("2", time(10, 0), timedelta(minutes=45)))

        tmpl2 = SchooldayTemplate()
        tmpl2.add(SchooldayPeriod("1", time(9, 0), timedelta(minutes=45)))
        tmpl2.add(SchooldayPeriod("2", time(10, 0), timedelta(minutes=45)))

        self.assertEqual(tmpl, tmpl)
        self.assertEqual(tmpl, tmpl2)
        self.assert_(not tmpl != tmpl2)


class SchooldayModelStub:

    implements(ISchooldayModel)

    #     November 2003
    #  Su Mo Tu We Th Fr Sa
    #                     1
    #   2  3  4  5  6  7  8
    #   9 10 11 12 13 14 15
    #  16 17 18 19 20 21 22
    #  23 24 25 26 27 28 29
    #  30

    first = date(2003, 11, 20)
    last = date(2003, 11, 26)

    def __iter__(self):
        return iter((date(2003, 11, 20),
                     date(2003, 11, 21),
                     date(2003, 11, 22),
                     date(2003, 11, 23),
                     date(2003, 11, 24),
                     date(2003, 11, 25),
                     date(2003, 11, 26)))

    def isSchoolday(self, day):
        return day in (date(2003, 11, 20),
                       date(2003, 11, 21),
                       date(2003, 11, 24),
                       date(2003, 11, 25),
                       date(2003, 11, 26))

    def __contains__(self, day):
        return date(2003, 11, 20) <= day <= date(2003, 11, 26)


class BaseTestTimetableModel:

    def extractCalendarEvents(self, cal, daterange):
        result = []
        for d in daterange:
            calday = cal.byDate(d)
            events = []
            for event in calday:
                events.append(event)
            result.append(dict([(event.dtstart, event.title)
                           for event in events]))
        return result


class TestSequentialDaysTimetableModel(unittest.TestCase,
                                       BaseTestTimetableModel):

    def test_interface(self):
        from schooltool.timetable import SequentialDaysTimetableModel
        from schooltool.interfaces import ITimetableModel

        model = SequentialDaysTimetableModel(("A","B"), {})
        verifyObject(ITimetableModel, model)

    def test_eq(self):
        from schooltool.timetable import SequentialDaysTimetableModel
        from schooltool.timetable import WeeklyTimetableModel
        model = SequentialDaysTimetableModel(("A","B"), {1: 2})
        model2 = SequentialDaysTimetableModel(("A","B"), {1: 2})
        model3 = WeeklyTimetableModel(("A","B"), {1: 2})
        model4 = SequentialDaysTimetableModel(("A"), {1: 2})

        self.assertEqual(model, model2)
        self.assertNotEqual(model2, model3)
        self.assertNotEqual(model2, model4)
        self.assert_(not model2 != model)

    def test_createCalendar(self):
        from schooltool.timetable import SequentialDaysTimetableModel
        from schooltool.timetable import SchooldayTemplate, SchooldayPeriod
        from schooltool.timetable import Timetable, TimetableDay
        from schooltool.timetable import TimetableActivity
        from schooltool.interfaces import ICalendar

        tt = Timetable(('A', 'B'))
        periods = ('Green', 'Blue')
        tt["A"] = TimetableDay(periods)
        tt["B"] = TimetableDay(periods)
        tt["A"].add("Green", TimetableActivity("English"))
        tt["A"].add("Blue", TimetableActivity("Math"))
        tt["B"].add("Green", TimetableActivity("Biology"))
        tt["B"].add("Blue", TimetableActivity("Geography"))

        t, td = time, timedelta
        template1 = SchooldayTemplate()
        template1.add(SchooldayPeriod('Green', t(9, 0), td(minutes=90)))
        template1.add(SchooldayPeriod('Blue', t(11, 0), td(minutes=90)))
        template2 = SchooldayTemplate()
        template2.add(SchooldayPeriod('Green', t(9, 0), td(minutes=90)))
        template2.add(SchooldayPeriod('Blue', t(10, 30), td(minutes=90)))

        model = SequentialDaysTimetableModel(("A", "B"),
                                             {None: template1,
                                              calendar.FRIDAY: template2})
        schooldays = SchooldayModelStub()

        cal = model.createCalendar(schooldays, tt)
        verifyObject(ICalendar, cal)

        result = self.extractCalendarEvents(cal, schooldays)

        expected = [{datetime(2003, 11, 20, 9, 0): "English",
                     datetime(2003, 11, 20, 11, 0): "Math"},
                    {datetime(2003, 11, 21, 9, 0): "Biology",
                     datetime(2003, 11, 21, 10, 30): "Geography"},
                    {}, {},
                    {datetime(2003, 11, 24, 9, 0): "English",
                     datetime(2003, 11, 24, 11, 0): "Math"},
                    {datetime(2003, 11, 25, 9, 0): "Biology",
                     datetime(2003, 11, 25, 11, 0): "Geography"},
                    {datetime(2003, 11, 26, 9, 0): "English",
                     datetime(2003, 11, 26, 11, 0): "Math"}]

        self.assertEqual(expected, result,
                         diff(pformat(expected), pformat(result)))


class TestWeeklyTimetableModel(unittest.TestCase, BaseTestTimetableModel):

    def test(self):
        from schooltool.timetable import WeeklyTimetableModel
        from schooltool.timetable import SchooldayTemplate, SchooldayPeriod
        from schooltool.timetable import Timetable, TimetableDay
        from schooltool.timetable import TimetableActivity
        from schooltool.interfaces import ITimetableModel

        days = ('Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday')
        tt = Timetable(days)
        periods = ('1', '2', '3', '4')
        for day_id in days:
            tt[day_id] = TimetableDay(periods)

        tt["Monday"].add("1", TimetableActivity("English"))
        tt["Monday"].add("2", TimetableActivity("History"))
        tt["Monday"].add("3", TimetableActivity("Biology"))
        tt["Monday"].add("4", TimetableActivity("Physics"))

        tt["Tuesday"].add("1", TimetableActivity("Geography"))
        tt["Tuesday"].add("2", TimetableActivity("Math"))
        tt["Tuesday"].add("3", TimetableActivity("English"))
        tt["Tuesday"].add("4", TimetableActivity("Music"))

        tt["Wednesday"].add("1", TimetableActivity("English"))
        tt["Wednesday"].add("2", TimetableActivity("History"))
        tt["Wednesday"].add("3", TimetableActivity("Biology"))
        tt["Wednesday"].add("4", TimetableActivity("Physics"))

        tt["Thursday"].add("1", TimetableActivity("Chemistry"))
        tt["Thursday"].add("2", TimetableActivity("English"))
        tt["Thursday"].add("3", TimetableActivity("English"))
        tt["Thursday"].add("4", TimetableActivity("Math"))

        tt["Friday"].add("1", TimetableActivity("Geography"))
        tt["Friday"].add("2", TimetableActivity("Drawing"))
        tt["Friday"].add("4", TimetableActivity("Math"))

        t, td = time, timedelta
        template = SchooldayTemplate()
        template.add(SchooldayPeriod('1', t(9, 0), td(minutes=45)))
        template.add(SchooldayPeriod('2', t(9, 50), td(minutes=45)))
        template.add(SchooldayPeriod('3', t(10, 50), td(minutes=45)))
        template.add(SchooldayPeriod('4', t(12, 0), td(minutes=45)))

        model = WeeklyTimetableModel(day_templates={None: template})
        verifyObject(ITimetableModel, model)

        cal = model.createCalendar(SchooldayModelStub(), tt)

        result = self.extractCalendarEvents(cal, SchooldayModelStub())

        expected = [
            {datetime(2003, 11, 20, 9, 0): "Chemistry",
             datetime(2003, 11, 20, 9, 50): "English",
             datetime(2003, 11, 20, 10, 50): "English",
             datetime(2003, 11, 20, 12, 00): "Math"},
            {datetime(2003, 11, 21, 9, 0): "Geography",
             datetime(2003, 11, 21, 9, 50): "Drawing",
             # skip! datetime(2003, 11, 21, 10, 50): "History",
             datetime(2003, 11, 21, 12, 00): "Math"},
            {}, {},
            {datetime(2003, 11, 24, 9, 0): "English",
             datetime(2003, 11, 24, 9, 50): "History",
             datetime(2003, 11, 24, 10, 50): "Biology",
             datetime(2003, 11, 24, 12, 00): "Physics"},
            {datetime(2003, 11, 25, 9, 0): "Geography",
             datetime(2003, 11, 25, 9, 50): "Math",
             datetime(2003, 11, 25, 10, 50): "English",
             datetime(2003, 11, 25, 12, 00): "Music"},
            {datetime(2003, 11, 26, 9, 0): "English",
             datetime(2003, 11, 26, 9, 50): "History",
             datetime(2003, 11, 26, 10, 50): "Biology",
             datetime(2003, 11, 26, 12, 00): "Physics"},
            ]

        self.assertEqual(expected, result,
                         diff(pformat(expected), pformat(result)))


class TimetabledStub(TimetabledMixin, RelatableMixin,
                     LocatableEventTargetMixin, FacetedMixin):

    def __init__(self, parent):
        RelatableMixin.__init__(self)
        TimetabledMixin.__init__(self)
        LocatableEventTargetMixin.__init__(self, parent)
        FacetedMixin.__init__(self)


class LocatableStub:
    implements(ILocation)
    __name__ = None
    __parent__ = None


class TestTimetableDict(unittest.TestCase):

    def test(self):
        from schooltool.timetable import TimetableDict
        from persistence.dict import PersistentDict
        from schooltool.interfaces import ILocation, IMultiContainer

        timetables = TimetableDict()
        self.assert_(isinstance(timetables, PersistentDict))
        verifyObject(ILocation, timetables)
        verifyObject(IMultiContainer, timetables)

    def test_setitem_delitem(self):
        from schooltool.timetable import TimetableDict

        td = TimetableDict()
        item = LocatableStub()
        td['aa', 'bb'] = item
        self.assertEqual(item.__name__, ('aa', 'bb'))
        self.assertEqual(item.__parent__, td)
        self.assertEqual(item, td['aa', 'bb'])
        del td['aa', 'bb']
        self.assertRaises(KeyError, td.__getitem__, ('aa', 'bb'))
        self.assertEqual(item.__parent__, None)
        self.assertEqual(item.__name__, None)

    def test_getRelativePath(self):
        from schooltool.timetable import TimetableDict
        from schooltool.interfaces import IContainmentRoot
        from schooltool.component import getPath
        from zope.interface import directlyProvides

        td = TimetableDict()
        item = LocatableStub()
        directlyProvides(td, IContainmentRoot)

        td['a', 'b'] = item
        self.assertEqual(getPath(item), '/a/b')


class TestTimetabledMixin(RegistriesSetupMixin, EventServiceTestMixin,
                          unittest.TestCase):

    def setUp(self):
        self.setUpRegistries()
        self.setUpEventService()

    def tearDown(self):
        self.tearDownRegistries()

    def test_interface(self):
        from schooltool.interfaces import ITimetabled
        from schooltool.timetable import TimetabledMixin, TimetableDict

        tm = TimetabledMixin()
        verifyObject(ITimetabled, tm)
        self.assert_(isinstance(tm.timetables, TimetableDict))
        self.assertEqual(tm.timetables.__parent__, tm)

    def newTimetable(self):
        from schooltool.timetable import Timetable, TimetableDay
        tt = Timetable(("A", "B"))
        tt["A"] = TimetableDay(("Green", "Blue"))
        tt["B"] = TimetableDay(("Green", "Blue"))
        return tt

    def test_composite_table_own(self):
        tm = TimetabledStub(self.eventService)
        self.assertEqual(tm.timetables, {})
        self.assertEqual(tm.getCompositeTimetable("a", "b"), None)
        self.assertEqual(tm.listCompositeTimetables(), Set())

        tt = tm.timetables["2003 fall", "sequential"] = self.newTimetable()

        result = tm.getCompositeTimetable("2003 fall", "sequential")
        self.assertEqual(result, tt)
        self.assert_(result is not tt)

        self.assertEqual(tm.listCompositeTimetables(),
                         Set([("2003 fall", "sequential")]))

    def test_composite_table_related(self):
        from schooltool.timetable import TimetableActivity
        from schooltool.membership import Membership
        from schooltool.uris import URIGroup
        import schooltool.membership

        schooltool.membership.setUp()

        tm = TimetabledStub(self.eventService)
        parent = TimetabledStub(self.eventService)
        Membership(group=parent, member=tm)

        composite = self.newTimetable()
        english = TimetableActivity("English")
        composite["A"].add("Green", english)

        def newComposite(period_id, schema_id):
            if (period_id, schema_id) == ("2003 fall", "sequential"):
                return composite
            else:
                return None

        def listComposites():
            return Set([("2003 fall", "sequential")])

        parent.getCompositeTimetable = newComposite
        parent.listCompositeTimetables = listComposites

        tm.timetableSource = ((URIGroup, False), )
        result = tm.getCompositeTimetable("2003 fall", "sequential")
        self.assert_(result is None)
        self.assertEqual(tm.listCompositeTimetables(), Set())

        tm.timetableSource = ((URIGroup, True), )
        result = tm.getCompositeTimetable("2003 fall", "sequential")
        self.assertEqual(result, composite)
        self.assert_(result is not composite)
        self.assertEqual(tm.listCompositeTimetables(),
                         Set([("2003 fall", "sequential")]))

        # Now test with our object having a private timetable
        private = self.newTimetable()
        math = TimetableActivity("Math")
        private["B"].add("Blue", math)
        tm.timetables["2003 fall", "sequential"] = private

        result = tm.getCompositeTimetable("2003 fall", "sequential")
        expected = composite.cloneEmpty()
        expected.update(composite)
        expected.update(private)
        self.assertEqual(result, expected)
        self.assertEqual(tm.listCompositeTimetables(),
                         Set([("2003 fall", "sequential")]))

        # Now test things with a table which says (URIGroup, False)
        tm.timetableSource = ((URIGroup, False), )

        parent_private = self.newTimetable()
        french = TimetableActivity("French")
        parent_private["A"].add("Green", french)
        parent.timetables["2003 fall", "sequential"] = parent_private

        result = tm.getCompositeTimetable("2003 fall", "sequential")
        expected = composite.cloneEmpty()
        expected.update(private)
        expected.update(parent_private)
        self.assertEqual(result, expected)
        self.assertEqual(Set(result["B"]["Blue"]), Set([math]))
        self.assertEqual(Set(result["A"]["Green"]), Set([french]))
        self.assertEqual(tm.listCompositeTimetables(),
                         Set([("2003 fall", "sequential")]))

    def test_getCompositeTable_facets(self):
        from schooltool.timetable import TimetableActivity
        from schooltool.component import FacetManager
        from schooltool.interfaces import IFacet, ICompositeTimetableProvider
        from schooltool.teaching import Teaching
        from schooltool.uris import URITaught
        import schooltool.relationship

        schooltool.relationship.setUp()

        class TeacherFacet(Persistent):
            implements(IFacet, ICompositeTimetableProvider)
            __parent__ = None
            __name__ = None
            active = False
            owner = None
            timetableSource = ((URITaught, False), )

        teacher = TimetabledStub(self.eventService)
        taught = TimetabledStub(self.eventService)
        Teaching(teacher=teacher, taught=taught)

        facets = FacetManager(teacher)
        facets.setFacet(TeacherFacet())

        tt = self.newTimetable()
        taught.timetables['2003 fall', 'sequential'] = tt
        stuff = TimetableActivity("Stuff")
        tt["A"].add("Green", stuff)

        result = teacher.getCompositeTimetable('2003 fall', 'sequential')
        self.assertEqual(result, tt)

    def test_paths(self):
        from schooltool.component import getPath

        tm = TimetabledStub(self.eventService)
        tm.__name__ = 'stub'
        tt = tm.timetables["2003-fall", "sequential"] = self.newTimetable()
        tt1 = tm.getCompositeTimetable("2003-fall", "sequential")

        self.assertEqual(getPath(tt),
                         '/stub/timetables/2003-fall/sequential')
        self.assertEqual(getPath(tt1),
                         '/stub/composite-timetables/2003-fall/sequential')


class TestTimetableSchemaService(unittest.TestCase):

    def test_interface(self):
        from schooltool.timetable import TimetableSchemaService
        from schooltool.interfaces import ITimetableSchemaService

        service = TimetableSchemaService()
        verifyObject(ITimetableSchemaService, service)

    def test(self):
        from schooltool.timetable import TimetableSchemaService
        from schooltool.timetable import Timetable, TimetableDay
        from schooltool.timetable import TimetableActivity

        service = TimetableSchemaService()
        self.assertEqual(service.keys(), [])

        tt = Timetable(("A", "B"))
        tt["A"] = TimetableDay(("Green", "Blue"))
        tt["B"] = TimetableDay(("Red", "Yellow"))
        tt["A"].add("Green", TimetableActivity("Slacking"))
        self.assertEqual(len(list(tt["A"]["Green"])), 1)

        service["super"] = tt
        self.assertEqual(service.keys(), ["super"])

        copy1 = service["super"]
        copy2 = service["super"]
        self.assert_(copy2 is not copy1)
        self.assertEqual(copy2, copy1)
        self.assertEqual(tt.cloneEmpty(), copy1)

        self.assertEqual(len(list(copy1["A"]["Green"])), 0)

        copy1["A"].add("Green", TimetableActivity("Slacking"))
        self.assertEqual(len(list(copy1["A"]["Green"])), 1)
        self.assertEqual(len(list(copy2["A"]["Green"])), 0)

        del service["super"]
        self.assertRaises(KeyError, service.__getitem__, "super")
        self.assertEqual(service.keys(), [])


class TestTimePeriodService(unittest.TestCase):

    def test_interface(self):
        from schooltool.timetable import TimePeriodService
        from schooltool.interfaces import ITimePeriodService

        service = TimePeriodService()
        verifyObject(ITimePeriodService, service)

    def test(self):
        from schooltool.timetable import TimePeriodService
        service = TimePeriodService()
        self.assertEqual(service.keys(), [])

        schooldays = SchooldayModelStub()
        service['2003 fall'] = schooldays
        self.assertEqual(service.keys(), ['2003 fall'])
        self.assert_('2003 fall' in service)
        self.assert_('2004 spring' not in service)
        self.assert_(service['2003 fall'] is schooldays)

        # duplicate registration
        schooldays2 = SchooldayModelStub()
        service['2003 fall'] = schooldays2
        self.assertEqual(service.keys(), ['2003 fall'])
        self.assert_('2003 fall' in service)
        self.assert_(service['2003 fall'] is schooldays2)

        schooldays3 = SchooldayModelStub()
        service['2004 spring'] = schooldays3
        self.assertEqual(sorted(service.keys()), ['2003 fall', '2004 spring'])
        self.assert_('2004 spring' in service)
        self.assert_(service['2004 spring'] is schooldays3)

        del service['2003 fall']
        self.assertEqual(service.keys(), ['2004 spring'])
        self.assert_('2003 fall' not in service)
        self.assert_('2004 spring' in service)
        self.assertRaises(KeyError, lambda: service['2003 fall'])

        # duplicate deletion
        self.assertRaises(KeyError, service.__delitem__, '2003 fall')


def test_suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(TestTimetable))
    suite.addTest(unittest.makeSuite(TestTimetableDay))
    suite.addTest(unittest.makeSuite(TestTimetableActivity))
    suite.addTest(unittest.makeSuite(TestTimetablingPersistence))
    suite.addTest(unittest.makeSuite(TestSchooldayPeriod))
    suite.addTest(unittest.makeSuite(TestSchooldayTemplate))
    suite.addTest(unittest.makeSuite(TestSequentialDaysTimetableModel))
    suite.addTest(unittest.makeSuite(TestWeeklyTimetableModel))
    suite.addTest(unittest.makeSuite(TestTimetableDict))
    suite.addTest(unittest.makeSuite(TestTimetabledMixin))
    suite.addTest(unittest.makeSuite(TestTimetableSchemaService))
    suite.addTest(unittest.makeSuite(TestTimePeriodService))
    return suite
