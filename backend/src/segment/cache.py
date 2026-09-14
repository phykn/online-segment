from collections import OrderedDict


class Cache:
    def __init__(self, mb):
        self.limit = mb * 1024**2
        self.values = OrderedDict()
        self.size = 0
    def get(self, key):
        value = self.values.get(key)
        if value is not None:
            self.values.move_to_end(key)
        return value

    def put(self, key, value):
        previous = self.values.pop(key, None)
        if previous is not None:
            self.size -= previous.nbytes
        if value.nbytes <= self.limit:
            while self.values and self.size + value.nbytes > self.limit:
                self.size -= self.values.popitem(last=False)[1].nbytes
            self.values[key] = value
            self.size += value.nbytes
        return value

    def clear(self):
        self.values.clear()
        self.size = 0
