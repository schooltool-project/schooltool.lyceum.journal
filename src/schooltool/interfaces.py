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
SchoolTool application interfaces

$Id$
"""

import datetime

from zope.interface import Interface, Attribute, implements
from zope.app.location.interfaces import ILocation
from zope.schema.interfaces import IField
from zope.schema import Field, Object, Int, Text, TextLine, List, Set, Tuple
from zope.schema import Dict, Date, Timedelta, Bool, Choice
from zope.app.container.interfaces import IContainer, IContained
from zope.app.container.constraints import contains, containers

from schoolbell.app import interfaces as sb
from schoolbell.app.overlay import ICalendarOverlayInfo
from schoolbell.calendar.interfaces import Unchanged
from schoolbell.calendar.interfaces import ICalendarEvent

from schooltool import SchoolToolMessageID as _

#
# Time field used in timetabling interfaces
#

class ITime(IField):
    u"""Field containing time."""


class Time(Field):
    __doc__ = ITime.__doc__
    _type = datetime.time

    implements(ITime)


#
#  Timetabling
#

class IDateRange(Interface):
    """A range of dates (inclusive).

    If r is an IDateRange, then the following invariant holds:
    r.first <= r.last

    Note that empty date ranges cannot be represented.
    """

    first = Date(
        title=u"The first day of the period of time covered.")

    last = Date(
        title=u"The last day of the period covered.")

    def __iter__():
        """Iterate over all dates in the range from the first to the last."""

    def __contains__(date):
        """Return True if the date is within the range, otherwise False.

        Raises a TypeError if date is not a datetime.date.
        """

    def __len__():
        """Return the number of dates covered by the range."""


class ITerm(IDateRange, IContained):
    """A calendar which can tell whether a day is a school day or not
    in a certain school term.
    """

    title = TextLine(title=_("Title"))

    def isSchoolday(date):
        """Return whether the date is a schoolday.

        Raises a ValueError if the date is outside of the term covered.
        """


class ITermWrite(Interface):

    def add(day):
        """Mark the day as a schoolday.

        Raises a ValueError if the date is outside of the term covered.
        """

    def remove(day):
        """Mark the day as a holiday.

        Raises a ValueError if the date is outside of the term covered.
        """

    def reset(first, last):
        """Change the term and mark all days as holidays.

        If first is later than last, a ValueError is raised.
        """

    def addWeekdays(*weekdays):
        """Mark that all days of week with a number in weekdays within the
        term will be schooldays.

        The numbering used is the same as one used by datetime.date.weekday()
        method, or the calendar module: 0 is Monday, 1 is Tuesday, etc.
        """

    def removeWeekdays(*weekdays):
        """Mark that all days of week with a number in weekdays within the
        term will be holidays.

        The numbering used is the same as one used by datetime.date.weekday()
        method, or the calendar module: 0 is Monday, 1 is Tuesday, etc.
        """

    def toggleWeekdays(*weekdays):
        """Toggle the state of all days of week with a number in weekdays.

        The numbering used is the same as one used by datetime.date.weekday()
        method, or the calendar module: 0 is Monday, 1 is Tuesday, etc.
        """


class ISchooldayTemplate(Interface):
    """A school-day template represents the times that periods are
    scheduled during a prototypical school day.

    Some schools need only one school-day template. For example, they
    have seven periods in a day, and the periods are always in the
    sequence 1 to 7, and start and end at the same time on each school
    day.

    Other schools will need more than one school-day template. For
    example, a school that has shorter school days on Wednesdays will
    have one template for Wednesdays, and one other template for
    Monday, Tuesday, Thursday and Friday.

    Other schools will want to re-order the periods on different days,
    so they will have one template with periods ABCDEF in that order,
    and another template with periods DEFABC.
    """

    def __iter__():
        """Return an iterator over the ISchooldayPeriods of this template."""


class ISchooldayTemplateWrite(Interface):
    """Write access to schoolday templates."""

    def add(obj):
        """Add an ISchooldayPeriod to the template.

        Raises a TypeError if obj is not an ISchooldayPeriod."""

    def remove(obj):
        """Remove an object from the template."""


class ISchooldayPeriod(Interface):
    """An object binding a timetable period to a concrete time
    interval within a schoolday template.
    """

    title = TextLine(
        title=u"Period id of this event")

    tstart = Time(
        title=u"Time of the start of the event")

    duration = Timedelta(
        title=u"Timedelta of the duration of the event")

    def __eq__(other):
        """SchooldayPeriods are equal if all three of their
        attributes are equal.

        Raises TypeError if other does not implement ISchooldayPeriod.
        """

    def __ne__(other):
        """SchooldayPeriods are not equal if any of their three
        attributes are not equal.

        Raises TypeError if other does not implement ISchooldayPeriod.
        """

    def __hash__():
        """Hashes of ISchooldayPeriods are equal iff those
        ISchooldayPeriods are equal.
        """


class ITimetableModel(Interface):
    """A timetable model knows how to create an ICalendar object when
    it is given a School-day model and a Timetable.

    The implementation of the timetable model knows how to arrange
    timetable days within the available school days.

    For example, a school with four timetable days 1, 2, 3, 4 has its
    timetable days laid out in sequence across consecutive school
    days. A school with a timetable days for Monday through Friday has
    its timetable days laid out to match the day of the week that a
    school day occurs on.

    The ICalendar produced will use an appropriate school-day template
    for each day, depending on (for example) what day of the week that
    day occurs on, or whatever other rules the implementation of the
    timetable model is coded to use.
    """

    factory_id = Attribute("""Name of the ITimetableModelFactory utility
                              that was used to create this model.""")

    timetableDayIds = List(
        title=u"A sequence of day_ids which can be used in the timetable.",
        value_type=TextLine(title=u"Day id"))

    dayTemplates = Dict(
        title=u"Schoolday templates",
        key_type=Int(title=u"Weekday", required=False),
        value_type=Object(title=u"Schoolday template",
                          schema=ISchooldayTemplate),
        description=u"""
        Schoolday templates.

        The template with the key of None is used if there is no template
        for a particular weekday.
        """)

    exceptionDays = Dict(
        title=u"Exception schoolday templates",
        key_type=Date(title=u"Date"),
        value_type=Object(title=u"Schoolday template",
                          schema=ISchooldayTemplate),
        description=u"""
        Schoolday templates for special days.

        Schoolday templates provided in this attribute override the
        templates in the dayTemplates attribute.
        """)

    exceptionDayIds = Dict(
        title=u"Day ids for special dates",
        key_type=Date(title=u"Date"),
        value_type=Object(title=u"Schoolday template",
                          schema=ISchooldayTemplate),
        description=u"""
        Day ids for special dates

        This allows to indicate, that a certain timetable day id
        should be used for a particular date, for example when the day
        is a replacement for some other day.
        """)

    def createCalendar(term, timetable):
        """Return an ICalendar composed out of term and timetable.

        This method has model-specific knowledge as to how the schooldays,
        weekends and holidays map affects the mapping of the timetable
        onto the real-world calendar.
        """

    def periodsInDay(term, timetable, date):
        """Return a sequence of periods defined in this day"""


class ITimetableModelFactory(Interface):
    """A factory of a timetable model"""

    def __call__(day_ids, day_templates):
        """Return a timetable model.

        `day_ids` is a sequence of day ids.

        `day_templates` is a dict with weekday numbers as keys and
        ITimetableDay objects as values.
        """


class ITimetableActivity(Interface):
    """An event in a timetable.

    Something that happens on a certain period_id in a certain day_id.

    Timetable activities are immutable and can be hashed or compared for
    equality.
    """

    title = TextLine(
        title=u"The title of the activity.")

    owner = Field(
        title=u"The group or person or other object that owns the activity.",
        description=u"""
        The activity lives in the owner's timetable.
        """)

    resources = Set(
        title=u"A set of resources assigned to this activity.",
        value_type=Field(title=u"A resource"),
        description=u"""
        The activity is also present in the timetables of all resources
        assigned to this activity.
        """)

    timetable = Field(
        title=u"The timetable that contains this activity.",
        description=u"""
        This attribute refers to the timetable of `owner`.  It never refers
        to a composite timetable or a timetable of a resource.
        """)

    def replace(title=Unchanged, owner=Unchanged, resources=Unchanged,
                timetable=Unchanged):
        """Return a copy of this activity with some fields changed."""

    def __eq__(other):
        """Is this timetable activity equal to `other`?

        Timetable activities are equal iff their title, owner and resources
        attributes are equal.

        Returns false if other is not a timetable activity.
        """

    def __ne__(other):
        """Is this timetable activity different from `other`?

        The opposite of __eq__.
        """

    def __hash__():
        """Calculate the hash value of a timetable activity."""


class ITimetableException(Interface):
    """An exception in a timetable.

    An exception specifies that on a particular day a particular activity
    either does not occur, or occurs but at a different time, or is replaced
    by a different activity.
    """

    date = Date(
        title=u"Date of the exception")

    period_id = TextLine(
        title=u"ID of the period that is exceptional.")

    activity = Object(
        title=u"The activity that does not occur.",
        schema=ITimetableActivity)

    replacement = Field(
        title=u"A replacement calendar event",
        # schema=IExceptionalTTCalendarEvent,
        required=False,
        description=u"""
        A calendar event that should replace the exceptional activity.
        If None, then the activity is simply removed.
        """)

    def __eq__(other):
        """See if self == other."""

    def __ne__(other):
        """See if self != other."""


class ITimetableSchema(IContained):
    """A timetable schema.

    A timetable schema is an ordered collection of timetable days that contain
    periods.
    """

    title = TextLine(
        title=u"The title of the timetable schema.")

    model = Object(
        title=u"A timetable model this timetable should be used with.",
        schema=ITimetableModel)

    def keys():
        """Return a sequence of identifiers for days within the timetable.

        The order of day IDs is fixed.
        """

    def items():
        """Return a sequence of tuples of (day_id, ITimetableSchemaDay).

        The order of day IDs is fixed and is the same as returned by keys().
        """

    def __getitem__(key):
        """Return a ITimetableSchemaDay for a given day id."""

    def createTimetable():
        """Return a new empty timetable with the same structure.

        The new timetable has the same set of day_ids, and the sets of
        period ids within each day.  It has no activities.
        """


class ITimetableSchemaWrite(Interface):
    """Interface for initializing timetable schemas."""

    def __setitem__(key, value):
        """Set an ITimetableSchemaDay for a given day id.

        Throws a TypeError if the value does not implement ITimetableSchemaDay.
        Throws a ValueError if the key is not a valid day id.
        """


class ITimetableSchemaDay(Interface):
    """A day in a timetable schema.

    A timetable day is an ordered collection of periods.

    Different days within the same timetable schema may have different periods.

    ITimetableSchemaDay has keys, items and __getitem__ for interface
    compatibility with ITimetableDay -- so that, for example, views for
    ITimetable can be used to render ITimetableSchemas.
    """

    periods = List(
        title=u"A list of period IDs for this day.",
        value_type=TextLine(title=u"A period id"))

    def keys():
        """Return self.periods."""

    def items():
        """Return a sequence of (period_id, empty_set)."""

    def __getitem__(key):
        """Return an empty set, if key is in periods, otherwise raise KeyError.
        """


class ITimetable(ILocation):
    """A timetable.

    A timetable is an ordered collection of timetable days that contain
    periods. Each period either contains a class, or is empty.

    A timetable represents the repeating lesson schedule for just one
    pupil, or one teacher, or one bookable resource.
    """

    model = Object(
        title=u"A timetable model this timetable should be used with.",
        schema=ITimetableModel)

    def keys():
        """Return a sequence of identifiers for days within the timetable.

        The order of day IDs is fixed.
        """

    def items():
        """Return a sequence of tuples of (day_id, ITimetableDay).

        The order of day IDs is fixed and is the same as returned by keys().
        """

    def __getitem__(key):
        """Return a ITimetableDay for a given day id."""

    def itercontent():
        """Iterate over all activites in this timetable.

        Return an iterator for tuples (day_id, period_id, activity).
        """

    def cloneEmpty():
        """Return a new empty timetable with the same structure.

        The new timetable has the same set of day_ids, and the sets of
        period ids within each day.  It has no activities.
        """

    def __eq__(other):
        """Is this timetable equal to other?

        Timetables are equal iff they have the same model,
        set of day IDs, and their corresponding days are equal.

        Returns False if other is not a timetable.
        """

    def __ne__(other):
        """Is this timetable different from other?

        The opposite of __eq__.
        """


class ITimetableWrite(Interface):
    """Write access to timetables."""

    def __setitem__(key, value):
        """Set an ITimetableDay for a given day id.

        Throws a TypeError if the value does not implement ITimetableDay.
        Throws a ValueError if the key is not a valid day id.
        """

    def clear(send_events=True):
        """Remove all activities for all periods.

        If send_events is True, sends ITimetableActivityRemovedEvents for
        all removed activities.
        """

    def update(timetable):
        """Add all the events from timetable to self.

        Useful for producing combined timetables.

        Does not send any events.
        """


class ITimetableDay(Interface):
    """A day in a timetable.

    A timetable day is an ordered collection of periods that each have
    a set of activites that occur during that period.

    Different days within the same timetable may have different periods.
    """

    timetable = Object(
        title=u"The timetable that contains this day.",
        schema=ITimetable)

    day_id = TextLine(
        title=u"The day id of this timetable day.")

    periods = List(
        title=u"A list of period IDs for this day.",
        value_type=TextLine(title=u"A period id"))

    def keys():
        """Return self.periods."""

    def items():
        """Return a sequence of (period_id, set_of_ITimetableActivity)."""

    def __getitem__(key):
        """Return the set of ITimetableActivities for a given period.

        If there is no activity for the period, an empty set is returned.
        """

    def __eq__(other):
        """Return True iff other is a TimetableDay with the same set of
        periods and with the same activities scheduled for those periods.
        """

    def __ne__(other):
        """Return True iff __eq__ returns False."""


class ITimetableDayWrite(Interface):
    """Writable timetable day.

    Note that all clients which use ITimetableDayWrite or ITimetableWrite
    to modify timetables should maintain the following invariant:
     - every TimetableActivity is present in the timetable of its owner
       and all the timetables of its resources.
    """

    def clear(period):
        """Remove all the activities for a certain period id.

        If send_events is True, sends an ITimetableActivityRemovedEvent
        for each removed activity.
        """

    def add(period, activity, send_event=True):
        """Add a single activity to the set of activities planned for
        a given period.

        If send_events is True, sends an ITimetableActivityAddedEvent.
        """

    def remove(period, value):
        """Remove a certain activity from a set of activities planned
        for a given period.

        Raises KeyError if there is no matching activity.

        If send_events is True, sends an ITimetableActivityRemovedEvent.
        """


class ITimetableActivityEvent(Interface):
    """Event that gets sent when an activity is added to a timetable day."""

    activity = Object(
        title=u"The timetable activity.",
        schema=ITimetableActivity)

    day_id = TextLine(
        title=u"The day_id of the containing timetable day.")

    period_id = TextLine(
        title=u"The period_id of the containing period.")


class ITimetableActivityAddedEvent(ITimetableActivityEvent):
    """Event that gets sent when an activity is added to a timetable."""


class ITimetableActivityRemovedEvent(ITimetableActivityEvent):
    """Event that gets sent when an activity is removed from a timetable."""


class ITimetableCalendarEvent(ICalendarEvent):
    """A calendar event that has been created from a timetable."""

    period_id = TextLine(
        title=u"The period id of the corresponding timetable event.")

    activity = Object(
        title=u"The activity from which this event was created.",
        schema=ITimetableActivity)


class ITimetableDict(IContainer):
    """Container for timetables.

    The id of the timetable is composed by joining term id and
    timetable schema id with a dot.  For example,"2005-fall.default"
    means a timetable for a term "2005-fall" with a timetable schema
    "default".
    """


class ITimetabled(Interface):
    """An object that has a timetable related to it -- either its own,
    or composed of the timetables of related objects.
    """

    timetables = Object(
        schema=ITimetableDict,
        title=u"Private timetables of this object",
        description=u"""

        These timetables can be directly manipulated.  Adding, changing
        or removing a timetable will result in a ITimetableReplacedEvent
        being sent.

        For a lot of objects this mapping will be empty.  Instead, they
        will inherit timetable events through composition (see
        getCompositeTimetable).
        """)

    def getCompositeTimetable(term_id, tt_schema_id):
        """Return a composite timetable for a given object with a
        given timetable schema for a given time period id.

        The timetable returned includes the events from the timetables
        of parent groups, groups taught, etc.

        This function can return None if the object has no timetable.
        """

    def listCompositeTimetables():
        """Return a sequence of (time_period_id, tt_schema_id) for all
        available composite timetables.
        """

    def makeTimetableCalendar():
        """Generate and return a calendar from all composite timetables."""


class ITimetableSource(Interface):
    """Timetable source.

    A subscription adapter that contributes a timetable to the
    composite timetable of the context.
    """

    def getTimetable(term_id, schema_id):
        """Return a timetable to be merged to the composite timetable
        of the context.

        Can return None if this adapter can not contribute to the
        timetable of this object.
        """

    def listTimetables():
        """Return a sequence of timetable keys for which getTimetable
        would return not a None.
        """


class ITimetableReplacedEvent(Interface):
    """Event that gets sent when a timetable is replaced."""

    object = Object(
        title=u"The owner of the timetable.",
        schema=ITimetabled)

    key = Tuple(
        title=u"Tuple (time_period_id, schema_id).",
        value_type=TextLine(),
        min_length=2,
        max_length=2)

    old_timetable = Object(
        title=u"The old timetable (can be None).",
        schema=ITimetable,
        required=False)

    new_timetable = Object(
        title=u"The new timetable (can be None).",
        schema=ITimetable,
        required=False)


class ITimetableModelRegistry(Interface):
    """A registry of timetable model classes present in the system.

    The timetable model classes are identified by the dotted class names.

    Timetable model classes are acquired as named utilities
    implementing ITimetableModelFactory.
    """

    def registerTimetableModel(id, factory):
        """Register a timetable schema identified by a given id."""


class ITimetableSchemaContainer(IContainer, ILocation):
    """Service for creating timetables of a certain schema.

    This service stores timetable prototypes (empty timetables) and
    can return a new timetable of a certain schema on request.
    """

    contains(ITimetableSchema)

    default_id = TextLine(
        title=u"Schema id of the default schema")

    def getDefault():
        """Return the default schema for the school"""


class ITermContainer(IContainer, ILocation):
    """A container for terms.

    It stores term calendars for registered term IDs.
    """

    contains(ITerm)


#
#  SchoolTool domain model objects
#


class IPerson(sb.IPerson, ITimetabled):
    """SchoolTool person object"""


class IGroup(sb.IGroup, ITimetabled):
    """SchoolTool group object"""


class IResource(sb.IResource, ITimetabled):
    """SchoolTool resource object"""


class ICourse(Interface):
    """Courses are similar to groups, membership is restricted to Sections."""

    title = TextLine(
        title=_("Title"),
        description=_("Title of the course."))

    description = Text(
        title=_("Description"),
        required=False,
        description=_("Description of the course."))

    sections = Attribute("""The Sections that implement this course material,
            see schoolbell.relationship.interfaces.IRelationshipProperty.""")


class ICourseContainer(IContainer, sb.IAdaptableToSchoolBellApplication):
    """Container of Courses."""

    contains(ICourse)


class ICourseContained(ICourse, IContained,
                       sb.IAdaptableToSchoolBellApplication):
    """Courses contained in an ICourseContainer."""

    containers(ICourseContainer)


class ISection(IGroup):
    """Sections are groups of users in a particular meeting of a Course."""

    label = TextLine(
        title=_("Label"),
        required=False,
        description=_(
            """An identifier for a section, made up of instructor
            names, courses, and meeting time."""))

    title = TextLine(
        title=_("Code"),
        required=True,
        description=_("ID code for the section."))

    description = Text(
        title=_("Description"),
        required=False,
        description=_("Description of the section."))

    instructors = Attribute(
               """A list of Person objects in the role of instructor""")

    members = Attribute("""Students listed in the role of member""")

    courses = Attribute("""A list of courses this section is a member of.""")

    size = Attribute("""The number of member students in the section.""")

    location = Choice(title=u"Location",
                      required=False,
                      description=u"The resource where this section meets.",
                      vocabulary="LocationResources")


class ISectionContainer(IContainer):
    """A container for Sections."""

    contains(ISection)


class ISectionContained(ISection, IContained,
                       sb.IAdaptableToSchoolBellApplication):
    """Sections in a SectionContainer."""

    containers(ISectionContainer)


class IPersonContainer(sb.IPersonContainer):
    """SchoolTool's person container"""

    contains(IPerson)


class IGroupContainer(sb.IGroupContainer):
    """SchoolTool's group container contains Groups and subclasses."""

    contains(IGroup, ICourse, ISection)


class IResourceContainer(sb.IResourceContainer):
    """SchoolTool's resource container"""

    contains(IResource)


#
#  Miscellaneous
#


class IPersonPreferences(sb.IPersonPreferences):

    cal_periods = Bool(
        title=_("Show periods"),
        description=_("Show period names in daily view"))


class ICalendarAndTTOverlayInfo(ICalendarOverlayInfo):

    show_timetables = Bool(
            title=u"Show timetables",
            description=u"""
            An option that controls whether the timetable of this calendar's
            owner is shown in the calendar views.
            """)


#
#  Main application
#

class ISchoolToolApplication(sb.ISchoolBellApplication):
    """The main SchoolTool application object

    The application is a read-only container with the following items:

        'persons' - IPersonContainer
        'groups' - IGroupContainer
        'resources' - IResourceContainer
        'terms' - ITermContainer
        'ttschemas' - ITimetableSchemaContainer
    """

