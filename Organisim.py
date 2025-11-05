class Organism:
    """Basic value object representing an organism on the habitat grid."""

    def __init__(self, i, n, r, c, size, ip=None, fecundity=1.0):
        self.id = i
        self.name = n
        self.row = r
        self.col = c
        self.imagePath = ip
        self.fecundity = fecundity #amt of offspring a species should have: apex predator is like 1-3, bug is like hundreds.
        self.size = size
        self.genes = [] #deap gene values

    def toDict(self):
        data = {"id": self.id, "name": self.name, "row": self.row, "col": self.col}
        if self.imagePath is not None:
            data["imagePath"] = self.imagePath
        if self.fecundity is not None:
            data["fecundity"] = self.fecundity
        return data

    def getId(self):
        return self.id

    def getName(self):
        return self.name

    def getPos(self):
        return (self.row, self.col)

    def getIP(self):
        return self.imagePath

    def getFecundity(self):
        return self.fecundity
    
    def getSize(self):
        return len(self.genes)
    
    def setSize(self, num):
        self.size = num

    def getGenes(self):
        return self.genes
    
    def setGenes(self, list):
        self.genes = list

    def setFecundity(self, fecundity):
        self.fecundity = fecundity

    def setPos(self, pos):
        self.row = pos[0]
        self.col = pos[1]
