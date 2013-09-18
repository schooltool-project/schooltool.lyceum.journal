#
from zope.i18nmessageid import MessageFactory
LyceumMessage = MessageFactory("schooltool.lyceum.journal")

import schooltool.common

schooltool.common.register_lauchpad_project(__package__, 'schooltool.lyceum.journal')
