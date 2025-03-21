# common/common_models.py
class SharedModel:
    def __init__(self, value):
        self.value = value

    def get_value(self):
        return self.value