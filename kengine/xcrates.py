class XCTypes(object):
    ADDER = 0
    FACTOR = 1

class XRates(object):

    def __init__(self, inputs_orig, outputs_orig, xheader, xrates):
        self.inputs_orig = inputs_orig
        self.outputs_orig = outputs_orig
        self.xheader = xheader
        self.xrates = xrates

        assert set(self.xheader) == set(self.inputs_orig.keys())
    
    def calculate(self,inputs):
        # make sure that our inputs line up against our model
        assert set(inputs.keys()) == set(self.inputs_orig.keys())

        outputs = {}
        for onm,oval0 in self.outputs_orig.items():
            result = oval0
            for index, inm in enumerate(self.xheader):
                ival0 = self.inputs_orig[inm]
                ival = inputs[inm]
                xcrate = self.xrates[onm][index]
                result += xcrate * (ival - ival0)
            outputs[onm]=result
        return outputs


def get_test_xrates():
    inputs_orig = {'a':1.0,'b':10.0,'c':20.}
    outputs_orig = {'x':100.,'y':200.,'z':300.}
    
    xheader = ['a','b','c']
    xrates = {'x':[1.0, 1.3,-1.0],
                   'y':[0.5,-0.2, 0.3],
                   'z':[2.3, 1.1, 0.2]}

    xc = XRates(inputs_orig, outputs_orig, xheader, xrates)
    return xc
