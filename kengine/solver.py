import numpy as np
from numpy.linalg import tensorsolve

class Solver(object):
    def __init__(self, engine, input_settings):
        """
        input_settings is a dict containing some info for the solver
        on how to work the inputs. Example:
        {'x':{'perturbation':0.01,
              'sval':2.0},
         'y':{'perturbation':0.01,
              'sval':3.0}}

        The solver completely WRAPS the engine. This is important.
        """
        self.engine = engine
        self.input_settings = input_settings


    def __getattr__(self,attr):
        """
        Any requests that we don't understand we delegate to the engine.
        """
        return getattr(self.engine,attr)

    def solve(self, targets):
        """
        Run the engine until all of our targets are met. We first
        partition the targets into inputs that go directly into the
        model, then make sure that we have balanced inputs and outputs
        to solve, and then run the solver.

        Targets is a dict of the form:
        {'varname': target_val}
        """

        # { name: value }
        solver_targets = {}
        

        # partition inputs into direct inputs and solver targets
        for t,v in targets.iteritems():
            if t in self.engine.input_aliases:
                self.engine.set_input_alias(t,v)
            else:
                solver_targets[t]=v

        self.targets = solver_targets # NASTY HACK so that I can see the targets when I'm making the gradients
                
        isets = self.input_settings
        # check for parity in solver variables & targets
        assert len(solver_targets) == len(isets)

        # do some reshuffling of input settings to get start values
        values = dict([(x,isets[x]['sval']) for x in isets])

        iter_limit = 100
        iteration = 0
        while True: # do until converged
            print 'Iteration #%i'%iteration
            print 'values:',values
            if iteration > iter_limit:
                raise Exception('Exceeded iteration limit')
            
            # calculate some results
            results = self.engine.calculate(values)
            print 'RESULTS:'
            print results
            # calculate errors
            errors = dict([(z,(targets[z] - results[z])) for z in targets])
            print 'ERRORS:'
            print errors
            if self.isconverged(errors):
                break
            
            # iterate!
            corrections = self.next_iteration(values, errors)

            values = dict([(x,values[x]+corrections[x]) for x in values])
            
            iteration += 1
            
        return values


    def isconverged(self, errors):
        """
        Check to see whether our calculated errors are within our allowable
        limits.
        """
        #simple to start!
        conv_crit = 1e-6
        print errors
        conv_results = [abs(errors[e]) < conv_crit for e in errors]
        print conv_results
        converged = all(conv_results)
        return converged
            
    def next_iteration(self, current_values, errors):
        gradients = self.generate_jacobian(current_values)
        print 'GRADIENTS'
        print gradients
        xs = gradients.keys()
        zs = gradients[xs[0]].keys()

        jacobian_matrix = [[gradients[x][z] for x in xs] for z in zs]

        J = np.array(jacobian_matrix)
        e = np.array([errors[z] for z in zs])

#        print 'jacobian\n',J
#        print 'errors\n',e
        
        result = tensorsolve(a=J,b=e)


#        print 'corrections\n', result
        #convert back from matrix to dict

        corrections = dict([(x,result[i]) for i,x in enumerate(xs)])

        return corrections
                                                    
    def generate_jacobian(self, current_values):
        jacobian = {}

        # start with defaults
        #defaults = dict([(nm, self.engine.get_output_alias(nm)) for nm in outputs])
        defaults = self.engine.calculate(current_values)
        #defaults = {}
        #for output_name in outputs:
        #    value = self.engine.get_output_alias(output_name)
        #    defaults[output_name]=value

        # step through inputs to calculate gradients
        gradients = {}
        for input_name in current_values:
            # make the perturbation
            perturbation = self.input_settings[input_name]['perturbation']
            new_values = current_values.copy()
            new_values[input_name]=current_values[input_name]+perturbation
            
            # treat the wrapped engine as a function to make testing easier
            calcd_outputs = self.engine.calculate(new_values)
            target_names = self.targets.keys()
            gradient_row = {}
            
            # look at the outputs and calculate the gradients for each
            for output_name in target_names:
                print 'OUTPUT NAME'
                print output_name
                value = calcd_outputs[output_name]
                default = defaults[output_name]
                difference = value - default
                gradient = difference / perturbation

                gradient_row[output_name]=gradient

            gradients[input_name]=gradient_row
            
        return gradients

class TestFunction(object):
    import math
    
    def calculate(self,inputs):
        x = inputs['x']
        y = inputs['y']
        z = 3*x + 0.1*y**1.7 - 4
        zz = 5*x**3.1 - 0.1*y - 1
        return {'z':z,'zz':zz}
    


def test2():
    fn = TestFunction()
    solver = Solver(engine=fn, input_settings={'x':{'perturbation':0.01,
                                                    'sval':2.0},
                                               'y':{'perturbation':0.01,
                                                    'sval':3.0}})

#    start_vals = {'x':1.0,'y':1.0}
    targets = {'z':10., 'zz':20.}

    input_settings = {'x':{'sval':2.},
                      'y':{'sval':3.}}

    results = solver.solve(targets)

    print results
    print solver.calculate(results)

def test1():
    jacobian = solver.generate_jacobian(start_vals)

    xs = jacobian.keys()
    zs = jacobian[xs[0]].keys()

    start_results = fn.calculate(start_vals)
    errors = dict([(z,(targets[z] - start_results[z])) for z in targets])
    print errors
    
    print '\t' + '\t'.join(xs)
    for z in zs:
        row = [jacobian[x][z] for x in xs]
        print z + '\t' + '\t'.join(map(str, row))

    # I originally got the rows an cols the wrong way round - eurgh, tired.
    jacobian_matrix = [[jacobian[x][z] for x in xs] for z in zs]
    #print jacobian_matrix
        
    J = np.array([[4.0, 3.0],
                  [-2.0, 5.0]])
    
    J = np.array(jacobian_matrix)
    
    print J
    #print J.shape

    e = np.array([errors[z] for z in zs])
    print e

    #e = np.array([[-11.0],
    #             [-2.0]])

    #e = np.array([-11.,-2.0])
    #print e
    #print e.shape

    result = tensorsolve(a=J,b=e)
    print result

    next_vals = dict([(x,(start_vals[x]+result[i])) for i,x in enumerate(xs)])
    print next_vals
#    new_values = {'x': start_vals['x']-1.88461538, 'y':start_vals['y']-1.15384615}
    print fn.calculate(next_vals)

if __name__=='__main__':
    pass#test2()
