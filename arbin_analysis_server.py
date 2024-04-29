


import sys
sys.path.append("../config")
sys.path.append("../driver")
from arbin_driver import arbin_driver 
from config.arbin_config import arbin_config
import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel
import requests
import matplotlib
#matplotlib.use('Agg')
import matplotlib.pyplot as plt
import hdfdict
import numpy as np
import re
#import seaborn as sea
import pandas as pd
import tkinter as tk
from tkinter import W, messagebox
import matplotlib.cm as cm 
import os
import csv
from matplotlib.colors import Normalize
import pickle
import shutil
import subprocess
from scipy import interpolate
from copy import deepcopy
from datetime import datetime

app = FastAPI(title="ARBIN battery cycler analysis_server V1", 
    description="This is a fancy ARBIN_analysis_server", 
    version="1.0")

appservername = "/arbin_analysis"

class return_class(BaseModel):
    parameters: dict = None
    data: dict = None

def atof(text):
    try:
        retval = float(text)
    except ValueError:
        retval = text
    return retval
def natural_keys(text):
    return [ atof(c) for c in re.split(r'[+-]?([0-9]+(?:[.][0-9]*)?|[.][0-9]+)', text) ]

def authentication_Header_finales():
    accessInfo = requests.post(
            "http://{}:{}/user_management/authenticate".format(arbin_config["finales"],arbin_config["portfinales"]),
                data={
                    "grant_type": "",
                    "username": arbin_config["tenantUsername"],
                    "password": arbin_config["tenantUserPassword"],
                    "scope": "",
                    "client_id": "",
                    "client_secret": ""

                },
                params={
                "userDB": f"/root/data/FINALES2/src/FINALES2/userManagement/userDB.db",
                    },
            headers={
                    "accept": "application/json",
                    "Content-Type": "application/x-www-form-urlencoded",
                    }
            )
    access_information = accessInfo.json()
    authorization_header = {
                "accept": "application/json",
                "Authorization": (
                    f"{access_information['token_type'].capitalize()} "
                    f"{access_information['access_token']}"
                ),
            }
    return(authorization_header)



@app.on_event("startup")
def startup():
    global arbin 
    arbin = arbin_driver(arbin_config)
    global analysisDict
    analysisDict = {}
    global cyclenamelist
    cyclenamelist = []

@app.get(appservername + "/check_on")
def check_on():
    return "200"


@app.get(appservername + "/loadHDF5")
def loadHDF5(hdf5name:str):
        data = requests.get("{}/arbin/loadHDF5".format(urlserver), params={"hdf5name":hdf5name}).json()
        return data
        

@app.get(appservername + "/EOLAnalysis")
def EOLAnalysis(data:dict , filepath):

    def get_capacity_curve(cell, cycle, is_discharge):
        """used to calculate the variance between two cycels, simply returns the relevant parts (ie discharging) of the v and q curve"""
        # v_curve = cell['V'][cycle]         
        # qc_curve = cell['Qc'][cycle]
        # qd_curve = cell['Qd'][cycle]

        # limit_idx = v_curve.shape[0]

        # v_curve = v_curve[:limit_idx]

        if is_discharge:
            q_curve = cell['dischargeE'][cycle]
            v_curve = cell['dischargeV'][cycle]


        else:
            q_curve = cell['chargeE'][cycle]
            v_curve = cell['chargeV'][cycle]

        return (v_curve, q_curve)

    def get_qefficiency(battery, cycle):
        """for a given battery data and cycle, calculate the coloumbic efficiency

        Args:
            battery ([type]): [description]
            cycle ([type]): [description]

        Returns:
            [type]: [description]
        """
        _, cq_curve = get_capacity_curve(battery, "Cycle_"+str(cycle), is_discharge=False)
        dv_curve, dq_curve = get_capacity_curve(battery, "Cycle_"+str(cycle+1), is_discharge=True)
        dv_filtered = []
        dq_filtered = []
        for i in range(len(dv_curve)):
            if dv_curve[i] > voltage_min + 0.005:
                dv_filtered.append(dv_curve[i])
                dq_filtered.append(dq_curve[i])
        dq_curve_abs = max(dq_filtered)  # - dq_curve.min()
        cv_curve_abs = max(cq_curve)  # - cq_curve.min()
        # return dq_curve_abs, cv_curve_abs, dq_curve_abs / cv_curve_abs

        return -1, -1, dq_curve_abs / cv_curve_abs

    def get_mean_voltage_difference(battery, cycle):
        """calculate overpotential for a given battery and cycle

        """
        cv_curve, _ = get_capacity_curve(battery, "Cycle_"+str(cycle), is_discharge=False)
        dv_curve, dq_curve = get_capacity_curve(battery, "Cycle_"+str(cycle+1), is_discharge=True)
        # print(dv_curve.max())
        # print(dv_curve.shape)
        dv_filtered = []
        for i in range(len(dv_curve)):
            if dv_curve[i] >  2.005:
                dv_filtered.append(dv_curve[i])
        # start_cap = cq_curve.max()
        # print(dv_curve.mean())
        mean_cv = sum(cv_curve)/ len(cv_curve)
        mean_dv = sum(dv_filtered)/ len(dv_filtered)

        return mean_cv - mean_dv

    def get_capacity_spline(cell, cycle):
        """
        splines the voltage capacity curve
        """

        v_curve, q_curve = get_capacity_curve(cell, "Cycle_"+str(cycle+1), is_discharge=True)
        unique_values, unique_indices = np.unique(v_curve, return_index=True)
        v_curve = v_curve[unique_indices]
        q_curve = q_curve[unique_indices]
        f = interpolate.interp1d(v_curve, q_curve, fill_value="extrapolate")
        points = np.linspace(voltage_max, voltage_min, num=1000) #XXX values
        spline = f(points)
        spline[np.where(np.isnan(spline))] = 0
        return spline

    print(data)
    analysisDict={}
    requestdata = deepcopy(data)
    net_use_command = f'net use {arbin_config["network_drive_path_40Cycles"]} {arbin_config["password"]} /user:{arbin_config["username"]} /persistent:no'
    subprocess.run(net_use_command, shell=True)
    try:
        originpath = os.getcwd()
        try:
            data = arbin.getChannelData(filepath)
        except:
            exit
        print(f'Folder access successfully.')
        os.chdir(originpath)
        testTime,cycleIndex,stepIndex,I,V,chargeEnergy,dischargeEnergy = arbin.serperaterawData(data)
        cyclelist = arbin.getCyclelimitListFINALES(cycleIndex,stepIndex,I)
        analysisDict={}
        cyclenamelist=[]
        analysisDict['raw'] = {}
        analysisDict['split'] = {}
        analysisDict['split']['Wettingtime'] = {} 
        cyclenamelist.append('Wettingtime')
        for i in range(1,4):
            analysisDict['split']['FormationCycle_Charge_'+str(i)] = {} 
            cyclenamelist.append('FormationCycle_Charge_'+str(i))
            analysisDict['split']['FormationCycle_Discharge_'+str(i)] = {} 
            cyclenamelist.append('FormationCycle_Discharge_'+str(i))
        analysisDict['split']['Rest'] = {} 
        cyclenamelist.append('Rest')
        for i in range(1,len(cyclelist)-7):
            analysisDict['split']['Cycle_'+str(i)] = {} 
            cyclenamelist.append('Cycle_'+str(i))
        #print(len(cyclelist))
        arbin.getandsafeCycledata(cyclelist,testTime,I,V,chargeEnergy,dischargeEnergy,analysisDict,cyclenamelist )
        """for i in cyclenamelist:
                t = analysisDict['split'][i]['t']
                v = analysisDict['split'][i]['V']
                print(i)
                plt.scatter(t,v)
                plt.show()"""
        arbin.saveDatatoDic(testTime,stepIndex,I,V,chargeEnergy,dischargeEnergy,analysisDict,cyclelist)
        arbin.changeDatatype(analysisDict)  # Error of ValueError: [TypeError('cannot convert dictionary update sequence element #0 to a sequence') is because of datatype np.arra in beginning
        hdf5name= filepath.split("\\")[-1] + '.hdf5'
        arbin.save_dict_to_hdf5(analysisDict,hdf5name)
    except Exception as e:
        print(f'An error occurred: {str(e)}')
    finally:
        # Unmap the network drive when done (optional)
        unmap_command = f'net use {arbin_config["network_drive_path_40Cycles"]} /delete'
        subprocess.run(unmap_command, shell=True)
    data = analysisDict
    data_prep = {}
    allcapa = []
    cycles = []
    for i in data['split'].keys():
        if re.search('FormationCycle_' +'.+',i) != None:
            pass
        elif re.search('Rest',i) != None:
            pass
        elif re.search('Wettingtim',i) != None:
            pass
        else:
            cycles.append(i)
    cycles.sort(key=natural_keys)
    #charge
    data_prep={
                "capacityCharge": {},
                "chargeE": {},
                "chargeV": {},
                "capacityDischarge": {},
                "dischargeE": {},
                "dischargeV": {}
            }
    for i in range(0,len(cycles),2):
        try:
            currentlist = data['split'][cycles[i]][str(cycles[i])+'_Current(A)']
            timelist = data['split'][cycles[i]][str(cycles[i])+'_Testtime(s)']
            #plt.plot(timelist,data['split'][l]['V'])
            #plt.show()
        except:
            currentlist = data['split'][cycles[i]]['I']
            timelist = data['split'][cycles[i]]['t']
            #plt.plot(timelist, data['split'][l]['V'])
            #plt.show()
        if currentlist[1] == 0: 
            c = 0
        else:
            c = np.trapz(currentlist, timelist) * (1000/3600)
        allcapa.append(abs(c))
        data_prep['capacityCharge'][cycles[i]] = abs(c)
        data_prep['chargeE'][cycles[i]] = data['split'][cycles[i]]['chargeE']
        data_prep['chargeV'][cycles[i]] = data['split'][cycles[i]]['V']
    # discharge
    for i in range(1,len(cycles),2):
        try:
            currentlist = data['split'][cycles[i]][str(cycles[i])+'_Current(A)']
            timelist = data['split'][cycles[i]][str(cycles[i])+'_Testtime(s)']
            #plt.plot(timelist,data['split'][l]['V'])
            #plt.show()
        except:
            currentlist = data['split'][cycles[i]]['I']
            timelist = data['split'][cycles[i]]['t']
            #plt.plot(timelist, data['split'][l]['V'])
            #plt.show()
        if currentlist[1] == 0: 
            c = 0
        else:
            c = np.trapz(currentlist, timelist) * (1000/3600)
        allcapa.append(abs(c))
        data_prep['capacityDischarge'][cycles[i]] = c
        data_prep['dischargeE'][cycles[i]] = data['split'][cycles[i]]['dischargeE']
        data_prep['dischargeV'][cycles[i]] = data['split'][cycles[i]]['V']
    data_prep['Capacity_list'] = allcapa

    voltage_min = 2.5
    voltage_max = 4.2

    start_cycle = 21 # correspons to charge part of cycle 10
    stop_cycle = 81 # correspons to charge part of cycle 40

    try:
        delta_coul_eff = get_qefficiency(data_prep, stop_cycle)[2] - get_qefficiency(data_prep, start_cycle)[2]
    except:
        delta_coul_eff = 0
    try:
        volt_gap = get_mean_voltage_difference(data_prep, stop_cycle) - get_mean_voltage_difference( data_prep, start_cycle)
    except:
        volt_gap = 0

    try:
        start_curve = get_capacity_spline( data_prep, start_cycle )
        stop_curve = get_capacity_spline( data_prep, stop_cycle)
        idxs = np.where( 1 - (np.isnan(start_curve) + np.isnan(stop_curve)) )  
        qv_variance = np.log( (start_curve[idxs] - stop_curve[idxs]).var())
    except:
        qv_variance = 0

    capa_list = data_prep['Capacity_list']

    #print(delta_coul_eff)
    #print(volt_gap)
    #print(qv_variance)
    print(capa_list)

    #print("WARNING: battery {} has fewer than 100 cycles".format(i))
    #print(delta_coul_eff)
        #print(volt_gap)
        #print(qv_variance)
    print(len(capa_list))
    if len(capa_list) == requestdata["request"]["parameters"]["cycling"]["number_cycles"]*2:
        succes_result = True
    else:
        succes_result= False
    print(requestdata["request"]["parameters"]["cycling"]["number_cycles"]*2)
    print("Success of cell: "+str(succes_result))
    result ={
        "data": {
            "capacity_list": capa_list,
            "average_charging_rate": 1.0,
            "maximum_charging_rate": 1.0,
            "minimum_charging_rate": 1.0,
            "delta_coulombic_efficiency": delta_coul_eff,
            "voltage_gap_charge_discharge": volt_gap,
            "capacity_vector_variance": qv_variance,
            "run_info" : {
                        "success": succes_result,
                        "errors": {},
                        "warning": {},
                        "run_timestamps": {"service": {"start": "", "finish": "" }},
                        "run_description": {"service":{"description":"Reservation of channels"}},
                        "predecessor": {},
                        "campaignID": "Auto-POLiS",
                        "studyID": "NVP Hückelsalts study"
                    }
        },
        "quantity": "capacity",
        "method": [
        "cycling"
        ],
        "parameters":{ "cycling": requestdata['request']['parameters']['cycling']},
        "tenant_uuid": arbin_config["tenantUUID"],
        "request_uuid": requestdata["uuid"]  
    }
    reply = requests.post(
        "http://{}:{}/results/".format(arbin_config["finales"],arbin_config["portfinales"]),
        json=result,
        params={},
        headers=authentication_Header_finales()
    )
    print(reply)
    print(datetime.now())




if __name__ == "__main__":
    urlanalysis = "http://{}:{}".format(arbin_config['arbinanalysis'],arbin_config['portanalysis'])
    urlaktion = "http://{}:{}".format(arbin_config['arbinaktion'],arbin_config['portaktion'])
    urlserver = "http://{}:{}".format(arbin_config['arbinserver'],arbin_config['portserver'])
    urlrobot = "http://{}:{}".format(arbin_config['robot'],arbin_config['portrobot'])
    uvicorn.run(app, host=arbin_config["arbinanalysis"], port=arbin_config["portanalysis"])

