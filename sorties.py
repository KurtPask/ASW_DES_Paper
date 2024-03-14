# sorties.py
# Description: This file contains the SortyModel class for running a discrete event simulation using the DESPy package
# Author: Kurt Pasque
# Date: March 14, 2024

from simkit.base import SimEntityBase, EventList
from math import nan

class SortyModel(SimEntityBase):
    
    def __init__(self, 
                 number_subs, #count
                 distance_subs_generator, #nm
                 plane_speed_generator, #knots/minute
                 time_refuel_generator, #minutes
                 time_maintenance_generator, #minutes
                 refuel_limit, # count
                 plane_endurance_generator, #minutes
                 minimum_endurance, #minutes
                 minimum_speed, #knots/minute
                 chance_overlap, # probability from 0 to 1
                 ):
        SimEntityBase.__init__(self)
        self.number_subs = number_subs
        self.time_refuel_generator = time_refuel_generator
        self.refuel_limit = refuel_limit
        self.time_maintenance_generator = time_maintenance_generator
        self.distance_subs_generator = distance_subs_generator
        self.plane_speed_generator = plane_speed_generator
        self.plane_endurance_generator = plane_endurance_generator
        self.minimum_endurance = minimum_endurance
        self.minimum_speed = minimum_speed

        h = 2/(self.plane_speed_generator.max - self.plane_speed_generator.min)
        mode_min = (self.plane_speed_generator.mode - self.plane_speed_generator.min)
        left_area = mode_min*h*0.5
        if left_area > chance_overlap:
            self.minimum_speed_relief = ((2*chance_overlap*mode_min)/h)**(0.5) + self.plane_speed_generator.min
        else:
            max_mode = (self.plane_speed_generator.max - self.plane_speed_generator.mode)
            self.minimum_speed_relief = ((2*(1-chance_overlap)*max_mode)/h)**(0.5) + self.plane_speed_generator.max

        # -- state variables -- 
        self.aircraft_off_CVN = nan
        self.aircraft_on_station = nan
        self.aircraft_refueling = nan
        self.aircraft_en_route = nan

        # -- state variable lists -- 
        self.list_aircraft_off_CVN = []
        self.list_aircraft_on_station = []
        self.list_aircraft_refueling = []
        self.list_aircraft_en_route = []
        self.list_time_points = []
        self.dict_sub_info = {}


    def reset(self):
        self.aircraft_off_CVN = 0
        self.aircraft_on_station = 0
        self.aircraft_refueling = 0
        self.aircraft_en_route = 0

        self.list_aircraft_off_CVN = []
        self.list_aircraft_on_station = []
        self.list_aircraft_refueling = []
        self.list_aircraft_en_route = []
        self.list_time_points = []
        self.dict_sub_info = {}


    def record_state(self):
        # Record state variables and time point
        self.list_time_points.append(EventList.simtime)
        self.list_aircraft_off_CVN.append(self.aircraft_off_CVN)
        self.list_aircraft_on_station.append(self.aircraft_on_station)
        self.list_aircraft_refueling.append(self.aircraft_refueling)
        self.list_aircraft_en_route.append(self.aircraft_en_route)


    def run(self): 
        self.schedule('initSubs', 0.0, 1) 
        self.notify_state_change('aircraft_off_CVN', self.aircraft_off_CVN)
        self.notify_state_change('aircraft_on_station', self.aircraft_on_station)
        self.notify_state_change('aircraft_refueling', self.aircraft_refueling)
        self.notify_state_change('aircraft_en_route', self.aircraft_en_route)
        self.record_state()


    def initSubs(self, id_sub):
        # -- initialize sub in dictionary tracker --
        dist = self.distance_subs_generator.generate()
        self.dict_sub_info[id_sub] = {'dist' : dist, # generate random distance away from CVN
                                      'units' : {}, # initialize sub-dictionary that will keep track of the aircraft assigned to track sub
                                      't_out_slowest' : dist/self.minimum_speed,
                                      't_out_relief' : dist/self.minimum_speed_relief} 
        self.schedule('initAircraft', 0.0, id_sub, 1) # begin initializing the aircraft that will support
        if id_sub < self.number_subs: 
            self.schedule('initSubs', 0.0, id_sub+1)
        self.record_state()


    def initAircraft(self, id_sub, id_air):
        t_out = self.dict_sub_info[id_sub]['dist'] / self.plane_speed_generator.generate()
        t_back = self.dict_sub_info[id_sub]['dist'] / self.plane_speed_generator.generate()
        self.dict_sub_info[id_sub]['units'][id_air] = {'refuel_counter' : 0, # initialize refuel counter for aircraft at 0
                                                       'endurance' : self.plane_endurance_generator.generate(), 
                                                       't_out' : t_out,
                                                       't_back' : t_back} 

        self.schedule('onStationStart', t_out, id_sub, id_air, t_out, 0)
        
        relief_take_off_time = self.dict_sub_info[id_sub]['units'][id_air]['endurance'] - self.dict_sub_info[id_sub]['t_out_slowest'] - self.dict_sub_info[id_sub]['t_out_relief']
        if t_out > relief_take_off_time and len(self.dict_sub_info[id_sub]['units']) == 1:
            self.schedule('initAircraft', relief_take_off_time, id_sub, id_air+1) 

        self.aircraft_en_route += 1
        self.aircraft_off_CVN += 1
        self.notify_state_change('aircraft_off_CVN', self.aircraft_off_CVN)
        self.notify_state_change('aircraft_en_route', self.aircraft_en_route)
        self.record_state()

    
    def onStationStart(self, id_sub, id_air, t_used, ind_last):
        self.aircraft_on_station += 1
        self.notify_state_change('aircraft_on_station', self.aircraft_on_station)

        self.schedule('scheduleBackup', (self.dict_sub_info[id_sub]['units'][id_air]['endurance'] - self.dict_sub_info[id_sub]['t_out_slowest'] - self.dict_sub_info[id_sub]['t_out_relief'] - t_used), id_sub, id_air)

        if ind_last == 0:
            self.aircraft_en_route -= 1
            self.notify_state_change('aircraft_en_route', self.aircraft_en_route)
        else:
            self.aircraft_refueling -= 1
            self.notify_state_change('aircraft_refueling', self.aircraft_refueling)
        self.record_state()


    def scheduleBackup(self, id_sub, id_air):
        self.schedule('onStationEnd', self.dict_sub_info[id_sub]['t_out_relief'], id_sub, id_air)
        if self.dict_sub_info[id_sub]['units'][id_air]['refuel_counter'] >= self.refuel_limit:
            self.schedule('initAircraft', 0.0, id_sub, id_air+1)


    def onStationEnd(self, id_sub, id_air):
        self.aircraft_on_station -= 1
        self.notify_state_change('aircraft_on_station', self.aircraft_on_station)
        if self.dict_sub_info[id_sub]['units'][id_air]['refuel_counter'] < self.refuel_limit:
            self.aircraft_refueling += 1
            t_refuel = self.time_refuel_generator.generate()
            self.schedule('onStationStart', t_refuel, id_sub, id_air, t_refuel, 1)
        else:
            self.schedule('returnToCarrier', 
                          self.dict_sub_info[id_sub]['units'][id_air]['t_back'] + self.time_maintenance_generator.generate(),
                          id_sub, id_air)
            del self.dict_sub_info[id_sub]['units'][id_air]
        self.record_state()


    def returnToCarrier(self):
        self.aircraft_off_CVN -= 1 
        self.notify_state_change('aircraft_off_CVN', self.aircraft_off_CVN)
        self.record_state() 
