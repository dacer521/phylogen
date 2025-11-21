document.addEventListener('DOMContentLoaded', () => {
  const startButton = document.getElementById('start-simulation');
  if (!startButton) {
    return;
  }

  let running = false;
  let currentController = null;
  const stepInterval = 800;    //delay stuff to make smoother
  const organismPanels = new Map();
  const levelPanels = new Map();

  const persistState = (cycle, summary, organisms) => {
    if (cycle === undefined || cycle === null) {
      return;
    }

    fetch('/api/simulation/save', { //json stuff to access current info
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        cycle,
        summary: Array.isArray(summary) ? summary : [],
        organisms: Array.isArray(organisms) ? organisms : [],
      }),
    }).catch((error) => {
      console.error('Failed to persist simulation state', error);
    });
  };

  const updateSprite = ({ id, row, col, caughtPrey, cycleStep, canMove }) => {
    const sprite = document.getElementById(id);
    if (!sprite) {
      return;
    }
    if (typeof row === 'number') {
      sprite.dataset.row = String(row);   //moving sprite logic
      sprite.style.setProperty('--sprite-row', row);
    }
    if (typeof col === 'number') {
      sprite.dataset.col = String(col);
      sprite.style.setProperty('--sprite-col', col);
    }

    if (typeof caughtPrey === 'boolean') {
      sprite.dataset.caughtPrey = caughtPrey ? 'true' : 'false'; //"true" if caughtprey == true "false" if not
    } else {
      delete sprite.dataset.caughtPrey;
    }

    if (typeof cycleStep === 'number') {
      sprite.dataset.cycleStep = String(cycleStep);
    } else {
      delete sprite.dataset.cycleStep;
    }

    if (typeof canMove === 'boolean') {
      sprite.dataset.canMove = canMove ? 'true' : 'false';
    } else {
      delete sprite.dataset.canMove;
    }
  };

  document.querySelectorAll('.trophic-level').forEach((section) => {
    const levelId = section.dataset.level;
    const countNode = section.querySelector('.trophic-level__count');
    if (!levelId || !countNode) {
      return;
    }
    levelPanels.set(levelId, { section, countNode });
  });

  document.querySelectorAll('.trophic-level__organism').forEach((button) => {
    const organismId = button.dataset.targetId;
    if (!organismId) {
      return;
    }
    const populationNode = button.querySelector('.trophic-level__organism-population');
    const genomeNode = button.querySelector('.trophic-level__organism-genome');
    const coordsNode = button.querySelector('.trophic-level__organism-coords');
    const parentSection = button.closest('.trophic-level');
    organismPanels.set(organismId, {
      populationNode,
      genomeNode,
      coordsNode,
      levelId: parentSection ? parentSection.dataset.level : null,
      population: null,
    });
  });

  const refreshLevelTotals = () => {
    levelPanels.forEach(({ countNode }, levelId) => {
      let total = 0;
      organismPanels.forEach((panel) => {
        if (panel.levelId === levelId && typeof panel.population === 'number') {
          total += panel.population;
        }
      });
      countNode.textContent = `Population: ${total} individuals`;
    });
  };

  const defaultTraitNames = ['Trait 1', 'Trait 2', 'Trait 3', 'Trait 4'];
  const resolveTraitName = (traitNames, index) => {
    if (Array.isArray(traitNames) && traitNames[index]) {
      return String(traitNames[index]);
    }
    return defaultTraitNames[index] || `Trait ${index + 1}`;
  };

  const updateOrganismPanel = ({ id, population, averageGenome, row, col, traitNames }) => {
    const panel = organismPanels.get(id);
    if (!panel) {
      return;
    }

    if (typeof population === 'number' && panel.populationNode) {
      panel.populationNode.textContent = `${population} individuals`;
      panel.population = population;
    }

    if (panel.genomeNode) {
      if (Array.isArray(averageGenome) && averageGenome.length > 0) {
        const formattedValues = averageGenome
          .map((value, index) => {
            const numeric = Number.parseFloat(value);
            const label = resolveTraitName(traitNames, index);
            const displayValue = Number.isFinite(numeric) ? numeric.toFixed(3) : 'n/a';
            return `${label}: ${displayValue}`;
          })
          .join(' | ');
        panel.genomeNode.textContent = `Avg genome: ${formattedValues}`;
      } else {
        panel.genomeNode.textContent = 'Avg genome: n/a';
      }
    }

    if (panel.coordsNode && typeof row === 'number' && typeof col === 'number') {
      const formatCoord = (value) => String(value).padStart(2, '0');
      panel.coordsNode.textContent = `${formatCoord(row)}, c${formatCoord(col)}`;
    }

    refreshLevelTotals();
  };

  const performStep = () => {
    if (!running) {
      return;
    }

    const controller = new AbortController();
    currentController = controller;

    fetch('/api/simulation/step', {   //writing to json
      method: 'POST',
      signal: controller.signal,
    })
      .then((response) => {
        if (!response.ok) {
          throw new Error(`Simulation step failed: ${response.status}`);
        }
        return response.json();
      })
      .then((data) => {
        if (!data) {
          return;
        }
        const {
          organisms = [],
          cycleComplete = false,
          cycleSummary = [],
          cycleIndex = null,
        } = data;

        if (Array.isArray(organisms)) {
          organisms.forEach((organism) => {
            updateSprite(organism);
            updateOrganismPanel(organism);
          });
        }

        if (cycleComplete) {
          const detail = {
            cycle: cycleIndex,
            summary: Array.isArray(cycleSummary) ? cycleSummary : [],
          };
          stopSimulation({ abort: false });
          persistState(cycleIndex, detail.summary, organisms);
          document.dispatchEvent(new CustomEvent('simulation:cycleComplete', { detail }));
        }
      })
      .catch((error) => { //error handling
        console.error(error);
        stopSimulation();
      })
      .finally(() => { //runs if no error
        if (currentController === controller) {
          currentController = null;
        }
        if (running && !controller.signal.aborted) {
          window.setTimeout(performStep, stepInterval);
        }
      });
  };

  function resetSimulationState() {
    fetch('/api/simulation/reset', {
      method: 'POST',
    }).catch((error) => {
      console.error('Failed to reset simulation state', error);
    });
  }

  const startSimulation = () => {
    if (running) {
      return;
    }
    running = true;
    startButton.textContent = 'Stop Movement';
    startButton.classList.add('is-active');
    performStep();
  };

  const stopSimulation = (options = {}) => {
    running = false;
    startButton.textContent = 'Start Movement';
    startButton.classList.remove('is-active');
    const { abort = true } = options;
    if (abort && currentController) {
      currentController.abort();
    }
  };

  startButton.addEventListener('click', () => { //resetting json file to stop bad data
    if (running) {
      stopSimulation();
    } else {
      startSimulation();
    }
  });

  resetSimulationState();
});
