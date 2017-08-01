import sys, logging, json, os.path
import tempfile
from EXOSIMS.util.get_module import get_module
import random as py_random
import numpy as np
import astropy.units as u
import copy, re, inspect, subprocess

class MissionSim(object):
    """Mission Simulation (backbone) class
    
    This class is responsible for instantiating all objects required 
    to carry out a mission simulation.
    
    Args:
        \*\*specs:
            user specified values
            
    Attributes:
        PlanetPopulation (PlanetPopulation):
            PlanetPopulation class object
        PlanetPhysicalModel (PlanetPhysicalModel):
            PlanetPhysicalModel class object
        OpticalSystem (OpticalSystem):
            OpticalSystem class object
        ZodiacalLight (ZodiacalLight):
            ZodiacalLight class object
        BackgroundSources (BackgroundSources):
            Background Source class object
        PostProcessing (PostProcessing):
            PostProcessing class object
        Completeness (Completeness):
            Completeness class object
        TargetList (TargetList):
            TargetList class object
        SimulatedUniverse (SimulatedUniverse):
            SimulatedUniverse class object
        Observatory (Observatory):
            Observatory class object
        TimeKeeping (TimeKeeping):
            TimeKeeping class object
        SurveySimulation (SurveySimulation):
            SurveySimulation class object
        SurveyEnsemble (SurveyEnsemble):
            SurveyEnsemble class object
    
    """

    _modtype = 'MissionSim'
    _outspec = {}

    def __init__(self, scriptfile=None, nopar=False, **specs):
        """Initializes all modules from a given script file or specs dictionary.
        
        Args: 
            scriptfile (string):
                Path to JSON script file. If not set, assumes that 
                dictionary has been passed through specs.
            specs (dictionary):
                Dictionary containing additional user specification values and 
                desired module names.
            nopar (bool):
                If True, ignore any provided ensemble module in the script or specs
                and force the prototype ensemble.
        
        """
        
        # extend given specs with (JSON) script file
        if scriptfile is not None:
            assert os.path.isfile(scriptfile), "%s is not a file."%scriptfile
            try:
                script = open(scriptfile).read()
                specs_from_file = json.loads(script)
                specs_from_file.update(specs)
            except ValueError as err:
                print "Error: %s: Input file `%s' improperly formatted."%(self._modtype,
                        scriptfile)
                print "Error: JSON error was: ", err
                # re-raise here to suppress the rest of the backtrace.
                # it is only confusing details about the bowels of json.loads()
                raise ValueError(err)
            except:
                print "Error: %s: %s", (self._modtype, sys.exc_info()[0])
                raise
        else:
            specs_from_file = {}
        specs.update(specs_from_file)
        
        if 'modules' not in specs.keys():
            raise ValueError("No modules field found in script.")
        
        # set up numpy random number seed at top
        self.seed = specs.get('seed', py_random.randint(1, 1e9))
        np.random.seed(self.seed)
        # add seed to specs
        specs['seed'] = self.seed
        print 'MissionSim seed is: ', self.seed
        
        # start logging, with log file and logging level (default: INFO)
        self.logfile = specs.get('logfile', None)
        self.loglevel = specs.get('loglevel', 'INFO').upper()
        specs['logger'] = self.get_logger(self.logfile, self.loglevel)
        specs['logger'].info('Start Logging: loglevel = %s'%specs['logger'].level \
                + ' (%s)'%self.loglevel)
        
        # populate outspec
        for att in self.__dict__.keys():
            self._outspec[att] = self.__dict__[att]
        
        # initialize top level, import modules
        if nopar:
            specs['modules']['SurveyEnsemble'] = ' '
            
        self.SurveyEnsemble = get_module(specs['modules']['SurveyEnsemble'],
                'SurveyEnsemble')(**specs)
        self.SurveySimulation = get_module(specs['modules']['SurveySimulation'],
                'SurveySimulation')(**specs)
        
        # collect sub-initializations
        SS = self.SurveySimulation
        self.StarCatalog = SS.StarCatalog
        self.PlanetPopulation = SS.PlanetPopulation
        self.PlanetPhysicalModel = SS.PlanetPhysicalModel
        self.OpticalSystem = SS.OpticalSystem
        self.ZodiacalLight = SS.ZodiacalLight
        self.BackgroundSources = SS.BackgroundSources
        self.PostProcessing = SS.PostProcessing
        self.Completeness = SS.Completeness
        self.TargetList = SS.TargetList
        self.SimulatedUniverse = SS.SimulatedUniverse
        self.Observatory = SS.Observatory
        self.TimeKeeping = SS.TimeKeeping
        
        # create a dictionary of all modules, except StarCatalog
        self.modules = SS.modules
        self.modules['SurveySimulation'] = SS
        self.modules['SurveyEnsemble'] = self.SurveyEnsemble

    def get_logger(self, logfile, loglevel):
        r"""Set up logging object so other modules can use logging.info(),
        logging.warning, etc.
        
        Args:
            logfile (string):
                Path to the log file. If None, logging is turned off. 
                If supplied but empty string (''), a temporary file is generated.
            loglevel (string): 
                The level of log, defaults to 'INFO'. Valid levels are: CRITICAL, 
                ERROR, WARNING, INFO, DEBUG (case sensitive).
                
        Returns:
            logger (logging object):
                Mission Simulation logger.
        
        """
        
        # this leaves the default logger in place, so logger.warn will appear on stderr
        if logfile is None:
            logger = logging.getLogger(__name__)
            return logger
        
        # if empty string, a temporary file is generated
        if logfile == '':
            (dummy, logfile) = tempfile.mkstemp(prefix='EXOSIMS.', suffix='.log',
                    dir='/tmp', text=True)
        else:
            # ensure we can write it
            try:
                f = open(logfile, 'w')
                f.close()
            except (IOError, OSError) as e:
                print '%s: Failed to open logfile "%s"'%(__file__, logfile)
                return None
        print "Logging to '%s' at level '%s'"%(logfile, loglevel.upper())
        
        # convert string to a logging.* level
        numeric_level = getattr(logging, loglevel.upper())
        if not isinstance(numeric_level, int):
            raise ValueError('Invalid log level: %s'%loglevel.upper())
        
        # set up the top-level logger
        logger = logging.getLogger(__name__.split('.')[0])
        logger.setLevel(numeric_level)
        # do not propagate EXOSIMS messages to higher loggers in this case
        logger.propagate = False
        # create a handler that outputs to the named file
        handler = logging.FileHandler(logfile, mode='w')
        handler.setLevel(numeric_level)
        # logging format
        formatter = logging.Formatter('%(levelname)s: %(filename)s(%(lineno)s): '\
                +'%(funcName)s: %(message)s')
        handler.setFormatter(formatter)
        # add the handler to the logger
        logger.addHandler(handler)
        
        return logger

    def run_sim(self):
        """Convenience method that simply calls the SurveySimulation run_sim method.
        
        """
        
        res = self.SurveySimulation.run_sim()
        
        return res

    def reset_sim(self, genNewPlanets=True, rewindPlanets=True):
        """Convenience method that simply calls the SurveySimulation reset_sim method.
        
        """
        
        res = self.SurveySimulation.reset_sim(genNewPlanets=genNewPlanets,
                rewindPlanets=rewindPlanets)
        
        return res

    def run_ensemble(self, nb_run_sim, run_one=None, genNewPlanets=True, 
            rewindPlanets=True,kwargs={}):
        """Convenience method that simply calls the SurveyEnsemble run_ensemble method.
        
        """
        
        res = self.SurveyEnsemble.run_ensemble(self, nb_run_sim, run_one=run_one,
                genNewPlanets=genNewPlanets, rewindPlanets=rewindPlanets,kwargs=kwargs)
        
        return res

    def genOutSpec(self, tofile=None):
        """Join all _outspec dicts from all modules into one output dict
        and optionally write out to JSON file on disk.
        
        Args:
            tofile (string):
                Name of the file containing all output specifications (outspecs).
                Default to None.
                
        Returns:
            out (dictionary):
                Dictionary containing additional user specification values and 
                desired module names.
        
        """
        
        out = self.SurveySimulation.genOutSpec(tofile=tofile)
        
        return out

    def DRM2array(self, key, DRM=None):
        """Creates an array corresponding to one element of the DRM dictionary. 
        
        Args:
            key (string):
                Name of an element of the DRM dictionary
            DRM (list of dicts):
                Design Reference Mission, contains the results of a survey simulation
                
        Returns:
            elem (ndarray / astropy Quantity array):
                Array containing all the DRM values of the selected element
        
        """
        
        # if the DRM was not specified, get it from the current SurveySimulation
        if DRM is None:
            DRM = self.SurveySimulation.DRM
        assert DRM != [], 'DRM is empty. Use MissionSim.run_sim() to start simulation.'
        
        # lists of relevant DRM elements
        keysStar = ['star_ind', 'star_name', 'arrival_time', 'OB_nb', 
                    'det_time', 'det_fZ', 'char_time', 'char_fZ']
        keysPlans = ['plan_inds', 'det_status', 'det_SNR', 'char_status', 'char_SNR']
        keysParams = ['det_fEZ', 'det_dMag', 'det_WA', 'det_d', 
                      'char_fEZ', 'char_dMag', 'char_WA', 'char_d']
        keysFA = ['FA_det_status', 'FA_char_status', 'FA_char_SNR', 
                  'FA_char_fEZ', 'FA_char_dMag', 'FA_char_WA']
        
        assert key in (keysStar + keysPlans + keysParams + keysFA), \
                "'%s' is not a relevant DRM keyword."
        
        # extract arrays for each relevant keyword in the DRM
        if key in keysParams:
            if 'det_' in key:
                elem = np.array([DRM[x]['det_params'][key[4:]] for x in range(len(DRM))])
            elif 'char_' in key:
                elem = np.array([DRM[x]['char_params'][key[5:]] for x in range(len(DRM))])
        elif isinstance(DRM[0][key], u.Quantity):
            elem = np.array([DRM[x][key].value for x in range(len(DRM))])*DRM[0][key].unit
        else:
            elem = np.array([DRM[x][key] for x in range(len(DRM))])
            
        return elem

    def filter_status(self, key, status, DRM=None, obsMode=None):
        """Finds the values of one DRM element, corresponding to a status value, 
        for detection or characterization.
        
        Args:
            key (string):
                Name of an element of the DRM dictionary
            status (integer):
                Status value for detection or characterization
            DRM (list of dicts):
                Design Reference Mission, contains the results of a survey simulation
            obsMode (string):
                Observing mode type ('det' or 'char')
                
        Returns:
            elemStat (ndarray / astropy Quantity array):
                Array containing all the DRM values of the selected element,
                and filtered by the value of the corresponding status array
        
        """
        
        # get DRM detection status array
        det = self.DRM2array('FA_det_status', DRM=DRM) if 'FA_' in key \
                else self.DRM2array('det_status', DRM=DRM)
        # get DRM characterization status array
        char = self.DRM2array('FA_char_status', DRM=DRM) if 'FA_' in key \
                else self.DRM2array('char_status', DRM=DRM)
        # get DRM key element array
        elem = self.DRM2array(key, DRM=DRM)
        
        # reshape elem array, for keys with 1 value per observation
        if elem[0].shape is () and 'FA_' not in key:
            if isinstance(elem[0], u.Quantity):
                elem = np.array([np.array([elem[x].value]*len(det[x]))*elem[0].unit \
                         for x in range(len(elem))])
            else:
                elem = np.array([np.array([elem[x]]*len(det[x])) for x in range(len(elem))])
        
        # assign a default observing mode type ('det' or 'char')
        if obsMode is None: 
            obsMode = 'char' if 'char_' in key else 'det'
        assert obsMode in ('det', 'char'), "Observing mode type must be 'det' or 'char'."
        
        # now, find the values of elem corresponding to the specified status value
        if obsMode is 'det':
            if isinstance(elem[0], u.Quantity):
                elemStat = np.concatenate([elem[x][det[x] == status].value \
                        for x in range(len(elem))])*elem[0].unit
            else:
                elemStat = np.concatenate([elem[x][det[x] == status] for x in range(len(elem))])
        else: # if obsMode is 'char'
            if isinstance(elem[0], u.Quantity):
                elemDet = np.concatenate([elem[x][det[x] == 1].value \
                        for x in range(len(elem))])*elem[0].unit
            else:
                elemDet = np.concatenate([elem[x][det[x] == 1] for x in range(len(elem))])
            charDet = np.concatenate([char[x][det[x] == 1] for x in range(len(elem))])
            elemStat = elemDet[charDet == status]
        
        return elemStat
