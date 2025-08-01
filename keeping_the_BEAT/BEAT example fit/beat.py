import matplotlib
matplotlib.use('agg')
import matplotlib.pyplot as plt
import pymultinest
import multiprocessing as mp
import numpy as np
import pandas as pd
import os
import glob
import numpy
import shutil
from scipy.optimize import curve_fit
from scipy.stats import norm

class Fit(object):
    """ Fit gaussian component(s) to specified emission line(s) for a number of pixel/spaxel.
        Parameters
        ----------
        out_dir : str
            The path where to put output catalog and plots
        spec_dir : str
            Path to spectra text files
        load_file : function
            User defined function that takes the path to a spectra text file (of a single pixel/spaxel) and returns
            row, column, wave, flux, and noise. Wave, flux, noise are used for fitting while row and column are used
            for naming output data and files
        fit_instructions : dict
            Dictionary that contains information for line(s) to be fit, fitting preferences, and general target
            and plotting information
        target_param : dict
            Dictionary that contains information general target information, fitting preferences and plotting info
    """

    def __init__(self, out_dir, spec_dir, load_file, target_param, make_dirs, fit_instructions, cont_instructions=None,
                 prefit_instructions=None, save_NLR_removed = False):
        self.basepath = out_dir
        self.specpath = spec_dir
        self.load_file = load_file
        self.target_param = target_param
        self.newfolder = make_dirs
        self.fit_instructions = fit_instructions
        self.cont_instructions = cont_instructions
        self.prefit_instructions = prefit_instructions
        self.save_NLR_removed = save_NLR_removed
        self.cat = None
        self.counter = 0
        self.listing = np.array(sorted(os.listdir(self.specpath)))
        self.listing = self.listing[self.listing != '.DS_Store']
        #print('listing: ',self.listing)
        self.free_lines = sum(self.fit_instructions[line]['flux_free'] is True for line in self.fit_instructions)
        if self.prefit_instructions is not None:
            self.known_comps = self.prefit_instructions.copy()
            self.known_comps.pop('flux')
            self.prefit_free_lines = sum(
                self.known_comps[line]['flux_free'] is True for line in self.known_comps)
            self.prefit_num_lines = len(self.known_comps)
        else:
            self.prefit_free_lines = 0
            self.prefit_num_lines = 0
        self.make_dirs()
        self.ordered_cube = []
        self.cubeaslist_global = 0

        self.start = 0 #np.argmin(np.abs(wave-self.target_param["plotmin"]))
        self.end = 0 #np.argmin(np.abs(wave-self.target_param["plotmax"]))

    def make_dirs(self):
        """make directory structure for output data"""
        #self.counter = 0

        if self.newfolder == 'make_new':
 
	        while os.path.exists(os.path.join(self.basepath, f'{self.target_param["name"]}_out_'+ str(self.counter))):
	        	self.counter +=1

	        if not os.path.exists(os.path.join(self.basepath, f'{self.target_param["name"]}_out_'+str(self.counter))):
	            os.mkdir(os.path.join(self.basepath, f'{self.target_param["name"]}_out_'+ str(self.counter)))

	        if (self.save_NLR_removed):
	            if not os.path.exists(os.path.join(self.basepath, f'{self.target_param["name"]}_out_'+ str(self.counter), 'NLR_removed')):
	                os.mkdir(os.path.join(self.basepath, f'{self.target_param["name"]}_out_'+ str(self.counter), 'NLR_removed'))

	        if not os.path.exists(os.path.join(self.basepath, f'{self.target_param["name"]}_out_'+ str(self.counter), 'out')):
	            os.mkdir(os.path.join(self.basepath, f'{self.target_param["name"]}_out_'+ str(self.counter), 'out'))

	        if not os.path.exists(os.path.join(self.basepath, f'{self.target_param["name"]}_out_'+ str(self.counter), 'plots')):
	            os.mkdir(os.path.join(self.basepath, f'{self.target_param["name"]}_out_'+ str(self.counter), 'plots'))

	        if not os.path.exists(os.path.join(self.basepath, f'{self.target_param["name"]}_out_'+ str(self.counter),
	                                           f'{self.target_param["name"]}_{self.fit_instructions["line1"]["name"]}.txt')):
	            self.init_cat()

        elif self.newfolder == 'replace':
	        
	        while os.path.exists(os.path.join(self.basepath, f'{self.target_param["name"]}_out_'+ str(self.counter))):
	        	self.counter +=1

	       	self.counter -=1

	       	if os.path.exists(os.path.join(self.basepath, f'{self.target_param["name"]}_out_'+str(self.counter))):
	            shutil.rmtree(os.path.join(self.basepath, f'{self.target_param["name"]}_out_'+ str(self.counter)))
	        
	        os.mkdir(os.path.join(self.basepath, f'{self.target_param["name"]}_out_'+ str(self.counter)))
	        
	        if (self.save_NLR_removed):
	        	os.mkdir(os.path.join(self.basepath, f'{self.target_param["name"]}_out_'+ str(self.counter), 'NLR_removed'))
	        os.mkdir(os.path.join(self.basepath, f'{self.target_param["name"]}_out_'+ str(self.counter), 'out'))
	        os.mkdir(os.path.join(self.basepath, f'{self.target_param["name"]}_out_'+ str(self.counter), 'plots'))
	        self.init_cat()



    # ____#
    def make_gaussian(self, mu, sigma, flux):
        """ centroid, width, integrated flux"""
        h = flux / (sigma * np.sqrt(2 * np.pi))
        s = -1.0 / (2 * sigma ** 2)

        def f(x):
            return h * np.exp(s * (x - mu) ** 2)
        return f


    def gauss(self, pos1, width1, *args):
        """"""
        pos_all = []
        flux_all = []
        lines = []

        args = list(args)
        for line in self.fit_instructions:
            lines.append(line)  # keeping track of what lines have been fit
            pos = (pos1 - ((1 + self.target_param['red']) * (self.fit_instructions['line1']['wave']
                                                             - self.fit_instructions[line]['wave'])))
            pos_all.append(pos)
            if self.fit_instructions[line]['flux_free'] is True:
                flux = args[0]  # get the argument
                flux_all.append(flux)
                args.pop(0)
            else:
                line_lock = self.fit_instructions[line]['locked_with']
                ratio = self.fit_instructions[line]['flux_ratio']
                flux_lock = flux_all[lines.index(line_lock)]
                flux = flux_lock / ratio
                flux_all.append(flux)

        all_gauss_functions = [0] * len(x)  # global variable at end
        for i in range(0, len(self.fit_instructions)):
            pos = pos_all[i]
            flux = flux_all[i]
            gauss_hold = self.make_gaussian(pos, width1, flux)
            all_gauss_functions += gauss_hold(x)
        
        #print(pos)

        return all_gauss_functions


    def gauss_cont(self, pos1, width1, *args):
        #print('made it here')                                   
        pos_all = []
        width_all = []
        flux_all = []
        lines = []
        args = list(args)

        for line in self.known_comps:
            #print('known comps: ', self.known_comps[line])
            lines.append(line)  # keeping track of what lines have been fit
            pos = self.known_comps[line]['cen']
            pos_all.append(pos)
            width = self.known_comps[line]['width']
            width_all.append(width)
            if self.known_comps[line]['flux_free'] is True:
                flux = args[0]  # get the argument
                flux_all.append(flux)
                args.pop(0)
            else:
                line_lock = self.known_comps[line]['locked_with']
                ratio = self.known_comps[line]['flux_ratio']
                flux_lock = flux_all[lines.index(line_lock)]
                flux = flux_lock / ratio
                flux_all.append(flux)

        all_gauss_functions = [0] * len(x)  # global variable at end
        for i in range(0, len(self.known_comps)):
            pos = pos_all[i]
            flux = flux_all[i]
            width = width_all[i]
            #print('broad params: ',pos, width, flux)
            gauss_hold = self.make_gaussian(pos, width, flux)
            all_gauss_functions += gauss_hold(x)
        return all_gauss_functions

    def prior(self, cube, ndim, nparams):
        """if ((ndim != 1) and (ndim % (2 + self.free_lines) != 0)) or (ndim <= 0): # 3 or 2 + free_lines
            raise ValueError(
                ('The number of dimensions must be positive and equal to '            figure this stuff out later
                 f'1 or a multiple of {2 + self.free_lines}. ndim={ndim}'))"""
        #print(self.free_lines)
        if ndim == 1:
            cube[0] = 0.
        else:
            if self.prefit_free_lines > 0:
                for i in range(0, self.prefit_num_lines):

                    # uniform wavelength prior
                    cube[i * 3] = (self.prefit_instructions[f'comp{i + 1}']['cen'])


                    # uniform width prior
                    cube[i * 3 + 1] = (self.prefit_instructions[f'comp{i + 1}']['width'])

                    # log-uniform flux prior
                    cube[i * 3 + 2] = ((stdev / 10) * cube[i * 3 + 1] * np.sqrt(2 * np.pi) *
                                       np.power(10, cube[i * 3 + 2] * 4))

            #print('range: ',range(self.prefit_num_lines * 3, ndim, 2 + self.free_lines))
            for i in range(self.prefit_num_lines * 3, ndim, 2 + self.free_lines):
                # uniform wavelength prior
                cube[i + 0] = self.fit_instructions['line1']['minwave'] + (cube[i + 0] * self.fit_instructions['line1']['wave_range'])
                #print('cube: ', cube[i+0])

                # uniform width prior
                cube[i + 1] = (self.target_param['minwidth']
                               + (cube[i + 1] * (self.target_param['maxwidth'] - self.target_param['minwidth'])))

                # log-uniform flux prior
                for fprior in range(0, self.free_lines):
                    cube[i + fprior + 2] = threesigma * cube[i + 1] * np.sqrt(2 * np.pi) * np.power(10, cube[
                        i + fprior + 2] * 4)
        #print('c0: ',cube[0], 'c1: ',cube[1], 'c2: ', cube[2], 'c3: ', cube[3], 'c4: ',cube[4], 'c5: ',cube[5], 'c6: ', cube[6], 'c7: ', cube[7])

        #cube_sorted = sorted([cube[i:i + 2+self.free_lines] for i in range(0, ndim, 2+self.free_lines)])

        #cube = []

        #for sublist in cube_sorted:
        #     for item in sublist:
        #         cube.append(item)
        
        #self.ordered_cube = cube

        #print(cube)


    def model(self, *args):
        nargs = len(args)
        #print(args)

        args_per_comp = 2 + self.prefit_free_lines #the 2 is for the centroid and the width

        """if ((nargs != 1) and (nargs % (2 + self.free_lines) != 0)) or (nargs <= 0):
            raise ValueError(
                ('The number of arguments must be positive and equal to '
                 f'1 or a multiple of 3. nargs={nargs}'))"""
        if nargs == 1:
            result = np.zeros(self.end - self.start) + avg#np.zeros(self.target_param['end'] - self.target_param['start']) + avg #args[0]
        else:
            result = np.zeros(self.end - self.start) + avg#np.zeros(self.target_param['end'] - self.target_param['start']) + avg

            for i in range(0, self.prefit_num_lines * 3, 2 + self.prefit_free_lines):
                result += self.gauss_cont(*args[i:(i + (2 + self.prefit_free_lines))])
            for i in range(self.prefit_num_lines * 3, nargs, 2 + self.free_lines):
                result += self.gauss(*args[i:(i + (2 + self.free_lines))])

        return result

    def model2(self, *args):
        nargs = len(args)
        #print(args)
        """if ((nargs != 1) and (nargs % (2 + self.free_lines) != 0)) or (nargs <= 0):
            raise ValueError(
                ('The number of arguments must be positive and equal to '
                 f'1 or a multiple of 3. nargs={nargs}'))"""
        if nargs == 1:
            result = np.zeros(self.end - self.start) + args[0]#np.zeros(self.target_param['end'] - self.target_param['start']) + args[0]
        else:
            result = np.zeros(self.end - self.start) + avg#np.zeros(self.target_param['end'] - self.target_param['start']) + avg
            for i in range(0, nargs, 2 + self.free_lines):
                result += self.gauss(*args[i:(i + (2 + self.free_lines))])
        return result

    def model3(self, *args):
        nargs = len(args)
        if nargs == 1:
            result = np.zeros(self.end - self.start) + args[0] #np.zeros(self.target_param['end'] - self.target_param['start']) + args[0]
        else:
            result = np.zeros(self.end - self.start) + avg #np.zeros(self.target_param['end'] - self.target_param['start']) + avg
            for i in range(0, nargs, 2 + self.prefit_free_lines):
                result += self.gauss_cont(*args[i:(i + (2 + self.prefit_free_lines))])
        #popt,pcov = curve_fit(self.make_gaussian,x, result)
        #print(popt)
        #print(result)
        return result

    def loglike(self, cube, ndim, nparams):
        #self.prior(cube, ndim, nparams)
        #print(self.ordered_cube)
        #print(cube)

        # if (ndim > 1):
	       #  cube_sorted = sorted([cube[i:i + 2+self.free_lines] for i in range(0, ndim, 2+self.free_lines)])

	       #  cubeaslist = []

	       #  for sublist in cube_sorted:
	       #       for item in sublist:
	       #           cubeaslist.append(item)
        # else:

        #print(ndim)
        cubeaslist = [cube[i] for i in range(ndim)]
        #cubeaslist = self.ordered_cube#[cube[i] for i in range(ndim)]
        #print(cubeaslist)
        ymodel = self.model(*cubeaslist)
        #print(ymodel)
        loglikelihood = -0.5 * (((ymodel - ydata) / noise) ** 2).sum()

        return loglikelihood

    #___________#

    def write_results(self, filename, ncomp, outmodel, modelsigma):
        #print("write results: ncomp, outmodel, broad_params, modelsigma")
        #print(ncomp)
        #print(outmodel)
        #print(modelsigma)
        cat_file = os.path.join(self.basepath, f'{self.target_param["name"]}_out_'+str(self.counter), f'{self.target_param["name"]}_'
                                               f'{self.fit_instructions["line1"]["name"]}.txt')
        cat = pd.read_csv(cat_file, index_col='index')


        use_col = cat.columns[2:len(outmodel[3 * self.prefit_num_lines:]) + 2].tolist()
        #print('filename is ',cat)
        for i, mod in enumerate(outmodel[3 * self.prefit_num_lines:]):
            cat.loc[cat['filename'] == filename, use_col[i]] = mod
            # cat.at[filename, use_col[i]] = mod
            

        sigma_col = cat.columns[cat.columns.str.endswith('sigma')].tolist()
        for i, sig in enumerate(modelsigma[3 * self.prefit_num_lines:]):
            cat.loc[cat['filename'] == filename, sigma_col[i]] = sig

        cat.loc[cat['filename'] == filename, 'ncomps'] = ncomp

        #print('filename', cat)
        cat.to_csv(cat_file, index_label='index', float_format='%.3e')




    def make_model_plot(self, ncomp, outmodel, loglike, filename, goodfit = False):
        colorlist = ['goldenrod', 'plum', 'teal', 'firebrick', 'darkorange']

        plt.rcParams["font.family"] = "STIXGeneral"
        plt.rcParams["mathtext.fontset"] = "stix"
        plt.rcParams["font.size"]       = 14
        fig, ax = plt.subplots()
        ax.set_xlim(self.target_param["plotmin"], self.target_param["plotmax"])
        ax.set_ylim(miny - ypadding, maxy + ypadding)
        ax.text(0.25, 0.95, f'ln(Z) = {loglike:.2f}', transform=ax.transAxes)
        #print(x, ydata)
        ax.plot(x, ydata, '-', lw=1, color='0.75', label='data', zorder=1)
        print('components: ', ncomp)
        #for i in range(len(x)):
        #    print(x[i], ',', ydata[i])
        # for 0 or 1 components, plot noise
        if (ncomp == 0) or (ncomp == 1):
            ax.plot(x, noise, '-', color='red', zorder=1)

        ax.axvline(systemic, 0, 1, ls='--', lw=0.5, color='blue')

        ax.axvspan(self.cont_instructions["continuum1"][0], self.cont_instructions["continuum1"][1], facecolor='black',
                   alpha=0.1)
        ax.axvspan(self.cont_instructions["continuum2"][0], self.cont_instructions["continuum2"][1], facecolor='black',
                   alpha=0.1)

        # Plot the best fit model.
        ax.plot(x, self.model(*outmodel), '-', lw=1, color='black', label='model',    zorder=3)
        ax.plot(x, avg, lw=1, color='green', label='model', zorder=3)

        model_fit = self.model3(*outmodel[0: 3 * self.prefit_num_lines])
        ax.plot(x, model_fit, '-', lw=0.75, color="olive",zorder=2)

        #print(model_fit)
        #mean,std=norm.fit(model_fit)
        #print(mean, 6*std)
        #y_test = norm.pdf(x, mean, std)
        #ax.plot(x, y_test, color = 'purple')
        #print(x)


        if ncomp > 0:
            f = lambda x, mu, sigma, flux: self.make_gaussian(mu, sigma, flux)(x)


            avg_true = np.average(avg)
            #print("avg: {:e}".format(model_fit[330:600]-avg_true))
            #print(model_fit[330:600]-avg_true)

            #### FOR KOSMOS H-BETA ###
            #popt,pcov = curve_fit(f, x, model_fit-avg_true, p0=[4872, 15, 7e-14])

            #### FOR KOSMOS H-ALPHA ###
            # popt,pcov = curve_fit(f, x, model_fit-avg_true, p0=[6563, 15, 7e-14])

            # #ax.plot(x, f(x, popt[0], popt[1], popt[2])+avg_true, color = 'purple')
            # infile = filename
            # inspecpath = os.path.join(self.specpath, infile)
            # #print(inspecpath)
            # infilebase = infile.split('.')[0]
            # print('broad profile: ', popt)


            # if not os.path.exists(os.path.join(self.basepath, f'{self.target_param["name"]}_out', 'broad')):
            # 	os.mkdir(os.path.join(self.basepath, f'{self.target_param["name"]}_out', 'broad'))

            # broad_outfile = os.path.join(self.basepath, f'{self.target_param["name"]}_out', 'broad',
            #                             f'{infilebase}_{self.fit_instructions["line1"]["name"]}')
            # np.savetxt(broad_outfile+ 'broad.csv',popt.reshape(1, popt.shape[0]), delimiter = ',')

        #if ncomp > 1:
            # fix the numbers here for slices of outmodel
        
        
        data_deblended = ydata

        for i in range(3 * self.prefit_num_lines, ((2 + self.free_lines) * ncomp) + (3 * self.prefit_num_lines),
                       (2 + self.free_lines)):
            color = colorlist[(i // self.target_param["maxcomp"]) % (len(colorlist))]
            ax.plot(x, self.model2(*outmodel[i:(i + 2 + self.free_lines)]), '-', lw=0.75, color=color,zorder=2)
            y_plot = self.model2(*outmodel[i:(i + 2 + self.free_lines)])
            data_deblended = data_deblended - (y_plot - avg)

        from astropy.table import Table 
        deblended_cols = Table((x, data_deblended, noise), names = ('wave', 'flux', 'noise'))
        #print(deblended_cols)

        infile = filename
        infilebase = infile.split('.')[0]
        deblended_outfile = os.path.join(self.basepath, f'{self.target_param["name"]}_out_'+str(self.counter), 'NLR_removed',
                                        f'{infilebase}_{self.fit_instructions["line1"]["name"]}_NLRremoved')
        if (self.save_NLR_removed):
            np.savetxt(deblended_outfile+ '.txt',deblended_cols, delimiter = ',', header = 'wavelength, flux, noise')
        #print('here now')
        #print(self.model2(*outmodel[i:(i + 2 + self.free_lines)]))

        ax.set_title(f'{filename} -- {ncomp} Components')
        ax.set_xlabel('Wavelength ($\mathrm{\AA}$)')
        ax.set_ylabel('Flux (erg s$^{-1}$ cm$^{-2}\ \mathrm{\AA}^{-1}}$)')
        fig.savefig(plot_outfile + f'_{ncomp}_posterior.pdf', bbox_inches='tight')
        plt.close()

    def init_cat(self):
        """Blank output catalog"""
        cols = ["index", "filename", "ncomps"]
        for i in range(1, self.target_param["maxcomp"] + 1):
            cols.append(f'wave_{i}')
            cols.append(f'width_{i}')
            for flux in range(1, self.free_lines + 1):
                cols.append(f'flux_{i}_{chr(ord("@") + flux)}')

        for i in range(1, self.target_param["maxcomp"] + 1):
            cols.append(f'wave_{i}_sigma')
            cols.append(f'width_{i}_sigma')
            for flux in range(1, self.free_lines + 1):
                cols.append(f'flux_{i}_{chr(ord("@") + flux)}_sigma')

        self.cat = pd.DataFrame(np.zeros((len(self.listing), len(cols))), columns=cols)
        #print(self.cat)
        self.cat.loc[:, 'ncomps'] = -1

        self.cat["index"] = self.cat.index

        outfile = os.path.join(self.basepath, f'{self.target_param["name"]}_out_'+str(self.counter),
                               f'{self.target_param["name"]}_{self.fit_instructions["line1"]["name"]}.txt')

        self.cat['filename'] = self.cat.apply(self.get_pix, axis=1)

        self.cat.to_csv(outfile, index=False)

    def get_pix(self, row_ind):
        infile = self.listing[int(row_ind['index'])]
        return infile

    def find_unfit(self):
        open_cat = pd.read_csv(os.path.join(self.basepath, f'{self.target_param["name"]}_out_'+str(self.counter),
                                                           f'{self.target_param["name"]}_'
                                                           f'{self.fit_instructions["line1"]["name"]}.txt'))
        file_list = list(open_cat.loc[open_cat['ncomps'] == -1, 'filename'])

        try:
        	file_list.remove('.DS_Store')
        except:
        	pass

        return file_list

    def remove_unnecessary_files(self, path, patterns):
        filestoremove = []
        for pattern in patterns:
            filelist = glob.glob(path + pattern)
            for file in filelist:
                filestoremove.append(file)
        for file in filestoremove:
            try:
                os.remove(file)
            except:
                print(f"Error while deleting '{file}'")

    def mp_worker(self, filename):
        # Set the variables that will be used directly within the functions below
        # rather than passing them in as arguments.
        global x, ydata, miny, maxy, avg, stdev, noise, wave, threesigma
        global column, row, line_outfile, ypadding, systemic, plot_outfile

        # Clean up the contents of the input directory
        #if os.path.exists(os.path.join(self.specpath, '.DS_Store')):
            #os.remove(os.path.join(self.specpath, '.DS_Store'))

        # Set the filename and filepaths for the various inputs and outputs.
        infile = filename
        #print('new file is', infile)

        inspecpath = os.path.join(self.specpath, infile)
        

        wave, flux, noise = self.load_file(inspecpath)
        infilebase = infile.split('.')[0]
        data_outfile = os.path.join(self.basepath, f'{self.target_param["name"]}_out_'+str(self.counter), 'out',
                                    f'{infilebase}_{self.fit_instructions["line1"]["name"]}')
        plot_outfile = os.path.join(self.basepath, f'{self.target_param["name"]}_out_'+str(self.counter), 'plots',
                                    f'{infilebase}_{self.fit_instructions["line1"]["name"]}')
        line_outfile = os.path.join(self.basepath, f'{self.target_param["name"]}_out_'+str(self.counter),
                                    f'{self.target_param["name"]}_{self.fit_instructions["line1"]["name"]}.txt')


        self.start = np.argmin(np.abs(wave-self.target_param["plotmin"]))
        self.end = np.argmin(np.abs(wave-self.target_param["plotmax"]))

        x = wave[self.start:self.end] #wave[self.target_param["start"]:self.target_param["end"]]
        ydata = flux[self.start:self.end] #flux[self.target_param["start"]:self.target_param["end"]]
        noise = noise[self.start:self.end] #noise[self.target_param["start"]:self.target_param["end"]]
        maxy = max(ydata)
        miny = min(ydata)
        ypadding = .05 * (maxy - miny)

        # is this right? should this be for all lines??
        systemic = (1. + self.target_param["red"]) * self.fit_instructions["line1"]["wave"]

        low1_ind = (np.abs(wave - self.cont_instructions["continuum1"][0])).argmin()
        upp1_ind = (np.abs(wave - self.cont_instructions["continuum1"][1])).argmin()
        low2_ind = (np.abs(wave - self.cont_instructions["continuum2"][0])).argmin()
        upp2_ind = (np.abs(wave - self.cont_instructions["continuum2"][1])).argmin()
        cont1 = flux[low1_ind:upp1_ind]
        cont2 = flux[low2_ind:upp2_ind]
        wave1 = wave[low1_ind:upp1_ind]
        wave2 = wave[low2_ind:upp2_ind]
        contwave = np.concatenate((wave1, wave2), axis=0)
        contflux = np.concatenate((cont1, cont2), axis=0)
        polycont = np.polyfit(contwave, contflux, self.cont_instructions['cont_poly'])
        poly = np.poly1d(polycont)
        avg = poly(x)
        stdev = (np.std(cont1) + np.std(cont2)) / 2  # stnd dev of continuum flux
        threesigma = (self.target_param["fluxsigma"] * stdev)  # * init.minwidth * np.sqrt(2*np.pi)

        # Set the maximum number of components that this program will model
        maxcomp = self.target_param["maxcomp"]

        # build lists that will hold the outputs for each model
        analyzers = [0] * (maxcomp + 1)
        lnZs = [0] * (maxcomp + 1)
        outmodels = [0] * (maxcomp + 1)
        modelsigma = [0] * (maxcomp + 1)

        # ------ CONTINUUM FIT ------

        print(f'Fitting {filename}')
        print(f'Min Y: {miny:.2e}')
        print(f'Max Y: {maxy:.2e}')
        # -----------------------------------------------working on this part-----------------------------------------#
        # Set the number of dimensions of this model
        ncomp = 0

        n_params = 1

        

        # run MultiNest
        pymultinest.run(self.loglike, self.prior, n_params,
                        outputfiles_basename=f'{data_outfile}_{ncomp}_',
                        n_live_points=200, multimodal=False, resume=False,
                        verbose=False)
        analyzers[ncomp] = pymultinest.Analyzer(
            outputfiles_basename=f'{data_outfile}_{ncomp}_',
            n_params=n_params, verbose=False)
        lnZs[ncomp] = analyzers[ncomp].get_stats()['global evidence']
        outmodels[ncomp] = analyzers[ncomp].get_best_fit()['parameters']
        modelsigma[ncomp] = analyzers[ncomp].get_stats()['modes'][0]['sigma']

        #print(outmodels[ncomp])


        #print(self.prior)
        #data_deblended = flux
        # plot best fit
        self.make_model_plot(ncomp, outmodels[ncomp], lnZs[ncomp], filename)

        # set this as the best fit
        bestncomp = ncomp

        # Now try increased number of components.

        

        for ncomp in range(1, maxcomp + 1):
            print(f'{filename}: trying {ncomp} component(s)')
            n_params = (2 + self.free_lines) * ncomp + (3 * self.prefit_num_lines)
            #self.prior(self.cube, ncomp, n_params)
            # run MultiNest

            pymultinest.run(self.loglike, self.prior, n_params,
                            outputfiles_basename=f'{data_outfile}_{ncomp}_',
                            n_live_points=200, multimodal=False, resume=False,
                            verbose=False)
            

            output_file_original = pd.read_csv(data_outfile+'_'+str(ncomp)+'_.txt', delim_whitespace = True)
            start_col = 2 + (self.prefit_num_lines * 3)
            cube_to_sort = np.array(output_file_original[output_file_original.columns[start_col:(start_col+(2+self.free_lines)*ncomp)]])
            df_dupe = np.array(output_file_original)
            for elements in range(len(cube_to_sort)):
            	f = sorted((cube_to_sort[elements][i:i + 2+self.free_lines] for i in range(0, (2+self.free_lines)*ncomp, 2+self.free_lines)), key=lambda elements: elements[0])
            	df_dupe[elements][start_col:(start_col+(2+self.free_lines)*ncomp)] = np.concatenate(f)

            np.savetxt(data_outfile+'_'+str(ncomp)+'_.txt', df_dupe, delimiter = '    ', newline = '\n    ')

            #np.set_printoptions(threshold=np.inf)
            #print(data_outfile+'_'+str(ncomp)+'_.txt')

            #print(df_dupe)



            analyzers[ncomp] = pymultinest.Analyzer(
                outputfiles_basename=f'{data_outfile}_{ncomp}_',
                n_params=n_params, verbose=True)
            lnZs[ncomp] = analyzers[ncomp].get_stats()['global evidence']
            outmodels[ncomp] = analyzers[ncomp].get_best_fit()['parameters']
            modelsigma[ncomp] = analyzers[ncomp].get_stats()['modes'][0]['sigma']



            post_file_original = pd.read_csv(data_outfile+'_'+str(ncomp)+'_post_equal_weights.dat', delim_whitespace = True)
            start_col = (self.prefit_num_lines * 3)
            cube_to_sort = np.array(post_file_original[post_file_original.columns[start_col:(start_col+(2+self.free_lines)*ncomp)]])
            post_dupe = np.array(post_file_original)
            for elements in range(len(cube_to_sort)):
            	f = sorted((cube_to_sort[elements][i:i + 2+self.free_lines] for i in range(0, (2+self.free_lines)*ncomp, 2+self.free_lines)), key=lambda elements: elements[0])
            	post_dupe[elements][start_col:(start_col+(2+self.free_lines)*ncomp)] = np.concatenate(f)

            np.savetxt(data_outfile+'_'+str(ncomp)+'_post_equal_weights.dat', post_dupe, delimiter = '    ', newline = '\n    ')

            post = np.loadtxt(data_outfile+'_'+str(ncomp)+'_post_equal_weights.dat', ndmin=2)
            summ_file_original = np.array(pd.read_csv(data_outfile+'_'+str(ncomp)+'_summary.txt', delim_whitespace = True))[0]
            means, sigmas, rest_of_summ = np.split(summ_file_original, [start_col+(2+self.free_lines)*ncomp, 2*(start_col+(2+self.free_lines)*ncomp)])
            cols = post[0]
            for nums in range(len(cols)-1):
            	sigmas[nums] = np.std(post[:,nums])    
            summary_new = np.concatenate([means, sigmas, rest_of_summ])


            np.savetxt(data_outfile+'_'+str(ncomp)+'_summary.txt', summary_new,  delimiter = '    ', newline ='    ' )



            df = pd.read_csv(data_outfile+'_'+str(ncomp)+'_stats.dat', skiprows = 3, delim_whitespace = True)
            df2 = df.copy()
            #df2['Mean'][0:len(sigmas)] = sigmas
            df2.iloc[0:len(sigmas), 2] = sigmas
            df2.to_csv(data_outfile+'_'+str(ncomp)+'_stats new.dat', sep = '\t', index = False)

            df_header = np.loadtxt(data_outfile+'_'+str(ncomp)+'_stats.dat', delimiter = '\n', max_rows = 2, dtype = 'object')
            with open(data_outfile+'_'+str(ncomp)+'_stats new.dat', "r+") as f:
            	old = f.read() # read everything in the file
            	f.seek(0) # rewind
            	f.write(str(df_header)[1:-1] +"\n" + old)
            os.rename(data_outfile+'_'+str(ncomp)+'_stats new.dat', data_outfile+'_'+str(ncomp)+'_stats.dat')



            
            #print(self.ordered_cube)
            #print(outmodels[ncomp])
 


            # plot best fit
            

            if lnZs[ncomp] - lnZs[bestncomp] > self.target_param["lnz"]:
                bestncomp = ncomp
                self.make_model_plot(ncomp, outmodels[ncomp], lnZs[ncomp], filename, goodfit = True)

            else:
                self.make_model_plot(ncomp, outmodels[ncomp], lnZs[ncomp], filename, goodfit = False)
                break
        
        


  
        self.write_results(filename, bestncomp, outmodels[bestncomp], modelsigma[bestncomp])

        print(f'{filename} fit with {bestncomp} components')
        print(f'Average Continuum = {np.mean(avg):.2e}')
        print(f'Standard deviation = {stdev:.4e}')

        # Delete extraneous outfiles
        self.remove_unnecessary_files(data_outfile, ['*ev.dat', '*IS.*', '*live.points',
                                                     '*phys_live.po', '*post_equal_w',
                                                     '*resume.dat'])

    def mp_handler(self):
        # make mp optional
        #if os.path.exists(os.path.join(self.specpath, '.DS_Store')):
            #os.remove(os.path.join(self.specpath, '.DS_Store'))
        unfit_pix = self.find_unfit()


        print(f'remaining to fit: {len(unfit_pix)}')
        pool = mp.Pool(processes=self.target_param["cores"])
        pool.map(self.mp_worker, unfit_pix)
