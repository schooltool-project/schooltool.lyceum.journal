##############################################################################
#
# Copyright (c) 2001 Zope Corporation and Contributors.
# All Rights Reserved.
#
# This software is subject to the provisions of the Zope Public License,
# Version 2.0 (ZPL).  A copy of the ZPL should accompany this distribution.
# THIS SOFTWARE IS PROVIDED "AS IS" AND ANY AND ALL EXPRESS OR IMPLIED
# WARRANTIES ARE DISCLAIMED, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF TITLE, MERCHANTABILITY, AGAINST INFRINGEMENT, AND FITNESS
# FOR A PARTICULAR PURPOSE.
#
##############################################################################

"""More recovery and iterator tests.
"""

import time

from transaction import get_transaction

from zodb.db import DB
from zodb.ztransaction import Transaction
from zodb.storage.tests.iterator import IteratorDeepCompare
from zodb.storage.tests.base import MinPO, zodb_unpickle, snooze
from zodb.serialize import findrefs


class RecoveryStorage(IteratorDeepCompare):
    # Requires a setUp() that creates a self._dst destination storage
    def testSimpleRecovery(self):
        oid = self._storage.newObjectId()
        revid = self._dostore(oid, data=11)
        revid = self._dostore(oid, revid=revid, data=12)
        revid = self._dostore(oid, revid=revid, data=13)
        self._dst.copyTransactionsFrom(self._storage)
        self.compare(self._storage, self._dst)

    def testRecoveryAcrossVersions(self):
        oid = self._storage.newObjectId()
        revid = self._dostore(oid, data=21)
        revid = self._dostore(oid, revid=revid, data=22)
        revid = self._dostore(oid, revid=revid, data=23, version='one')
        revid = self._dostore(oid, revid=revid, data=34, version='one')
        # Now commit the version
        t = Transaction()
        self._storage.tpcBegin(t)
        self._storage.commitVersion('one', '', t)
        self._storage.tpcVote(t)
        self._storage.tpcFinish(t)
        self._dst.copyTransactionsFrom(self._storage)
        self.compare(self._storage, self._dst)

    def testRecoverAbortVersion(self):
        oid = self._storage.newObjectId()
        revid = self._dostore(oid, data=21, version="one")
        revid = self._dostore(oid, revid=revid, data=23, version='one')
        revid = self._dostore(oid, revid=revid, data=34, version='one')
        # Now abort the version and the creation
        t = Transaction()
        self._storage.tpcBegin(t)
        oids = self._storage.abortVersion('one', t)
        self._storage.tpcVote(t)
        self._storage.tpcFinish(t)
        self.assertEqual(oids, [oid])
        self._dst.copyTransactionsFrom(self._storage)
        self.compare(self._storage, self._dst)
        # Also make sure the the last transaction has a data record
        # with None for its data attribute, because we've undone the
        # object.
        for s in self._storage, self._dst:
            siter = s.iterator()
            for trans in siter:
                pass # iterate until we get the last one
            txniter = iter(trans)
            data = txniter.next()
            self.assertRaises(StopIteration, txniter.next)
            self.assertEqual(data.oid, oid)
            self.assertEqual(data.data, None)
            siter.close()

    def testRecoverUndoInVersion(self):

        def checkObj(oid, version, v_data, nv_data):
            # Cause test to fail if object oid has wrong data.
            # Last two args are MinPO value on version and non-version.
            data, revid = self._storage.load(oid, "")
            self.assertEqual(zodb_unpickle(data).value, nv_data)
            data, revid = self._storage.load(oid, version)
            self.assertEqual(zodb_unpickle(data).value, v_data)


        oid = self._storage.newObjectId()
        version = "aVersion"
        revid_a = self._dostore(oid, data=MinPO(91))
        revid_b = self._dostore(oid, revid=revid_a, version=version,
                                data=MinPO(92))
        revid_c = self._dostore(oid, revid=revid_b, version=version,
                                data=MinPO(93))
        self._undo(self._storage.undoInfo()[0]['id'], oid)
        self._commitVersion(version, '')
        self._undo(self._storage.undoInfo()[0]['id'], oid)

        # now copy the records to a new storage
        self._dst.copyTransactionsFrom(self._storage)
        self.compare(self._storage, self._dst)

        # The last two transactions were applied directly rather than
        # copied.  So we can't use compare() to verify that they new
        # transactions are applied correctly.  (The new transactions
        # will have different timestamps for each storage.)

        self._abortVersion(version)
        self.assert_(self._storage.versionEmpty(version))
        self._undo(self._storage.undoInfo()[0]['id'], oid)
        self.assert_(not self._storage.versionEmpty(version))

        checkObj(oid, version, 92, 91)

        # and swap the storages
        tmp = self._storage
        self._storage = self._dst
        self._abortVersion(version)
        self.assert_(self._storage.versionEmpty(version))
        self._undo(self._storage.undoInfo()[0]['id'], oid)
        self.assert_(not self._storage.versionEmpty(version))

        checkObj(oid, version, 92, 91)

        # swap them back
        self._storage = tmp

        # Now remove _dst and copy all the transactions a second time.
        # This time we will be able to confirm via compare().
        self._dst.close()
        self._dst.cleanup()
        self._dst = self.new_dest()
        self._dst.copyTransactionsFrom(self._storage)
        self.compare(self._storage, self._dst)

    def testRestoreAcrossPack(self):
        eq = self.assertEqual
        db = DB(self._storage)
        c = db.open()
        r = c.root()
        obj = r["obj1"] = MinPO(1)
        get_transaction().commit()
        obj = r["obj2"] = MinPO(1)
        get_transaction().commit()

        self._dst.copyTransactionsFrom(self._storage)
        self._dst.pack(time.time())

        self._undo(self._storage.undoInfo()[0]['id'])

        # copy the final transaction manually.  even though there
        # was a pack, the restore() ought to succeed.
        iter = self._storage.iterator()
        final = list(iter)[-1]
        self._dst.tpcBegin(final, final.tid, final.status)
        datarefs = []
        for r in final:
            datarefs.append((r.data, r.refs))
            self._dst.restore(r.oid, r.serial, r.data, r.refs, r.version,
                              r.data_txn, final)
        self._dst.tpcVote(final)
        self._dst.tpcFinish(final)
        iter.close()
        data, refs = datarefs[0]
        eq(findrefs(data), refs)
        data, refs = datarefs[1]
        eq(data, None)
        eq(refs, None)

    def testPackWithGCOnDestinationAfterRestore(self):
        raises = self.assertRaises
        db = DB(self._storage)
        conn = db.open()
        root = conn.root()
        root.obj = obj1 = MinPO(1)
        txn = get_transaction()
        txn.note('root -> obj')
        txn.commit()
        root.obj.obj = obj2 = MinPO(2)
        txn = get_transaction()
        txn.note('root -> obj -> obj')
        txn.commit()
        del root.obj
        txn = get_transaction()
        txn.note('root -X->')
        txn.commit()
        # Now copy the transactions to the destination
        self._dst.copyTransactionsFrom(self._storage)
        # Now pack the destination.
        snooze()
        self._dst.pack(time.time())
        # And check to see that the root object exists, but not the other
        # objects.
        data, serial = self._dst.load(root._p_oid, '')
        raises(KeyError, self._dst.load, obj1._p_oid, '')
        raises(KeyError, self._dst.load, obj2._p_oid, '')
