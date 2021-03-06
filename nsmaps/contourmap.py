import sys
import os
import math
import fnmatch

from timeit import default_timer as timer
from multiprocessing import Process, Queue

import numpy
from scipy.spatial import KDTree

import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas

import geojson
import geojsoncontour

import nsmaps
from nsmaps.logger import logger


def dotproduct(v1, v2):
    return sum((a * b) for a, b in zip(v1, v2))


def length(v):
    return math.sqrt(dotproduct(v, v))


def angle(v1, v2):
    return math.acos(dotproduct(v1, v2) / (length(v1) * length(v2)))


class ContourData(object):
    def __init__(self):
        self.Z = None
        self.index_begin = 0


class ContourPlotConfig(object):
    def __init__(self):
        self.stepsize_deg = 0.005
        self.n_processes = 4
        self.cycle_speed_kmh = 18.0
        self.n_nearest = 20
        self.lon_start = 3.0
        self.lat_start = 50.5
        self.delta_deg = 6.5
        self.lon_end = self.lon_start + self.delta_deg
        self.lat_end = self.lat_start + self.delta_deg / 2.0
        self.min_angle_between_segments = 7

    def print_bounding_box(self):
        print(
            '[[' + str(self.lon_start) + ',' + str(self.lat_start) + '],'
            '[' + str(self.lon_start) + ',' + str(self.lat_end) + '],'
            '[' + str(self.lon_end) + ',' + str(self.lat_end) + '],'
            '[' + str(self.lon_end) + ',' + str(self.lat_start) + '],'
            '[' + str(self.lon_start) + ',' + str(self.lat_start) + ']]'
        )


class TestConfig(ContourPlotConfig):
    def __init__(self):
        super().__init__()
        self.stepsize_deg = 0.005
        self.n_processes = 4
        self.lon_start = 4.8
        self.lat_start = 52.0
        self.delta_deg = 1.0
        self.lon_end = self.lon_start + self.delta_deg
        self.lat_end = self.lat_start + self.delta_deg / 2.0
        self.min_angle_between_segments = 7
        self.latrange = []
        self.lonrange = []
        self.Z = [[]]


class Contour(object):
    def __init__(self, departure_station, stations, config):
        self.departure_station = departure_station
        self.stations = stations
        self.config = config
        self.lonrange = numpy.arange(self.config.lon_start, self.config.lon_end, self.config.stepsize_deg)
        self.latrange = numpy.arange(self.config.lat_start, self.config.lat_end, self.config.stepsize_deg / 2.0)

    def create_contour_data(self):
        logger.info('BEGIN')
        if self.departure_station.has_travel_time_data():
            self.stations.travel_times_from_json(self.departure_station.get_travel_time_filepath())
        else:
            logger.error('Input file ' + self.departure_station.get_travel_time_filepath() + ' not found. Skipping station.')

        start = timer()
        numpy.set_printoptions(3, threshold=100, suppress=True)  # .3f

        altitude = 0.0
        self.Z = numpy.zeros((int(self.lonrange.shape[0]), int(self.latrange.shape[0])))
        gps = nsmaps.utilgeo.GPS()

        positions = []
        for station in self.stations:
            x, y, z = gps.lla2ecef([station.get_lat(), station.get_lon(), altitude])
            positions.append([x, y, z])

        logger.info('starting spatial interpolation')

        # tree to find nearest neighbors
        tree = KDTree(positions)

        queue = Queue()
        processes = []
        if self.config.n_nearest > len(self.stations):
            self.config.n_nearest = len(self.stations)
        latrange_per_process = int(len(self.latrange)/self.config.n_processes)
        for i in range(0, self.config.n_processes):
            begin = i * latrange_per_process
            end = (i+1) * latrange_per_process
            latrange_part = self.latrange[begin:end]
            process = Process(target=self.interpolate_travel_time, args=(queue, i, self.stations.stations, tree, gps, latrange_part,
                                                                         self.lonrange, altitude, self.config.n_nearest, self.config.cycle_speed_kmh))
            processes.append(process)

        for process in processes:
            process.start()

        # get from the queue and append the values
        for i in range(0, self.config.n_processes):
            data = queue.get()
            index_begin = data.index_begin
            begin = int(index_begin*len(self.latrange)/self.config.n_processes)
            end = int((index_begin+1)*len(self.latrange)/self.config.n_processes)
            self.Z[0:][begin:end] = data.Z

        for process in processes:
            process.join()

        end = timer()
        logger.info('finished spatial interpolation in ' + str(end - start) + ' [sec]')
        logger.info('END')

    @property
    def data_filename(self):
        return 'data/contour_data_' + self.departure_station.get_code() + '.npz'

    def load(self):
        with open(self.data_filename, 'rb') as filein:
            self.Z = numpy.load(filein)

    def save(self):
        with open(self.data_filename, 'wb') as fileout:
            numpy.save(fileout, self.Z)

    def create_geojson(self, filepath, stroke_width=1, levels=[], norm=None, overwrite=False):
        if not overwrite and os.path.exists(filepath):
            logger.error('Output file ' + filepath + ' already exists. Will not override.')
            return

        figure = Figure(frameon=False)
        FigureCanvas(figure)
        ax = figure.add_subplot(111)
        # contours = plt.contourf(lonrange, latrange, Z, levels=levels, cmap=plt.cm.plasma)
        contours = ax.contour(
            self.lonrange, self.latrange, self.Z,
            levels=levels,
            norm=norm,
            cmap=plt.cm.jet,
            linewidths=3
        )

        ndigits = len(str(int(1.0 / self.config.stepsize_deg))) + 1
        logger.info('converting contour to geojson file: ' + filepath)
        geojsoncontour.contour_to_geojson(
            contour=contours,
            geojson_filepath=filepath,
            contour_levels=levels,
            min_angle_deg=self.config.min_angle_between_segments,
            ndigits=ndigits,
            unit='min',
            stroke_width=stroke_width
        )

        cbar = figure.colorbar(contours, format='%d', orientation='horizontal')
        cbar.set_label('Travel time [minutes]')
        # cbar.set_ticks(self.config.colorbar_ticks)
        ax.set_visible(False)
        figure.savefig(
            filepath.replace('.geojson', '') + "_colorbar.png",
            dpi=90,
            bbox_inches='tight',
            pad_inches=0,
            transparent=True,
        )

    @staticmethod
    def interpolate_travel_time(q, position, stations, kdtree, gps, latrange, lonrange, altitude, n_nearest, cycle_speed_kmh):
        # n_nearest: check N nearest stations as best start for cycle route
        logger.info('interpolate_travel_time')
        Z = numpy.zeros((int(latrange.shape[0]), int(lonrange.shape[0])))
        min_per_m = 1.0 / (cycle_speed_kmh / 60.0 * 1000.0)
        for i, lat in enumerate(latrange):
            if i % (len(latrange) / 10) == 0:
                logger.debug(str(int(i / len(latrange) * 100)) + '%')

            for j, lon in enumerate(lonrange):
                x, y, z = gps.lla2ecef([lat, lon, altitude])
                distances, indexes = kdtree.query([x, y, z], n_nearest)
                min_travel_time = sys.float_info.max
                for distance, index in zip(distances, indexes):
                    if stations[index].travel_time_min is None:
                        continue
                    travel_time = stations[index].travel_time_min + distance * min_per_m
                    if travel_time < min_travel_time:
                        min_travel_time = travel_time
                Z[i][j] = min_travel_time
        data = ContourData()
        data.index_begin = position
        data.Z = Z
        q.put(data)
        logger.info('end interpolate_travel_time')
        return


class ContourMerged(object):

    def __init__(self, config):
        self.config = config
        self.lonrange = numpy.arange(self.config.lon_start, self.config.lon_end, self.config.stepsize_deg)
        self.latrange = numpy.arange(self.config.lat_start, self.config.lat_end, self.config.stepsize_deg / 2.0)
        self.Z = numpy.zeros((int(self.lonrange.shape[0]), int(self.latrange.shape[0])))

    def merge_grid_data(self, data_dir):
        counter = 0
        for file in os.listdir(data_dir):
            if fnmatch.fnmatch(file, '*.npz'):
                print(file)
                counter += 1
                with open(os.path.join(data_dir, file), 'rb') as filein:
                    self.Z += numpy.load(filein)
        self.Z = self.Z / counter

    def create_geojson(self, filepath, stroke_width=1, levels=[], norm=None):
        figure = Figure(frameon=False)
        FigureCanvas(figure)
        ax = figure.add_subplot(111)
        colormap = plt.cm.jet
        contours = ax.contourf(self.lonrange, self.latrange, self.Z, levels=levels, cmap=colormap)
        contours = ax.contour(
            self.lonrange, self.latrange, self.Z,
            levels=levels,
            norm=norm,
            cmap=colormap,
            linewidths=1
        )

        ndigits = len(str(int(1.0 / self.config.stepsize_deg))) + 1
        geojsoncontour.contour_to_geojson(
            contour=contours,
            geojson_filepath=filepath,
            contour_levels=levels,
            min_angle_deg=self.config.min_angle_between_segments,
            ndigits=ndigits,
            unit='min',
            stroke_width=stroke_width
        )

        # figure.savefig(
        #     "combined_map.png",
        #     dpi=300,
        #     bbox_inches='tight',
        #     pad_inches=0,
        #     transparent=True,
        # )