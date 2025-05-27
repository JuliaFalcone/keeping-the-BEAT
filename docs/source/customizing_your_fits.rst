Customizing your fits
==========================
*Contributors: Julia Falcone,  Dzhuliya Dashtamirova*

At this point, you should be able to run the example BEAT code in a way that produces an output folder with plots, as shown on the previous page. However, there are a lot of parameters that we see in the code! This page will define these parameters, and you can observe how the example fits change depending on any adjustments to the parameters.

In the ``main()`` function, there are three subsections of parameters: ``target_param``, ``cont_instructions``, and ``fit_instructions``. 

target_param
------------

.. list-table:: 
   :header-rows: 1
   :class: tight-table

   * - Parameter name
     - Description
   * - ``name``
     - Name of your target (in string format)
   * - ``red``
     - Redshift of your target
   * - ``minwidth``
     - The minimum Gaussian sigma value to be fit to features. See [a] below for more details on units.
   * - ``maxwidth``
     - The minimum Gaussian sigma value to be fit to features. This value should be set to the maximum width expected in the spectra. Emission-line gas in the example spectra likely does not exceed FWHM = 2000 km/s, so we will use that to define the maximum width. See [a] below for more details on units.
   * - ``start``
     - Minimum array value used in input spectrum
   * - ``fluxsigma``
     - Minimum S/N value. The flux height must be greater than this value multiplied by the standard deviation to be considered a legitimate fit. This value is typically 3. 
   * - ``plotmin``
     - The x-axis minimum wavelength in output plots, in units of Angstroms
   * - ``plotmax``
     - The x-axis maximum wavelength in output plots, in units of Angstroms
   * - ``maxcomp``
     - The maximum number of Gaussian components that can be attempted per line. This is often 3, and can go as high as 5 or 6 (but will run very slowly). However, BEAT will stop fitting when a more complex model is less likely than a simpler model (e.g. when using 2 components is a less likely fit than 1 component). Thus, even if we set a maxcomp value of 6, the routine will likely only fit up to 3 components per spectrum.
   * - ``lnz``
     - Minimum acceptable logarithm of the ratio of Bayesian evidences. This should usually be 5. See Feroz et al. 2011 and Section 3.1 of Falcone et al. 2024 for more information on ln(z). 
   * - ``cores``
     - Number of processors that are free to be assigned to multiprocessing pool. Currently, personal laptops usually have 4 processors, so try changing cores to 2 and note the difference in time it takes to finish fitting the spectra. Always allow one free processor to continue using your computer!   
       

[a] The units for the minwidth and maxwidth paramters are in sigma (will need to change this)
    

cont_instructions
------------
In BEAT, we measure the height of the emission lines against a continuum region. We manually define the continuum by choosing two regions slightly above and below the lines we wish to observe. In the example fits on the previous page, the continuum regions are shown as gray shaded regions on either side of the fitted lines, and are intended to be areas of low emission. The continuum fit, which is marked on the output plots as a dark  
