"""margin.py

Functions for computing stability margins and related functions.

Routeins in this module:

margin.stability_margins
margin.phase_crossover_frequencies
"""

# Python 3 compatibility (needs to go here)
from __future__ import print_function

"""Copyright (c) 2011 by California Institute of Technology
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions
are met:

1. Redistributions of source code must retain the above copyright
   notice, this list of conditions and the following disclaimer.

2. Redistributions in binary form must reproduce the above copyright
   notice, this list of conditions and the following disclaimer in the
   documentation and/or other materials provided with the distribution.

3. Neither the name of the California Institute of Technology nor
   the names of its contributors may be used to endorse or promote
   products derived from this software without specific prior
   written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
"AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS
FOR A PARTICULAR PURPOSE ARE DISCLAIMED.  IN NO EVENT SHALL CALTECH
OR THE CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF
USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT
OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF
SUCH DAMAGE.

Author: Richard M. Murray
Date: 14 July 2011

$Id$

"""

import numpy as np
from . import xferfcn
from .lti import issiso
from . import frdata
import scipy as sp

__all__ = ['stability_margins', 'phase_crossover_frequencies', 'margin']

# helper functions for stability_margins
def _polyimsplit(pol):
    """split a polynomial with (iw) applied into a real and an
       imaginary part with w applied"""
    rpencil = np.zeros_like(pol)
    ipencil = np.zeros_like(pol)
    rpencil[-1::-4] = 1.
    rpencil[-3::-4] = -1.
    ipencil[-2::-4] = 1.
    ipencil[-4::-4] = -1.
    return pol * rpencil, pol*ipencil

def _polysqr(pol):
    """return a polynomial squared"""
    return np.polymul(pol, pol)

# Took the framework for the old function by
# Sawyer B. Fuller <minster@caltech.edu>, removed a lot of the innards
# and replaced with analytical polynomial functions for LTI systems.
#
# idea for the frequency data solution copied/adapted from
# https://github.com/alchemyst/Skogestad-Python/blob/master/BODE.py
# Rene van Paassen <rene.vanpaassen@gmail.com>
#
# RvP, July 8, 2014, corrected to exclude phase=0 crossing for the gain
#                    margin polynomial
# RvP, July 8, 2015, augmented to calculate all phase/gain crossings with
#                    frd data. Correct to return smallest phase
#                    margin, smallest gain margin and their frequencies
def stability_margins(sysdata, returnall=False, epsw=1e-8):
    """Calculate stability margins and associated crossover frequencies.

    Parameters
    ----------
    sysdata: LTI system or (mag, phase, omega) sequence
        sys : LTI system
            Linear SISO system
        mag, phase, omega : sequence of array_like
            Arrays of magnitudes (absolute values, not dB), phases (degrees),
            and corresponding frequencies.  Crossover frequencies returned are
            in the same units as those in `omega` (e.g., rad/sec or Hz).
    returnall: bool, optional
        If true, return all margins found. If false (default), return only the
        minimum stability margins.  For frequency data or FRD systems, only one
        margin is found and returned.
    epsw: float, optional
        Frequencies below this value (default 1e-8) are considered static gain,
        and not returned as margin.

    Returns
    -------
    gm: float or array_like
        Gain margin
    pm: float or array_loke
        Phase margin
    sm: float or array_like
        Stability margin, the minimum distance from the Nyquist plot to -1
    wg: float or array_like
        Gain margin crossover frequency (where phase crosses -180 degrees)
    wp: float or array_like
        Phase margin crossover frequency (where gain crosses 0 dB)
    ws: float or array_like
        Stability margin frequency (where Nyquist plot is closest to -1)
    """

    try:
        if isinstance(sysdata, frdata.FRD):
            sys = frdata.FRD(sysdata, smooth=True)
        elif isinstance(sysdata, xferfcn.TransferFunction):
            sys = sysdata
        elif getattr(sysdata, '__iter__', False) and len(sysdata) == 3:
            mag, phase, omega = sysdata
            sys = frdata.FRD(mag * np.exp(1j * phase * np.pi/180), 
                             omega, smooth=True)
        else:
            sys = xferfcn._convertToTransferFunction(sysdata)
    except Exception as e:
        print (e)
        raise ValueError("Margin sysdata must be either a linear system or "
                         "a 3-sequence of mag, phase, omega.")

    # calculate gain of system
    if isinstance(sys, xferfcn.TransferFunction):

        # check for siso
        if not issiso(sys):
            raise ValueError("Can only do margins for SISO system")

        # real and imaginary part polynomials in omega:
        rnum, inum = _polyimsplit(sys.num[0][0])
        rden, iden = _polyimsplit(sys.den[0][0])

        # test (imaginary part of tf) == 0, for phase crossover/gain margins
        test_w_180 = np.polyadd(np.polymul(inum, rden), np.polymul(rnum, -iden))
        w_180 = np.roots(test_w_180)
        #print ('1:w_180', w_180)

        # first remove imaginary and negative frequencies, epsw removes the
        # "0" frequency for type-2 systems
        w_180 = np.real(w_180[(np.imag(w_180) == 0) * (w_180 >= epsw)])
        #print ('2:w_180', w_180)

        # evaluate response at remaining frequencies, to test for phase 180 vs 0
        resp_w_180 = np.real(np.polyval(sys.num[0][0], 1.j*w_180) /
                             np.polyval(sys.den[0][0], 1.j*w_180))
        #print ('resp_w_180', resp_w_180)                     

        # only keep frequencies where the negative real axis is crossed
        w_180 = w_180[np.real(resp_w_180) < 0.0]

        # and sort
        w_180.sort()
        #print ('3:w_180', w_180)

        # test magnitude is 1 for gain crossover/phase margins
        test_wc = np.polysub(np.polyadd(_polysqr(rnum), _polysqr(inum)),
                             np.polyadd(_polysqr(rden), _polysqr(iden)))
        wc = np.roots(test_wc)
        wc = np.real(wc[(np.imag(wc) == 0) * (wc > epsw)])
        wc.sort()

        # stability margin was a bitch to elaborate, relies on magnitude to
        # point -1, then take the derivative. Second derivative needs to be >0
        # to have a minimum
        test_wstabd = np.polyadd(_polysqr(rden), _polysqr(iden))
        test_wstabn = np.polyadd(_polysqr(np.polyadd(rnum,rden)),
                                 _polysqr(np.polyadd(inum,iden)))
        test_wstab = np.polysub(
            np.polymul(np.polyder(test_wstabn),test_wstabd),
            np.polymul(np.polyder(test_wstabd),test_wstabn))

        # find the solutions, for positive omega, and only real ones
        wstab = np.roots(test_wstab)
        #print('wstabr', wstab)
        wstab = np.real(wstab[(np.imag(wstab) == 0) * 
                        (np.real(wstab) >= 0)])
        #print('wstab', wstab)

        # and find the value of the 2nd derivative there, needs to be positive
        wstabplus = np.polyval(np.polyder(test_wstab), wstab)
        #print('wstabplus', wstabplus)
        wstab = np.real(wstab[(np.imag(wstab) == 0) * (wstab > epsw) *
                              (wstabplus > 0.)])
        #print('wstab', wstab)
        wstab.sort()

    else:
        # a bit coarse, have the interpolated frd evaluated again
        def mod(w):
            """to give the function to calculate |G(jw)| = 1"""
            return np.abs(sys.evalfr(w)[0][0]) - 1

        def arg(w):
            """function to calculate the phase angle at -180 deg"""
            return np.angle(-sys.evalfr(w)[0][0])

        def dstab(w):
            """function to calculate the distance from -1 point"""
            return np.abs(sys.evalfr(w)[0][0] + 1.)

        # Find all crossings, note that this depends on omega having
        # a correct range
        widx = np.where(np.diff(np.sign(mod(sys.omega))))[0]
        wc = np.array(
            [ sp.optimize.brentq(mod, sys.omega[i], sys.omega[i+1])
              for i in widx if i+1 < len(sys.omega)])
        
        # find the phase crossings ang(H(jw) == -180
        widx = np.where(np.diff(np.sign(arg(sys.omega))))[0]
        #print('widx (180)', widx, sys.omega[widx])
        #print('x', sys.evalfr(sys.omega[widx])[0][0])
        widx = widx[np.real(sys.evalfr(sys.omega[widx])[0][0]) <= 0]
        #print('widx (180,2)', widx)
        w_180 = np.array(
            [ sp.optimize.brentq(arg, sys.omega[i], sys.omega[i+1])
              for i in widx if i+1 < len(sys.omega) ])
        #print('x', sys.evalfr(w_180)[0][0])
        #print('w_180', w_180)

        # find all stab margins?
        widx = np.where(np.diff(np.sign(np.diff(dstab(sys.omega)))))[0]
        #print('widx', widx)
        #print('wstabx', sys.omega[widx])
        wstab = np.array([ sp.optimize.minimize_scalar(
                  dstab, bracket=(sys.omega[i], sys.omega[i+1])).x
              for i in widx if i+1 < len(sys.omega) and
              np.diff(np.diff(dstab(sys.omega[i-1:i+2])))[0] > 0 ])
        #print('wstabf0', wstab)
        wstab = wstab[(wstab >= sys.omega[0]) * 
                      (wstab <= sys.omega[-1])]
        #print ('wstabf', wstab)
        

    # margins, as iterables, converted frdata and xferfcn calculations to
    # vector for this
    GM = 1/np.abs(sys.evalfr(w_180)[0][0])
    SM = np.abs(sys.evalfr(wstab)[0][0]+1)
    PM = np.angle(sys.evalfr(wc)[0][0], deg=True) + 180
    
    if returnall:
        return GM, PM, SM, w_180, wc, wstab
    else:
        return (
            (GM.shape[0] or None) and np.amin(GM),
            (PM.shape[0] or None) and np.amin(PM),
            (SM.shape[0] or None) and np.amin(SM),
            (w_180.shape[0] or None) and w_180[GM==np.amin(GM)][0],
            (wc.shape[0] or None) and wc[PM==np.amin(PM)][0],
            (wstab.shape[0] or None) and wstab[SM==np.amin(SM)][0])


# Contributed by Steffen Waldherr <waldherr@ist.uni-stuttgart.de>
#! TODO - need to add test functions
def phase_crossover_frequencies(sys):
    """
    Compute frequencies and gains at intersections with real axis
    in Nyquist plot.

    Call as:
        omega, gain = phase_crossover_frequencies()

    Returns
    -------
    omega: 1d array of (non-negative) frequencies where Nyquist plot
    intersects the real axis

    gain: 1d array of corresponding gains

    Examples
    --------
    >>> tf = TransferFunction([1], [1, 2, 3, 4])
    >>> PhaseCrossoverFrequenies(tf)
    (array([ 1.73205081,  0.        ]), array([-0.5 ,  0.25]))
    """

    # Convert to a transfer function
    tf = xferfcn._convertToTransferFunction(sys)

    # if not siso, fall back to (0,0) element
    #! TODO: should add a check and warning here
    num = tf.num[0][0]
    den = tf.den[0][0]

    # Compute frequencies that we cross over the real axis
    numj = (1.j)**np.arange(len(num)-1,-1,-1)*num
    denj = (-1.j)**np.arange(len(den)-1,-1,-1)*den
    allfreq = np.roots(np.imag(np.polymul(numj,denj)))
    realfreq = np.real(allfreq[np.isreal(allfreq)])
    realposfreq = realfreq[realfreq >= 0.]

    # using real() to avoid rounding errors and results like 1+0j
    # it would be nice to have a vectorized version of self.evalfr here
    gain = np.real(np.asarray([tf.evalfr(f)[0][0] for f in realposfreq]))

    return realposfreq, gain


def margin(*args):
    """Calculate gain and phase margins and associated crossover frequencies

    Parameters
    ----------
    sysdata: LTI system or (mag, phase, omega) sequence
        sys : StateSpace or TransferFunction
            Linear SISO system
        mag, phase, omega : sequence of array_like
            Input magnitude, phase (in deg.), and frequencies (rad/sec) from
            bode frequency response data

    Returns
    -------
    gm : float
        Gain margin
    pm : float
        Phase margin (in degrees)
    Wcg : float
        Gain crossover frequency (corresponding to phase margin)
    Wcp : float
        Phase crossover frequency (corresponding to gain margin) (in rad/sec)
        
   Margins are of SISO open-loop. If more than one crossover frequency is
   detected, returns the lowest corresponding margin.

    Examples
    --------
    >>> sys = tf(1, [1, 2, 1, 0])
    >>> gm, pm, Wcg, Wcp = margin(sys)

    """
    if len(args) == 1:
        sys = args[0]
        margin = stability_margins(sys)
    elif len(args) == 3:
        margin = stability_margins(args)
    else:
        raise ValueError("Margin needs 1 or 3 arguments; received %i."
            % len(args))

    return margin[0], margin[1], margin[3], margin[4]
