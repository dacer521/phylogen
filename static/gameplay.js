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

  const tour = document.querySelector('.simulation-tour');
  const openTourButton = document.getElementById('open-simulation-tour');
  const tourStorageKey = 'phylogen-simulation-tour-v1';

  if (tour) {
    const slides = Array.from(tour.querySelectorAll('.simulation-tour__slide'));
    const dotGroup = tour.querySelector('.simulation-tour__dot-group');
    let dots = Array.from(tour.querySelectorAll('.simulation-tour__dot'));
    const progress = tour.querySelector('[data-tour-progress]');
    const prevButton = tour.querySelector('[data-tour-action="prev"]');
    const nextButton = tour.querySelector('[data-tour-action="next"]');
    const closeTriggers = Array.from(tour.querySelectorAll('[data-tour-action="close"]'));

    let currentSlideIndex = 0;

    const syncDots = () => {
      if (!dotGroup) return;
      if (dots.length === slides.length) return;
      dotGroup.innerHTML = '';
      for (let i = 0; i < slides.length; i += 1) {
        const dot = document.createElement('span');
        dot.className = 'simulation-tour__dot';
        dotGroup.appendChild(dot);
      }
      dots = Array.from(dotGroup.querySelectorAll('.simulation-tour__dot'));
    };

    const updateDots = () => {
      syncDots();
      dots.forEach((dot, index) => {
        dot.classList.toggle('is-active', index === currentSlideIndex);
      });
    };

    const updateSlides = () => {
      slides.forEach((slide, index) => {
        slide.classList.toggle('is-active', index === currentSlideIndex);
      });
      if (progress) {
        progress.textContent = `${currentSlideIndex + 1} / ${slides.length}`;
      }
      if (prevButton) {
        prevButton.disabled = currentSlideIndex === 0;
      }
      if (nextButton) {
        nextButton.textContent = currentSlideIndex === slides.length - 1 ? 'Finish' : 'Next';
      }
      updateDots();
    };

    const openTour = () => {
      tour.classList.add('is-open');
      tour.setAttribute('aria-hidden', 'false');
      window.localStorage.setItem(tourStorageKey, 'seen');
      currentSlideIndex = 0;
      updateSlides();
    };

    const closeTour = () => {
      tour.classList.remove('is-open');
      tour.setAttribute('aria-hidden', 'true');
      window.localStorage.setItem(tourStorageKey, 'seen');
    };

    nextButton?.addEventListener('click', () => {
      if (currentSlideIndex < slides.length - 1) {
        currentSlideIndex += 1;
        updateSlides();
      } else {
        closeTour();
      }
    });

    prevButton?.addEventListener('click', () => {
      if (currentSlideIndex === 0) return;
      currentSlideIndex -= 1;
      updateSlides();
    });

    closeTriggers.forEach((button) => {
      button.addEventListener('click', closeTour);
    });

    document.addEventListener('keydown', (event) => {
      if (event.key === 'Escape' && tour.classList.contains('is-open')) {
        closeTour();
      }
    });

    openTourButton?.addEventListener('click', () => {
      openTour();
    });

    const hasSeenTour = window.localStorage.getItem(tourStorageKey);
    if (!hasSeenTour) {
      openTour();
    }
  }

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
      element: button,
      populationNode,
      genomeNode,
      coordsNode,
      levelId: parentSection ? parentSection.dataset.level : null,
      population: null,
      lastAverageGenome: null,
      lastTraitNames: null,
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

  let showExactGenes = false;
  const genomeDisplayButton = document.getElementById('toggle-genome-display');

  const genotypeLabel = (value) => {
    const numeric = Number.parseFloat(value);
    if (!Number.isFinite(numeric)) {
      return 'n/a';
    }
    if (numeric >= 0.75) {
      return 'TT';
    }
    if (numeric > 0.25 && numeric < 0.75) {
      return 'Tt';
    }
    return 'tt';
  };

  const formatGeneValue = (value, traitNames, index) => {
    const label = resolveTraitName(traitNames, index);
    if (showExactGenes) {
      const numeric = Number.parseFloat(value);
      const displayValue = Number.isFinite(numeric) ? numeric.toFixed(3) : 'n/a';
      return `${label}: ${displayValue}`;
    }
    return `${label}: ${genotypeLabel(value)}`;
  };

  const updateGenomeToggleLabel = () => {
    if (!genomeDisplayButton) return;
    genomeDisplayButton.textContent = showExactGenes ? 'Show Gene Notation' : 'Show Exact Genes';
  };

  const markExtinct = (organismId) => {
    const panel = organismPanels.get(organismId);
    if (panel) {
      panel.population = 0;
      if (panel.populationNode) {
        panel.populationNode.textContent = 'Extinct';
      }
      if (panel.element) {
        panel.element.style.display = 'none';
      }
    }
    const sprite = document.getElementById(organismId);
    if (sprite && sprite.parentElement) {
      sprite.parentElement.removeChild(sprite);
    }
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
      const genomeText = panel.genomeNode.querySelector('.trophic-level__organism-genome-text');
      if (Array.isArray(averageGenome) && averageGenome.length > 0) {
        const formattedValues = averageGenome
          .map((value, index) => formatGeneValue(value, traitNames, index))
          .join(' | ');
        if (genomeText) {
          genomeText.textContent = `Avg genome: ${formattedValues}`;
        } else {
          panel.genomeNode.textContent = `Avg genome: ${formattedValues}`;
        }
      } else {
        if (genomeText) {
          genomeText.textContent = 'Avg genome: n/a';
        } else {
          panel.genomeNode.textContent = 'Avg genome: n/a';
        }
      }
      panel.lastAverageGenome = Array.isArray(averageGenome) ? averageGenome : null;
      panel.lastTraitNames = Array.isArray(traitNames) ? traitNames : null;
    }

    if (panel.coordsNode && typeof row === 'number' && typeof col === 'number') {
      const formatCoord = (value) => String(value).padStart(2, '0');
      panel.coordsNode.textContent = `${formatCoord(row)}, c${formatCoord(col)}`;
    }

    refreshLevelTotals();
  };

  if (genomeDisplayButton) {
    genomeDisplayButton.addEventListener('click', () => {
      showExactGenes = !showExactGenes;
      updateGenomeToggleLabel();
      // Refresh existing panels with last known genomes
      organismPanels.forEach((panel, organismId) => {
        if (!panel.lastAverageGenome || !panel.genomeNode) return;
        const genomeText = panel.genomeNode.querySelector('.trophic-level__organism-genome-text');
        const formattedValues = panel.lastAverageGenome
          .map((value, index) => formatGeneValue(value, panel.lastTraitNames, index))
          .join(' | ');
        if (genomeText) {
          genomeText.textContent = `Avg genome: ${formattedValues}`;
        } else {
          panel.genomeNode.textContent = `Avg genome: ${formattedValues}`;
        }
      });
    });
    updateGenomeToggleLabel();
  }

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

        const extinctIds = Array.isArray(data.extinct) ? data.extinct : [];  //don't show extinct species
        if (extinctIds.length) {
          extinctIds.forEach(markExtinct);
          refreshLevelTotals();
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


function highlightOrganism(row, col) {
  const mapGrid = document.querySelector('.map-grid');
  if (!mapGrid) {
    return;
  }

  row = row - 1 
  col = col - 1

  const rowValue = String(row);
  const colValue = String(col);


  const tile = mapGrid.querySelector(`.map-tile[data-row=\"${rowValue}\"][data-col=\"${colValue}\"]`);
  if (!tile) {
    return;
  }

  const previousTile = mapGrid.querySelector('.map-tile.is-highlighted');
  if (previousTile && previousTile !== tile) {
    previousTile.classList.remove('is-highlighted');
  }
  tile.classList.add('is-highlighted');
}

function removeHighlightOrganism(row, col) {
 const mapGrid = document.querySelector('.map-grid');
  if (!mapGrid) {
    return;
  }

  row = row - 1
  col = col - 1

   const rowValue = String(row);
  const colValue = String(col);
  const tile = mapGrid.querySelector(`.map-tile[data-row=\"${rowValue}\"][data-col=\"${colValue}\"]`);
  if (!tile) {
    return;
  }
 
  tile.classList.remove('is-highlighted');
}
