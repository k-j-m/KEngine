from performance import *

class EngineAssembly(Engine):
    def __init__(self):
        super(EngineAssembly,self).__init__()
        self.input_aliases={}
        self.output_aliases={}
        self.solver = None

    def get_input_info(self):
        inputs = []
        for k,v in self.input_aliases.items():
            _,min,max = v
            inputs.append((k,min,max))
        return inputs
        
    def set_inputs(self, input_dict):
        for k,v in input_dict.items():
            self.set_input_alias(k,v)

    def get_inputs(self):

        return dict([(nm,self.get_input_alias(nm))
                     for nm in self.get_input_aliases()])         #return inps
            
    def add_input_alias(self,name,path,min=None,max=None):
        self.input_aliases[name]=path,min,max

    def add_output_alias(self,name,path):
        self.output_aliases[name]=path
                
    def get_input_aliases(self):
        return self.input_aliases.keys()

    def get_input_alias(self,alias):
        path = self.input_aliases[alias][0]
        item = self
        for p in path:
            item = item[p]
        return item

    def get_input_limits(self,alias):
        path,_min,_max = self.input_aliases[alias]
        return _min,_max

    def set_input_alias(self, alias, value):
        path = self.input_aliases[alias][0]
        last = path[-1]
        path2 = path[:-1]
        item = self
        for p in path2:
            item=item[p]
        item[last]=value

    def get_output_aliases(self):
        return self.output_aliases.keys()

    def get_output_alias(self,alias):
        path = self.output_aliases[alias]
        item = self
        for p in path:
            item = item[p]
        return item

    def get_outputs(self):
        """
        Returns the engine outputs in a list of (key,values)
        for example:
        [('THRUST', 300.0), ('SFC', ...)]

        This is really for convenience so that the results
        are guaranteed to be returned in the same order.
        """
        outputs=[]
        for k in self.output_aliases:
            outputs.append((k, self.get_output_alias(k)))
        return outputs


    def calculate(self, input_dict):
        """
        Recalculates the engine for the given inputs and
        returns the calculated outputs in dictionary form:
        { name: value }
        """
        self.set_inputs(input_dict)
        self.update()
        return dict(self.get_outputs())
    
class _Solver(object):
    def __init__(self, engine, match_pairs):
        self.engine = engine
        self.match_pairs = match_pairs

    def __getattr__(self,attr):
        return getattr(engine,attr)

    def generate_jacobian(self, current_values):
        jacobian = {}

        # start with defaults
        #defaults = dict([(nm, self.engine.get_output_alias(nm)) for nm in outputs])
        defaults = {}
        for output_name in outputs:
            value = self.engine.get_output_alias(output_name)
            defaults[output_name]=value

        # step through inputs to calculate gradients
        gradients = {}
        for input_name in inputs:
            # make the perturbation
            perturbation = self.input_settings[input_name]['perturbation']
            new_values = current_values.copy()
            new_values[input_name]=current_value[input_name]+perturbation
            
            # send through to the engine calculator
            self.engine.set_inputs(new_values)
            self.engine.update()

            gradient_row = {}
            # look at the outputs and calculate the gradients for each
            for output_name in outputs:
                value = self.engine.get_output_alias(output_name)
                difference = value - defaults[output_name]
                gradient = difference / perturbation

                gradient_row[output_name]=gradient

            gradients[input_name]=gradient_row
            
        return gradients
    
class TurboFan(EngineAssembly):
    def __init__(self):
        super(TurboFan,self).__init__()
        # Create Components
        self['INTAKE'] = Intake({'W':1.0})
        self['FAN'] = Compressor({'PR':1.5})
        self['SPLITTER'] = Splitter({'BPR':8.0})
        self['HPC'] = Compressor({'PR':40.0})
        self['COMBUSTOR'] = Combustor({'TEX':1600.0,'FHV':45.E6})
        self['HPT'] = Turbine()
        self['LPT'] = Turbine()
        self['CNOZ'] = Nozzle()
        self['HNOZ'] = Nozzle()
        self['HPSHAFT'] = Shaft(name='hp_shaft')
        self['LPSHAFT'] = Shaft(name='lp_shaft')

        # Create Stations
        self.stations['0'] = Station('0') # fan inlet
        self.stations['1'] = Station('1') # fan exit
        self.stations['20'] = Station('20') # bypass entry/cnoz in
        self.stations['2'] = Station('2') # core entry
        self.stations['3'] = Station('3') # hpc ex/comb in
        self.stations['4'] = Station('4') # comb ex/hpt in
        self.stations['5'] = Station('5') # hpt ex/lpt in
        self.stations['6'] = Station('6') # lpt ex/hnoz in

        # Connect Flows
        stns=self.stations
        self['INTAKE'].connect_downstream(stns['0'])
        self['FAN'].connect_stations(stns['0'],stns['1'])
        self['SPLITTER'].connect_stations(stns['1'],stns['2'],stns['20'])

        # bypass stream
        self['CNOZ'].connect_upstream(stns['20'])

        # core stream
        self['HPC'].connect_stations(stns['2'], stns['3'])
        self['COMBUSTOR'].connect_stations(stns['3'],stns['4'])
        self['HPT'].connect_stations(stns['4'],stns['5'])
        self['LPT'].connect_stations(stns['5'],stns['6'])
        self['HNOZ'].connect_upstream(stns['6'])

        # connect shafts
        self['HPSHAFT'].add_turbine(self['HPT'])
        self['HPSHAFT'].add_driven(self['HPC'])
        self['LPSHAFT'].add_turbine(self['LPT'])
        self['LPSHAFT'].add_driven(self['FAN'])

        # set up aliases to get to component parameters

        #self.input_aliases['FANPR']=('FAN','PR')
        self.add_input_alias('HPCPR',('HPC','PR'), min=10., max=20.)
        self.add_input_alias('RIT',('COMBUSTOR','TEX'), min=1600., max=2000.)
        self.add_input_alias('BPR',('SPLITTER','BPR'), min=4., max=12.)
        self.add_input_alias('FLOW',('INTAKE','W'), min=200., max=800.)

        # output aliases

        self.add_output_alias('SFC',('ENGINE','SFC'))
        self.add_output_alias('THRUST',('ENGINE','THRUST'))
        
        # set default environment
        env = self.environment
        env.p, env.t, env.w = (30000.0,300.0,1.0)


        
class TurboJet(EngineAssembly):
    def __init__(self):
        super(TurboJet,self).__init__()
        # Create Components
        self['INTAKE'] = Intake({'W':1.0})
        self['HPC'] = Compressor({'PR':40.0})
        self['COMBUSTOR'] = Combustor({'TEX':1600.0,'FHV':45.E6})
        self['HPT'] = Turbine()
        self['NOZ'] = Nozzle()
        self['HPSHAFT'] = Shaft(name='hp_shaft')

        # Create Stations
        self.stations['2'] = Station('2') # core entry
        self.stations['3'] = Station('3') # hpc ex/comb in
        self.stations['4'] = Station('4') # comb ex/hpt in
        self.stations['5'] = Station('5') # hpt ex/lpt in

        # Connect Flows
        stns=self.stations
        self['INTAKE'].connect_downstream(stns['2'])
        self['HPC'].connect_stations(stns['2'], stns['3'])
        self['COMBUSTOR'].connect_stations(stns['3'],stns['4'])
        self['HPT'].connect_stations(stns['4'],stns['5'])
        self['NOZ'].connect_upstream(stns['5'])

        # connect shafts
        self['HPSHAFT'].add_turbine(self['HPT'])
        self['HPSHAFT'].add_driven(self['HPC'])

        # set up aliases to get to component parameters

        self.add_input_alias('HPCPR',('HPC','PR'),min=10.0,max=25.0)
        self.add_input_alias('RIT',('COMBUSTOR','TEX'),min=1400.0,max=1800.0)
        self.add_input_alias('FLOW',('INTAKE','W'),min=10.0,max=100.)

        # output aliases
        self.add_output_alias('SFC',('ENGINE','SFC'))
        self.add_output_alias('THRUST',('ENGINE','THRUST'))
        
        # set default environment
        env = self.environment
        env.p, env.t, env.w = (30000.0,300.0,1.0)

