from qcodes.plots.pyqtgraph import QtPlot

import time

import qcodes as qc
from qcodes.dataset.data_set import load_by_id
from qcodes.dataset.data_export import (get_data_by_id, flatten_1D_data_for_plot,
                          get_1D_plottype, get_2D_plottype, reshape_2D_data,
                          _strings_as_ints)



class QtLivePlot(QtPlot):
    
    def __init__(self, *args, experiment, refresh=1):
        
        super().__init__(*args, window_title='Liveplot', figsize=(2000, 400), fig_x_position=0, fig_y_position=0.3)
        
        self.experiment = experiment
        self.refresh = refresh
        
    def _get_recent_id(self):
        self.id = self.experiment.last_data_set().run_id
        return self.id
    
    def _get_recent_data(self):
        last_id = self._get_recent_id()
        return get_data_by_id(last_id)
    
    def _add_1d(self, i, x, y):
        return self.add_to_plot(subplot=i+1, x=x['data'], xlabel=x['label'], xunit=x['unit'],
                                                   y=y['data'], ylabel=y['label'], yunit=y['unit'])
    def _get_2d_data(self,x,y,z):
        return reshape_2D_data(flatten_1D_data_for_plot(x['data']), 
                                                        flatten_1D_data_for_plot(y['data']), 
                                                        flatten_1D_data_for_plot(z['data']))
    def _add_2d(self, i, x, y, z):
        xrow, yrow, z_to_plot = self._get_2d_data(x,y,z)
        return self.add_to_plot(subplot=i+1, x=xrow, y=yrow, z=z_to_plot,
                                                    xlabel=x['label'], xunit=x['unit'],
                                                    ylabel=y['label'], yunit=y['unit'],
                                                    zlabel=z['label'], zunit=z['unit'])        
    
    def update_plots(self):
        alldata = self._get_recent_data()

        # update all plots
        for trace, data in zip(self.traces, alldata):
            x = data[0]
            y = data[1]
            if len(data) == 2:  # 1D PLOTTING
                trace['plot_object'].setData(*self._line_data(x['data'], y['data']))

            elif len(data) == 3:  # 2D PLOTTING
                z = data[2]
                xrow, yrow, z_to_plot = self._get_2d_data(x,y,z)
                self._update_image(trace['plot_object'], {'x':xrow, 'y':yrow, 'z':z_to_plot})
        
    def close(self):
        self.win.close()
        
    def liveplot(self):        
        self.clear()
        plotting_done = False
        while not plotting_done:
            try:
                alldata = self._get_recent_data()

                # initiate plots
                for i, data in enumerate(alldata):

                    x = data[0]
                    y = data[1]

                    if len(data) == 2:  # 1D PLOTTING
                        po = self._add_1d(i, x, y)

                    elif len(data) == 3:  # 2D PLOTTING
                        z = data[2]
                        po = self._add_2d(i, x, y, z)

                dataset = load_by_id(self.id)
                self.completed = dataset.completed

                while not self.completed:
                    dataset = load_by_id(self.id)
                    self.completed = dataset.completed
                    self.update_plots()
                    time.sleep(self.refresh)
                
                plotting_done = True
            except RuntimeError:
                # handle error from data being unready for loading from database
                time.sleep(self.refresh)
        
    def continuous_liveplot(self):
        try:
            self.liveplot()
            last_id = self._get_recent_id()
            while True:
                new_id = self._get_recent_id()
                if new_id > last_id:
                    self.liveplot()
                    last_id = new_id
                time.sleep(self.refresh)
        finally:
            # always finish by closing the window used for live plotting
            self.close()