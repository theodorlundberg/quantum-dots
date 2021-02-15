from contextlib import contextmanager
from typing import Callable, Sequence, Union, Tuple, List, Optional, Iterator
import os
import time

import numpy as np
import matplotlib
import matplotlib.pyplot as plt

from qcodes.dataset.measurements import Measurement, res_type, DataSaver
from qcodes.instrument.base import _BaseParameter
from qcodes.dataset.plotting import plot_by_id
from qcodes import config

ActionsT = Sequence[Callable[[], None]]

ParamMeasT = Union[_BaseParameter, Callable[[], None]]

AxesTuple = Tuple[matplotlib.axes.Axes, matplotlib.colorbar.Colorbar]
AxesTupleList = Tuple[List[matplotlib.axes.Axes],
                      List[Optional[matplotlib.colorbar.Colorbar]]]
AxesTupleListWithRunId = Tuple[int, List[matplotlib.axes.Axes],
                      List[Optional[matplotlib.colorbar.Colorbar]]]


def _process_params_meas(param_meas: ParamMeasT) -> List[res_type]:
    output = []
    for parameter in param_meas:
        if isinstance(parameter, _BaseParameter):
            output.append((parameter, parameter.get()))
        elif callable(parameter):
            parameter()
    return output


def _register_parameters(
        meas: Measurement,
        param_meas: List[ParamMeasT],
        setpoints: Optional[List[_BaseParameter]] = None
) -> None:
    for parameter in param_meas:
        if isinstance(parameter, _BaseParameter):
            meas.register_parameter(parameter,
                                    setpoints=setpoints)


def _register_actions(
        meas: Measurement,
        enter_actions: ActionsT,
        exit_actions: ActionsT
) -> None:
    for action in enter_actions:
        # this omits the possibility of passing
        # argument to enter and exit actions.
        # Do we want that?
        meas.add_before_run(action, ())
    for action in exit_actions:
        meas.add_after_run(action, ())



def _set_write_period(
        meas: Measurement,
        write_period: Optional[float] = None
) -> None:
    if write_period is not None:
        meas.write_period = write_period


@contextmanager
def _catch_keyboard_interrupts() -> Iterator[Callable[[], bool]]:
    interrupted = False
    def has_been_interrupted():
        nonlocal interrupted
        return interrupted
    try:
        yield has_been_interrupted
    except KeyboardInterrupt:
        interrupted = True



def do0d(
    exp,
    *param_meas:  ParamMeasT,
    write_period: Optional[float] = None,
    do_plot: bool = True,
    name: str = ''
) -> AxesTupleListWithRunId:
    """
    Perform a measurement of a single parameter. This is probably most
    useful for an ArrayParamter that already returns an array of data points

    Args:
        *param_meas: Parameter(s) to measure at each step or functions that
          will be called at each step. The function should take no arguments.
          The parameters and functions are called in the order they are
          supplied. 
        do_plot: should png and pdf versions of the images be saved after the
            run.

    Returns:
        The run_id of the DataSet created
    """
    meas = Measurement(exp=exp)
    _register_parameters(meas, param_meas)
    _set_write_period(meas, write_period)
    
    with meas.run() as datasaver:
        datasaver.add_result(*_process_params_meas(param_meas))
        
    return _handle_plotting(datasaver, do_plot, name = name)





def do1d(
    exp,
    param_set: _BaseParameter, start: float, stop: float,
    num_points: int, delay: float,
    *param_meas: ParamMeasT,
    enter_actions: ActionsT = (),
    exit_actions: ActionsT = (),
    before_inner_actions: ActionsT = (),
    after_inner_actions: ActionsT = (),
    write_period: Optional[float] = None,
    do_plot: bool = True,
    name: str = ''
) -> AxesTupleListWithRunId:
    """
    Perform a 1D scan of ``param_set`` from ``start`` to ``stop`` in
    ``num_points`` measuring param_meas at each step. In case param_meas is
    an ArrayParameter this is effectively a 2d scan.

    Args:
        param_set: The QCoDeS parameter to sweep over
        start: Starting point of sweep
        stop: End point of sweep
        num_points: Number of points in sweep
        delay: Delay after setting paramter before measurement is performed
        *param_meas: Parameter(s) to measure at each step or functions that
          will be called at each step. The function should take no arguments.
          The parameters and functions are called in the order they are
          supplied.
        enter_actions: A list of functions taking no arguments that will be
            called before the measurements start
        exit_actions: A list of functions taking no arguments that will be
            called after the measurements ends
        do_plot: should png and pdf versions of the images be saved after the
            run.

    Returns:
        The run_id of the DataSet created
    """
    meas = Measurement(exp=exp)
    _register_parameters(meas, (param_set,))
    _register_parameters(meas, param_meas, setpoints=(param_set,))
    _set_write_period(meas, write_period)
    _register_actions(meas, enter_actions, exit_actions)
    param_set.post_delay = delay

    # do1D enforces a simple relationship between measured parameters
    # and set parameters. For anything more complicated this should be
    # reimplemented from scratch
    with _catch_keyboard_interrupts() as interrupted, meas.run() as datasaver:
        for set_point in np.linspace(start, stop, num_points):
            for action in before_inner_actions:
                action()
                
            param_set.set(set_point)
            datasaver.add_result((param_set, set_point),
                                  *_process_params_meas(param_meas))
            for action in after_inner_actions:
                action()
    return _handle_plotting(datasaver, do_plot, interrupted(), name = name)


def do2d(
    exp,
    param_set1: _BaseParameter, start1: float, stop1: float,
    num_points1: int, delay1: float,
    param_set2: _BaseParameter, start2: float, stop2: float,
    num_points2: int, delay2: float,
    *param_meas: ParamMeasT,
    set_before_sweep: Optional[bool] = False,
    enter_actions: ActionsT = (),
    exit_actions: ActionsT = (),
    before_inner_actions: ActionsT = (),
    after_inner_actions: ActionsT = (),
    write_period: Optional[float] = None,
    flush_columns: bool = False,
    do_plot: bool=True,
    name: str = ''
) -> AxesTupleListWithRunId:

    """
    Perform a 1D scan of ``param_set1`` from ``start1`` to ``stop1`` in
    ``num_points1`` and ``param_set2`` from ``start2`` to ``stop2`` in
    ``num_points2`` measuring param_meas at each step.

    Args:
        param_set1: The QCoDeS parameter to sweep over in the outer loop
        start1: Starting point of sweep in outer loop
        stop1: End point of sweep in the outer loop
        num_points1: Number of points to measure in the outer loop
        delay1: Delay after setting parameter in the outer loop
        param_set2: The QCoDeS parameter to sweep over in the inner loop
        start2: Starting point of sweep in inner loop
        stop2: End point of sweep in the inner loop
        num_points2: Number of points to measure in the inner loop
        delay2: Delay after setting paramter before measurement is performed
        *param_meas: Parameter(s) to measure at each step or functions that
          will be called at each step. The function should take no arguments.
          The parameters and functions are called in the order they are
          supplied.
        set_before_sweep: if True the outer parameter is set to its first value
            before the inner parameter is swept to its next value.
        enter_actions: A list of functions taking no arguments that will be
            called before the measurements start
        exit_actions: A list of functions taking no arguments that will be
            called after the measurements ends
        before_inner_actions: Actions executed before each run of the inner loop
        after_inner_actions: Actions executed after each run of the inner loop
        do_plot: should png and pdf versions of the images be saved after the
            run.

    Returns:
        The run_id of the DataSet created
    """

    meas = Measurement(exp=exp)
    _register_parameters(meas, (param_set1, param_set2))
    _register_parameters(meas, param_meas, setpoints=(param_set1, param_set2))
    _set_write_period(meas, write_period)
    _register_actions(meas, enter_actions, exit_actions)

    param_set1.post_delay = delay1
    param_set2.post_delay = delay2

    with _catch_keyboard_interrupts() as interrupted, meas.run() as datasaver:
        for set_point1 in np.linspace(start1, stop1, num_points1):
                if set_before_sweep:
                    param_set2.set(start2)

                param_set1.set(set_point1)
                for action in before_inner_actions:
                    action()
                for set_point2 in np.linspace(start2, stop2, num_points2):
                    # skip first inner set point if `set_before_sweep`
                    if set_point2 == start2 and set_before_sweep:
                        pass
                    else:
                        param_set2.set(set_point2)

                    datasaver.add_result((param_set1, set_point1),
                                         (param_set2, set_point2),
                                         *_process_params_meas(param_meas))
                for action in after_inner_actions:
                    action()
                if flush_columns:
                    datasaver.flush_data_to_database()

    return _handle_plotting(datasaver, do_plot, interrupted(), name = name)


def subplot_by_id_2(dataid, name):
    fig, figaxes = plt.subplots(1, 2, figsize = (10,5))
    axes, cbs = plot_by_id(dataid, [figaxes[0],figaxes[1]])
    fig.suptitle(figaxes[0].get_title() + '\n' + name)
    figaxes[0].set_title('')
    figaxes[1].set_title('')
    if figaxes[0].get_xlabel()[:23]=='LCR_Reflectometry_Sweep':
        unit = figaxes[0].get_xlabel()[23:]
        figaxes[0].set_xlabel('Sweep'+unit)
        figaxes[1].set_xlabel('Sweep'+unit)
    elif figaxes[0].get_ylabel()[:23]=='LCR_Reflectometry_Sweep':
        unit = figaxes[0].get_xlabel()[23:]
        figaxes[0].set_ylabel('Sweep'+unit)
        figaxes[1].set_ylabel('Sweep'+unit)
    plt.tight_layout(pad=0.4, rect=[0.2, 0, 0.8, 0.92])
    return axes, cbs

def subplot_by_id_3(dataid, name):
    fig, figaxes = plt.subplots(3, 1, figsize = (5,7))
    axes, cbs = plot_by_id(dataid, [figaxes[0],figaxes[1],figaxes[2]])
    fig.suptitle(figaxes[0].get_title() + '\n' + name)
    figaxes[0].set_title('')
    figaxes[1].set_title('')
    figaxes[2].set_title('')
    if figaxes[0].get_xlabel()[:23]=='LCR_Reflectometry_Sweep':
        unit = figaxes[0].get_xlabel()[23:]
        figaxes[0].set_xlabel('Sweep'+unit)
        figaxes[1].set_xlabel('Sweep'+unit)
        figaxes[2].set_xlabel('Sweep'+unit)
    elif figaxes[0].get_ylabel()[:23]=='LCR_Reflectometry_Sweep':
        unit = figaxes[0].get_xlabel()[23:]
        figaxes[0].set_ylabel('Sweep'+unit)
        figaxes[1].set_ylabel('Sweep'+unit)
        figaxes[2].set_ylabel('Sweep'+unit)
    plt.tight_layout(pad=0.4, rect=[0.2, 0, 0.8, 0.92])
    return axes, cbs

def subplot_by_id_4(dataid, name):
    fig, figaxes = plt.subplots(2, 2, figsize = (9,7))
    axes, cbs = plot_by_id(dataid, [figaxes[0,0],figaxes[0,1],figaxes[1,0],figaxes[1,1]])
    fig.suptitle(figaxes[0,0].get_title() + '\n' + name)
    figaxes[0,0].set_title('')
    figaxes[1,0].set_title('')
    figaxes[0,1].set_title('')
    figaxes[1,1].set_title('')
    if figaxes[0,1].get_xlabel()[:23]=='LCR_Reflectometry_Sweep':
        unit = figaxes[0,1].get_xlabel()[23:]
        figaxes[0,0].set_xlabel('Sweep'+unit)
        figaxes[1,0].set_xlabel('Sweep'+unit)
        figaxes[0,1].set_xlabel('Sweep'+unit)
        figaxes[1,1].set_xlabel('Sweep'+unit)
    elif figaxes[0,1].get_ylabel()[:23]=='LCR_Reflectometry_Sweep':
        unit = figaxes[0,1].get_ylabel()[23:]
        figaxes[0,0].set_ylabel('Sweep'+unit)
        figaxes[1,0].set_ylabel('Sweep'+unit)
        figaxes[0,1].set_ylabel('Sweep'+unit)
        figaxes[1,1].set_ylabel('Sweep'+unit)
    plt.tight_layout(pad=0.4, rect=[0.02, 0, 0.98, 0.92])
    return axes, cbs

def _handle_plotting(
        datasaver: DataSaver,
        do_plot: bool = True,
        interrupted: bool = False,
        name: str = ''
) -> AxesTupleList:
    """
    Save the plots created by datasaver as pdf and png

    Args:
        datasaver: a measurement datasaver that contains a dataset to be saved
            as plot.
            :param do_plot:

    """
    dataid = datasaver.run_id
    if do_plot == True:
        res = _create_plots(datasaver, name)
    else:
        res = dataid, None, None

    if interrupted:
        raise KeyboardInterrupt

    return res


def _create_plots(datasaver: DataSaver, name: str = '') -> AxesTupleList:
    dataid = datasaver.run_id
    no_dependent_params = len(datasaver.dataset.dependent_parameters)
    plt.ioff()
    start = time.time()
    if no_dependent_params == 2:
        axes, cbs = subplot_by_id_2(dataid, name)
    elif no_dependent_params == 3:
        axes, cbs = subplot_by_id_3(dataid, name)
    elif no_dependent_params == 4:
        axes, cbs = subplot_by_id_4(dataid, name)
    else:
        axes, cbs = plot_by_id(dataid)
        axes[0].set_title(axes[0].get_title() + '\n' + name)
    stop = time.time()
    print(f"plot by id took {stop - start}")
    mainfolder = config.user.mainfolder
    experiment_name = datasaver._dataset.exp_name
    sample_name = datasaver._dataset.sample_name
    storage_dir = os.path.join(mainfolder, experiment_name, sample_name)
    os.makedirs(storage_dir, exist_ok=True)
    png_dir = os.path.join(storage_dir, 'png')
    pdf_dir = os.path.join(storage_dir, 'pdf')
    os.makedirs(png_dir, exist_ok=True)
    #os.makedirs(pdf_dir, exist_ok=True)
    save_pdf = False
    save_png = True
    if no_dependent_params < 5:
        if save_pdf:
            full_path = os.path.join(pdf_dir, f'{dataid}.pdf')
            plt.savefig(full_path, dpi=300)
        if save_png:
            full_path = os.path.join(png_dir, f'{dataid}.png')
            plt.savefig(full_path, dpi=300)
    else:
        for i, ax in enumerate(axes):
            if save_pdf:
                full_path = os.path.join(pdf_dir, f'{dataid}_{i}.pdf')
                ax.figure.savefig(full_path, dpi=300)
            if save_png:
                full_path = os.path.join(png_dir, f'{dataid}_{i}.png')
                ax.figure.savefig(full_path, dpi=300)
    plt.ion()
    res = dataid, axes, cbs
    return res
