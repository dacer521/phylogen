class Organism:
    """Basic value object representing an organism on the habitat grid."""

    def __init__(
        self,
        i,
        n,
        r,
        c,
        size,
        ip=None,
        fecundity=1.0,
        moves=True,
        ideal_traits=None,
        trait_names=None,
    ):
        self.id = i
        self.name = n
        self.row = r
        self.col = c
        self.imagePath = ip
        self.fecundity = fecundity #amt of offspring a species should have: apex predator is like 1-3, bug is like hundreds.
        self.size = size
        self.genes = [] #deap gene values
        self.moves = moves
        self.ideal_traits = list(ideal_traits) if ideal_traits is not None else []
        self.trait_names = list(trait_names) if trait_names is not None else []
        self._cycle_steps = 0
        self._caught_prey = False
        self._was_caught = False

    def toDict(self):
        data = {"id": self.id, "name": self.name, "row": self.row, "col": self.col}
        if self.imagePath is not None:
            data["imagePath"] = self.imagePath
        if self.fecundity is not None:
            data["fecundity"] = self.fecundity
        if self.ideal_traits:
            data["idealTraits"] = self.ideal_traits
        if self.trait_names:
            data["traitNames"] = self.trait_names
        data["wasCaught"] = self._was_caught
        return data

    def getId(self):
        return self.id

    def getName(self):
        return self.name

    def getPos(self):
        return (self.row, self.col)

    def getY(self):
        return self.row

    def getX(self):
        return self.col

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

    def setY(self, row):
        self.row = row

    def setX(self, col):
        self.col = col

    def canMove(self):
        return self.moves

    def setMoves(self, moves):
        self.moves = moves

    def getCycleSteps(self):
        return self._cycle_steps

    def advanceCycle(self):
        self._cycle_steps += 1
        return self._cycle_steps

    def resetCycle(self):
        self._cycle_steps = 0
        self._caught_prey = False
        self._was_caught = False

    def hasCaughtPrey(self):
        return self._caught_prey

    def setCaughtPrey(self, caught=True):
        self._caught_prey = caught

    def getIdealTraits(self):
        return self.ideal_traits

    def setIdealTraits(self, traits):
        self.ideal_traits = list(traits) if traits is not None else []

    def getTraitNames(self):
        return self.trait_names

    def setTraitNames(self, trait_names):
        self.trait_names = list(trait_names) if trait_names is not None else []

    def wasCaught(self):
        return self._was_caught

    def setWasCaught(self, caught=True):
        self._was_caught = caught

    def setMoves(self, moves):
        self.moves = moves
