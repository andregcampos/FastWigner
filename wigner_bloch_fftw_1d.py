from wigner_moyal_fftw_1d import WignerMoyalFTTW1D
from types import MethodType
import numpy as np


class WignerBlochFFTW1D(WignerMoyalFTTW1D):
    """
    Find the Wigner function of the Maxwell-Gibbs canonical state [rho = exp(-H/kT)]
    by second-order split-operator propagation of the Bloch equation in phase space.
    The Hamiltonian should be of the form H = K(p) + V(x).

    This implementation is based on the algorithm described in
        D. I Bondar, A. G. Campos, R. Cabrera, H. A. Rabitz, arXiv:1602.07288
    """
    def __init__(self, **kwargs):
        """
        In addition to kwagrs of WignerMoyalFTTW1D.__init__ this constructor accepts:

        kT - the temperature for the Gibbs state [rho = exp(-H/kT)]
        dbeta (optional) -  inverse temperature increments for the split-operator propagation
        """
        try:
            self.kT = kwargs['kT']
        except KeyError:
            raise AttributeError("Temperature (kT) was not specified")

        if self.kT > 0:
            try:
                self.dbeta = kwargs['dbeta']
            except KeyError:
                # if dbeta is not defined, just choose some value
                self.dbeta = 0.01

            # get number of dbeta steps to reach the desired Gibbs state
            self.num_beta_steps = 1. / (self.kT*self.dbeta)

            if round(self.num_beta_steps) <> self.num_beta_steps:
                # Changing self.dbeta so that num_beta_steps is an exact integer
                self.num_beta_steps = round(self.num_beta_steps)
                self.dbeta = 1. / (self.kT*self.num_beta_steps)

            self.num_beta_steps = int(self.num_beta_steps)

        else:
            raise NotImplemented("The calculation of the ground state Wigner function has not been implemented")

        # Save the inverse temperature increment also dbeta takes the form of dt
        kwargs.update(dbeta=self.dbeta, dt=self.dbeta)

        # Initialize parent class
        WignerMoyalFTTW1D.__init__(self, **kwargs)

        # Make sure the Ehrenfest theorems are not calculated
        self.isEhrenfest = False

        ##########################################################################################
        #
        # Re-assign the exponents
        #
        ##########################################################################################

        # To find the Gibbs state, the Hamiltonian must be time independent.
        # If it is not, then take the Hamiltonian at the current time self.t

        try:
            self._expV = self.V(self.X - 0.5 * self.Theta) + self.V(self.X + 0.5 * self.Theta)
        except TypeError:
            print(
                "Warning: The potential energy is time dependent. " +
                "The Gibbs state will be calculated with respect to time t = %f." % self.t
            )
            self._expV = self.V(self.X - 0.5 * self.Theta, self.t) + self.V(self.X + 0.5 * self.Theta, self.t)

        self._expV -= self._expV.min()
        self._expV *= -self.dbeta * 0.5
        np.exp(self._expV, out=self._expV)

        # Apply absorbing boundary
        self._expV *= self.abs_boundary

        # Dynamically assign the method self.get_exp_v(t) to access the cached exponential
        self.get_exp_v = MethodType(lambda self, t: self._expV, self, self.__class__)

        ##########################################################################################

        try:
            self._expK = self.K(self.P + 0.5 * self.Lambda) + self.K(self.P - 0.5 * self.Lambda)
        except TypeError:
            print(
                "Warning: The kinetic energy is time dependent. " +
                "The Gibbs state will be calculated with respect to time t = %f." % self.t
            )
            self._expK = self.K(self.P + 0.5 * self.Lambda, self.t) + self.K(self.P - 0.5 * self.Lambda, self.t)

        self._expK -= self._expK.min()
        self._expK *= -self.dbeta
        np.exp(self._expK, out=self._expK)

        # Dynamically assign the method self.get_exp_k(t) to access the cached exponential
        self.get_exp_k = MethodType(lambda self, t: self._expK, self, self.__class__)

    def get_gibbs_state(self):
        """
        Calculate the Boltzmann-Gibbs state and save it in self.wignerfunction
        :return: Boltzmann-Gibbs state
        """
        # Set the initial state and propagate
        self.set_wignerfunction(lambda _, x, p: 0*x + 0*p + 1.)
        return self.propagate(self.num_beta_steps)

##########################################################################################
#
# Example
#
##########################################################################################

if __name__ == '__main__':

    print(WignerBlochFFTW1D.__doc__)

    import matplotlib.pyplot as plt

    # parameters for the quantum system
    params = dict(
        t=0,
        dt=0.01,
        X_gridDIM=512,
        X_amplitude=10.,
        P_gridDIM=512,
        P_amplitude=10,

        # Temperature of the initial state
        kT=np.random.uniform(0.1, 1.),

        # randomized parameter
        omega=np.random.uniform(0.5, 2.),

        # parameter controlling the width of the initial wigner function
        sigma=np.random.uniform(0.5, 4.),

        # kinetic energy part of the hamiltonian
        K=lambda _, p: 0.5 * p ** 2,

        # potential energy part of the hamiltonian
        V=lambda self, x: 0.5 * self.omega**2 * x ** 2,

        # these functions are used for evaluating the Ehrenfest theorems
        diff_K=lambda _, p: p,
        diff_V=lambda self, x: self.omega**2 * x,

        # Exact analytical expression for the harmonic oscillator Gibbs state
        get_exact_gibbs=lambda self: np.tanh(0.5 * self.omega / self.kT) / np.pi * np.exp(
            -2. * np.tanh(0.5 * self.omega / self.kT) * (self.K(self.P) + self.V(self.X)) / self.omega
        )
    )

    print("Calculating the Gibbs state...")
    gibbs_state = WignerBlochFFTW1D(**params).get_gibbs_state()

    print("Check that the obtained Gibbs state is stationary under the Wigner-Moyal propagation...")
    propagator = WignerMoyalFTTW1D(**params)
    final_state = propagator.set_wignerfunction(gibbs_state).propagate(3000)

    exact_gibbs = propagator.get_exact_gibbs()
    print(
        "\nIninity norm between analytical and numerical Gibbs states = %.2e ." %
        (np.linalg.norm(exact_gibbs.reshape(-1) - gibbs_state.reshape(-1), np.inf) * propagator.dX * propagator.dP)
    )

    ##########################################################################################
    #
    #   Plot the results
    #
    ##########################################################################################

    from wigner_normalize import WignerSymLogNorm

    # save common plotting parameters
    plot_params = dict(
        origin='lower',
        extent=[propagator.X.min(), propagator.X.max(), propagator.P.min(), propagator.P.max()],
        cmap='seismic',
        # make a logarithmic color plot (see, e.g., http://matplotlib.org/users/colormapnorms.html)
        norm=WignerSymLogNorm(linthresh=1e-14, vmin=-0.01, vmax=0.1)
    )
    plt.subplot(131)

    plt.title("The Gibbs state (initial state)")
    plt.imshow(gibbs_state, **plot_params)
    plt.colorbar()
    plt.xlabel('$x$ (a.u.)')
    plt.ylabel('$p$ (a.u.)')

    plt.subplot(132)

    plt.title("The exact Gibbs state")
    plt.imshow(exact_gibbs, **plot_params)
    plt.colorbar()
    plt.xlabel('$x$ (a.u.)')
    plt.ylabel('$p$ (a.u.)')

    plt.subplot(133)

    plt.title("The Gibbs state after propagation")
    plt.imshow(final_state, **plot_params)
    plt.colorbar()
    plt.xlabel('$x$ (a.u.)')
    plt.ylabel('$p$ (a.u.)')

    plt.show()