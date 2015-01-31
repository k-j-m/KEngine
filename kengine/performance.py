import compressible
from compressible import gamma, R, cp
#gamma = 1.4
#cp = 1004.0


class Calculable(object):
    """
    The basic building block of our calculation chain.
    The Calculable class holds a list of precedents and dependents.
    Calculation may only occur when all of the precedents are
    up to date.
    Once the calculation has taken place an update message is
    broadcast to all dependents.

    We end up with a network of calculation-cells that are activated
    as dependencies are resolved. This is similar to how calculation
    flows through a spreadsheet application.

    There are edge cases that won't be dealt with completely.
    Multiple root Calculables: as it is currently configured, the entire
    calculation network needs to be initiated from a single source. If
    there are more than 1 Calculables with no precedents then they will
    not be triggered and the network calculation will not complete.
    This can be resolved by passing an update() message back up the
    dependency tree to cause unfired Calculables to trigger.

    Circular references will not be caught. There are a couple of ways to
    catch this...
    Maintain a global set of Calculable ids. If a Calculable is able to
    find itself in this set when it is asked to recalculate then
    there are some circular dependencies.
    Also, if a Calculable is asked to recalculate despite already
    being marked as 'clean' then something has gone wrong.

    Alternatively, instead of maintaining a global set of calculated
    Calculables, we could pass the set down the calculation network
    as an argument.
    """

    def __init__(self):
        """
        The Calculable needs to maintain a list of precedents and
        dependents as well as a 'dirty' flag to indicate whether the
        calculation has been triggered.
        """
        self.dependents=[]
        self.precedents=[]
        self.dirty = True
    
    def make_dirty(self):
        """
        When the Calculable is marked as dirty, all of its depedents
        need to be marked as well.
        """
        self.dirty = True
        for d in self.dependents:
            d.make_dirty()

    def update(self):
        """
        The update method should only be called via a recently updated
        precedent or by a dependent whose calculation is blocked.
        In both of these cases the Calculable should be marked as dirty.
        If this is not the case then something has gone wrong in the
        calculation chain.
        """
        assert self.dirty, 'If a precedent tells us to update we must be dirty: [%s] %s'%(self.name,str(self))

        # We are currently only progressing the calculation if
        # all precedents are clean, but there is no active feedback
        # to trigger calculation if we are 'blocked' by a dirty precedent
        if not any([p.dirty for p in self.precedents]):
            #print 'Undirtying',self
            self.dirty = False
            self.calculate()
            for d in self.dependents:
                d.update()

    def add_dependent(self, dependent):
        self.dependents.append(dependent)

    def add_precedent(self, precedent):
        self.precedents.append(precedent)

    def calculate(self):
        """Default implementation does nothing."""
        pass
                                    
class Station(Calculable):
    """
    A station represents the state of the gas flow between two
    connected components. It has fields for total pressure,
    total temperature, and mass flow.
    """
    def __init__(self, name=None):
        super(Station,self).__init__()
        self.name = name
        self.p = 0.0
        self.t = 0.0
        self.w = 0.0

    def __repr__(self):
        return 'Station(name=%s, p=%f,t=%f,w=%f)' % (self.name,self.p,self.t,self.w)

class Environment(Station):
    """
    The environment is a special case of Station where we also
    have additional attributes that describe the engine's operational
    environment. This may include items like ambient conditions,
    airspeed, etc.
    """
    def __init__(self, attributes={}, name=None):
        super(Environment, self).__init__(name)
        self.attributes = attributes

    def __getattr__(self, name):
        return self.attributes[name]

    def calculate(self):
        #print 'CALCULATING ENVIRONMENT'
        if 'v0' in self.attributes:
            v0 = self.attributes['v0']
            self.attributes['MACH'] = v0 / (gamma * R * self.t)**0.5

        elif 'MACH' in self.attributes:
            mn = self.attributes['MACH']
            self.attributes['v0'] = mn * (gamma * R * self.t)**0.5

        else:
            raise Exception('Missing airspeed input in Environment')
        

class Component(Calculable):
    """
    An engine is built up from several components connected with
    stations.
    """
    cname = 'generic component'
    def __init__(self, attributes={}, name=None):
        super(Component,self).__init__()
        self.attributes = attributes
        if name is None:
            self.name = self.cname
        else:
            self.name = name
            
    def __getitem__(self,name):
        return self.attributes[name]

    def __setitem__(self,name,value):
        if not name in self.attributes:
            raise LookupError('Component does not have access to parameter: %s'%name)
        self.make_dirty()
        self.attributes[name] = value
    
    def calculate(self):
        raise NotImplementedError('Components need to provide the calculation logic.')
    
class InletComponent(Component):
    """
    This is the base class for any components that can have flow
    ENTER from the front. It only provides the connect_upstream
    method that is used to connect this component with its upstream
    Station.
    """
    def connect_upstream(self, inlet):
        # take care of the dependency mapping
        inlet.add_dependent(self)
        self.add_precedent(inlet)
        # and give us a handle on the inlet to use later
        self.inlet = inlet

class ExitComponent(Component):
    """
    Base class for any components that have flow EXIT from the
    rear. The connect_downstream method is used to connect
    the component to its downstream Station.
    """
    def connect_downstream(self, exit):
        # take care of the dependency mapping
        self.add_dependent(exit)
        exit.add_precedent(self)
        # and give us a handle on the inlet to use later
        self.exit = exit
        
class FlowComponent(InletComponent,ExitComponent):
    """
    Base class for any components that have flow both
    enter and exit. Provides the connect_stations method
    that is used to connect the component to its upstream
    and downstream Stations
    """
    def connect_stations(self, inlet, exit):
        self.connect_upstream(inlet)
        self.connect_downstream(exit)
    
class Intake(ExitComponent):
    """
    The Intake is a flow-originator. That is, it sits at the
    very top of the calculation tree and creates the flow that
    passes back through the rest of the engine.

    To function, it needs to be connected to an ambient station
    which serves as a precedent. The total pressure and temperature
    are calculated from the ambient conditions and the airspeed (Mn).
    NOTE: this SHOULD be the case, but I haven't implemented it yet.
    """
    cname = 'intake'

    def connect_ambient(self, ambient):
        self.ambient = ambient
        self.precedents.append(ambient)
        ambient.add_dependent(self)

    def calculate(self):
        M = self.ambient.MACH
        w = self['W']
        self.exit.p = self.ambient.p / compressible.p_P(M)
        self.exit.t = self.ambient.t / compressible.t_T(M)
        self.exit.w = w
    
class Splitter(Component):
    """
    The Splitter takes a single inlet flow and splits it into two
    exit flows according to the bypass ratio, whereby... Wex1/Wex0 = BPR.
    """
    
    cname = 'splitter'
    def connect_stations(self, inlet, exit0, exit1):
        """exit0 is the core flow and exit1 is the bypass flow"""
        inlet.add_dependent(self)
        self.inlet = inlet
        self.exit0 = exit0
        self.exit1 = exit1
        self.precedents.append(inlet)
        self.dependents.append(exit0)
        self.dependents.append(exit1)
    
    def calculate(self):
        #print 'Calculating splitter'
        p0,t0,w0 = self.inlet.p, self.inlet.t, self.inlet.w
        bpr = self['BPR']
        
        self.exit0.p = p0
        self.exit0.t = t0
        self.exit0.w = w0/(bpr+1)

        self.exit1.p = p0
        self.exit1.t = t0
        self.exit1.w = w0*bpr/(bpr+1)

class Shaft(Component):
    """
    The shaft is one of the more complicated components.

    Each shaft should be connected to a single turbine to
    provide power, and multiple (one or more) consumers,
    such as compressors or power offtakes.

    Each of the consumers are added as precedents since their
    power requirement must be known before the turbine knows
    how much power it has to extract from the flow.

    The turbine is added as a dependent.
    """
    cname = 'shaft'
    
    def add_turbine(self,driver):
        # establish bidirectional link
        self.driver = driver
        self.dependents.append(driver)
        driver.precedents.append(self)
        driver.shaft = self

    def add_driven(self, item):
        # establish bidirectional link
        self.precedents.append(item)
        item.dependents.append(self)
        
    def calculate(self):
        self.power = sum([p.shaft_power() for p in self.precedents])

class Propeller(Component):
    """
    EXPERIMENTAL:
    Propeller sits in the free-stream and converts shaft power into
    a change in flow velocity across the properller. This produces
    thrust that is picked up by the engine.
    """
    def calculate(self):
        pass
        
class Compressor(FlowComponent):
    """
    The Compressor consumes shaft power to effect an increase in pressure
    between the inlet and exit Stations. The Compressor uses an attribute
    'PR' to set the pressure ratio.
    """
    cname = 'compressor'
    
    def calculate(self):
        print 'Calculating compressor'
        
        p0,t0,w0 = self.inlet.p, self.inlet.t, self.inlet.w
        
        p1 = p0 * self['PR']
        t1 = t0 * self['PR'] ** (1-1/gamma)
        w1 = w0

        self.exit.p, self.exit.t, self.exit.w = p1, t1, w1
        
    def shaft_power(self):
        """
        All components that consume shaft power need to implement
        this shaft_power method so that the shaft can know how much
        power it is being asked to deliver.
        """
        w0 = self.inlet.w
        t0 = self.inlet.t
        t1 = self.exit.t
        
        return cp*w0*(t1-t0)
    
class Turbine(FlowComponent):
    """
    The Turbine component extracts power from the flow to achieve
    a power requirement from it's connected shaft.

    Note that it is possible for the turbine to be asked to provide
    more power than is available in the flow. Two examples of this are
    when using large power offtakes or when using a small core to power
    a large Fan.

    I would like to change the parameterisation of the engine to be
    absolutely bullet-proof, but this isn't possible without robust
    solvers to convert the fail-safe parameterisation into useful engine
    attributes (the difference between solver-friendly parameterisation and
    engineer-friendly parameterisation - an interesting topic!)
    """
    cname = 'turbine'
    
    def calculate(self):
        #print 'Calculating turbine'
        p0,t0,w0 = self.inlet.p, self.inlet.t, self.inlet.w
        power = self.shaft.power
        
        t1 = t0 - power/(cp*w0)
        p1 = p0 * (t1/t0)**(gamma / (gamma-1))
        w1 = w0
        
        self.exit.p, self.exit.t, self.exit.w = p1, t1, w1
        

class Combustor(FlowComponent):
    """
    The combustor adds heat to the flow without changing the pressure
    or mass flow. This heat addition can be expressed as a fuel-flow
    by factoring in a fuel-heating value.

    I have made no attempt to account for changes in fuel-air ratio.

    Note that we have a couple of different methods for parameterising
    the exit temperature here, either as a temperature delta across the
    combustor, or as a fixed exit temperature.

    I have added the fixed exit temperature as an option to make up for
    not having a whole-engine solver that can achieve a target turbine
    Rotor Inlet Temperature (RIT).
    """
    cname = 'combustor'
        
    def calculate(self):
        #print 'calculating combustor'
        p0,t0,w0 = self.inlet.p, self.inlet.t, self.inlet.w

        try:
            dt = self['deltaT']
            p1,t1,w1 = p0, t0+dt, w0
        except:
            t1 = self['TEX']
            p1,w1 = p0,w0
        
        self.exit.p, self.exit.t, self.exit.w = p1, t1, w1

    def fuel_flow(self):
        w0,t0,t1 = self.inlet.w, self.inlet.t, self.exit.t
        ff = w0 * cp * (t1 - t0) / self['FHV']
        return ff
        
class Nozzle(InletComponent):
    """
    The nozzle is a flow terminator. A flow enters, but no flow leaves.
    This isn't necessarily realistic but is quite sufficient for our
    purposes.

    Every nozzle that is added to the engine is kept track of and
    is queried when it comes to thrust-calculation time.
    """
    cname = 'nozzle'
      
    def connect_ambient(self, ambient):
        self.ambient = ambient
        #self.precedents.append(ambient)
        #ambient.dependents.append(self)

    def calculate(self):
        #print 'Calculating nozzle'
        p0,t0,w0 = self.inlet.p, self.inlet.t, self.inlet.w
        
        pamb = self.ambient.p
        
#        t1 = t0 * (p1/p0) ** (1-1/gamma)
        p1,t1,w1 = p0,t0,w0
        # convert available pressure into kinetic energy
        #self.vj = (cp*(t0-t1))**0.5 #WRONG!
        eta = 1.0
        npr = p0 / pamb

        #throat_mach = 1.0
        self.vj = (2*cp*t1*eta * (1 - (1/npr)**((gamma-1)/gamma)))**0.5
        self.athroat = w0 * t0**0.5 / (p0 * compressible.q_choke())
        self.throat_ps = p0 * compressible.p_P(1.0)
        

class Engine(object):
    """
    The Engine contains a single Intake and multiple Nozzles. After all of
    the Components have been calculated the Intake and Nozzles are used
    to calculate the thrust.
    """
    def __init__(self):
        self.intake = None
        self.components={}
        self.nozzles=[]
        self.fuel_entry=[]
        self.environment=Environment({'v0':0.0}, 'ambient')
        self.stations={}
        self.attributes={}
        self.components['ENGINE']=self.attributes
                
    def __setitem__(self, ident, component):
        assert not ident in self.components, 'Component idents must be unique: %s'%ident
        self.components[ident]=component
        if isinstance(component,Nozzle):
            component.connect_ambient(self.environment)
            self.nozzles.append(component)
        
        if isinstance(component,Intake):
            assert self.intake is None, 'Have already set the intake?'
            self.intake = component
            component.connect_ambient(self.environment)
                        
    def __getitem__(self, ident):
        return self.components[ident]

    def update(self):
        self.environment.make_dirty()
        self.environment.update()
        self.calculate_thrust()
        self.calculate_attributes()
    
    def calculate_thrust(self):
        thrust=0
        v0 = self.environment.v0
        for nozz in self.nozzles:
            thrust += nozz.inlet.w * (nozz.vj - v0)

        self.thrust = thrust
        self.attributes['THRUST']=thrust

    def calculate_attributes(self):
        fuel_flow = self['COMBUSTOR'].fuel_flow()
        self.attributes['FUEL_FLOW']=fuel_flow

        fn = self.attributes['THRUST']
        self.attributes['SFC'] = fuel_flow / fn
        

    def connect_intake(self, intake_ident):
        assert intake_ident in self.components
        self.components[intake_ident].connect_upstream(self.environment)
        
    def connect_flows(self, upstream_ident, downstream_ident, station_name=None):
        assert upstream_ident in self.components
        assert downstream_ident in self.components

        stn = Station(station_name)
        if station_name is not None:
            self.stations[station_name]=stn

        self.components[upstream_ident].connect_downstream(stn)
        self.components[downstream_ident].connect_upstream(stn)
        

if __name__=='__main__':
#def example2():
    engine = Engine()
    engine['INTAKE'] = Intake({'W':1.0})
    engine['FAN'] = Compressor({'PR':1.5})
    engine['COMB'] = Combustor({'deltaT':300.})
    engine['TURB'] = Turbine()
    engine['NOZ'] = Nozzle()
    engine.connect_flows('INTAKE','FAN')
    engine.connect_flows('FAN','COMB')
    engine.connect_flows('COMB','TURB')
    engine.connect_flows('TURB','NOZ')

    engine['SHAFT'] = Shaft()
    
    engine['SHAFT'].add_driven(engine['FAN'])
    engine['SHAFT'].add_turbine(engine['TURB'])
    
    env = engine.environment
    env.p, env.t, env.w = (30000.0,300.0,1.0)
    env.update()
    #    return engine 
            
def example1():
    stn0 = Station('fan inlet')
    stn1 = Station('fan exit')
    stn2 = Station('core inlet')
    stn12 = Station('bypass stream')
    stn13 = Station('cnoz exit')
    stn3 = Station('comb inlet')
    stn4 = Station('turb inlet')
    stn5 = Station('lpt inlet')
    stn6 = Station('hnozzle inlet')
    stn7 = Station('hnozzle exit')


    fan = Compressor({'PR':1.5})
    split = Splitter({'BPR':3})
    compr = Compressor({'PR':30.})
    shaft = Shaft()
    lpshft = Shaft()
    comb = Combustor({'deltaT':200.})
    turb = Turbine()
    lpt = Turbine()
    nozz = Nozzle()
    cnozz = Nozzle(name='CNOZ')
    
    fan.connect_stations(stn0,stn1)
    split.connect_stations(stn1,stn2,stn12)
    compr.connect_stations(stn2,stn3)
    comb.connect_stations(stn3,stn4)
    turb.connect_stations(stn4,stn5)
    lpt.connect_stations(stn5,stn6)
    nozz.connect_upstream(stn6)
    nozz.connect_ambient(stn0)
    cnozz.connect_upstream(stn12)
    cnozz.connect_ambient(stn0)
    
    shaft.add_driven(compr)
    shaft.add_turbine(turb)

    lpshft.add_driven(fan)
    lpshft.add_turbine(lpt)
    
    stn0.p, stn0.t, stn0.w = (30000.0,300.0,1.0)

    #We're done setting up the model - let's fire execution
    stn0.update()

def example3():
#if __name__=='__main__':
    compr = Compressor({'PR':30.})
    shaft = Shaft()
    comb = Combustor({'deltaT':200.})
    turb = Turbine()

    stn2 = Station('core inlet')
    stn3 = Station('comb inlet')
    stn4 = Station('turb inlet')
    stn5 = Station('turb exit')
    
    compr.connect_stations(stn2,stn3)
    comb.connect_stations(stn3,stn4)
    turb.connect_stations(stn4,stn5)

    shaft.add_driven(compr)
    shaft.add_turbine(turb)
    
    stn2.p, stn2.t, stn2.w = (30000.0,300.0,1.0)
    stn2.update()
        
if __name__=='__main__':
    #example2()
    #example1()
    pass
