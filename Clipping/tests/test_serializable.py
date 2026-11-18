import pytest

import json
from ..Serializable import Serializable, SerializableCollection

# TEST FIXTURE HERE

class TestSerializable:
    ### HELPERS:

    ### TESTS:
    def from_dict(self):
        #short deserialization test

    def to_dict(self):
        #short serialization test

    def from_dict_with_relations(self):
        #short deserialization test, using OIDs to rebuild Object links between another
        #not yet implemented

    def find_by_oid(self):
        #test the method for finding an Object with a given OID within the relation tree
        #not yet implemented