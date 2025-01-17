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
This module is obsolete.  It is here for evolution script evolve1.py that
actually removes these objects.
"""
from persistent import Persistent

from zope.container.btree import BTreeContainer


class LyceumTermDataContainer(BTreeContainer):
    """Container for person term grading data."""


class TermGradingData(Persistent):
    __parent__ = None
    __name__ = None
    __data__ = None

