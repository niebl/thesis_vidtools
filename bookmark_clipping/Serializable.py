import json
class Serializable:
    @classmethod
    def from_dict(cls, data):
        return cls._from_dict(data)

    @classmethod
    def from_string(cls, in_str):
        return cls.from_dict(json.loads(in_str))

    def to_dict(self):
        raise NotImplementedError(f"{type(self).__name__} must implement to_dict")

    def to_string(self):
        return json.dumps(self.to_dict())

    def __str__(self):
        return self.to_string()
        

class SerializableCollection(Serializable):
    items_attribute = None

    def __iter__(self):
        return iter(getattr(self, self.items_attribute))

    def __len__(self):
        return len(getattr(self, self.items_attribute))
    
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