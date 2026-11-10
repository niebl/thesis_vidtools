import json
import inspect
import nanoid
from pathlib import Path

class OID:
    def __init__(self, oid:String=None):
        if (not oid) or (oid == "None") or (len(oid) != 10):
            oid = nanoid.generate(size=10)
        self.oid = oid    
    
    def __str__(self):
        return self.oid

class Serializable:
    def __init__(self, workdir=None, parent=None, oid:str=None, verbose:bool=False):
        self.workdir = workdir
        self.parent = parent
        self.oid = OID(oid)
        self.verbose = verbose

    @classmethod
    def from_dict(cls, data):
        return cls._from_dict(data)

    @classmethod
    def _from_dict(cls, data):
        #filter so not too many args are passed
        args = cls.filter_kwargs(cls, data)
        #TODO: some way to handle references to parents?
        return cls(**args)

    @classmethod
    def from_string(cls, in_str):
        return cls.from_dict(json.loads(in_str))

    @staticmethod
    def filter_kwargs(func, data):
        sig = inspect.signature(func)
        params = sig.parameters
        # if **kwargs accepted, pass all
        if any(
            p.kind == inspect.Parameter.VAR_KEYWORD
            for p in params.values()
        ):
            return data
        # keep only keys that are valid keyword parameters
        return {
            key: value
            for key, value in data.items()
            if key in params
            and params[key].kind in (
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                inspect.Parameter.KEYWORD_ONLY,
            )
        }
    
    def log(self, *args):
        if self.is_verbose: print(*args)

    def is_verbose(self):
        if not hasattr(self, "verbose"):
            return False
        return self.verbose or self.parent.is_verbose()

    def find_item(self, lambda_f, attr):
        for item in getattr(self, attr):
            if lambda_f(item):
                return item
        return None
    
    def to_dict(self):
        return self._to_dict()

    def _to_dict(self, exclude_keys=["parent", "verbose"]):
        data = self.__dict__
        out_data = {}
        for key in exclude_keys:
            data.pop(key, None)
        for key in data:
            if isinstance(data[key], Serializable):
                out_data[key] = data[key].to_dict()
            elif isinstance(data[key], OID):
                out_data[key] = str(data[key])
            elif isinstance(data[key], list):
                out_data[key] = data[key]
                for i, entry in enumerate(data[key]):
                    if isinstance(entry, Serializable):
                        out_data[key][i] = data[key][i].to_dict()
            elif isinstance(data[key], Path):
                out_data[key] = str(data[key])
            else:
                out_data[key] = data[key]
        return out_data

    def to_string(self):
        return json.dumps(self.to_dict())

    def __str__(self):
        return self.to_string()


class SerializableCollection(Serializable):
    items_attribute = "collection"

    def __init__(self, 
            workdir=None, 
            parent=None, 
            collection = None, 
            items_attribute=items_attribute, 
            oid:str=None,
            verbose:bool=False
            ):
        super().__init__(workdir=workdir, parent=parent, oid=oid, verbose=verbose)
        if items_attribute is None:
            items_attribute = self.items_attribute
        setattr(self, items_attribute, collection)

    def __iter__(self):
        return iter(getattr(self, self.items_attribute))

    def __len__(self):
        return len(getattr(self, self.items_attribute))
    
    def __getitem__(self, item):
         return getattr(self, self.items_attribute)[item]
    
    def find_item(self, lambda_f, attr=None):
        collection = attr or self.items_attribute
        return super().find_item(lambda_f, collection)

    def append(self, item):
        getattr(self, self.items_attribute).append(item)

    def remove(self, item):
        getattr(self, self.items_attribute).remove(item)

    def pop(self, index=-1):
        return getattr(self, self.items_attribute).pop(index)

    def index(self, item, start=0, stop=None):
        items = getattr(self, self.items_attribute)
        if stop is None:
            return items.index(item, start)
        return items.index(item, start, stop)

    def map(self, lambda_f):
        items = getattr(self, self.items_attribute)
        setattr(self, self.items_attribute, list(map(lambda_f, items)))