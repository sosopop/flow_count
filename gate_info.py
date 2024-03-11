class GateInfo:
    def __init__(self, config):
        self.name = config["name"]
        self.tags = config["tags"]
        self.lines = config["lines"]
        self.in_count = 0
        self.out_count = 0
        self.cross_render = 0