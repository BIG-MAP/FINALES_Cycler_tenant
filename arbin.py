#this is the server
import sys
sys.path.append("../FINALES2")
sys.path.append('../FINALES2_schemas')
from arbin_driver import arbin_driver 
from config.arbin_config import arbin_config
import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel
from copy import deepcopy
from datetime import datetime, timedelta
import numpy as np
import os
import re
from uuid import uuid4
import json
import shutil
import subprocess
import time

import requests

from logging.config import dictConfig
import logging
import pytz
from Logger.logger import LogConfig
from Logger.loggerreservation import LogConfigRes


from fastapi_utils.tasks import repeat_every
import traceback



#
# TODO:
# nach circa 40 Zyklen daten exportieren, an Analyse schicken und als results schicken für EOL
# Channels limitieren damit nicht 1 Project alle Kanäle braucht -> interner Standardwert der schaut wie viele Projekte eingetragens sind
# Absicherung gegen Ausfälle => Channels mit daten Speichern und dann immer wieder neu als config laden ?
# mitspeichern wo rohdaten liegen/gespeichert werden
# channels reservation aufpicken und bearbeiten & ids speichern 

arbin = arbin_driver(arbin_config)
daq_number = 0
jobqueue = []
channels_blocked= {}
channels_available = []
TTL = 20
quantities = {
            "capacity": {
                            "methods": ["cycling"]
                        },
            "cycling_channel": {
                            "methods": ["service"]
            }   
                }
status = 0 # status 0 = free, status = 1 in Use


app = FastAPI(title="ARBIN battery cycler server V1", 
    description="This is a fancy ARBIN server", 
    version="1.0")

appservername = "/arbin"

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

def change_status(requestID, new_status):
    auth_header = authentication_Header_finales()
    reserved = requests.post("http://{}:{}/requests/{}/update_status/".format(arbin_config["finales"],arbin_config["portfinales"], requestID),
                                        params={'request_id' : requestID, 'new_status': new_status},
                                        headers=auth_header,
                                        )
    logger.info("Request: "+ str(requestID)+ " : " + str(reserved.json()))
    return reserved

def utc_to_local(utc_dt):
            local_tz = pytz.timezone('Europe/Berlin')
            local_dt = utc_dt.replace(tzinfo=pytz.utc).astimezone(local_tz)
            return local_tz.normalize(local_dt)

@app.get("/")
async def get_global_variables():
    # Access global variables
    return {
        "arbin": arbin,
        "daq_number": daq_number,
        "jobqueue": jobqueue,
        "channels_blocked": channels_blocked,
        "channels_available": channels_available,
        "TTL": TTL,
        "quantities": quantities,
        "status": status
    }

@app.on_event("startup")
def startup():
    global arbin
    global daq_number
    global jobqueue
    global channels_blocked
    global channels_available
    global TTL
    global quantities
    global status
    logger.info('Starting Arbin Server')
    loggerreservation.info('Starting Reservations') 
    try:
        aktion = requests.get("http://{}:{}/arbin_aktion/check_on".format(arbin_config["arbinaktion"],arbin_config["portaktion"]), params={}).status_code
    except:
        aktion = 500
    try:
        analysis = requests.get("http://{}:{}/arbin_analysis/check_on".format(arbin_config["arbinanalysis"],arbin_config["portanalysis"]), params={}).status_code
    except:
        analysis = 500
    try:
        authorization_header= authentication_Header_finales()
        finales = requests.get("http://{}:{}/".format(arbin_config["finales"],arbin_config["portfinales"]), params={}, headers=authorization_header).status_code
    except:
        finales = 500
    if aktion !=200:
        connectiontext = "Cannot establish connection to arbinaktion"
        logger.error(str(connectiontext))
    elif analysis !=200:
        connectiontext = "Cannot establish connection to arbinanalysis"
        logger.error(str(connectiontext))
    elif finales !=200:
        connectiontext = "Cannot establish connection to finales"
        logger.error(str(connectiontext))
    else:
        connectiontext = "Connected to all servers"
        logger.info(str(connectiontext))
    
    for i in range(1,65):
        channels_blocked[str(i)] = {'requestID': '',
                                    'reservationID': '',
                                    "protocol": "",
                                    "numbCycles": "",
                                    "startDate":"",
                                    "endDate": "",
                                    "finaleExport": "",
                                    'TTL': TTL,
                                    'Problems': {}}
    path = os.getcwd()
    os.chdir(arbin.pathdaqlog)
    foldercontent = os.listdir()
    foldercontent.sort(key=natural_keys)
    for i in range(len(foldercontent)-1, -1, -1):    # reversed looping over content for lates log file
        if re.search('DaqInfoLog' +'.+',foldercontent[i]) != None: 
            name_logfile = foldercontent[i]
            break
    with open(name_logfile, 'r')as log:
        lines = log.readlines()
    log.close()
    os.chdir(path)  # latest number of entry in daq infolog
    daq_number = int(lines[-1].split(" ")[2].split("]")[0])
    logger.info("First daq number: "+ str(daq_number))
    batch_list = arbin.get_ArbinSysbatch()
    for i in range(len(batch_list)):
        if "Batch_Test" in batch_list[i]:
            channelnumb = batch_list[i].split('Batch_Test')[1]
            channelnumb = int(channelnumb[:-1])+1 # deleting the outer bracket and increment(as count starts from 0) 
            schedulename = batch_list[i+5].split('=')[1]
            if schedulename == '': # if empty no test is running
                channels_available.append(channelnumb)
    total_channels = list(range(1,65))
    blocked = list(set(total_channels) - set(channels_available))
    blocked.sort()
    channels_available.sort()
    try:
        filepath = "cycler_info.json"
        with open(filepath, 'r') as fileobj:
            cycler_params = json.load(fileobj)
        jobqueue = cycler_params["jobqueue"]
        daq_number = cycler_params["daq_number"]
        channels_blocked = cycler_params["channels_blocked"]
        channels_blocked_number= []
        channels_available_file = []
        for key in channels_blocked.keys():
            if channels_blocked[key]["reservationID"] == "":
                channels_available_file.append(int(key))
            else:
                channels_blocked_number.append(int(key))
        if blocked == channels_blocked_number and channels_available_file == channels_available:
            loggerreservation.info("Loaded initialy blocked channels"+ str(channels_blocked_number))
            logger.info("Loaded channels available : "+ str(channels_available))
        else:            
            dif1 = list(np.setdiff1d(np.array(blocked), np.array(channels_blocked_number)))
            dif2 = list(np.setdiff1d(np.array(channels_blocked_number), np.array(blocked))  ) 
            for element in dif1:
                channels_blocked[str(element)]['requestID'] =  'Check log for id'
                channels_blocked[str(element)]["reservationID"] = "11111111111111"
                now = datetime.now()
                current_time = now.strftime("%Y-%m-%d %H:%M:%S CET")
                channels_blocked[str(element)]['Problems'][current_time] ='Check log for id'
            """
            turn on so batchfile information you want to use
            for element in dif2:
                channels_blocked[str(element)]['requestID'] =  ''
                channels_blocked[str(element)]["reservationID"] = ""
                channels_blocked[str(element)]['Problems']={}"""
            loggerreservation.info("Loaded blocked channels "+ str(channels_blocked_number)+" and the current blocked channels from batch file "+str(blocked)+" are not the same.\n Proceeding with blocked channels from cycler_info file")
            logger.info("Loaded channels available : "+ str(channels_available_file)+" and the current available channels from batch file "+str(channels_available)+" are not the same. \n Proceeding with blocked channels from cycler_info file")
    except:
        cycler_params_dict = {}
        for i in blocked:
            channels_blocked[str(i)]['requestID'] =  'Check log for id'
            channels_blocked[str(i)]["reservationID"] = "11111111111111"
            now = datetime.now()
            current_time = now.strftime("%Y-%m-%d %H:%M:%S CET")
            channels_blocked[str(i)]['Problems'] ='Check log for id'
        cycler_params_dict["daq_number"] = daq_number
        cycler_params_dict["jobqueue"] = jobqueue
        cycler_params_dict["channels_blocked"] = channels_blocked
        filepath =  "cycler_info.json"
        now = utc_to_local(datetime.now())
        current_time = now.strftime("%Y-%m-%d %H:%M:%S CET")
        filepath =  "cycler_info.json"
        with open(filepath, 'w') as fileobj:
            json.dump(cycler_params_dict, fileobj, indent=2)
        logger.info("Saved first cycler_info file with current status of channels")
        loggerreservation.info("Saved first cycler_info file with current status of channels")
    logger.info("Loaded jobs from Jobqueue : "+ str(jobqueue))


@app.on_event("startup")
@repeat_every(seconds=30)
def save_cycler_params():
    global arbin
    global daq_number
    global jobqueue
    global channels_blocked
    global channels_available
    global TTL
    global quantities
    global status
    cycler_params_dict = {}
    cycler_params_dict["daq_number"] = daq_number
    cycler_params_dict["jobqueue"] = jobqueue
    cycler_params_dict["channels_blocked"] = channels_blocked
    now = utc_to_local(datetime.now())
    current_time = now.strftime("%Y-%m-%d %H:%M:%S CET")
    cycler_params_dict["creation_time"] = current_time
    filepath =  arbin_config["pathOfJsonfile"] + "\cycler_info.json"
    with open(filepath, 'w') as fileobj:
        json.dump(cycler_params_dict, fileobj, indent=2)
    os.chdir()
    logger.info("Saved")

@app.on_event("startup")
@repeat_every(seconds=90)
def update_queue():
    '''
    Combines get_requests and update_queue of the reference tenant
    '''    
    global arbin
    global daq_number
    global jobqueue
    global channels_blocked
    global channels_available
    global TTL
    global quantities
    global status
    logger.info("Updating request queue")
    if len(channels_available) == 0: # if no channels are free wait for next check
        pass
    else:  
        # login to the server
        authorization_header= authentication_Header_finales()
        logger.info("Logged in as "+str(arbin_config["tenantUsername"],)+" now looking for tasks...")

        # get the quantity-specific pending requests from the FINALES server
        pendingRequests=[]
        for quantity in quantities.keys():
            for method in quantities[quantity]["methods"]:
                req = requests.get("http://{}:{}/pending_requests/".format(arbin_config["finales"],arbin_config["portfinales"]),
                                            params={"quantity": quantity, "method": method},
                                            headers=authorization_header,
                                            ).json()
                pendingRequests = pendingRequests + req
                logger.info("Adding new request: ")
        # get the relevant requests
        for pendingItem in pendingRequests:
            # create the Request object from the json string
            requestDict = pendingItem["request"]
            ID = pendingItem['uuid']
            # request for reservation
            if requestDict["quantity"] == "cycling_channel" and requestDict["methods"][0] == "service":
                logger.info("Reservation Request started")
                status = 1
                temp = []
                try:
                    numChannelreserved = requestDict["parameters"][requestDict["methods"][0]]["number_required_channels"] 
                    numCycles = requestDict["parameters"][requestDict["methods"][0]]["number_cycles"] 
                    protocol = requestDict["parameters"][requestDict["methods"][0]]["cycling_protocol"] 
                    channels_available.sort()  # sort channels for later check
                    if len(channels_available) < numChannelreserved or channels_available[numChannelreserved]>25:  # check if enough channels are free & if last reservation is within the 24 channels
                        logger.error("Not enough available channels within the Project")
                        loggerreservation.error("Not enough available channels. Currently only "+ str(channels_available)+" for the project are available.")
                        continue
                    reservationID = uuid4()
                    for i in range(numChannelreserved):
                        if channels_blocked[str(channels_available[i])]["reservationID"] == "":
                            channels_blocked[str(channels_available[i])]["reservationID"] = str(reservationID)
                            channels_blocked[str(channels_available[i])]["numbCycles"] = numCycles
                            channels_blocked[str(channels_available[i])]["protocol"] = protocol
                            temp.append(channels_available[i])
                        else:
                            logger.error("Found channel {channels_available[0]} marked available but with reservation ID")
                            loggerreservation.error("Found channel {channels_available[0]} marked available but with reservation ID")
                            continue
                    channel_temp = result = [x for x in channels_available if x not in temp]
                    channels_available = channel_temp
                    result = requestDict.copy()
                    result["data"] = {
                        "success": True,
                        "reservation_id": str(reservationID)
                    }
                    result["request_uuid"] = ID
                    met = result.pop("methods")
                    result["method"]= met
                    #print(channels_blocked)
                    authorization_header= authentication_Header_finales()
                    postedResult = requests.post(
                        "http://{}:{}/results/".format(arbin_config["finales"],arbin_config["portfinales"]),
                        json=result,
                        params={},
                        headers= authorization_header,
                    )
                    if postedResult.status_code== 200:
                        logger.info("Reservation successfully posted to FINALES")
                        loggerreservation.info("Reservation with ID:"+str(ID)+" successfully posted to FINALES with result ID: "+str(postedResult.json()))  
                        continue  
                    else:
                        for i in temp:
                            channels_blocked[i] = {'requestID': '',
                                                    'reservationID': '',
                                                    "protocol": "",
                                                    "numbCycles": "",
                                                    "startDate":"",
                                                    "endDate": "",
                                                    "finaleExport": "",
                                                    'TTL': TTL,
                                                    'Problems': {}
                            }
                        logger.error("Something went wrong when posting the reservation to FINALES. Status code ist {postedResult}. Blocked channels are no longer blocked.")
                        loggerreservation.error("Soemthing went wrong when posting the reservation to FINALES. Status code ist {postedResult}.Blocked channels are no longer blocked.")     
                        status = 0
                        continue                       
                except:
                    for i in temp:
                                    channels_blocked[i] = {'requestID': '',
                                                            'reservationID': '',
                                                            "protocol": "",
                                                            "numbCycles": "",
                                                            "startDate":"",
                                                            "endDate": "",
                                                            "finaleExport": "",
                                                            'TTL': TTL,
                                                            'Problems': {}
                                    }
                    logger.error("Something went wrong when posting the reservation to FINALES. Status code ist {postedResult}. Blocked channels are no longer blocked.")
                    loggerreservation.error("Soemthing went wrong when posting the reservation to FINALES. Status code ist {postedResult}.Blocked channels are no longer blocked.")
                    logger.error("Reservation request failed.")
                    continue
             
            logger.info('Request '+str(ID)+ ' Input validation ...')
            try:
                reservationID = requestDict["parameters"][requestDict["methods"][0]]["reservation_number"]
            except:
                logger.info()
            reserved = change_status(requestID=ID, new_status="reserved")
            if str(reserved.status_code) == "200":
                jobqueue.append(pendingItem) # pass it to jobqueue to be worked on asap
            else:
                logger.error("New Job was accepted but could not be marked reserved")
        logger.info("Update queue finished")


@app.on_event("startup")
@repeat_every(seconds=60)
def start_job():
    global arbin
    global daq_number
    global jobqueue
    global channels_blocked
    global channels_available
    global TTL
    global quantities
    global status
    logger.info("Looking to start job from queue with length "+ str(len(jobqueue)))
    if len(jobqueue)==0:
        pass
    else:
        if status ==1:
            logger.info("Start of new job blocked")
            pass
        else:
            status =1
            tempjobqueue = deepcopy(jobqueue)
            for i in range(len(tempjobqueue)):
                try:
                    activeRequest = tempjobqueue[i]
                    # get the method, which matches
                    list_key = list(activeRequest.keys())
                    list_value = list(activeRequest.values())
                    quant = list(list_value[3].values())[0]
                    method = list(list(list_value[3].values())[2].keys())[0]
                    # get first channel number with correct reservationID and start test there
                    for channel in channels_blocked.keys():
                        if channels_blocked[channel]["reservationID"] == activeRequest["request"]["parameters"]["cycling"]["reservation_number"] and channels_blocked[channel]["requestID"] == "":
                            channels_blocked[channel]["requestID"] = activeRequest["uuid"]
                            channels_blocked[channel]["protocol"] = activeRequest["request"]["parameters"]["cycling"]["cycling_protocol"]
                            channels_blocked[channel]["numbCycles"] = activeRequest["request"]["parameters"]["cycling"]["number_cycles"]
                            ret = requests.get("http://{}:{}/arbin/capacity_cycling".format(arbin_config["arbinserver"], arbin_config["portserver"]), params={"data": json.dumps(activeRequest),"channel": channel }) 
                            print(ret.json())
                            if ret.json()== True :
                                now = datetime.now()
                                current_time = now.strftime("%Y-%m-%d %H:%M:%S")
                                channels_blocked[channel]["startDate"] = current_time
                                data_export_time = now + timedelta(days=arbin_config["data_export_delay_days"], hours=arbin_config["data_export_delay_hours"], minutes=arbin_config["data_export_delay_min"])
                                end_time = data_export_time.strftime("%Y-%m-%d %H:%M:%S")
                                channels_blocked[channel]["endDate"] = end_time
                                logger.info("Request "+ str(activeRequest["uuid"])+" startet successfully")
                                change_status(requestID=activeRequest["uuid"], new_status="reserved")
                                del jobqueue[0]
                                break
                            
                            else:
                                raise Exception("Bad")   
                except:
                    change_status(requestID=activeRequest["uuid"], new_status="pending")
                    channels_blocked[channel]["startDate"] = ""
                    channels_blocked[channel]["endDate"] = ""
                    channels_blocked[channel]["requestID"] = ""
                    channels_blocked[channel]["protocol"] = ""
                    channels_blocked[channel]["numbCycles"] = ""
                    logger.error("Request: "+ str(activeRequest["uuid"])+ " something went wrong when try to start job on the channel " + str(channel) + " \n Status is now pending again, reservation is still on channel")
    status = 0


@app.get(appservername + "/run_method_dummy")
def run_method_dummy(list_keys: list, list_values: list, channel:str):
    activeRequest = {k: v for k, v in zip(list_keys, list_values)}
    # strip the metadata from the request
    reqMethod = activeRequest["request"]["methods"][0]
    reqParameters = activeRequest["request"]["parameters"]["cycling"]
    reqID = activeRequest['uuid']
    reqtenantID = activeRequest["request"]['tenant_uuid']
    reservationID = reqParameters['reservationID']

    now = datetime.now()
    current_time = now.strftime("%Y-%m-%d %H:%M:%S")
    logger.info("Starting method " + str(reqMethod))
    logger.info(f"Job with ID {reqID} is progress now on following channel {channel} and removed from the jobqueue.")

    activeRequest.update({'data': {'Capacity': [4.1,4.1,4.0,3.9,3.9,3.89]}})
    current_time = now.strftime("%Y-%m-%d %H:%M:%S")
    activeRequest['status'][0] = [current_time, 'finished']

    finishedRequest ={
    "data" : activeRequest['data'],

    "quantity": str(activeRequest['request']['quantity']),

    "method": [reqMethod],

    "parameters": reqParameters,

    "tenant_uuid": reqtenantID,

    "request_uuid": reqID
    }

    # post the result
    authorization_header= authentication_Header_finales()
    postedResult = requests.post(
        "http://{}:{}/results/".format(arbin_config["finales"],arbin_config["portfinales"]),
        json=finishedRequest,
        params={},
        headers= authorization_header,
    )
    logger.info(f"Job with ID {reqID} is in progress on following channel {channel} and posted back on Finales with code {postedResult}.")

@app.get(appservername + "/capacity_cycling")
def capacity_cycling(data , channel):
    global status
    status = 1
    activeRequest = json.loads(data)
    reqMethod = activeRequest["request"]["methods"][0]
    reqParameters = activeRequest["request"]["parameters"]["cycling"]
    reqID = activeRequest['uuid']
    reqtenantID = activeRequest["request"]['tenant_uuid']
    reservationID = reqParameters['reservation_number']
    logger.info("Starting method " + str(reqMethod) + ' on Channel '+ str(channel))
    try:

        batteryobjectname = str(reqID)+'_Channel-'+str(channel)+'_'+str(uuid4())
        arbin.create_Batteryobject(batteryobjectname = batteryobjectname,
                                mass= 0,
                                Imax = reqParameters["I_max"],
                                Vmax = reqParameters["cycling_V_max"]*1.1,
                                Vmin = -0.3,
                                NCapacity = reqParameters["capacity"]*1.2,
                                NIR = 0)
        logger.info("Batteryobject created")
        arbin.initaliseSchedule(batteryobjectname = batteryobjectname +'.to', defaultSteptime=10) # default steptime equals 6,3h, so 6h rest wont cause errors
        logger.info("Schedule created")
        arbin.bigmapstandard(formchargecurrent=reqParameters["c_rate_charge_formation"] * reqParameters["capacity"],
                            formchargeVolt=reqParameters["V_max"],
                            formdccurrent=-(reqParameters["c_rate_discharge_formation"] * reqParameters["capacity"]),
                            formdcVolt=reqParameters["V_min"],
                            numberForm = reqParameters["repetions_formation_cycle"],
                            cyclechargecurrent=reqParameters["c_rate_charge"] * reqParameters["capacity"],
                            cyclechargeVolt=reqParameters["cycling_V_max"],
                            CVchargecuttoff=reqParameters["CV_I_cutoff"],
                            cycledccurrent=-(reqParameters["c_rate_discharge"] * reqParameters["capacity"]),
                            cycledcVolt=reqParameters["cycling_V_min"],
                            numbercycles=reqParameters["number_cycles"])
        logger.info("Protocol created")
        logger.info('Creating Schedulefile for channel '+ str(channel))
        arbin.createSchedulefile(batteryobjectname = batteryobjectname)
        arbin.refreshMonitorAndControlWindow()
        arbin.initaliseBatch()
        arbin.addNewScheduleToChannel(CH_Nr = int(channel), schedulename = batteryobjectname)
        #remove schedule form channel 25 for next 
        # remove old test from datawatcher
        logger.info('Starting Channel '+ str(channel) + ' ...')
        arbin.startNewChannel(CH_Nr = int(channel), reqID=reqID)       
        logger.info(f"Job with ID {reqID} is in progress now on following channels {channel} and removed from the jobqueue.")
        return True
    except Exception :
        logger.error(str(traceback.print_exc()))
        change_status(requestID=activeRequest["uuid"], new_status="pending")
        channels_blocked[channel]["startDate"] = ""
        channels_blocked[channel]["endDate"] = ""
        channels_blocked[channel]["requestID"] = ""
        channels_blocked[channel]["protocol"] = ""
        channels_blocked[channel]["numbCycles"] = ""
        logger.error("Request: "+ str(activeRequest["uuid"])+ " something went wrong when try to start job on the channel " + str(channel) + " \n Status is now pending again, reservation is still on channel")
        return False
    


@app.on_event("startup")
@repeat_every(seconds=50)
def check_end_time():
    global arbin
    global daq_number
    global jobqueue
    global channels_blocked
    global channels_available
    global TTL
    global quantities
    global status
    logger.info("Check end time")
    if status == 1:
        pass
    else:
        status=1
        for channel in channels_blocked:
            now = datetime.now()
            current_time = now.strftime("%Y-%m-%d %H:%M:%S CET")
            if channels_blocked[channel]["endDate"] <= current_time and channels_blocked[channel]["endDate"]!="":
                try:
                    arbin.exportData(CH_Nr=int(channel), reqID=channels_blocked[channel]["requestID"])
                    os.chdir(arbin_config["pathToCSV"])
                    origtemppath = os.getcwd()
                    content = list(os.listdir())
                    reqident = channels_blocked[channel]["requestID"]
                    for folder in content:
                        if reqident in folder:
                            os.chdir(folder)
                            source_folder = os.getcwd()
                    os.chdir(origtemppath)
                    # Define the destination folder on the mapped network drive
                    destination_folder = folder  # Change 'Z' to your desired drive letter

                    # Map the network drive using the net use command
                    net_use_command = f'net use {arbin_config["network_drive_path_40Cycles"]} {arbin_config["password"]} /user:{arbin_config["username"]} /persistent:no'
                    subprocess.run(net_use_command, shell=True)

                    try:
                        # Copy the folder to the mapped network drive
                        shutil.copytree(source_folder, str(arbin_config["network_drive_path_40Cycles"]+"\\"+destination_folder))

                        # Print a success message
                        print(f'Folder "{source_folder}" copied to "{arbin_config["network_drive_path_40Cycles"]}" successfully.')
                    except Exception as e:
                        print(f'An error occurred: {str(e)}')
                    finally:
                        # Unmap the network drive when done (optional)
                        unmap_command = f'net use {arbin_config["network_drive_path_40Cycles"]} /delete'
                        subprocess.run(unmap_command, shell=True)
                    logger.info("Data of channel "+str(channel)+ " exportet and copied to network drive in 40Cycles folder")
                    pathtofile = str(arbin_config["network_drive_path_40Cycles"]+"\\"+destination_folder)
                    now = datetime.now()
                    current_time = now.strftime("%Y-%m-%d %H:%M:%S")
                    data_end_time = now + timedelta(days=arbin_config["data_end_delay_days"], hours=arbin_config["data_end_delay_hours"], minutes=arbin_config["data_end_delay_min"])
                    end_time = data_end_time.strftime("%Y-%m-%d %H:%M:%S")
                    channels_blocked[str(channel)]["finaleExport"] = end_time   # set aprox Endtime of the test for export
                    channels_blocked[str(channel)]["endDate"] = ""
                    requests.get("http://{}:{}/arbin_analysis/EOLAnalysis".format(arbin_config["arbinanalysis"], arbin_config["portanalysis"]), params={"filepath": pathtofile})
                except:
                    logger.info("Data of channel "+str(channel)+ " exportet but trigger analysis failed")
                status=0
            elif channels_blocked[channel]["finaleExport"] <= current_time and channels_blocked[channel]["finaleExport"]!="":
                try: 
                    arbin.exportData(CH_Nr=int(channel), reqID=channels_blocked[channel]["requestID"], overwrite=True, exporttime=20)
                    os.chdir(arbin_config["pathToCSV"])
                    origtemppath = os.getcwd()
                    content = list(os.listdir())
                    reqident = channels_blocked[channel]["requestID"]
                    for folder in content:
                        if reqident in folder:
                            os.chdir(folder)
                            source_folder = os.getcwd()
                    os.chdir(origtemppath)
                    # Define the destination folder on the mapped network drive
                    destination_folder = folder  # Change 'Z' to your desired drive letter

                    # Map the network drive using the net use command
                    net_use_command = f'net use {arbin_config["network_drive_path_final"]} {arbin_config["password"]} /user:{arbin_config["username"]} /persistent:no'
                    subprocess.run(net_use_command, shell=True)

                    try:
                        # Copy the folder to the mapped network drive
                        shutil.copytree(source_folder, str(arbin_config["network_drive_path_final"]+"\\"+destination_folder))

                        # Print a success message
                        print(f'Folder "{source_folder}" copied to "{arbin_config["network_drive_path_final"]}" successfully.')
                    except Exception as e:
                        print(f'An error occurred: {str(e)}')
                    finally:
                        # Unmap the network drive when done (optional)
                        unmap_command = f'net use {arbin_config["network_drive_path_final"]} /delete'
                        subprocess.run(unmap_command, shell=True)
                    logger.info("Data of finished channel "+str(channel)+ " exportet and copied to network drive")
                    channels_blocked[channel]["startDate"] = ""
                    channels_blocked[channel]["endDate"] = ""
                    channels_blocked[channel]["finaleExport"] = ""
                    channels_blocked[channel]["requestID"] = ""
                    channels_blocked[channel]["protocol"] = ""
                    channels_blocked[channel]["numbCycles"] = ""
                    channels_blocked[channel]["reservationID"] = ""
                    logger.info("Channel "+str(channel)+" is now available again")
                except:
                    logger.info("Final export of channel "+str(channel)+ " failed")
                status=0
            else:
                continue
        status=0

@app.on_event("startup")
@repeat_every(seconds=10)
def check_channel_finished():
    ## still to implement : start with the checking function if channels are done
    ## if done send post result quest
    #function to see if channel/ channels are finished
    global arbin
    global daq_number
    global jobqueue
    global channels_blocked
    global channels_available
    global TTL
    global quantities
    global status
    if status == 1:
        print("asdasd")
        pass
    else:
        status = 1
        try:
            path = os.getcwd()
            os.chdir(arbin.pathdaqlog)
            foldercontent = os.listdir()
            foldercontent.sort(key=natural_keys)
            for i in range(len(foldercontent)-1, -1, -1):    # reversed looping over content for lates log file
                if re.search('DaqInfoLog' +'.+',foldercontent[i]) != None: 
                    name_logfile = foldercontent[i]
                    break
            logger.info('Checking '+ str(name_logfile)+ ' for stauts of channels ...')
            with open(name_logfile, 'r')as log:
                lines = log.readlines()
            log.close()
            os.chdir(path)
            # checking last 20 lines for news
            if len(lines) < 4:
                lines_max = len(lines)
                stop = -1
            else:
                lines_max = 4
                stop = len(lines)-lines_max-1
            daqloginfo = []
            for i in range(len(lines)-1,stop,-2): 
                daqinfos = lines[i].split(" ")
                daqnumber_file = int(daqinfos[2].split("]")[0])
                daqloginfo.append(daqinfos)
            #print(daqloginfo)
            # check for finished, stop, Unsafe and logg it in the good logger
            for i in range(len(daqloginfo)):
                if daqloginfo[i][3] == "Start/resume":
                    pass
                    """arbin.refreshMonitorAndControlWindow()
                    time.sleep(3)
                    channel_resumed = daqloginfo[i][4:-1]
                    logger.info('Started/Resumed '+ str(channel_resumed[0].split(':')[0])+ ' ' +str(channel_resumed[1:]))"""
                elif daqloginfo[i][3] == "Stop":
                    pass
                    """arbin.refreshMonitorAndControlWindow()
                    time.sleep(3)
                    channels_stopped = daqloginfo[i][5:]
                    del channels_stopped[-1]
                    logger.info('Stopped channels '+ str(channels_stopped)+ ' at '+ str(daqloginfo[i][0].split('[')[1])+' '+str(daqloginfo[i][1].split(',')[0]))"""
                elif daqloginfo[i][3]=='Channel':  # when Channel is unsafe it startes with channel
                    arbin.refreshMonitorAndControlWindow()
                    time.sleep(3)
                    channel_unsafe = int(daqloginfo[i][4])
                    parameter_unsafe = daqloginfo[i][7]
                    message_unsafe = daqloginfo[i][8][:-1]
                    if channels_blocked[str(channel_unsafe)]['TTL'] <= 0:
                        arbin.stopChannel(channel_unsafe)
                        logger.error("No TTL left for channel: " + str(channel_unsafe) + "\n Stoped test")
                        channels_blocked[str(channel_unsafe)]['endDate'] = ""
                        channels_blocked[str(channel_unsafe)]['finaleExport'] = ""
                    else:
                        try:
                            arbin.stopChannel(channel_unsafe)
                            arbin.resume_channel(channel_unsafe)
                            logger.info("Channel "+str(channel_unsafe) + " resumed")
                            remaining_TTL = channels_blocked[str(channel_unsafe)]['TTL']-1
                            channels_blocked[str(channel_unsafe)]['TTL'] = remaining_TTL
                            channels_blocked[str(channel_unsafe)]['Problems'][str(daqloginfo[i][0].split('[')[1])+' '+str(daqloginfo[i][1].split(',')[0])] = str('Channel '+ str(channel_unsafe) +' '+ parameter_unsafe + ' ' + message_unsafe)
                            logger.info("Resuming channel" + str(channel_unsafe) )
                        except:
                            logger.error("Failed to resume channel " + str(channel_unsafe) )
                        # restart channel
                """elif daqloginfo[i][3]=='Channels':
                    channel_finished = daqloginfo[3:]
                    del channel_finished[-1]"""
            else:
                logger.info("No new errors on channels")
        except:
            logger.error("Failed to restart test")
        daq_number = int(lines[-1].split(" ")[2].split("]")[0])
        status= 0

   
@app.get(appservername + "/get_free_channels")
def get_free_channels():
    return channels_available


@app.get(appservername + "/check_on")
def check_on():
    logger.info('Server is on')
    return "200"

@app.get(appservername + "/checkChannelfinished")
async def checkChannelfinished():
    ret = arbin.checkChannelfinished()
    retc = return_class(parameters=None, data=ret)
    return retc

@app.get("/arbin/checkbusy")
def recievefeedback(message:bool, CH_Nr:int):
    '''
        Function for the robot to trigger message if busy.

        Passed Parameters
        ------------------
        message(bool): Robot checks if busy true or false.
        CH_Nr(int): Channelnumber he is busy at the moment.
        ------------------

        Returns
        ------------------
        ------------------
        '''
    print("Busy "+str(message) + "  Channel" +str(CH_Nr))

@app.get("/arbin/savemetaData")
def savemetaData():
    arbin.savemetaData()
    retc = return_class(parameters=None, data=None)
    return retc

##################################################################### Sysbatch functions
@app.get(appservername + "/get_ArbinSysbatch")
def get_ArbinSysbatch():
    ret = arbin.get_ArbinSysbatch()
    retc = return_class(parameters = None, data = {'data': ret})
    return retc

@app.get(appservername + "/get_batchdetails")
def get_batchdetails():
        batch_list = arbin.get_ArbinSysbatch()
        channeldetails = []
        tempdetails = []
        for i in range(len(batch_list)):
            if "Batch_Test" in batch_list[i]:
                channelnumb = batch_list[i].split('Batch_Test')[1]
                channelnumb = int(channelnumb[:-1])+1 # deleting the outer bracket and increment 
                schedulename = batch_list[i+5].split('=')[1]
                tempdetails.append(channelnumb)
                tempdetails.append(schedulename)
                channeldetails.append(tempdetails)
                tempdetails=[]
        return channeldetails

##################################################################### Batteryobject functions
@app.get(appservername + "/create_Batteryobject")
def create_Batteryobject(batteryobjectname:str,mass:float,Imax:float,Vmax:float,Vmin:float,NCapacity:int,NIR:int):
    arbin.create_Batteryobject(batteryobjectname,mass,Imax,Vmax,Vmin,NCapacity,NIR)
    retc = return_class(parameters={'batteryobjectname':batteryobjectname, 'mass':mass, 'maxstrom':Imax, 'maxvoltage':Vmax, 'minvoltage':Vmin,'nominalcapaity':NCapacity, 'nominalresistance':NIR}, data=None)
    return retc

@app.get(appservername + "/load_Batteryobject")
def load_Batteryobject(batteryobjectname):
    content = arbin.load_Batteryobject(batteryobjectname)
    retc = return_class(parameters ={'batteryobjectname':batteryobjectname}, data={'data':content})
    return retc

@app.get(appservername + "/list_Batteryobject")
def list_Batteryobject():
    content = arbin.list_Batteryobject()
    retc = return_class(parameters = None, data={'data':content})
    return retc

@app.get(appservername + "/saveBatteryobjectData")
def saveBatteryobjectData():
    arbin.saveBatteryobjectData()
    retc = return_class(parameters=None, data=None)
    return retc


@app.get(appservername + "/initaliseSchedule")
def initaliseSchedule(Batteryobjectname:str,defaultSteptime:int):
    arbin.initaliseSchedule(Batteryobjectname, defaultSteptime)
    retc = return_class(parameters={'batteryobjectname':Batteryobjectname, 'defaultsteptime':defaultSteptime}, data=None)
    return retc

@app.get(appservername + "/getpossibleBatteryobjects")
def getpossibleBatteryobjects():
    arbin.getpossibleBatteryobjects()
    retc = return_class(parameters=None, data=None)
    return retc

@app.get(appservername + "/addChargeDischargeCrateloop")
def chargedischargeCrateloop(crate:float,endVoltagecharge:float, endVoltagedischarge:float, steptimelimit:int,lograte:int,numberofloops:int):
    arbin.chargedischargeCrateloop(crate,endVoltagecharge,endVoltagedischarge,steptimelimit,lograte,numberofloops)
    retc = return_class(parameters={'crate':crate, 'endvoltagecharge':endVoltagecharge, 'endvoltagedischarge':endVoltagedischarge,'steptimelimit':steptimelimit, 'lograte':lograte,'numberofloops':numberofloops}, data=None)
    return retc

@app.get(appservername + "/addCyclingCR2032Coincells")
def addCyclingCR2032Coincell():
    arbin.addCyclingCR2032Coincell()
    retc = return_class(parameters=None, data=None)
    return retc

@app.get(appservername + "/addGITT")
def addGITT(discurrent:float, minvoltage:float, endvoltage:float,cutoffcurrent:float,gittcurrent:float):
    arbin.addGITT(discurrent,minvoltage,endvoltage,cutoffcurrent,gittcurrent)
    retc = return_class(parameters={'dischargecurrent':discurrent, 'Minvoltage':minvoltage, 'endvoltage':endvoltage, 'cutoffcurrent':cutoffcurrent, 'gittcurrent': gittcurrent}, data=None)
    return retc

# basiclly savemetaDataAsJson function from above
@app.get(appservername + "/saveScheduledataAsJson")
def saveScheduleData(batteryobjectname:str):
    arbin.saveScheduleData(batteryobjectname)
    retc = return_class(parameters={'batteryobjectname':batteryobjectname}, data=None)
    return retc

@app.get(appservername + "/createSchedulefile")
def createSchedulefile(batteryobjectname:str):
    arbin.createSchedulefile(batteryobjectname)
    retc = return_class(parameters=None, data=None)
    return retc

@app.get(appservername + "/initaliseBatch")
async def initaliseBatch():
    arbin.initaliseBatch()
    retc = return_class(parameters=None, data=None)
    return retc

@app.get(appservername + "/saveBatchdict")
def saveBatchdict():
    arbin.saveBatchdict()  
    retc = return_class(parameters=None, data=None)
    return retc  

@app.get(appservername + "/get_schedules")
def get_schedules():
    ret = arbin.get_schedules()
    retc = return_class(parameters=None, data={'data': ret})
    return retc

@app.get(appservername + "/load_schedule")
def load_schedule(schedulename):
    ret = arbin.load_schedule(schedulename)
    retc = return_class(parameters=None, data={'data': ret})
    return retc

@app.get(appservername + "/addScheduletoChannel")
def addScheudletoChannel(CH_Nr:int,schedulename:str):
    arbin.addNewScheduleToChannel(CH_Nr,schedulename)
    retc = return_class(parameters={'channelnumber': CH_Nr, 'schedulename':schedulename}, data=None)
    return retc

@app.get(appservername + "/removeSchedulefromBatch")
def removeSchedulefromBatch(CH_Nr:int):
    arbin.removeSchedule(CH_Nr)
    retc = return_class(parameters={'channelnumber': CH_Nr}, data=None)
    return retc

@app.get(appservername+"/sacrificalChannel")
def sacrificalChannel():
    arbin.sacrificalChannel()
    retc = return_class(parameters=None, data=None)
    return retc


@app.get(appservername + "/startnewChannel")
def startnewChannel(CH_Nr:int, reqID:str):
    arbin.startNewChannel(CH_Nr, reqID)
    retc = return_class(parameters={'channelnumber': CH_Nr, "reqID": reqID}, data=None)
    return retc

@app.get(appservername + "/stopChannel")
def stopChannel(CH_Nr:int):
    arbin.stopChannel(CH_Nr)
    retc = return_class(parameters={'channelnumber': CH_Nr}, data=None)
    return retc

#check positons of buttons
@app.get(appservername + "/saveData")
def getData(CH_Nr:int):
    arbin.exportData(CH_Nr)
    retc = return_class(parameters={'channelnumber': CH_Nr}, data=None)
    return retc

@app.get(appservername + "/exportData")
def exportData(CH_Nr:int):
    arbin.exportData(CH_Nr)
    retc = return_class(parameters={'channelnumber': CH_Nr}, data=None)
    return retc

@app.get(appservername + "/exportallData")
def getDataallChannels():
    arbin.exportAllData()

# need to check return class
@app.get(appservername + "/getpossibletestnamesChannel")
def getpossibletestnamesChannel(CH_Nr:int):
    ret = arbin.getpossibletestnamesChannel(CH_Nr)
    #retc = return_class(parameters={'channelnumber': CH_Nr}, data=ret)
    return ret

@app.get(appservername + "/getpossibletestnames")
def getpossibletestnames():
    ret = arbin.getpossibletestnames()
    #retc = return_class(parameters={'channelnumber': CH_Nr}, data=ret)
    return ret

@app.get(appservername + "/getChannelData")
def getDataChannel(datapath:str):
    ret =arbin.getChannelData(datapath)
    #retc = return_class(parameters={'datapath': datapath}, data=ret)
    return ret

@app.get(appservername + "/loadHDF5")
def loadHDF5(hdf5name:str): 
    ret = arbin.loadHDF5(hdf5name)
    retc = return_class(parameters={'hdf5name': hdf5name}, data=ret)
    return retc
    

@app.get(appservername + "/getMetaDataDict")
def getMetaDataDict():
    '''
        Returs the global metaDataDict of the driver.

        Passed Parameters
        ------------------
        ------------------

        Returns
        ------------------
        ------------------
        '''
    retc = return_class(parameters=None, data=arbin.metaDataDict)
    return retc

@app.get(appservername + "/message")
def message(text:str):
    print(text)

@app.on_event("shutdown")
def cleargloballist():
    arbin.cleargloballist()    # clears the list with finished channels, so when started again it won't exchange last finshed channel again
    print("Shutting down")
    retc = return_class(parameters=None, data=None)
    return retc

if __name__ == "__main__":
    dictConfig(LogConfig().dict())
    logger = logging.getLogger("arbinlogger")
    #logger.info("Dummy Info")
    #logger.error("Dummy Error")
    #logger.debug("Dummy Debug")
    #logger.warning("Dummy Warning")

    logFileFormatter = logging.Formatter(
        fmt=f"%(levelname)s %(asctime)s (%(relativeCreated)d) \t %(pathname)s request: %(funcName)s - Info: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    fileHandler = logging.FileHandler(filename='arbinserver.log')
    fileHandler.setFormatter(logFileFormatter)
    fileHandler.setLevel(level=logging.INFO)

    logger.addHandler(fileHandler)


    dictConfig(LogConfigRes().dict())
    loggerreservation = logging.getLogger("loggerreservation")

    logFileFormatter2 = logging.Formatter(
        fmt=f"%(levelname)s %(asctime)s (%(relativeCreated)d) \t %(pathname)s request: %(funcName)s - Info: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    fileHandler2 = logging.FileHandler(filename='reservation.log')
    fileHandler2.setFormatter(logFileFormatter2)
    fileHandler2.setLevel(level=logging.INFO)

    loggerreservation.addHandler(fileHandler2)

    uvicorn.run(app, host=arbin_config["arbinserver"], port=arbin_config["portserver"])
