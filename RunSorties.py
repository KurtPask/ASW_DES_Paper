# RunSorties.py
# Description: This file contains the script used to run the sorties.py discrete event simulation.
# Author: Kurt Pasque
# Date: March 14, 2024

from simkit.rand import RandomVariate 
from simkit.base import EventList
from simkit.stats import SimpleStatsTimeVarying
from sorties import SortyModel
import matplotlib.pyplot as plt

import numpy as np
import seaborn as sns
import pandas as pd
from scipy.stats import gaussian_kde
import csv

num_steps = 25
sub_list = [10]
total_subs = len(sub_list)
simulation_iterations = 1
for_report = False
probability = 0.95
dict_data = {number_subs : {} for number_subs in range(1, total_subs + 1)}

def get_kde_value_at_probability(integer_list, probability, plot):
    kde = gaussian_kde(integer_list) # Create kernel density estimate from the integer list
    x_values = np.linspace(min(integer_list), max(integer_list), 1000) # Define range of values for the KDE evaluation
    kde_values = kde.evaluate(x_values) # Evaluate the KDE at the defined x values
    pdf = np.cumsum(kde_values) / np.sum(kde_values) # Integrate KDE values to find the probability density function
    index = np.argmax(pdf >= probability) # Find the value corresponding to the given probability
    kde_value = x_values[index]
    if plot:
        plt.plot(x_values, kde_values, label='KDE')
        plt.axvline(x=kde_value, color='red', linestyle='--', label=f'{probability * 100}% Probability')
        plt.xlabel('Number of Aircraft')
        plt.ylabel('Probability')
        plt.title(f'Kernel Density Estimation\n{round(kde_value,1)} Aircraft needed for {probability * 100}% Mission Coverage')
        plt.legend()
        plt.show()
    return kde_value

for number_subs in sub_list:
    list_off_cvn = []
    for iterations in range(simulation_iterations):
        if (iterations+1) % 5 == 0:
            print(number_subs, iterations+1)
        # ---- INPUT PARAMETERS ----
        # -- time distributions --
        time_refuel_generator = RandomVariate.instance('Triangular', min=1*60 - 15, mode=1*60, max=1*60 + 30) # minutes 
        time_maintenance_generator = RandomVariate.instance('Triangular', min=7*60, mode=8*60, max=72*60) 

        distance_out_generator = RandomVariate.instance('Triangular', min=100, mode=600, max=750) # nm, for subs "spawning"

        minimum_speed = 2.5
        plane_speed_generator = RandomVariate.instance('Triangular', min=minimum_speed, mode=3.5, max=3.8) # nautical miles per minute

        minimum_endurance = 20*60 #minutes  
        plane_endurance_generator = RandomVariate.instance('Triangular', min=minimum_endurance, mode=30*60, max=32*60) # nautical miles per minute

        # -- size of model -- 
        refuel_limit = 0
        chance_overlap = 1

        # ---- SIMULATION ----
        # -- initialize model -- 
        missions = SortyModel(
                        number_subs = number_subs, #count
                        distance_subs_generator = distance_out_generator, #nm
                        plane_speed_generator = plane_speed_generator, #nautical miles/minute
                        time_refuel_generator = time_refuel_generator, #minutes
                        time_maintenance_generator = time_maintenance_generator, #minutes
                        refuel_limit = refuel_limit, # count
                        plane_endurance_generator = plane_endurance_generator, #minutes
                        minimum_endurance = minimum_endurance, #minutes
                        minimum_speed = minimum_speed, #knots/minute
                        chance_overlap = 1 - chance_overlap,
                        )

        # -- track key state variables from project prompt -- 
        aircraft_off_CVN = SimpleStatsTimeVarying('aircraft_off_CVN')
        missions.add_state_change_listener(aircraft_off_CVN)

        aircraft_on_station = SimpleStatsTimeVarying('aircraft_on_station')
        missions.add_state_change_listener(aircraft_on_station)

        aircraft_refueling = SimpleStatsTimeVarying('aircraft_refueling')
        missions.add_state_change_listener(aircraft_refueling)

        aircraft_en_route = SimpleStatsTimeVarying('aircraft_en_route')
        missions.add_state_change_listener(aircraft_en_route)

        # -- begin simulation -- 
        EventList.verbose = False
        EventList.stop_at_time(4*7*24*60) 
        EventList.reset()
        EventList.start_simulation()

        # ---- RESULTS ---- 
        # -- printout -- 
        sigFigs = 4

        missions.list_aircraft_off_CVN

        plt.plot(missions.list_time_points, missions.list_aircraft_off_CVN, label="MQ-9B's in Use")
        plt.plot(missions.list_time_points, missions.list_aircraft_on_station, label="MQ-9B's on Station over Sub")
        plt.plot(missions.list_time_points, missions.list_aircraft_en_route, label="MQ-9B's en Route from CVN to Station")
        plt.ylabel("Count of MQ-9B's")
        plt.xlabel("Simulation Time (minutes) - Total Time is 4 Weeks")
        plt.title("Simulation of MQ-9B's in CVW Maintaining Contact with 10 Submarines")
        plt.legend()
        plt.show()
        for integer in [i for i in missions.list_aircraft_off_CVN if i > (number_subs*2 - 2)]:
            if integer in dict_data[number_subs]:
                dict_data[number_subs][integer] += 1
            else:
                dict_data[number_subs][integer] = 1
        EventList.reset()
        missions.reset()

if for_report:
    row_names = set()
    for inner_dict in dict_data.values():
        row_names.update(inner_dict.keys())

    # Sort row names for consistent order
    row_names = sorted(row_names)

    # Write the dictionary to a CSV file
    with open('full_data.csv', 'w', newline='') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=[''] + list(dict_data.keys()))
        writer.writeheader()
        for row_name in row_names:
            row_dict = {'': row_name}
            for col_name, inner_dict in dict_data.items():
                row_dict[col_name] = inner_dict.get(row_name, '')
            writer.writerow(row_dict)


    fig, axs = plt.subplots(len(dict_data), 1, figsize=(10, 10), sharex=True)  
    dfs = []
    # -- loop for plotting histogram on the figure --
    for i, key in enumerate(list(dict_data.keys())):
        ax = axs[i] if len(dict_data) > 1 else axs  # handle case for single subplot
        
        #-----
        data = []
        for value, count in dict_data[key].items():
            data.extend([value] * count)

        # Create Gaussian KDE
        kde = gaussian_kde(data)
        #-----
        #kde = gaussian_kde(dict_data[key]) # Create kernel density estimate from the integer list
        x_values = np.linspace(min(data), max(data), 1000) # Define range of values for the KDE evaluation
        kde_values = kde.evaluate(x_values) # Evaluate the KDE at the defined x values
        pdf = np.cumsum(kde_values) / np.sum(kde_values) # Integrate KDE values to find the probability density function
        index = np.argmax(pdf >= probability) # Find the value corresponding to the given probability
        kde_value = x_values[index]

        # -- 99% --
        index = np.argmax(pdf >= 0.99) # Find the value corresponding to the given probability
        kde_value_99 = x_values[index]

        #--
        ax.axvline(x=kde_value, color='blue', linestyle='--', label=f'95% Mission Coverage with {round(kde_value, 1)} Aircraft')
        ax.axvline(x=kde_value_99, color='green', linestyle='--', label=f'99% Mission Coverage with {round(kde_value_99, 1)} Aircraft')

        # - histogram and kde's - 
        sns.histplot(data, ax=ax, kde=False, color="red", alpha = 0.2, stat="probability", label=f'Aircraft Requirements during Simulation')

        sns.kdeplot(data, ax=ax, color="red", bw_method=0.65)

        # - title and legend -
        ax.set_ylabel(f'{key} Subs')
        ax.legend(facecolor='lightgrey')
        df_temp = pd.DataFrame({'95': [kde_value], '99': [kde_value_99]})
        dfs.append(df_temp)
    df = pd.concat(dfs, ignore_index=True)
    df.to_csv('percentage_results.csv', index=False)
    # - last adjustment to plot and print -
    plt.tight_layout(pad=0.1, h_pad=0.1, w_pad=0.1)
    plt.show()


