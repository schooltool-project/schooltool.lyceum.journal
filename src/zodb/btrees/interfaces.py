##############################################################################
#
# Copyright (c) 2001, 2002 Zope Corporation and Contributors.
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
from zodb.interfaces import ConflictError
from zope.interface import Interface

class BTreesConflictError(ConflictError):

    msgs = [# 0; i2 or i3 bucket split; positions are all -1
            'Conflicting bucket split',

            # 1; keys the same, but i2 and i3 values differ, and both values
            # differ from i1's value
            'Conflicting changes',

            # 2; i1's value changed in i2, but key+value deleted in i3
            'Conflicting delete and change',

            # 3; i1's value changed in i3, but key+value deleted in i2
            'Conflicting delete and change',

            # 4; i1 and i2 both added the same key, or both deleted the
            # same key
            'Conflicting inserts or deletes',

            # 5;  i2 and i3 both deleted the same key
            'Conflicting deletes',

            # 6; i2 and i3 both added the same key
            'Conflicting inserts',

            # 7; i2 and i3 both deleted the same key, or i2 changed the value
            # associated with a key and i3 deleted that key
            'Conflicting deletes, or delete and change',

            # 8; i2 and i3 both deleted the same key, or i3 changed the value
            # associated with a key and i2 deleted that key
            'Conflicting deletes, or delete and change',

            # 9; i2 and i3 both deleted the same key
            'Conflicting deletes',

            # 10; i2 and i3 deleted all the keys, and didn't insert any,
            # leaving an empty bucket; conflict resolution doesn't have
            # enough info to unlink an empty bucket from its containing
            # BTree correctly
            'Empty bucket from deleting all keys',

            # 11; conflicting changes in an internal BTree node
            'Conflicting changes in an internal BTree node',
            ]

    def __init__(self, p1, p2, p3, reason):
        self.p1 = p1
        self.p2 = p2
        self.p3 = p3
        self.reason = reason

    def __repr__(self):
        return "BTreesConflictError(%d, %d, %d, %d)" % (self.p1,
                                                        self.p2,
                                                        self.p3,
                                                        self.reason)
    def __str__(self):
        return "BTrees conflict error at %d/%d/%d: %s" % (
            self.p1, self.p2, self.p3, self.msgs[self.reason])

class ICollection(Interface):

    def clear():
        """Remove all of the items from the collection"""

    def __nonzero__():
        """Check if the collection is non-empty.

        Return a true value if the collection is non-empty and a
        false otherwise.
        """

class IReadSequence(Interface):

    def __getslice__(index1, index2):
        """Return a subsequence from the original sequence

        Such that the subsequence includes the items from index1 up
        to, but not including, index2.
        """

class IKeyed(ICollection):

    def has_key(key):
        """Check whether the object has an item with the given key"""

    def keys(min=None, max=None, excludemin=False, excludemax=False):
        """Return an IReadSequence containing the keys in the collection.

        The type of the IReadSequence is not specified. It could be a list
        or a tuple or some other type.

        All arguments are optional, and may be specified as keyword
        arguments, or by position.

        If a min is specified, then output is constrained to keys greater
        than or equal to the given min, and, if excludemin is specified and
        true, is further constrained to keys strictly greater than min.  A
        min value of None is ignored.  If min is None or not specified, and
        excludemin is true, the smallest key is excluded.

        If a max is specified, then output is constrained to keys less than
        or equal to the given max, and, if excludemax is specified and
        true, is further constrained to keys strictly less than max.  A max
        value of None is ignored.  If max is None or not specified, and
        excludemax is true, the largest key is excluded. """

    def maxKey(key=None):
        """Return the maximum key

        If a key argument if provided, return the largest key that is
        less than or equal to the argument.
        """

    def minKey(key=None):
        """Return the minimum key

        If a key argument if provided, return the smallest key that is
        greater than or equal to the argument.
        """

class ISetMutable(IKeyed):

    def insert(key):
        """Add the key (value) to the set.

        If the key was already in the set, return 0, otherwise return 1.
        """

    def remove(key):
        """Remove the key from the set."""

    def update(seq):
        """Add the items from the given sequence to the set"""

class IKeySequence(IKeyed):

    def __getitem__(index):
        """Return the key in the given index position

        This allows iteration with for loops and use in functions,
        like map and list, that read sequences.
        """

class ISet(IKeySequence, ISetMutable):
    pass

class ITreeSet(IKeyed, ISetMutable):
    pass


class IDictionaryIsh(IKeyed):

    def update(collection):
        """Add the items from the given collection object to the collection

        The input collection must be a sequence of key-value tuples,
        or an object with an 'items' method that returns a sequence of
        key-value tuples.
        """

    def values(min=None, max=None, excludemin=False, excludemax=False):
        """Return an IReadSequence containing the values in the collection.

        The type of the IReadSequence is not specified. It could be a list
        or a tuple or some other type.

        All arguments are optional, and may be specified as keyword
        arguments, or by position.

        If a min is specified, then output is constrained to values whose
        keys are greater than or equal to the given min, and, if excludemin
        is specified and true, is further constrained to values whose keys
        are strictly greater than min.  A min value of None is ignored.  If
        min is None or not specified, and excludemin is true, the value
        corresponding to the smallest key is excluded.

        If a max is specified, then output is constrained to values whose
        keys are less than or equal to the given max, and, if excludemax is
        specified and true, is further constrained to values whose keys are
        strictly less than max.  A max value of None is ignored.  If max is
        None or not specified, and excludemax is true, the value
        corresponding to the largest key is excluded.
        """

    def items(min=None, max=None, excludemin=False, excludemax=False):
        """Return an IReadSequence containing the items in the collection.

        An item is a 2-tuple, a (key, value) pair.

        The type of the IReadSequence is not specified.  It could be a list
        or a tuple or some other type.

        All arguments are optional, and may be specified as keyword
        arguments, or by position.

        If a min is specified, then output is constrained to items whose
        keys are greater than or equal to the given min, and, if excludemin
        is specified and true, is further constrained to items whose keys
        are strictly greater than min.  A min value of None is ignored.  If
        min is None or not specified, and excludemin is true, the item with
        the smallest key is excluded.

        If a max is specified, then output is constrained to items whose
        keys are less than or equal to the given max, and, if excludemax is
        specified and true, is further constrained to items whose keys are
        strictly less than max.  A max value of None is ignored.  If max is
        None or not specified, and excludemax is true, the item with the
        largest key is excluded.
        """

    def byValue(minValue):
        """Return a sequence of value-key pairs, sorted by value

        Values < min are ommitted and other values are "normalized" by
        the minimum value. This normalization may be a noop, but, for
        integer values, the normalization is division.
        """

class IBTree(IDictionaryIsh):

    def insert(key, value):
        """Insert a key and value into the collection.

        If the key was already in the collection, then there is no
        change and 0 is returned.

        If the key was not already in the collection, then the item is
        added and 1 is returned.

        This method is here to allow one to generate random keys and
        to insert and test whether the key was there in one operation.

        A standard idiom for generating new keys will be::

          key=generate_key()
          while not t.insert(key, value):
              key=generate_key()
        """

class IMerge(Interface):
    """Object with methods for merging sets, buckets, and trees.

    These methods are supplied in modules that define collection
    classes with particular key and value types. The operations apply
    only to collections from the same module.  For example, the
    IIBTree.union can only be used with IIBTree.IIBTree,
    IIBTree.IIBucket, IIBTree.IISet, and IIBTree.IITreeSet.

    The implementing module has a value type. The IOBTree and OOBTree
    modules have object value type. The IIBTree and OIBTree modules
    have integer value types. Other modules may be defined in the
    future that have other value types.

    The individual types are classified into set (Set and TreeSet) and
    mapping (Bucket and BTree) types.
    """

    def difference(c1, c2):
        """Return the keys or items in c1 for which there is no key in
        c2.

        If c1 is None, then None is returned.  If c2 is None, then c1
        is returned.

        If neither c1 nor c2 is None, the output is a Set if c1 is a Set or
        TreeSet, and is a Bucket if c1 is a Bucket or BTree.
        """

    def union(c1, c2):
        """Compute the Union of c1 and c2.

        If c1 is None, then c2 is returned, otherwise, if c2 is None,
        then c1 is returned.

        The output is a Set containing keys from the input
        collections.
        """

    def intersection(c1, c2):
        """Compute the Intersection of c1 and c2.

        If c1 is None, then c2 is returned, otherwise, if c2 is None,
        then c1 is returned.

        The output is a Set containing matching keys from the input
        collections.
        """

class IIMerge(IMerge):
    """Merge collections with integer value type.

    A primary intent is to support operations with no or integer
    values, which are used as "scores" to rate indiviual keys. That
    is, in this context, a BTree or Bucket is viewed as a set with
    scored keys, using integer scores.
    """

    def weightedUnion(c1, c2, weight1=1, weight2=1):
        """Compute the weighted union of c1 and c2.

        If c1 and c2 are None, the output is (0, None).

        If c1 is None and c2 is not None, the output is (weight2, c2).

        If c1 is not None and c2 is None, the output is (weight1, c1).

        Else, and hereafter, c1 is not None and c2 is not None.

        If c1 and c2 are both sets, the output is 1 and the (unweighted)
        union of the sets.

        Else the output is 1 and a Bucket whose keys are the union of c1 and
        c2's keys, and whose values are::

          v1*weight1 + v2*weight2

          where:

            v1 is 0        if the key is not in c1
                  1        if the key is in c1 and c1 is a set
                  c1[key]  if the key is in c1 and c1 is a mapping

            v2 is 0        if the key is not in c2
                  1        if the key is in c2 and c2 is a set
                  c2[key]  if the key is in c2 and c2 is a mapping

        Note that c1 and c2 must be collections.
        """

    def weightedIntersection(c1, c2, weight1=1, weight2=1):
        """Compute the weighted intersection of c1 and c2.

        If c1 and c2 are None, the output is (0, None).

        If c1 is None and c2 is not None, the output is (weight2, c2).

        If c1 is not None and c2 is None, the output is (weight1, c1).

        Else, and hereafter, c1 is not None and c2 is not None.

        If c1 and c2 are both sets, the output is the sum of the weights
        and the (unweighted) intersection of the sets.

        Else the output is 1 and a Bucket whose keys are the intersection of
        c1 and c2's keys, and whose values are::

          v1*weight1 + v2*weight2

          where:

            v1 is 1        if c1 is a set
                  c1[key]  if c1 is a mapping

            v2 is 1        if c2 is a set
                  c2[key]  if c2 is a mapping

        Note that c1 and c2 must be collections.
        """

class IMergeIntegerKey(IMerge):
    """IMerge-able objects with integer keys.

    Concretely, this means the types in IOBTree and IIBTree.
    """

    def multiunion(seq):
        """Return union of (zero or more) integer sets, as an integer set.

        seq is a sequence of objects each convertible to an integer set.
        These objects are convertible to an integer set:

        + An integer, which is added to the union.

        + A Set or TreeSet from the same module (for example, an
          IIBTree.TreeSet for IIBTree.multiunion()).  The elements of the
          set are added to the union.

        + A Bucket or BTree from the same module (for example, an
          IOBTree.IOBTree for IOBTree.multiunion()).  The keys of the
          mapping are added to the union.

        The union is returned as a Set from the same module (for example,
        IIBTree.multiunion() returns an IIBTree.IISet).

        The point to this method is that it can run much faster than
        doing a sequence of two-input union() calls.  Under the covers,
        all the integers in all the inputs are sorted via a single
        linear-time radix sort, then duplicates are removed in a second
        linear-time pass.
        """

###############################################################
# IMPORTANT NOTE
#
# Getting the length of a BTree, TreeSet, or output of keys,
# values, or items of same is expensive. If you need to get the
# length, you need to maintain this separately.
#
# Eventually, I need to express this through the interfaces.
#
################################################################

# XXX These interfaces need to be set in the C code, not in Python code.

# XXX You can't import OOBTree in this module, because it would create
# a circular reference.

# from zope.interface import classImplements
# classImplements(OOBTree.OOSet, ISet)
# classImplements(OOBTree.OOTreeSet, ITreeSet)
# classImplements(OOBTree.OOBucket, IDictionaryIsh)
# classImplements(OOBTree.OOBTree, IBTree)
