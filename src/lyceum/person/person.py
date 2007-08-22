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
Lyceum person specific code.

$Id$

"""
from zope.interface import implements
from zope.app.catalog.interfaces import ICatalog
from zope.app.catalog.catalog import Catalog
from zope.component import getUtility

from zc.catalog.catalogindex import ValueIndex

from schooltool.basicperson.person import BasicPerson
from schooltool.basicperson.person import PersonFactoryUtility as BasicPersonFactoryUtility
from schooltool.utility.utility import UtilitySetUp

from lyceum.person.interfaces import ILyceumPerson


PERSON_CATALOG_KEY = 'lyceum.person'


class LyceumPerson(BasicPerson):
    implements(ILyceumPerson)


class PersonFactoryUtility(BasicPersonFactoryUtility):

    def __call__(self, *args, **kw):
        result = LyceumPerson(*args, **kw)
        return result

    def createManagerUser(self, username, system_name):
        return self(username, system_name, "Administratorius")


def catalogSetUp(catalog):
    catalog['__name__'] = ValueIndex('__name__', ILyceumPerson)
    catalog['title'] = ValueIndex('title', ILyceumPerson)
    catalog['first_name'] = ValueIndex('first_name', ILyceumPerson)
    catalog['last_name'] = ValueIndex('last_name', ILyceumPerson)


catalogSetUpSubscriber = UtilitySetUp(
    Catalog, ICatalog, PERSON_CATALOG_KEY, setUp=catalogSetUp)


def getPersonContainerCatalog(container):
    return getUtility(ICatalog, PERSON_CATALOG_KEY)
