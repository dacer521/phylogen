class Organism:
    """Basic value object representing an organism on the habitat grid."""

    def __init__(self, i, n, r, c, ip=None):
        self.id = i
        self.name = n
        self.row = r
        self.col = c
        self.imagePath = ip

    def toDict(self):
        data = {"id": self.id, "name": self.name, "row": self.row, "col": self.col}
        if self.imagePath is not None:
            data["imagePath"] = self.imagePath
        return data

    def getId(self):
        return self.id

    def getName(self):
        return self.name

    def getPos(self):
        return (self.row, self.col)

    def getIP(self):
        return self.imagePath

    def setPos(self, pos):
        self.row = pos[0]
        self.col = pos[1]
