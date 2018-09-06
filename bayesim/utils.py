from copy import deepcopy
import numpy as np
import pandas as pd
import sys
import bayesim.params as pm
import bayesim.model as bym
#import model as bym
import bayesim.pmf as pmf
import matplotlib.pyplot as plt
import matplotlib.patches as mplp
from matplotlib import colors as mcolors

def visualize_PMF_sequence(statefile_list, **argv):
    """
    Create plot akin to that produced by pmf.visualize() but with data from multiple PMF's overlaid. All should have the same set of fitting parameters. For now assumes that first statefile has the largest axes bounds, will add automated check later.

    Args:
        statefile_list (list of str): list of paths to statefiles (saved by Model.save_state function storing PMF's to be visualized), in order from least to most subdivided
        name_list (list of str): optional, list of names for legend, defaults to filenames
        true_vals (`dict`): optional, set of param values to highlight on PMF
        fpath (str): optional, path to save image to
    """

    # get legend names
    if 'name_list' in argv.keys():
        name_list = argv['name_list']
    else:
        name_list = [sf.split('/')[-1].split('.')[0] for sf in statefile_list]

    if 'true_vals' in argv.keys():
        plot_true_vals = True
        true_vals = argv['true_vals']
    else:
        plot_true_vals = False

    # load the models one by one (to save RAM) and get visualizations
    figs = []
    axes_sets = []
    for statefile in statefile_list:
        m = bym.Model(load_state=True, state_file=statefile)
        if plot_true_vals:
            f, a = m.probs.visualize(return_plots=True, true_vals=true_vals)
        else:
            f, a = m.probs.visualize(return_plots=True)
        figs.append(f)
        axes_sets.append(a)
    num_params = len(m.params.fit_params)

    # get color cycle
    prop_cycle = plt.rcParams['axes.prop_cycle']
    colors = prop_cycle.by_key()['color']

    # initialize the figure
    fig, axes = plt.subplots(nrows=num_params, ncols=num_params, figsize=(5*num_params, 5*num_params))

    for rownum in range(num_params):
        for colnum in range(num_params):
            for i in range(len(figs)):
                old_ax = axes_sets[i][rownum][colnum]
                color = colors[i]
                patches = old_ax.patches
                if i==0: # formatting stuff
                    if rownum<colnum: # build the legend here
                        if rownum==0 and colnum==num_params-1:
                            axes[rownum][colnum].axis('off')
                            axes[rownum][colnum].set_xlim([0,1])
                            axes[rownum][colnum].set_ylim([0,1])

                            for j in range(len(axes_sets)):
                                x = 0.2
                                if plot_true_vals:
                                    y = 0.8-(float(j)/float(len(axes_sets)+1))*0.7
                                else:
                                    y = 0.8-(float(j)/float(len(axes_sets)))*0.7
                                axes[rownum][colnum].add_patch(mplp.Rectangle((x,y), 0.1, 0.1, facecolor=colors[j]))
                                axes[rownum][colnum].text(x+0.15, y, name_list[j], color='k', fontsize=20)
                            if plot_true_vals:
                                axes[rownum][colnum].scatter([0.16],[0.1],200,'#FFFF00',marker='*')
                                axes[rownum][colnum].scatter([0.25],[0.1],200,c="None",marker='o',linewidths=3,edgecolors='#FFFF00')
                                axes[rownum][colnum].text(0.35, 0.1, 'true values', color='k', fontsize=20)
                        else:
                            fig.delaxes(axes[rownum][colnum])
                    else:
                        axes[rownum][colnum].set_xlim(old_ax.get_xlim())
                        axes[rownum][colnum].set_ylim(old_ax.get_ylim())
                        axes[rownum][colnum].set_xlabel(old_ax.get_xlabel(), fontsize=24)
                        axes[rownum][colnum].set_xscale(old_ax.get_xscale())
                        axes[rownum][colnum].set_yscale(old_ax.get_yscale())
                        axes[rownum][colnum].set_axisbelow(True)

                        if rownum==colnum:
                            axes[rownum][colnum].yaxis.set_label_position("right")
                            axes[rownum][colnum].set_ylabel(old_ax.get_ylabel(), rotation=270, labelpad=24, fontsize=24)
                            if plot_true_vals:
                                true_x, true_y = old_ax.collections[0]._offsets[0]
                                axes[rownum][colnum].scatter(true_x,0.05,200,'#FFFF00',marker='*',zorder=100)

                        else:
                            axes[rownum][colnum].set_ylabel(old_ax.get_ylabel(), fontsize=24)
                            if plot_true_vals:
                                true_x, true_y = old_ax.collections[0]._offsets[0]
                                axes[rownum][colnum].scatter(true_x,true_y,200,c="None",marker='o',linewidths=3,edgecolors='#FFFF00',zorder=100)

                        for item in (axes[rownum][colnum].get_xticklabels() + axes[rownum][colnum].get_yticklabels()):
                            item.set_fontsize(20)

                for patch in patches:
                    axes[rownum][colnum].add_patch(mplp.Rectangle((patch._x, patch._y), patch._width, patch._height, facecolor=color, alpha=patch._alpha, zorder=i+1))

    if 'fpath' in argv.keys():
        plt.savefig(argv['fpath'])

    else:
        plt.show()


def calc_deltas(grp, inds, param_lengths, model_data, fit_param_names, probs, output_var):
    # construct matrix of output_var({fit_params})
    subset = deepcopy(model_data.loc[inds])
    # sort and reset index of subset to match probs so we can use the find_neighbor_boxes function if needed
    subset.drop_duplicates(subset=fit_param_names, inplace=True)
    subset.sort_values(fit_param_names, inplace=True)
    subset.reset_index(inplace=True)
    if not len(subset.index)==len(probs.points.index):
        raise ValueError("Subset at EC's %s does not match probability grid!"%str(grp))

    # check if on a grid
    if not len(subset)==np.product(param_lengths):
        is_grid = False
        # construct grid at the highest level of subdivision
        dense_grid = probs.populate_dense_grid(df=subset, col_to_pull=output_var, make_ind_lists=True)
        mat = dense_grid['mat']
        ind_lists = dense_grid['ind_lists']

    else:
        is_grid = True
        mat = np.reshape(list(subset[output_var]), param_lengths)

    # given matrix, compute largest differences along any direction
    winner_dim = [len(mat.shape)]
    winner_dim.extend(mat.shape)
    winners = np.zeros(winner_dim)

    # for every dimension (fitting parameter)
    for i in range(len(mat.shape)):
        # build delta matrix
        # certain versions of numpy throw an "invalid value encountered" RuntimeError here but the function behaves correctly
        with np.errstate(invalid='ignore'):
            deltas_here = np.absolute(np.diff(mat,axis=i))
        pad_widths = [(0,0) for j in range(len(mat.shape))]
        pad_widths[i] = (1,1)
        deltas_here = np.pad(deltas_here, pad_widths, mode='constant', constant_values=0)

        # build "winner" matrix in this direction (ignore nans)
        # this is really ugly because we have to index in at variable positions...
        # likewise here with the error
        with np.errstate(invalid='ignore'):
            winners[i]=np.fmax(deltas_here[tuple([Ellipsis]+[slice(None,mat.shape[i],None)]+[slice(None)]*(len(mat.shape)-i-1))],deltas_here[tuple([Ellipsis]+[slice(1,mat.shape[i]+1,None)]+[slice(None)]*(len(mat.shape)-i-1))])

    grad = np.amax(winners,axis=0)

    # save these values to the appropriate indices in the vector
    if is_grid:
        return (grp, grad.flatten())
    else:
        # pick out only the boxes that exist
        return (grp, grad[tuple([i for i in list([ind_lists[p] for p in fit_param_names])])])
