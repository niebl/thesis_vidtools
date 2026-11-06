import json
import inspect

class Serializable:
    def __init__(self, workdir=None, parent=None):
        self.workdir = workdir
        self.parent = parent

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

    def to_dict(self):
        raise NotImplementedError(f"{type(self).__name__} must implement to_dict")

    def to_string(self):
        return json.dumps(self.to_dict())

    def __str__(self):
        return self.to_string()


class SerializableCollection(Serializable):
    items_attribute = "collection"

    def __init__(self, workdir=None, parent=None, collection = None, items_attribute=items_attribute):
        super().__init__(workdir=workdir, parent=parent)
        if items_attribute is None:
            items_attribute = self.items_attribute
        setattr(self, items_attribute, collection)

    def __iter__(self):
        return iter(getattr(self, self.items_attribute))

    def __len__(self):
        return len(getattr(self, self.items_attribute))
    
    def __getitem__(self, item):
         return getattr(self, self.items_attribute)[item]
    
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