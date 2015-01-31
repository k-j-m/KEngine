
gamma = 1.4
R = 287.0

def acrit(WRTP):
    pass

def rho_RHO(Mach):
    return (1 + (gamma-1)/2 * Mach**2)**(-1/(gamma-1))
