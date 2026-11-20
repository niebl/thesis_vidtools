import pytest

import json
from pathlib import Path
from ..Serializable import Serializable, SerializableCollection, OID

class SerializableFixture(Serializable):
    def __init__(self, workdir=None, parent=None, oid=None, verbose=False, peer=None, child=None):
        super().__init__(workdir=workdir, parent=parent, oid=oid, verbose=verbose)
        self.peer = peer
        self.child = child
    
    @classmethod
    def from_dict(cls, data):
        data["peer"] = OID(data["peer"])
        #TODO if needed: child (type should be known)
        return cls._from_dict(data)

class ObjectCollection(SerializableCollection):
    items_attribute = "children"
    def __init__(self, workdir=None, parent=None, children=None, oid=None, verbose=False):
        super().__init__(workdir=workdir, parent=parent, collection=children, oid=oid, verbose=verbose)
        self.children = children or []
        self.selected = self.children[0] if self.children else None

    @classmethod
    def from_dict(cls, data):
        children = []
        for item in data["children"]:
            if "children" in item:
                children.append(ObjectCollection.from_dict(item))
            else:
                children.append(SerializableFixture.from_dict(item))
        data["children"] = children
        obj = cls._from_dict(data)
        obj.build_rel_from_oids()
        return obj

@pytest.fixture
def serializable_data():
    return {
        "workdir": "/tmp/clips",
        "oid": "sample0001",
    }

@pytest.fixture
def relation_data():
    return {
        "children": [
            {
                "oid": "child-0001",
                "peer": "child-0002"
            },
            {
                "oid": "child-0002",
                "peer": "child-0001"
            }
        ]
    }

@pytest.fixture
def tree_data():
    return {
        "children": [
            {
                "children": [
                    {
                        "oid": "child-0003",
                        "peer": "child-0002"
                    },
                    {
                        "oid": "child-0001",
                        "peer": "child-0003"
                    }
                ]
            },
            {
                "oid": "child-0002",
                "peer": "child-0001"
            }
        ]
    }


class TestSerializable:
    ### HELPERS:

    ### TESTS:
    def test_from_dict(self, serializable_data):
        instance = Serializable.from_dict(serializable_data)

        assert isinstance(instance, Serializable)
        assert instance.workdir == serializable_data["workdir"]
        assert str(instance.oid) == serializable_data["oid"]

    def test_to_dict(self):
        instance = SerializableFixture(
            workdir=Path("/tmp/clips"),
            oid="sample0001",
            verbose=True,
        )

        assert instance.to_dict() == {
            "workdir": "/tmp/clips",
            "oid": "sample0001",
            "child": None,
            "peer": None,
        }

    def test_collect_objects(self, tree_data):
        root = ObjectCollection.from_dict(tree_data)
        ch2 = root[1]
        ch1 = root[0][1]
        ch3 = root[0][0]

        objects = root.collect_objects()
        assert objects[str(ch1.oid)] == ch1
        assert objects[str(ch2.oid)] == ch2

        #TODO
        #objects = ch1.collect_objects()
        #assert objects[str(ch1.oid)] == ch1
        #assert objects[str(ch2.oid)] == ch2

    def test_from_dict_with_relations(self, relation_data):
        root = ObjectCollection.from_dict(relation_data)

        assert isinstance(root.children[0], SerializableFixture)
        assert root.children[0].peer is root.children[1]
        assert root.children[1].peer is root.children[0]
        #TODO
        #assert root.children[0].parent is root
        #assert root.children[1].parent is root

    @pytest.mark.skip(reason="not yet implemented")
    def test_find_by_oid(self, tree_data):
        root = ObjectCollection.from_dict(tree_data)

        ch1 = root[0][1] #child1, looks for child3
        ch2 = root[1] #child2, looks for child1
        ch3 = root[0][0] #child3, looks for child2

        #simulate search
        assert ch2.find_by_oid("child0001") is ch1

        #construction should have correctly assigned peers using oids
        #assert ch1.peer is ch3
        #assert ch2.peer is ch1
        #assert ch3.peer is ch2

        
        