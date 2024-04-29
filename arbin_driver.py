
from config.arbin_config import arbin_config
import os
import json
import sys
import datetime
import re
from ahk import AHK
import pandas as pd
import numpy as np
import time
import hdfdict
import h5py
from scipy.optimize import curve_fit
from scipy import stats
import matplotlib.pyplot as plt


class arbin_driver:
    def __init__(self, arbin_config):
        self.newTests =[]
        self.newTestsnames =[]
        self.pathToBatteryobjectFiles = arbin_config['pathToBatteryobjectFiles']
        self.pathToEmptyScheduleFile = arbin_config['pathToEmptyScheduleFile']
        self.emptyScheduleFileName = arbin_config['emptyScheduleFileName']
        self.pathToScheduleFiles = arbin_config['pathToScheduleFiles'] 
        self.nameofSchedulefolder = arbin_config['nameofSchedulefolder']
        self.pathToArbinSysbatchfile = arbin_config['pathToArbinSysbatchfile']
        self.batchName = arbin_config['batchName']
        self.pathOfJsonfile = arbin_config['pathOfJsonfile']
        self.pathToCSV = arbin_config['pathToCSV']
        self.pathdaqlog = arbin_config['pathdaqlog']
        self.logfinishedChannel = [0]
        #create nested dictionary for the different blocks in schedule file
        self.fileDictionary = {
                            'versionSection' : {},
                            'signatureSection' : {},
                            'Schedule' : {},
                            'Schedule_Step0' : {},
                            'Schedule_Step0_Limit0' : {},
                            'Schedule_Step0_Limit1' : {},
                            'Schedule_Step1' : {},
                            'Schedule_Step1_Limit0' : {},
                            'Schedule_UserDefineSafety0' : {},
                            'Schedule_UserDefineSafety1' : {},
                            'Schedule_UserDefineSafety2' : {},
                            'Schedule_UserDefineSafety3' : {},
                            'Schedule_UserDefineSafety4' : {},
                            'Schedule_UserDefineSafety5' : {},
                            'Schedule_UserDefineSafety6' : {},
                            'Schedule_UserDefineSafety7' : {},
                            'Schedule_UserDefineSafety8' : {},
                            'Schedule_UserDefineSafety9' : {},
                            'Schedule_UserDefineSafety10' : {},
                            'Schedule_UserDefineSafety11' : {},
                            'Schedule_UserDefineSafety12' : {},
                            'Schedule_UserDefineSafety13' : {},
                            'Schedule_UserDefineSafety14' : {},
                            'Schedule_UserDefineSafety15' : {},
                            'SDU_DXDY_DVDT' : {},
                            'SDU_DXDY_DVDQ' : {},
                            'SDU_DXDY_DQDV' : {},
                            'Aux_Voltage' : {},
                            'Aux_Temperature' : {},
                            'Aux_Pressure' : {},
                            'Aux_pH' : {},
                            'Aux_FlowRate' : {},
                            'Aux_Concentration' : {},
                            'Aux_Digital_Input' : {},
                            'Aux_Digital_Output' : {},
                            'Aux_External_Charge ' : {},
                            'Aux_Safety' : {},
                            'Aux_Humidity' : {},
                            'Aux_AO' : {},
                            'CAN' : {},
                            'SMB' : {}  }
        #create dictionary for important data
        self.scheduledata ={}
        #create name list of the nested dictionaries
        self.dictionaryNameList = []
        for x in self.fileDictionary:
            self.dictionaryNameList.append(x)
        #get current(original) path to jump back to
        self.originalPath = os.getcwd()
        
        #create nested dictionary for the different blocks in schedule file
        self.batchDictionary = {
                    'versionSection' : {},
                    'signatureSection' : {},
                    'Batch' : {},
                    }
        
        self.metaDataDict = {
            'Schedule' : {}
        }
        self.metaDataDict['Schedule']['Channels'] = []

    def atof(self,text):
        try:
            retval = float(text)
        except ValueError:
            retval = text
        return retval
    
    def natural_keys(self,text):
        return [ self.atof(c) for c in re.split(r'[+-]?([0-9]+(?:[.][0-9]*)?|[.][0-9]+)', text) ]


    def create_Batteryobject(self,batteryobjectname:str,mass:float,Imax:float,Vmax:float,Vmin:float,NCapacity:int,NIR:int):
        '''
        Creates batteryobjectfile at specified path with input parameters as values.
        Vmax,Vmin,Imax and NCapacity must have values.

        Passed Parameters
        ------------------
        batteryobjectname(string): Complete name of the batteryobject(including .to)
        mass(float): Mass of battery in [g].
        Imax(float): Maximum current that should be applied to the battery in [A].
        Vmax(float): Maximum Voltage the battery should be at in loaded status.
        Vmin(float): Minimum Voltage the battery should be at in discharged status.
        NCapacity(int): Nominal Capacity of the battery in (Ah).
        NIR(int): Nominal internal resistance in (Ohm).
        ------------------

        Returns
        ------------------
        ------------------
        '''
        #initalise empty dic to fill with Battery properties and values
        Objekt= {}
        # current Path for jumping back later
        currentpath = os.getcwd()
        keys = ['m_bAutoCalcNCapacity','m_fMass','m_fMaxCurrentCharge','m_fMaxVoltageCharge','m_fMinVoltageCharge','m_fNorminalCapacitance','m_fNorminalCapacity','m_fNorminalIR','m_fNorminalVoltage','m_fSpecificCapacity']
        values = [False,mass,Imax,Vmax,Vmin,0,NCapacity,NIR,0,0]
        Objekt = dict(zip(keys,values))
        Objekt['SER'] = 1321994960
        Objekt['VER'] = 27265537
        # got to Path where Batterybjectfile should be created in
        os.chdir(arbin_config['pathToBatteryobjectFiles'])
        # create name of object as Object + Date + Time
        batteryobjectname = batteryobjectname 
        f = open(str(batteryobjectname)+'.to','x')
        f.write('[Content]' + '\n')                      # 1st line of template file 
        for x,y in Objekt.items():
            f.write(x + '=' + str(y) + '\n')
        f.close()
        #go back to old Path
        os.chdir(currentpath)
        Objekt['Name'] = batteryobjectname +'.to'
        self.metaDataDict['Batteryobject'] = Objekt
        units = ['bool','g','A','V','V','F','Ah','Ohm','V','Ah/g']
        objectunits = dict(zip(keys,units))
        self.metaDataDict['units'] = {}
        self.metaDataDict['units']['Batteryobject'] = objectunits
        return(Objekt)

    def saveBatteryobjectData(self):
        '''
        Saves Battery parameter from object file as json at specified folder.

        Passed Parameters
        ------------------
        ------------------

        Returns
        ------------------
        ------------------
        '''
        currentpath = os.getcwd()
        os.chdir(arbin_config['pathOfJsonfile'])
        batteryobjectname = self.metaDataDict['Batteryobject']['Name'][:3]
        with open(str(batteryobjectname)+'.json','x') as fp:
            json.dump(self.metaDataDict['Batteryobject'],fp,sort_keys=True)
            json.dump(self.metaDataDict['units']['Batteryobject'],fp,sort_keys=True)
        os.chdir(currentpath)

    def pathToFile(self,pathToFile:str):
        '''
        Checks if path exists.

        Passed Parameters
        ------------------
        pathToFile(str): path to check.(Carefull for double /)
        ------------------

        Returns
        ------------------
        ------------------
        '''
        if pathToFile =='':
            return(self.originalPath)
        else:
            #try if the given Path to emptySchedule exists else give an error and quit Programm
            if os.path.exists(pathToFile) == True:
                return(pathToFile)
            else:
                print('Given Path is not a correct Path')

    def getEmptySchedule(self):
        '''
        Checks if empty schedule file is in current folder else goes to predefined and reads content in.

        Passed Parameters
        ------------------
        ------------------

        Returns
        ------------------
        ------------------
        '''
        #look for the empty schedule named emptySchedule file in current folder
        try:
            f = open(self.emptyScheduleFileName,'r')
        except:
        #try if the given Path to emptySchedule exists else give an error and quit Programm
            os.chdir(self.pathToEmptyScheduleFile)    #since Path to emptyScheduleFile exists we change to this Path/folder
            try:
                os.path.isfile(self.emptyScheduleFileName)
            except:
                print('File emptySchedule.sdx is neither in the folder of this script ,')
                print('nor in the Path written in this Script(See variable pathToEmptyScheduleFile in config)')
                sys.exit()    # exit script
        # read in every line of the emptySchedule File
        contentemptySchedule =[]
        with open(self.emptyScheduleFileName,'r') as f:
            for line in f:
                line = line.strip()
                contentemptySchedule.append(line)
        f.close()
        return(contentemptySchedule)

    def seperateKeyValue(self,contentemptySchedule):     
        '''
        Splits strings based on equalsign into "keys and values" and save this list at the same position in the original list.

        Passed Parameters
        ------------------
        contentemptySchedule(list of str): List containing all strings from empty schedulefile.
        ------------------

        Returns
        ------------------
        ------------------
        '''
        for x in range(len(contentemptySchedule)):        # loop over all elements and sort them(new line elements, only string elements and string plus value elements) in dicts
            try:
                s = contentemptySchedule[x].split('=')       # check if we have string+value element and split them into a list and safe them again in the original list 
                contentemptySchedule[x] = s
            except:
              continue

    def safeToScheduleDictionary(self,contentemptySchedule):
        '''
        Adding content of empty schedule to scheduldictionary.

        Passed Parameters
        ------------------
        contentemptySchedule(list of str): List containing all content as str from the empty schedulefile.
        ------------------

        Returns
        ------------------
        ------------------
        '''
        counter = 0     # count variable that refers later to the name of te nested dictionary
        x = 0
        while x in range(len(contentemptySchedule)):
            try:     
                if contentemptySchedule[x] == contentemptySchedule[x+1]:
                    counter = counter +1     # if 2 blancs occur the next section(in form of nested dic) occurs
                    x = x + 2                # change number so next iteration starts with the next variable of the next section
                else:
                    l = contentemptySchedule[x]                # try to read in the list with string+varaible seperated before
                    try:
                        self.fileDictionary[self.dictionaryNameList[counter]][l[0]] = l[1]    # adding to nested dic the key and value from the list
                        x = x + 1
                    except:                    # occurs when only a string is safed in the list (e.g. 1 line [Version Section]
                        self.fileDictionary[self.dictionaryNameList[counter]][l[0]] = None   #safes string as a key with value None
                        x = x + 1
            except:
                x = x+1
                continue        # there is no x+1 value for the last x so we continue and break the while loop

    #adds one key-value pair to a nested dictionary in fileDictionary
    def addInputToFiledic(self,namedic:str, keyvariable:str, variablevalue:str):
        self.fileDictionary[namedic][keyvariable] = variablevalue

    def addglobalsafetys(self,defaultsteptime:int):
        '''
        Adding Safety paramters from golbal page to scheduldictionary.
        m_CRM_Deviation=1% is set in emptyschedule equal to Step Control Error Check in global page.

        Passed Parameters
        ------------------
        defaultSteptime(int): Maximum hours one step has time to finish.
        ------------------

        Returns
        ------------------
        ------------------
        '''
        names = ['','','','','']
        keynames = ['m_SDLMax','m_SDLMin','m_szItem','m_szSafetyHigh','m_szSafetyLow']                  # keynames
        values = [['20%','','DV_Current','105%','-105%'],['10%','','DV_Voltage','100%','100%'],     # values of different dictionaries
              ['','','Power','110%','-110%'],['','','Capacity','2','0'],
              ['360','1','StepTime',str(defaultsteptime),''] ]                                    # insert default steptime
        for i in range(5):
            names[i] = '[Schedule_CSchedule_IvSafetyAndSDL' + str(i) +']'                                    # create the different dicitonaries
            self.fileDictionary[names[i]] = {}
        for l in range(len(names)):
            for o in range(len(keynames)):
                self.addInputToFiledic(str(names[l]),str(names[l]),None)                                     # adds name of section to fileDic (later will be printed out)
                self.addInputToFiledic(str(names[l]),str(keynames[o]), values[l][o])                        # loop over dictionaries+keys+values
                self.addInputToFiledic('Schedule','m_nIvSafetyAndSDLNum','5')                                        # number of these safeties in schedule section

    def checkBatteryobjectname(self,batteryobjectName:str):
        '''
        Checks if given batteryobjectname exists in the folder where all objects are saved in.

        Passed Parameters
        ------------------
        batteryobjectname(string): Complete name of the batteryobject to add batteryspecific parameters(Vmax, Imax, ....)
        ------------------

        Returns
        ------------------
        ------------------
        '''
        path = self.pathToBatteryobjectFiles        # check if path to object is correct and return it 
        os.chdir(path)                        # go to path of scheudles
        check = os.path.isfile(batteryobjectName)              # check if file with input name is there
        if check ==True:
            os.chdir(self.originalPath)
            return(True)
        else:
            print('There is no Batterobject with this name in the given Path ')
            print('Please create an Batteryobject with this name or correct your input')
            print('Forgott to add .to ??')
        
    def assignBatteryobject(self,batteryobjectname:str):
        '''
        Adding Batteryobjectname to the scheduledictioanry.

        Passed Parameters
        ------------------
        batteryobjectname(string): Complete name of the batteryobject to add batteryspecific parameters(Vmax, Imax, ....)
        ------------------

        Returns
        ------------------
        ------------------
        '''
        checkfile = self.checkBatteryobjectname(batteryobjectname)
        if checkfile == False:
            print('Batteryobjectfile is not in this folder neither in the given one')
            print('Forgott to add .to ??')
        else:
            self.fileDictionary['Schedule']['m_TestObjName'] = batteryobjectname
            self.metaDataDict['Schedule']['Batteryobjectname'] = batteryobjectname

####################################################################################################################

    def createNewStep(self,numberofStep:int, numberOfLimits:int,controlvaraibleName:str,controlvalue:str, label:str,extCtrlValue1:float, extctrlValue2:float):
        '''
        Adds a single Step(no limits) to the scheduledictioanry.

        Passed Parameters
        ------------------
        numberofStep(int): Number of the step in the schedule.
        numberofLimits(int): Number limits the step will have(steplimits + loglimits).
        controlvariableName(str): Specific Names of Parameters(e.g. current, CCCV) you can control.
        controlvalue(int): Value of the before specified parameter.
        label(str): Label for step for later jumps.
        extCtrlValue1(float): 1st extra control Value.
        extCtrlValue2(float): 2nd extra control Value. 
        ------------------

        Returns
        ------------------
        ------------------
        '''
        maxcurrent = 0
        newName = 'Schedule_Step'+str(numberofStep)
        step = {
            '['+ newName +']': None,                         
        }
        if numberOfLimits == 0 and numberofStep == 0 :
            step = self.fileDictionary['Schedule_Step0'].copy()    # copy the template of the step (this always has to be there) Note: Name will just be overwritten if it is the first limit ot first step
        else: 
            template = self.fileDictionary['Schedule_Step0'].copy()
            for x,y in template.items():                               # copy all keys and values from template except for first name
                if x == '[Schedule_Step0]' :
                    continue
                else:
                    step[x] = y
        step['m_nMaxCurrent'] = maxcurrent
        step['m_szCtrlValue'] = controlvalue
        step['m_szLabel'] = label
        step['m_szStepCtrlType'] = controlvaraibleName
        step['m_uLimitNum'] = numberOfLimits
        if extCtrlValue1 == None:
            step['m_szExtCtrlValue1'] = ''                     # extra control values (if none need to set emty string else no = in output cause parameter for section)
        else:
            step['m_szExtCtrlValue1'] = extCtrlValue1  
        if extctrlValue2 == None:
            step['m_szExtCtrlValue2'] = ''  
        else:
            step['m_szExtCtrlValue2'] = extctrlValue2
        if controlvaraibleName != 'Rest':                             # only for Rest step it´s 1 (as far as I know)
            step['m_bAutoPidTips'] = '0'
        else:
            step['m_bAutoPidTips'] = '1'
        self.fileDictionary[newName] = step.copy()
        parameters = ['controlvaraibleName','controlvalue','maxcurrent', 'label','extCtrlValue1', 'extctrlValue2']
        values = [controlvaraibleName,controlvalue,maxcurrent, label,extCtrlValue1, extctrlValue2]
        stepdict = dict(zip(parameters,values))
        self.metaDataDict['Schedule'] ['Step_'+str(numberofStep)] = {}
        self.metaDataDict['Schedule']['Step_'+str(numberofStep)]['StepData'] = stepdict

    def createStepLimit(self,numberofStep:int,limitnumber:int,controlvaraibleName:str,compareSign:str,controlvalue:int,nameNextStep:str):
        '''
        Adds a single Steplimit with one condition to a Step.
        Condition: the fileDic has to have Schedule_Step0_Limit0 already.

        Passed Parameters
        ------------------
        numberofStep(int): Number of the step in the schedule.
        limitnumber(int): Number of this limit in the step.
        controlvariableName(str): Specific Names of Parameters(e.g. current, CCCV) you can control.
        compareSign(str): This is either >, >=, <,<= .
        controlvalue(int): Value of the before specified parameter.
        namenextstep(str): Name of the next step (normal "Next Step"). 
        ------------------

        Returns
        ------------------
        ------------------
        '''
        newName = 'Schedule_Step'+str(numberofStep)+'_Limit'+str(limitnumber)
        limit = {
            '['+ newName +']': None,                         
        }
        if limitnumber == 0 and numberofStep == 0 :
            limit = self.fileDictionary['Schedule_Step0_Limit0'].copy()    # copy the template of this limit(always has to be there) Note: Name will just be overwritten if it is the first limit ot first step
            self.fileDictionary.pop('Schedule_Step0_Limit0')                # removing already existing limits(there from the template)
            self.fileDictionary.pop('Schedule_Step0_Limit1')
            self.fileDictionary.pop('Schedule_Step1_Limit0')
            self.fileDictionary.pop('Schedule_Step1')               # removing already existing steps and limits(there from the template)
        else: 
            template = self.fileDictionary['Schedule_Step0_Limit0'].copy()
            for x,y in template.items():                               # copy all keys and values from template except for first name
                if x == '[Schedule_Step0_Limit0]' :
                    continue
                else:
                    limit[x] = y
        limit['Equation0_szCompareSign'] = compareSign                 # change all input you gave to this function
        limit['Equation0_szLeft'] = controlvaraibleName
        limit['Equation0_szRight'] = controlvalue
        limit['m_szGotoStep'] = nameNextStep
        limit['m_bStepLimit'] = 1                                       # defines it as a steplimit
        if controlvaraibleName == 'PV_CHAN_Cycle_Index':                  # for this name has to set to 0 (don´t know why)
            limit['m_bLogDataLimit'] = 0
        else:
            limit['m_bLogDataLimit'] = 1
        self.fileDictionary[newName] = limit.copy()
        parameters = ['IndexofSteplimit','NumberofLimits','ControlvaraibleName','CompareSign','Controlvalue','NameofNextStep']
        values = [numberofStep,limitnumber,controlvaraibleName,compareSign,controlvalue,nameNextStep]
        steplimitdict = dict(zip(parameters,values))
        self.metaDataDict['Schedule']['Step_'+str(numberofStep)]['Steplimit_'+str(limitnumber)] = steplimitdict
        #print(fileDictionary[newName])

    def createLogLimit(self,numberofStep:int,limitnumber:int,controlvaraibleName:str,compareSign:str,controlvalue:int,nameNextStep:str):
        '''
        Adds a single Loglimit with one condition to a Step.
        Condition: the fileDic has to have Schedule_Step0_Limit0 already.(Source: read in empty schedulefile)

        Passed Parameters
        ------------------
        numberofStep(int): Number of the step in the schedule.
        limitnumber(int): Number of this limit in the step.
        controlvariableName(str): Specific Names of Parameters(e.g. current, CCCV) you can control.
        compareSign(str): This is either >, >=, <,<= .
        controlvalue(int): Value of the before specified parameter.
        namenextstep(str): Name of the next step (normal "Next Step"). 
        ------------------

        Returns
        ------------------
        ------------------
        '''
        newName = 'Schedule_Step'+str(numberofStep)+'_Limit'+str(limitnumber)
        limit = {
            '['+ newName +']': None,                         
        }
        if limitnumber == 0 and numberofStep == 0 :
            limit = self.fileDictionary['Schedule_Step0_Limit0'].copy()    # copy the template of this limit(always has to be there) Note: Name will just be overwritten if it is the first limit ot first step
            self.fileDictionary.pop('Schedule_Step0_Limit0')                # removing already existing limits(there from the template)
            self.fileDictionary.pop('Schedule_Step0_Limit1')
            self.fileDictionary.pop('Schedule_Step1_Limit0')
        else: 
            template = self.fileDictionary['Schedule_Step0_Limit0'].copy()
            for x,y in template.items():                               # copy all keys and values from template except for first name
                if x == '[Schedule_Step0_Limit0]' :
                    continue
                else:
                    limit[x] = y
        limit['Equation0_szCompareSign'] = compareSign                 # change all input you gave to this function
        limit['Equation0_szLeft'] = controlvaraibleName
        limit['Equation0_szRight'] = controlvalue
        limit['m_szGotoStep'] = nameNextStep
        limit['m_bStepLimit'] = 0      
        limit['m_bLogDataLimit'] = 1                                    # defines it as a loglimit
        self.fileDictionary[newName] = limit.copy()
        parameters = ['IndexofLoglimit','NumberofLimits','ControlvaraibleName','CompareSign','Controlvalue','NameofNextStep']
        values = [numberofStep,limitnumber,controlvaraibleName,compareSign,controlvalue,nameNextStep]
        loglimitdict = dict(zip(parameters,values))
        self.metaDataDict['Schedule']['Step_'+str(numberofStep)]['Loglimit_'+str(limitnumber)] = loglimitdict
        #print(fileDictionary[newName])

    def chargeStep(self,numberofStep:int,current:float,endVoltagecharge:int,steptimeLimit:int,lograte:int,stepname ='charge'):
        '''
        Adds a step that discharge with a specified  current until a steptimeLimit or a specified voltage is reached.

        Passed Parameters
        ------------------
        numberofStep(int): Number of the step in the schedule.
        chargecurrent(float): Positiv current to charge a battery in [A].
        endVoltagecharge(float): Maximum voltage to charge[V].
        steptimeLimit(int): Time the step should take at maximum in [s].
        lograte(int): Periodic time when data should be collected from channel in [s].
        ------------------

        Returns
        ------------------
        ------------------
        '''
        self.createNewStep(numberofStep,2,'Current(A)',current,stepname,None,None)
        self.createStepLimit(numberofStep,0,'PV_CHAN_Voltage','>=',endVoltagecharge,'Next Step')
        self.createLogLimit(numberofStep,1,'DV_Time','>=',lograte,'Next Step')

    def dischargeStep(self,numberofStep:int, dischargecurrent:float,endVoltagedischarge:int,steptimeLimit:int,lograte:int,stepname = 'discharge'):
        '''
        Adds a step that discharge with a specified negativ current until a steptimeLimit or a specified voltage is reached.

        Passed Parameters
        ------------------
        numberofStep(int): Number of the step in the schedule.
        dischargecurrent(float): Negativ current to discharge a battery in [A].
        endVoltagedischarge(float): Minimum voltage to discharge[V].
        steptimeLimit(int): Time the step should take at maximum in [s].
        lograte(int): Periodic time when data should be collected from channel in [s].
        ------------------

        Returns
        ------------------
        ------------------
        '''
        self.createNewStep(numberofStep,2,'Current(A)',dischargecurrent,stepname,None,None)
        self.createStepLimit(numberofStep,0,'PV_CHAN_Voltage','<=',endVoltagedischarge,'Next Step')
        self.createLogLimit(numberofStep,1,'DV_Time','>=',lograte,'Next Step')

    def chargeStepCrate(self,numberofStep:int,Crate:float,steptimeLimit:int,endVoltagecharge:float,lograte:int):
        '''
        Adds a step that charge with a specified c-rate until a steptimeLimit or a specified voltage is reached.

        Passed Parameters
        ------------------
        numberofStep(int): Number of the step in the schedule. 
        Crate(float): Based on this C-rate system calculates dischargecurrent. [a.u]
        steptimeLimit(int): Time the step should take at maximum in [s].
        endVoltagecharge(float): Maxium voltage to charge[V].
        lograte(int): Periodic time when data should be collected from channel in [s].
        ------------------

        Returns
        ------------------
        ------------------
        '''
        self.createNewStep(numberofStep,3,'C-Rate',Crate,'charge',None,None)
        self.createStepLimit(numberofStep,0,'PV_CHAN_Voltage','>=',endVoltagecharge,'Next Step')
        self.createStepLimit(numberofStep,1,'PV_CHAN_Step_Time','>=',steptimeLimit,'Next Step')
        self.createLogLimit(numberofStep,2,'DV_Time','>=',lograte,'Next Step')

    def dischargeStepCrate(self,numberofStep:int,Crate:float,steptimeLimit:int,endVoltagedischarge:float,lograte:int):
        '''
        Adds a step that discharge with a specified c-rate until a steptimeLimit or a specified voltage is reached.

        Passed Parameters
        ------------------
        numberofStep(int): Number of the step in the schedule. 
        Crate(float): Based on this C-rate system calculates dischargecurrent. [a.u]
        steptimeLimit(int): Time the step should take at maximum in [s].
        endVoltagedischarge(float): Minimum voltage to discharge[V].
        lograte(int): Periodic time when data should be collected from channel in [s].
        ------------------

        Returns
        ------------------
        ------------------
        '''
        self.createNewStep(numberofStep,3,'C-Rate',Crate,'discharge',None,None)
        self.createStepLimit(numberofStep,0,'PV_CHAN_Voltage','<=',endVoltagedischarge,'Next Step')
        self.createStepLimit(numberofStep,1,'PV_CHAN_Step_Time','>=',steptimeLimit,'Next Step')
        self.createLogLimit(numberofStep,2,'DV_Time','>=',lograte,'Next Step')

    def CCCVStepCurrent(self,numberofStep:int,current:float, voltage:float, resistance:float,steptimeLimit:int,lograte:int):
        '''
        Adds a step that apply a constant voltage and current to charge until a steptimeLimit or a specified voltage is reached.

        Passed Parameters
        ------------------
        numberofStep(int): Number of the step in the schedule.
        current(float): Constant current value to charge in [A].
        voltage(float): Maximum voltage to charge[V].
        resistance(float): Resistance of the system (if not known just 0).
        steptimeLimit(int): Time the step should take at maximum in [s].
        lograte(int): Periodic time when data should be collected from channel in [s].
        ------------------

        Returns
        ------------------
        ------------------
        '''
        self.createNewStep(numberofStep,3,'CCCV',current,'charge',voltage,resistance)
        self.createStepLimit(numberofStep,0,'PV_CHAN_Voltage','>=',voltage,'Next Step')
        self.createStepLimit(numberofStep,1,'PV_CHAN_Step_Time','>=',steptimeLimit,'Next Step')
        self.createLogLimit(numberofStep,2,'DV_Time','>=',lograte,'Next Step')

    def CCCVStepDischargeCurrent(self,numberofStep:int,current:float, voltage:float, resistance:float,steptimeLimit:int,lograte:int):
        '''
        Adds a step that apply a constant voltage and current to discharge until a steptimeLimit or a specified voltage is reached.
        Passed Parameters
        ------------------
        numberofStep(int): Number of the step in the schedule.
        current(float): Constant current value to discharge in [A].
        voltage(float): Minimum voltage to discharge[V].
        resistance(float): Resistance of the system (if not known just 0).
        steptimeLimit(int): Time the step should take at maximum in [s].
        lograte(int): Periodic time when data should be collected from channel in [s].
        ------------------

        Returns
        ------------------
        ------------------
        '''
        self.createNewStep(numberofStep,3,'CCCV',current,'discharge',voltage,resistance)
        self.createStepLimit(numberofStep,0,'PV_CHAN_Voltage','<=',voltage,'Next Step')
        self.createStepLimit(numberofStep,1,'PV_CHAN_Step_Time','>=',steptimeLimit,'Next Step')
        self.createLogLimit(numberofStep,2,'DV_Time','>=',lograte,'Next Step')

    def ConstantVoltageCharge(self,numberofStep:int,voltage:float,resistance:float,mincurrent:float,steptimeLimit:int,lograte:int):
        '''
        Adds a step that apply a constant voltage after charge until a cutoff current or a steptimeLimit is reached.

        Passed Parameters
        ------------------
        numberofStep(int): Number of the step in the schedule. 
        voltage(float): Minimum voltage to discharge[V].
        resistance(float): Resistance of the system (if not known just 0).
        mincurrent(float): Cutoff current as conditon for CV part.
        steptimeLimit(int): Time the step should take at maximum in [s].
        lograte(int): Periodic time when data should be collected from channel in [s].
        ------------------

        Returns
        ------------------
        ------------------
        '''
        self.createNewStep(numberofStep,2,'Voltage(V)',voltage,'ConstantVoltageCharge',None,resistance)
        self.createStepLimit(numberofStep,0,'PV_CHAN_Current','<=',mincurrent,'Next Step')
        self.createLogLimit(numberofStep,1,'DV_Time','>=',lograte,'Next Step')

    def ConstantVoltageDischarge(self,numberofStep:int,voltage:float,resistance:float,mincurrent:float,steptimeLimit:int,lograte:int):
        '''
        Adds a step that apply a constant voltage after discharge until a cutoff current or a steptimeLimit is reached.

        Passed Parameters
        ------------------
        numberofstep(int): Number of the step in the schedule. 
        voltage(float): Minimum voltage to discharge[V].
        resistance(float): Resistance of the system (if not known just 0).
        mincurrent(float): Cutoff current as conditon for CV part.
        steptimeLimit(int): Time the step should take at maximum in [s].
        lograte(int): Periodic time when data should be collected from channel in [s].
        ------------------

        Returns
        ------------------
        ------------------
        '''
        self.createNewStep(numberofStep,2,'Voltage(V)',voltage,'ConstantVoltageDischarge',None,resistance)
        self.createStepLimit(numberofStep,0,'PV_CHAN_Current','>=',mincurrent,'Next Step')
        self.createLogLimit(numberofStep,1,'DV_Time','>=',lograte,'Next Step')

    def rest(self,numberofStep:int,time:int, namenextstep:str):
        '''

        Passed Parameters
        ------------------
        numberofstep(int): Number of the step in the schedule. 
        time(int): Time the system should rest in [s].
        namenextstep(str): Name of the next step (normal "Next Step").
        ------------------

        Returns
        ------------------
        ------------------
        '''
        self.createNewStep(numberofStep,2,'Rest',None,'rest',None,None)
        self.createStepLimit(numberofStep,0,'PV_CHAN_Step_Time','>=',time,namenextstep)
        self.createLogLimit(numberofStep,1,'DV_Time','>=',1,'Next Step')

    def loop(self,numberofStep:int,numberIterations:int,gobackToStep:str):
        '''
        Adds a step that creates a loop.

        Passed Parameters
        ------------------
        numberofstep(int): Number of the step in the schedule.
        numberInterations(int): Number of loops.
        gobackToStep(str): Label of the step you jump back to for the loop.
        ------------------

        Returns
        ------------------
        ------------------
        '''
        self.createNewStep(numberofStep, 2,'Set Variable(s)','0','loop','1','0')         # last 2 parameters are for increment first variable in list and decrement first variable in list with 0
        self.createStepLimit(numberofStep,0,'PV_CHAN_Cycle_Index','<=',numberIterations,gobackToStep)
        self.createStepLimit(numberofStep,1,'PV_CHAN_Cycle_Index','>',numberIterations,"Next Step")

    def incCycleindex(self, numberofStep:int, label:str):
        '''
        Adds a step that increments the cycleindex.

        Passed Parameters
        ------------------
        numberofStep(int): Number of the step in the schedule. 
        label(str): Label name the step should have.
        ------------------

        Returns
        ------------------
        ------------------
        '''
        self.createNewStep(numberofStep, 1,'Set Variable(s)','0','0',label,'1','0')         # last 2 parameters are for increment first variable in list and decrement first variable in list with 0
        self.createStepLimit(numberofStep,0,'PV_CHAN_Step_Time','>=',0,"Next Step")
    
    def GITTcharge(self, numberofStep:int,gittcurrent:float, endVoltagecharge:float, chargetime:int,resttime:int, lograte:float):
        '''
        Creates a GITT measurement part in the scheudledict.

        Passed Parameters
        ------------------
        numberofStep(int): Number of the step in the schedule. This adds 2 steps.
        gittcurrent(float): Current value for the chargepuls in [A].
        endVoltagecharge(float): Maxium voltage to charge[V].
        chargetime(int): Duration of the chargepuls in [s].
        resttime(int): Duration of the restpuls in [s].
        lograte(int): Periodic time when data should be collected from channel in [s].
        ------------------

        Returns
        ------------------
        ------------------
        '''
        self.createNewStep(numberofStep,3,'Current(A)',gittcurrent,'charge',None,None)
        self.createStepLimit(numberofStep,0,'PV_CHAN_Step_Time','>=',chargetime,'Next Step')
        self.createStepLimit(numberofStep,1,'PV_CHAN_Voltage','>=',endVoltagecharge,'incaftercharge')
        self.createLogLimit(numberofStep,2,'DV_Time','>=',lograte,'Next Step')
        self.rest(numberofStep+1,resttime,"charge")

    def chargedischargeCrateloop(self,crate:float,endVoltagecharge:float, endVoltagedischarge:float, steptimeLimit:int,lograte:int,numberofloops:int):
        '''
        Creates steps for a charge-discharge loop with c-rate as input.

        Passed Parameters
        ------------------
        crate(float): C-rate for charge and discharge.
        endVoltagecharge(float): Maxium voltage to charge[V].
        endVoltagedischarge(float): Minimum voltage to charge[V].
        steptimeLimit(int): Time the step should take at maximum in [s].
        lograte(int): Periodic time when data should be collected from channel in [s].
        numberofloops(int): Number of loops for charge-discharge cycle.
        ------------------

        Returns
        ------------------
        ------------------
        '''
        self.chargeStepCrate(0,crate,steptimeLimit,endVoltagecharge,lograte)
        self.dischargeStepCrate(1,(crate*(-1)),steptimeLimit,endVoltagedischarge,lograte)
        self.loop(2,numberofloops,'charge')
        self.rest(3,60,"End Test")


    def bigmapstandard(self, formchargecurrent, formchargeVolt, formdccurrent,formdcVolt,numberForm ,cyclechargecurrent,cyclechargeVolt,CVchargecuttoff,cycledccurrent,cycledcVolt,numbercycles):
        self.rest(numberofStep=0, time=21600,namenextstep='Next Step')
        self.chargeStep(numberofStep=1, current=formchargecurrent,endVoltagecharge=formchargeVolt,steptimeLimit=43200, lograte=1, stepname='chargeFormation')
        self.ConstantVoltageCharge(numberofStep=2, voltage=cyclechargeVolt,resistance=0, mincurrent=CVchargecuttoff, steptimeLimit=43200,lograte=1)
        self.dischargeStep(numberofStep=3,dischargecurrent=formdccurrent, endVoltagedischarge=formdcVolt,steptimeLimit=43200,lograte=1, stepname='dcFormation')
        self.loop(numberofStep=4, numberIterations=numberForm, gobackToStep='chargeFormation')
        self.chargeStep(numberofStep=5, current=cyclechargecurrent, endVoltagecharge=cyclechargeVolt, steptimeLimit=5400, lograte=1)
        self.ConstantVoltageCharge(numberofStep=6, voltage=cyclechargeVolt,resistance=0, mincurrent=CVchargecuttoff, steptimeLimit=43200,lograte=1)
        self.dischargeStep(numberofStep=7, dischargecurrent=cycledccurrent,endVoltagedischarge=cycledcVolt,steptimeLimit=5400, lograte=1)
        self.loop(numberofStep=8,numberIterations=numbercycles, gobackToStep='charge')
        

########################################################################################################################################################################################################

    def getnames(self,inputlist:list, name:str, outputlist:list):
        '''
        Searches for name+wildcards in the given list and returns all strings similar to parameter name.

        Passed Parameters
        ------------------
        inputlist(list of str): list of all possible names of paramters/keys.
        name(string): name of the paramter/key and all similar words the function should look for.
        ------------------

        Returns
        ------------------
        outputlist(list of str): list of all found strings similar to the name parameter.
        ------------------
        '''
        for i in range(len(inputlist)):
            if re.search(name +'.+',inputlist[i]) != None:   # search for the name + wild cards for chars and gets back the object
                outputlist.append(inputlist[i])
            else:
                continue
        return(outputlist)

    def orderfileDic(self):
        '''
        Puts scheduledictionary in the correct order for later saving.

        Passed Parameters
        ------------------
        ------------------

        Returns
        ------------------
        ------------------
        '''
        copydic = {}
        unorderedList = []
        orderedList = []
        counterSteps = 0 
        counterLimits = 0
        self.fileDictionary                                    # define it as the global fileDictionary else you get error
        for x in self.fileDictionary:
            unorderedList.append(x)
        self.getnames(unorderedList,'version',orderedList)           # get version section
        self.getnames(unorderedList,'signature',orderedList)           #get signature section
        orderedList.append(unorderedList[2])                     # get schedule section (not possible with function cause of names of next section)
        for i in range(len(unorderedList)):                       # gets Steps and their limits directly afterwards
            if unorderedList[i] == 'Schedule_Step'+str(counterSteps):
                orderedList.append(unorderedList[i])
                for o in range(len(unorderedList)):
                    if unorderedList[o] == 'Schedule_Step'+str(counterSteps)+'_Limit'+str(counterLimits):
                        orderedList.append(unorderedList[o])
                        counterLimits  = counterLimits + 1
                counterSteps = counterSteps +1
                counterLimits = 0
            else:
                continue
        self.fileDictionary['Schedule']['m_uStepNum'] = counterSteps            # update the stepnumber in the schedule section
        self.getnames(unorderedList,'Schedule_UserDefineSafety',orderedList)
        self.getnames(unorderedList,'SDU_',orderedList)
        self.getnames(unorderedList,'Schedule_CSchedule_IvSafetyAndSDL', orderedList)
        self.getnames(unorderedList,'Aux',orderedList)
        self.getnames(unorderedList,'CA',orderedList)
        self.getnames(unorderedList,'SM',orderedList)
        # now safe dics in right order in fileDictionary and the steps and limits to dataforJson
        for i in range(len(orderedList)):
            copydic[orderedList[i]] = self.fileDictionary[orderedList[i]].copy()
            if re.search('Schedule_Step.+',orderedList[i]):
                self.scheduledata[orderedList[i]] = self.fileDictionary[orderedList[i]].copy()
        self.fileDictionary.clear()
        self.fileDictionary = copydic.copy()

    def getpossibleBatteryobjects(self):
        '''
        Prints out content of the folder where batteryobjects are saved in.

        Passed Parameters
        ------------------
        ------------------

        Returns
        ------------------
        ------------------
        '''
        path = self.pathToFile(self.pathToBatteryobjectFiles)          # check if path to objects is correct and return it 
        liste = os.listdir(path)
        print(liste)
   
    def initaliseSchedule(self,batteryobjectname:str,defaultSteptime:int):
        '''
        Creates Scheduledictionary based on an empty schedulefile and adding batteryobject and defaultsteptime.

        Passed Parameters
        ------------------
        batteryobjectname(string): Complete name of the batteryobject to add batteryspecific parameters(Vmax, Imax, ....)
        defaultSteptime(int): Maximum hours one step has time to finish.
        ------------------

        Returns
        ------------------
        ------------------
        '''
        self.__init__(arbin_config)
        orig = os.getcwd()
        self.emptySchedulePath = self.pathToFile(arbin_config["pathToEmptyScheduleFile"])  # get pathname to emptySchedule file (by default the current Path of this Python Script)
        self.contentemptySchedule = self.getEmptySchedule()     # safes empty schedule file as a list where keys-Values are not seperated

        self.seperateKeyValue(self.contentemptySchedule)                  # seperates keys&Values inside list as nested list in the content list

        self.safeToScheduleDictionary(self.contentemptySchedule)                  # safes the content list in nested dictionaries

        self.assignBatteryobject(batteryobjectname)            # assign Batteryobjectname to the schedule
        self.addglobalsafetys(defaultSteptime)                # adds global safeties(normaly on global page in MITS Pro 8), parameter is default steptime in hours
        os.chdir(orig)
    
    def saveScheduleData(self,name:str):
        '''
        Saves scheudledictionary in json format at the specific folder jsonfiles.

        Passed Parameters
        ------------------
        name(string): Name the file should get.
        ------------------

        Returns
        ------------------
        ------------------
        '''
        os.chdir(self.pathOfJsonfile)
        with open(name+".json",'a') as fp:
            json.dump(self.scheduledata,fp,sort_keys=True)
            fp.write('\n')
        fp.close()
        os.chdir(self.originalPath)

    def createSchedulefile(self, batteryobjectname:str):
        '''
        Creates Schedulefile based on the filedictionary.

        Passed Parameters
        ------------------
        batteryobjectname(string): Complete name of the batteryobject to generate the name.
        ------------------

        Returns
        ------------------
        ------------------
        '''
        #batteryobjectname = self.fileDictionary['Schedule']['m_TestObjName'] [:-3]  # slicing of .to to later give new filetype json
        self.orderfileDic()
        #self.saveScheduleData(nameOfObject+'.json') # name of object is safed there
        os.chdir(self.pathToScheduleFiles)                      # path where all schedule files for arbin are
        f = open(batteryobjectname+'.sdx', 'a')
        for x,y in self.fileDictionary.items():                # double loop over nested fileDictionary
            for i,l in y.items():
                if l == None:                              # if value is None it´s only a describtive string in file
                    f.write(i)
                    f.write('\n')
                else:                                      #else there is value for a parameter that needs to be set
                    f.write(i)
                    f.write('=')
                    f.write(str(l))
                    f.write('\n')                               
            f.write('\n')                                   # seperators for different parts in the file
            f.write('\n')
        f.close()
        os.chdir(self.originalPath)

#########################################################################################################################################################################################################

    def saveBatchdict(self):
        '''
        Saves batchdictionary in json format at the specific folder jsonfiles.

        Passed Parameters
        ------------------
        ------------------

        Returns
        ------------------
        ------------------
        '''
        path = os.getcwd()
        os.chdir(arbin_config['pathOfJsonfile'])
        with open('batchDict.json','x') as fp:
            json.dump(self.batchDictionary,fp)
            fp.write('\n')
        os.chdir(path)

    def addEmptyTesttoBatch_Test(self,CH_Nr:int):
        '''
        Creates a testsdictionary in batchdictionary at given test containing None.

        Passed Parameters
        ------------------
        CH_Nr(int number): Number of the channel/test/coincell 
        ------------------

        Returns
        ------------------
        ------------------
        '''
        self.batchDictionary['Batch_Test'+str(CH_Nr)] = {
            '[Batch_Test'+str(CH_Nr) + ']': None,
        }

    def addBatch_ParallelGroup(self):
        '''
        Adds specific part of the Batchfile to batchdictioanry.

        Passed Parameters
        ------------------
        ------------------

        Returns
        ------------------
        ------------------
        '''
        self.batchDictionary['Batch_ParallelGroup'] = {
            '[Batch_ParallelGroup]' : None,
            'm_ParaGroupManager' : '',
        }

    def addTestsTobatchDictionary(self):
        '''
        Adds None to all tests in batchfile.

        Passed Parameters
        ------------------
        ------------------

        Returns
        ------------------
        ------------------
        '''
        for i in range(64):
            self.addEmptyTesttoBatch_Test(i)
        self.addBatch_ParallelGroup()

    def createKeyNameList(self):
        '''
        Creates a list with all paramters as keys read in from empty bactch.

        Passed Parameters
        ------------------
        ------------------

        Returns
        ------------------
        batchDictionaryNameList(list of str): List containing all names of paramters of a batch file.
        ------------------
        '''
        batchDictionaryNameList = []
        for x in self.batchDictionary:
            batchDictionaryNameList.append(x)
        return(batchDictionaryNameList)

    def get_ArbinSysbatch(self):
        '''
        Reads in the ArbinSys.btch file line by line into a list.

        Passed Parameters
        ------------------
        ------------------

        Returns
        ------------------
        contentcurrentBatch(list of str): List containing all strings from current ArbinSys batchfile.
        ------------------
        '''
        #look for the ArbinSysbatchfile in the current folder
        try:
            f = open(self.batchName,'r')
        except:
        #try if the given Path exists else give an error and quit Programm
            orig = os.getcwd()
            os.chdir(self.pathToArbinSysbatchfile)    #since Path to emptyScheduleFile exists we change to this Path/folder
            try:
                os.path.isfile(self.batchName)
            except:
                print('File ArbinSys.bth is neither in the folder of this script ,')
                print('nor in the Path written in this Script(See variable pathToArbinSysbatchfile)')
            
        # read in every line of the Batch File
        contentcurrentBatch =[]
        with open(self.batchName,'r') as f:
            for line in f:
                line = line.strip()
                contentcurrentBatch.append(line)
        f.close()
        os.chdir(orig)
        return contentcurrentBatch

    def seperateKeyValue(self,contentcurrentBatche):     
        '''
        Splits strings based on equalsign into "keys and values" and save this list at the same position in the original list.

        Passed Parameters
        ------------------
        contentcurrentBatch(list of str): List containing all strings from current ArbinSys batchfile.
        ------------------

        Returns
        ------------------
        ------------------
        '''
        for x in range(len(contentcurrentBatche)):        # loop over all elements and sort them(new line elements, only string elements and string plus value elements) in dicts
            try:
                s = contentcurrentBatche[x].split('=')       # check if we have string+value element and split them into a list and safe them again in the original list 
                contentcurrentBatche[x] = s
            except:
                continue

    def safeToBatchDictionary(self,contentcurrentBatch:list,batchDictionaryNameList:list):
        '''
        Saves the current content of the ArbinSys.btch file to batchdictionary as keys and values.

        Passed Parameters
        ------------------
        contentcurrentBatch(list of str): List containing all strings from current ArbinSys batchfile.
        batchDictionaryNameList(list of ): List containing all names of paramters of a batch file.
        ------------------

        Returns
        ------------------
        ------------------
        '''
        counter = 0     # count variable that refers later to the name of te nested dictionary
        x = 0
        while x in range(len(contentcurrentBatch)):
            try:     
                if contentcurrentBatch[x] == contentcurrentBatch[x+1]:
                    counter = counter +1     # if 2 blancs occur the next section(in form of nested dic) occurs
                    x = x + 2                # change number so next iteration starts with the next variable of the next section
                else:
                    l = contentcurrentBatch[x]                # try to read in the list with string+varaible seperated before
                    try:
                        self.batchDictionary[batchDictionaryNameList[counter]][l[0]] = l[1]    # adding to nested dic the key and value from the list
                        x = x + 1
                    except:                    # occurs when only a string is safed in the list (e.g. 1 line [Version Section]
                        self.batchDictionary[batchDictionaryNameList[counter]][l[0]] = None   #safes string as a key with value None
                        x = x + 1
            except:
                x = x+1
                continue        # there is no x+1 value for the last x so we continue and break the while loop

    def initaliseBatch(self):
        '''
        Reads in current batchfile and saves all parts in batchdictionary.

        Passed Parameters
        ------------------
        ------------------

        Returns
        ------------------
        ------------------
        '''
        self.contentlist = self.get_ArbinSysbatch()
        self.addTestsTobatchDictionary()
        batchDictionaryNameList = self.createKeyNameList()
        contentList = self.get_ArbinSysbatch()
        self.seperateKeyValue(contentList)
        self.safeToBatchDictionary(contentList,batchDictionaryNameList)

    def createBatchfile(self):
        '''
        Creates the batchfile in the right folder based on the batchdictionary.

        Passed Parameters
        ------------------
        ------------------

        Returns
        ------------------
        ------------------
        '''
        #os.chdir(self.pathToArbinSysbatchfile)
        os.chdir(arbin_config["pathToArbinSysbatchfile"])
        try:
            os.remove(self.batchName)
        except:
            time.sleep(0.5)
        f = open(self.batchName, 'w')
        for x,y in self.batchDictionary.items():                # double loop over nested fileDictionary
            for i,l in y.items():
                if l == None:                              # if value is None it´s only a describtive string in file
                    f.write(i)
                    f.write('\n')
                else:                                      #else there is value for a parameter that needs to be set
                    f.write(i)
                    f.write('=')
                    f.write(str(l))
                    f.write('\n')                               
            f.write('\n')                                   # seperators for different parts in the file
            f.write('\n')
        f.close()
        os.chdir(self.originalPath)

    def checkSchedulename(self,scheduleName:str,pathSchedules:str):
        '''
        Checks if the given schedulename is a file in the given path.

        Passed Parameters
        ------------------
        scheduleName(str): Name of schedule you want to check for existence.
        pathSchedule(str): Path where content should be checked for the schedulename
        ------------------

        Returns
        ------------------
        ------------------
        '''
        path = self.pathToFile(pathSchedules)          # check if path to schedules is correct and return it 
        os.chdir(path)                           
        check = os.path.isfile(scheduleName)              # check if file with input name is there
        if check ==True:
            return(True)
        else:
            print('There is no Schedule with this name in the given Path of Schedules')
            print('Please create a schedule with this name or correct your input')

    def get_schedules(self):
        '''
        Printing out content of the folder where all schedules should be in.

        Passed Parameters
        ------------------
        ------------------

        Returns
        ------------------
        ------------------
        '''
        originalpath = os.getcwd()
        #os.chdir(arbin_config['pathToScheduleFiles'])
        content = []
        for (root,dirs,files) in os.walk('./'):
            content.append(files)
        schedule_files =[]
        for i in range(len(content)):
            for l in range(len(content[i])):
                if content[i][l].split('.')[-1] == 'sdx':
                    schedule_files.append(content[i][l])
        os.chdir(originalpath)
        return schedule_files

    def load_schedule(self,schedulename):
        '''
        Checks if empty schedule file is in current folder else goes to predefined and reads content in.

        Passed Parameters
        ------------------
        ------------------

        Returns
        ------------------
        ------------------
        '''
        originalpath = os.getcwd()
        #os.chdir(arbin_config['pathToScheduleFiles'])
        

        raw_schedule_content =[]
        with open(schedulename,'r') as f:
            for line in f:
                line = line.strip()
                raw_schedule_content.append(line)
        f.close()
        os.chdir(originalpath)

        temp = []
        temp2 = []
        for i in range(len(raw_schedule_content)):
            temp.append(raw_schedule_content[i])
            if raw_schedule_content[i] == '' and raw_schedule_content[i-1] == '' and i >0:
                temp = temp[:-2]
                temp2.append(temp)
                temp = []
                continue
        
        details = []
        for i in range(len(temp2)):
            if ('[Schedule_Step' in temp2[i][0]):
                details.append(i)
            else:
                continue
                
        temp2 = temp2[details[0]:details[-1]+1]

        detail_numbers_step = [0,7,9,10,15,16]

        schedule_details = []
        counter_step = 0

        step_and_limit_details = []
        details_temp= []
        for i in range(len(temp2)):
            if len(temp2[i][0].split('_'))==2:
                if i > 0: # to also include first step
                    schedule_details.append(step_and_limit_details)
                    step_and_limit_details = []
                    details_temp = []
                for l in detail_numbers_step:
                    details_temp.append(temp2[i][l].split('='))
                step_and_limit_details.append(details_temp)
            else:
                details_temp=[]
                details_temp.append(temp2[i][0])
                for m in range(1,len(temp2[i])):
                    split = temp2[i][m].split('=')
                    try:
                        floatnumber = split[1].split('.')
                        split[1] = float(split[1])
                    except:
                        try:
                            intnumber = int(split[1])
                            split[1] = intnumber
                        except:
                            pass
                    if len(split) == 3 : # having an <=, ... sign
                        add_sign = split[1] + '='
                        split[1] = add_sign
                        del split[-1]
                    details_temp.append(split)
                # restructure equations
                for i in range(len(details_temp)):
                    if 'szLeft' in details_temp[i][0]:
                        details_temp[i], details_temp[i-1] = details_temp[i-1], details_temp[i]
                step_and_limit_details.append(details_temp)
                
        schedule_details.append(step_and_limit_details)
                    
        return schedule_details

    def addNewScheduleToChannel(self,CH_Nr:int,schedulename:str):
        '''
        Adding given schedule to given channel in the batchDictionary, saving number and schedulename in global lists and refreshing the window.(Monitor and Controll Window must be open at most top layer)
        Watch out: This only works if you empty/remove the schedule at the channel before using removeSchedule-function.

        Passed Parameters
        ------------------
        CH_Nr(int number): Number of the channel/test/coincell 
        schedulename(string): complete name of schedule you want to add (including .sdx ending)
        ------------------

        Returns
        ------------------
        ------------------
        '''
        time.sleep(5)
        if self.checkSchedulename(schedulename+'.sdx',self.pathToScheduleFiles) == True:
            self.removeSchedule(CH_Nr)
            if CH_Nr in range(1,65) and self.batchDictionary['Batch_Test'+str(CH_Nr-1)]['m_szScheduleName'] == '':           # CH_Nr-1 cause in batchfile tests start with 0 and not 1
                self.batchDictionary['Batch_Test'+str(CH_Nr-1)]['m_szScheduleName'] = "FINALES2\\"+str(schedulename)+'.sdx'
                self.newTests.append(CH_Nr)
                self.newTestsnames.append(schedulename)
                self.createBatchfile()
                self.metaDataDict['Schedule']['Channels'].append(CH_Nr)
                time.sleep(3)
                self.refreshMonitorAndControlWindow()
                self.refreshbyassign(CH_Nr=25)
            else:
                print('This is an error either cause CH_Nr is out of range or cause there is already a schedule written in(then remove it first)')
        else:
            print('Something went wrong with the schedulename(either no file with this name in scheudle path or path to schedules is not correct)')

    def refreshbyassign(self,CH_Nr:int):
        xchannel=24
        ychannel= 145
        xassign = 448
        yassign = 860
        xtest=497
        ytest=896
        xtestname = 890
        ytestname = 445
        time.sleep(3)
        ahk=AHK()
        ahk.mouse_move(x=xchannel,y=ychannel,blocking=True)    # click on channel
        ahk.click()
        for l in range(64):                          # start a CH_Nr 1
                    ahk.key_press('Up')
        currentCH_Nr = 1
        diff = currentCH_Nr - CH_Nr        # for checking wheter to go up or down in CH_Nr list and how many times
        if diff<0:
            for o in range(abs(diff)):
                ahk.key_press('Down')
        elif diff>0:
            for o in range(diff):
                ahk.key_press('Up')
        self.clickChannel(CH_Nr)
        time.sleep(3)
        ahk.mouse_move(x=xassign,y=yassign,blocking=True) 
        ahk.right_click()   # click assign
        time.sleep(3)
        ahk.mouse_move(x=xtest,y=ytest,blocking=True) 
        ahk.click()  
        time.sleep(3)
        ahk.mouse_move(x=xtestname,y=ytestname,blocking=True) 
        ahk.double_click()
        time.sleep(3)
        ahk.mouse_move(x=xassign,y=yassign,blocking=True) 
        ahk.right_click()   # click assign
        time.sleep(3)
        ahk.mouse_move(x=486,y=912,blocking=True) # move to clear
        ahk.click()




    def startNewChannel(self, CH_Nr:int, reqID:str):
        '''
        Starts the channel with automated testname at the given number using AHK.(Monitor and Controll Window must be open at most top layer)
        Testnamescheme: 'test_'+str(CH_Nr)+'_'+str(today) where today: '%d-%m-%Y-%H_%M'

        Passed Parameters
        ------------------
        CH_Nr(int number): Number of the channel/test/coincell 
        ------------------

        Returns
        ------------------
        ------------------
        '''
        xchannel=24
        ychannel= 145
        xstartch = 20
        ystartch = 80
        time.sleep(3)
        ahk=AHK()
        #ahk.mouse_move(x=xchannel,y=ychannel,blocking=True)    # click on channel
        #ahk.click()
        #for l in range(64):                          # start a CH_Nr 1
        #    ahk.key_press('Up')
        #time.sleep(2)
        #self.sacrificalChannel()
        #time.sleep(5)
        ahk.mouse_move(x=xchannel,y=ychannel,blocking=True)    # click on channel
        ahk.click()
        for l in range(64):                          # start a CH_Nr 1
                    ahk.key_press('Up')
        currentCH_Nr = 1
        diff = currentCH_Nr - CH_Nr        # for checking wheter to go up or down in CH_Nr list and how many times
        if diff<0:
            for o in range(abs(diff)):
                ahk.key_press('Down')
        elif diff>0:
            for o in range(diff):
                ahk.key_press('Up')
        self.clickChannel(CH_Nr)
        ahk.mouse_move(x=xstartch,y=ystartch,blocking=True)
        ahk.click()
        time.sleep(5)
        now = datetime.datetime.now()
        today = now.strftime('%d-%m-%Y-%H_%M')
        ahk.send_input('test_'+str(CH_Nr)+ "_"+str(reqID)) #name for test on CH_Nr
        time.sleep(1)
        ahk.key_press('Enter')
        time.sleep(5)
        ahk.mouse_move(x=xchannel,y=ychannel,blocking=True)    # click on CH_Nr
        ahk.click()
        for l in np.arange(1,65):                   # going back to channel 1 when all newTests are started
            ahk.key_press('Up')
        time.sleep(2)
        ahk.mouse_move(x=xchannel,y=ychannel,blocking=True)    # click on CH_Nr
        ahk.click()
        self.newTests.clear()
        self.newTestsnames.clear()
        time.sleep(2)

    def resume_channel(self, CH_Nr:int):
            '''
            Starts the channel with automated testname at the given number using AHK.(Monitor and Controll Window must be open at most top layer)
            Testnamescheme: 'test_'+str(CH_Nr)+'_'+str(today) where today: '%d-%m-%Y-%H_%M'

            Passed Parameters
            ------------------
            CH_Nr(int number): Number of the channel/test/coincell 
            ------------------

            Returns
            ------------------
            ------------------
            '''
            xchannel=24
            ychannel= 145
            xstartch = 41
            ystartch = 78
            time.sleep(3)
            ahk=AHK()
            #ahk.mouse_move(x=xchannel,y=ychannel,blocking=True)    # click on channel
            #ahk.click()
            #for l in range(64):                          # start a CH_Nr 1
            #    ahk.key_press('Up')
            #time.sleep(2)
            #self.sacrificalChannel()
            #time.sleep(5)
            ahk.mouse_move(x=xchannel,y=ychannel,blocking=True)    # click on channel
            ahk.click()
            for l in range(64):                          # start a CH_Nr 1
                        ahk.key_press('Up')
            currentCH_Nr = 1
            diff = currentCH_Nr - CH_Nr        # for checking wheter to go up or down in CH_Nr list and how many times
            if diff<0:
                for o in range(abs(diff)):
                    ahk.key_press('Down')
            elif diff>0:
                for o in range(diff):
                    ahk.key_press('Up')
            self.clickChannel(CH_Nr)
            ahk.mouse_move(x=xstartch,y=ystartch,blocking=True)
            ahk.click()
            time.sleep(5)
            ahk.key_press('Enter')
            time.sleep(3)
            ahk.key_press('Enter')
            time.sleep(3)
            ahk.mouse_move(x=xchannel,y=ychannel,blocking=True)    # click on CH_Nr
            ahk.click()
            for l in np.arange(1,65):                   # going back to channel 1 when all newTests are started
                ahk.key_press('Up')
            time.sleep(2)
            ahk.mouse_move(x=xchannel,y=ychannel,blocking=True)    # click on CH_Nr
            ahk.click()
            time.sleep(2)


    def removeSchedule(self,CH_Nr:int,):
        '''
        Removes schedule from the batchdictionary at the given channelnumber.

        Passed Parameters
        ------------------
        CH_Nr(int number): Number of the channel/test/coincell 
        ------------------

        Returns
        ------------------
        ------------------
        '''
        if CH_Nr in range(1,65):
            self.batchDictionary['Batch_Test'+str(CH_Nr-1)]['m_szScheduleName'] = ''    # CH_Nr-1 cause in batchfile tests start with 0 and not 1
        else:
            print('Given CH_Nr is out of range(1-64)')
            
    def getmouseposition():
        '''
        Pprints out current mouse position.

        Passed Parameters
        ------------------
        ------------------

        Returns
        ------------------
        ------------------
        '''
        ahk= AHK()
        pos = list(ahk.mouse_position)
        print(pos)

    def printOpenWindows(self):
        '''
        Prints out all current open windows with their id.

        Passed Parameters
        ------------------
        ------------------

        Returns
        ------------------
        ------------------
        '''
        ahk = AHK()
        for window in ahk.windows():
            print(window.title)
            print(window.id)

    def refreshMonitorAndControlWindow(self):
        '''
        Open up Monitor and Controll Window then closes and open it again using AHK.

        Passed Parameters
        ------------------
        ------------------

        Returns
        ------------------
        ------------------
        '''
        ahk = AHK()
        xwindowmiddle = 1061 #clicks in the middle of the screen to activate window
        ywindowmiddle = 19
        xMonitornControll = 21  # click to start monitor&controll
        yMonitornControll = 61
        try:
            win = ahk.find_window(title=b'MITS Pro - Arbin Instruments (admin)')
            win.activate_bottom()
            win.maximize()                                          # maximize window just for saftey
            win = ahk.find_window(title=b'<Monitor & Control Window>  ArbinSys.bth (admin) - ')
            win.activate_bottom()
            win.maximize()                                          # maximize for saftey
            ahk.click(xwindowmiddle,ywindowmiddle)
            win.close()
            time.sleep(2)
            ahk.key_press('Enter')
            ahk.mouse_move(x=xMonitornControll,y=yMonitornControll,blocking=True)                   # click on Monitor&Control launcher
            ahk.click()
        except:
            print('MITS Pro software not found as an open Window. Please execute Console.exe and launch Monitor&Control')
        time.sleep(1)

    def clickChannel(self,CH_Nr:int):
        '''
        Click on the channelnumber using AHK.(Monitor and Controll Window must be open at most top layer)
        It assums you scrolled up to first channel.

        Passed Parameters
        ------------------
        CH_Nr(int number): Number of the channel/test/coincell
        ------------------

        Returns
        ------------------
        ------------------
        '''
        xlastchannel = 31 # for clicking last channel when scrolling down is needed
        ylastchannel = 869
        time.sleep(3)
        ahk = AHK()
        if CH_Nr < 25:
            x = 35
            y = (CH_Nr * 31 + 120)-CH_Nr                # position difference of channels times CH_Nr gives postition in window
        else:
            x = xlastchannel
            y = ylastchannel                              # jump to CH_Nr 25(started by 1)
        ahk.mouse_move(x=x,y=y,blocking=True)       #click on channel
        ahk.click()   
        time.sleep(2)
        ahk.click()

    def refreshtestwindow(self):
        time.sleep(2)
        ahk = AHK()
        ahk.mouse_move(x=227,y=37,blocking=True)    
        ahk.click()
        ahk.mouse_move(x=250,y=57,blocking=True)    
        ahk.click()
        time.sleep(3)
        ahk.mouse_move(x=250,y=57,blocking=True)    
        ahk.mouse_drag(354,0,relative=True)
        self.clickChannel(1)

    def exportData(self,CH_Nr:int, reqID:str, overwrite = False, exporttime = 15):
        '''
        Exports data using AHK and Datawatchersoftware to ArbinData folder of the given channelnumber.(Monitor and Controll Window must be open at most top layer)

        Passed Parameters
        ------------------
        CH_Nr(int number): Number of the channel/test/coincell
        ------------------

        Returns
        ------------------
        ------------------
        '''
        self.refreshMonitorAndControlWindow()
        time.sleep(3)
        ahk = AHK()
        xdatawatcher = 164   #click on DataWatcherbutton
        ydatawatcher = 78
        xexport = 217
        yexport = 176
        xaddtest= xexport
        yaddtest = yexport -37
        xtestname = 686
        ytestname = 324
        xtestclick = 615
        ytestclick = 454
        self.clickChannel(1)    # click on channel
        ahk.click()
        for l in range(64):                          # start a CH_Nr 1
                    ahk.key_press('Up')
        for i in range(CH_Nr):
            ahk.key_press('Down')
        self.clickChannel(CH_Nr)
        ahk.mouse_move(x=xdatawatcher,y=ydatawatcher,blocking=True)    # click on DataWatcher
        ahk.click()
        time.sleep(4)
        ahk.mouse_move(x=xaddtest,y=yaddtest,blocking=True)
        ahk.click()
        time.sleep(4)
        ahk.mouse_move(x=xtestname,y=ytestname,blocking=True)
        ahk.click()
        ahk.send_input('test_'+str(CH_Nr)+ "_"+str(reqID)) #name for test on CH_Nr
        time.sleep(4)
        ahk.mouse_move(x=xtestclick,y=ytestclick,blocking=True)
        ahk.double_click()
        ahk.mouse_move(x=xexport,y=yexport,blocking=True)    # click on Export Data
        time.sleep(3)                                # wait 2 sec until window of DataWatcher appears
        ahk.click()
        time.sleep(3)
        ahk.key_press('Enter')
        time.sleep(3)
        ahk.key_press('Enter')
        if overwrite == True:
            time.sleep(1)
            ahk.key_press('Enter')
        time.sleep(exporttime)   # sleeptime for export                                              
        self.refreshMonitorAndControlWindow()                                  # find, activate and then close the DataWatcher window
        time.sleep(1)
        ahk.mouse_move(x=32,y=147,blocking=True)    # click on top channel
        ahk.click()
        for l in range(CH_Nr):                          # go back to CH_Nr 1
                    ahk.key_press('Up')
        self.clickChannel(1)

    def exportAllData(self):
        '''
        Execute expoertData-function for all 64 channels to export all data of all channels(Monitor and Controll Window must be open at most top layer)

        Passed Parameters
        ------------------
        ------------------

        Returns
        ------------------
        ------------------
        '''
        for i in range(1,65):
            self.exportData(i)

    def stopChannel(self,CH_Nr:int):
        '''
        Stoping tests at the given channelnumber using AHK.(Monitor and Controll Window must be open at most top layer)

        Passed Parameters
        ------------------
        CH_Nr(int number): Number of the channel/test/coincell
        ------------------

        Returns
        ------------------
        ------------------
        '''
        time.sleep(5)
        ahk = AHK()
        ahk.mouse_move(x=32,y=147,blocking=True)    # click on channel
        ahk.click()
        for l in range(64):                          # start a CH_Nr 1
                    ahk.key_press('Up')
        for i in range(CH_Nr-1):
            ahk.key_press('Down')
        time.sleep(3)
        self.clickChannel(CH_Nr)
        ahk.mouse_move(x=65,y=81,blocking=True)     # stop button
        ahk.click()
        ahk.click()
        for l in range(CH_Nr):                          # start a CH_Nr 1
            ahk.key_press('Up')
        
    def checkChannelfinished(self):
        '''
        Checks in Daq-logilfe for finished channel based on a written message inside and returning the channelnumber.

        Passed Parameters
        ------------------
        ------------------

        Returns
        ------------------
        ret(int): Number of the before determined finished channel/test/coincell
        ------------------
        '''
        path = os.getcwd()
        os.chdir(self.pathdaqlog)
        foldercontent = os.listdir()
        with open(foldercontent[-1], 'r')as log:
            lines = log.readlines()
        log.close()
        r = lines[-1].split()
        if r[-1] == 'finished.':
            del r[0:4]
            del r[-1]       #deletes front and back text of log so only CH_Nrs as strings remain(if more than 1 is finished at same time)
            for i in range(0,len(r)):
                if self.logfinishedChannel[-1] != int(r[i]): # assuming the CH_Nr is not finished restarted and finished again before another CH_Nr
                    l = int(r[i])
                    r[i] = l
                    self.logfinishedChannel.append(l)
                else:
                    r = None
            #returndict = {"CH_Nrs": r}
            ret = r
            r = None
            os.chdir(path)
            return ret
        os.chdir(path)  

    def cleargloballist(self):
        '''
        Clears the global list containing finished channels.

        Passed Parameters
        ------------------
        ------------------

        Returns
        ------------------
        ------------------
        '''
        self.logfinishedChannel.clear()
        
    def getpossibletestnamesChannel(self,CH_Nr:int):
        '''
        Lists and saves all possible testnames in the Datafolder

        Passed Parameters
        ------------------
        CH_Nr(int number): Number of the channel/test/coincell you want for future work.(Already needs to be exported to the specific folder ArbinData)
        ------------------

        Returns
        ------------------
        testdatafolder(list of str): List containing Names of all tests of the given channel saved in the specific folder ArbinData
        ------------------
        '''
        path = os.getcwd()
        os.chdir(arbin_config["pathToCSV"])     # path to Datafiles
        folderlist = os.listdir()
        testdatafolder = []
        print('Searching for Data')
        for x in range(len(folderlist)):
            if  re.search("test_"+str(CH_Nr)+".+", folderlist[x]): # check for test_CH_Nr + wildcards to get foldername
                testdatafolder.append(folderlist[x])
            else:
                pass
        print('Possible tests data : ' + str(testdatafolder))
        os.chdir(path)
        return testdatafolder

    def getpossibletestnames(self):
        '''
        Navigates through data folder and returns path to it

        Passed Parameters
        ------------------
        ------------------

        Returns
        ------------------
        datapath(str): path to choosen data.
        ------------------
        '''
        end = False
        path = os.getcwd()
        ordnername = ''
        targetpath = str(arbin_config["pathToCSV"])+'\\'+str(ordnername)
        os.chdir(targetpath)     # path to Datafiles
        folderlist = os.listdir()
        print(folderlist)
        while end == False:
            ordnername = input('Print next ordner to look in or n to leave: ') # !!!! upper and lower case writing of folder is important
            if ordnername == 'n':
                break
            content = os.listdir()
            ordnernamelist = []
            for x in range(len(content)):
                if  re.search('^'+str(ordnername), content[x]): # check if there is a similar called ordnername 
                    ordnernamelist.append(content[x])
                else:
                    pass
            print(ordnernamelist)
            while len(ordnernamelist)>1:    # if there are multiple options further user input is required
                ordnername = input('Write option you want: ')
                ordnernamelist.clear()
                for x in range(len(content)):
                    if  re.search(str(ordnername)+".+", content[x]): # check 
                        ordnernamelist.append(content[x])
                    else:
                        pass
            ordnername = ordnernamelist[0]
            targetpath = targetpath + '\\'+str(ordnername)
            os.chdir(targetpath)     # go to next instance in folder
            targetpath = os.getcwd()
            folderlist = os.listdir()
            print(folderlist)    # print content  
        datapath = targetpath      
        os.chdir(path)
        return datapath
       
    def save_dict_to_hdf5(self,dic, filename):
        '''
        Saves a dictioanry to a hdf5file.

        This function was copied from stackoverflow.
        '''
        path = os.getcwd()
        os.chdir(arbin_config['pathHDF5'])
        with h5py.File(filename, 'a') as h5file:
            self.recursively_save_dict_contents_to_group(h5file, '/', dic)
        os.chdir(path)

    def recursively_save_dict_contents_to_group(self,h5file, path, dic):
            '''
            Saves dictionary content to groups.

            This function was copied from stackoverflow.
            '''
            # argument type checking
            if not isinstance(dic, dict):
                raise ValueError("must provide a dictionary")        
            if not isinstance(path, str):
                raise ValueError("path must be a string")
            if not isinstance(h5file, h5py._hl.files.File):
                raise ValueError("must be an open h5py file")
            # save items to the hdf5 file
            for key, item in dic.items():
                #print(key,item)
                key = str(key)
                if isinstance(item, list):
                    item = np.array(item)
                    #print(item)
                if not isinstance(key, str):
                    raise ValueError("dict keys must be strings to save to hdf5")
                # save strings, numpy.int64, and numpy.float64 types
                if isinstance(item, (np.int64, np.float64, str, float, float, float,int)):
                    #print( 'here' )
                    h5file[path + key] = item
                    #print(h5file[path + key])
                    #print(item)
                    if not h5file[path + key].value == item:
                        raise ValueError('The data representation in the HDF5 file does not match the original dict.')
                # save numpy arrays
                elif isinstance(item, np.ndarray):            
                    try:
                        h5file[path + key] = item
                    except:
                        item = np.array(item).astype('|S32')      # S32 defines you length of reserved diskspace and max number of letters
                        h5file[path + key] = item
                    #if not np.array_equal(h5file[path + key].value, item):
                    #   raise ValueError('The data representation in the HDF5 file does not match the original dict.')
                # save dictionaries
                elif isinstance(item, dict):
                    self.recursively_save_dict_contents_to_group(h5file, path + key + '/', item)
                # other types cannot be saved and will result in an error
                else:
                    #print(item)
                    raise ValueError('Cannot save %s type.' % type(item))

    def getChannelData(self,datapath:str):
        '''
        Reading in csv file of the testname, poping some parameters to avaoid discspace problems and saving remaining as a dictionary.

        Passed Parameters
        ------------------
        datapath(string): Path to data choosen before when using getpossibletestnames()
        ------------------

        Returns
        ------------------
        datadict(dictionary): Dictionary containing all read-in data from the csv outputfile from arbin.
        ------------------
        '''
        path = os.getcwd()
        os.chdir(datapath)     # path to Datafiles
        content = os.listdir()
        print(str(content))
        df = pd.read_csv(str(content[0]), delimiter=',')
        df.pop('Power(W)')
        df.pop('Internal_Resistance(Ohm)')
        df.pop('dQ/dV(Ah/V)')
        df.pop('dV/dQ(V/Ah)')
        df.pop('dV/dt(V/s)')    
        df.pop('ACR(Ohm)') 
        #df.pop('Charge_Capacity(Ah)')  
        #df.pop('Discharge_Capacity(Ah)')  
        df.pop('Date_Time')
        df.pop('Step_Time(s)')
        #print(df)   
        df = df.astype(np.float64)
        datadict = df.to_dict()
        if len(content) > 1:
                print('There are more csv files in.')
                for i in range(1,len(content)):
                    df2 = pd.read_csv(str(content[i]), delimiter=',')
                    df2.pop('Power(W)')
                    df2.pop('Internal_Resistance(Ohm)')
                    df2.pop('dQ/dV(Ah/V)')
                    df2.pop('dV/dQ(V/Ah)')
                    df2.pop('dV/dt(V/s)')    
                    df2.pop('ACR(Ohm)') 
                    #d2f.pop('Charge_Capacity(Ah)')  
                    #d2f.pop('Discharge_Capacity(Ah)')  
                    df2.pop('Date_Time')
                    df2.pop('Step_Time(s)')
                    #print(df)   
                    print(len(df))
                    print(len(df2))
                    df = pd.concat([df, df2])
                    print(df)
                df.set_index('Data_Point', inplace = True)
                completeDict = df.to_dict()
                print(completeDict.keys())
                print(len(completeDict['Current(A)']))
                return completeDict
        else:
            os.chdir(path)
            return datadict

    def serperaterawData(self,data:dict):
        '''
        Serperates and saves the raw data saved in a dictionary to lists of each in future used parameter.

        Passed Parameters
        ------------------
        data(Dictioanry): Dictionary containing all information from the read in csv result file from arbin.
        ------------------

        Returns
        ------------------
        testTime(list of int): List containing increasing testtime(int) read-in from csv-datafile.
        cycleIndex(list of int): List containing the corresponging cycleindex to each datapoint read-in from csv-file.
        I(list of float): List containing all Currentvalues(float) read-in from csv-datafile.
        V(list of float): List containing all Voltagevalues(float) read-in from csv-datafile.
        chargeEnergy(list of float): List containing all Chargeenergyvalues(loat) read-in from csv-datafile.
        dischargeEnergy(list of float): List containing all Dischargeenergyvalues(float) read-in from csv-datafile.
        ------------------
        '''
        testTime=list(data['Test_Time(s)'].values())
        #datapoint = list(data['Data_Point'].values())                
        cycleIndex =list(data['Cycle_Index'].values())
        stepIndex = list(data['Step_Index'].values())
        I = list(data['Current(A)'].values())
        V = list(data['Voltage(V)'].values())
        chargeEnergy = list(data['Charge_Energy(Wh)'].values())
        dischargeEnergy = list(data['Discharge_Energy(Wh)'].values())
        #chargeCapacity = list(data['Charge_Capacity(Ah)'].values())
        #dischargeCapacity = list(data['Discharge_Capacity(Ah)'].values())
        return  testTime,cycleIndex,stepIndex,I,V,chargeEnergy,dischargeEnergy
    
    
    def getCyclelimitListFINALES(self,cycleindex:list, stepindex:list,current:list):
        '''
        Returns a list containing cyclelimits based on changes in stepindices and current.

        Passed Parameters
        ------------------
        cycleindex(list of int):  List containing all Cycleindices(int) read-in from csv-datafile.
        stepindex(list of int): List containing all Stepindices(int) read-in from csv-datafile.
        current(list of float): List containing all Currentvalues(loat) read-in from csv-datafile.
        ------------------

        Returns
        ------------------
        cycleborderlist(list of int): List containing Limitindices(including Indice to cycle)
        ------------------
        '''
        cyclelimitlist = []
        cycleindexlist = []
        stepindexlist = []
        currentlist = []

        for l in range(len(current)-1):
            cycleindexlist.append(cycleindex[l])
            stepindexlist.append(stepindex[l])
            currentlist.append(current[l])
            if (stepindex[l]!=stepindex[l-1] and l >0 and stepindex[l]!=3 and stepindex[l]!=5 and stepindex[l]!=8 and stepindex[l]!=10):
                cyclelimitlist.append(l)
        cyclelimitlist.append(len(current))   
        return cyclelimitlist

    def getandsafeCycledata(self,cycleList:list,testTime:list,current:list, voltage: list, chargeEnergy:list, dischargeEnergy:list,analysisDict:dict, cyclenamelist:list):
        '''
        Slices and saves data for each cycle.
        
        
        Passed Parameters
        ------------------
        cycleList(list of int):  List containing all Cycleindices(int) read-in from csv-datafile.
        testTime(list of int): List containing increasing testtime(int) read-in from csv-datafile.
        current(list of float): List containing all Currentvalues(float) read-in from csv-datafile.
        voltage(list of float): List containing all Voltagevalues(float) read-in from csv-datafile.
        chargeEnergy(list of float): List containing all Chargeenergyvalues(loat) read-in from csv-datafile.
        dischargeEnergy(list of float): List containing all Dischargeenergyvalues(float) read-in from csv-datafile.
        analysisDict(Dictioanry): Global Dictionary to save all raw and split up Data
        cyclenamelist(list of int): List containing the limiting points of the charge/discharge cycles also including CV step.
        ------------------

        Returns
        ------------------
       
        ------------------
        
        '''
        for i in range(len(cycleList)):
            cycletesttime = []
            if i == 0:
                minlimit = 0
            else:
                minlimit = cycleList[i-1]
            correction = testTime[minlimit]
            for l in range(minlimit,cycleList[i]):
                cycletesttime.append(testTime[l]-correction)
            currentlist = []
            voltlist = []
            chargeenergylist = []
            dischargeenergylist= []
            cycleend = cycleList[i]
            cyclestart = cycleList[i-1]
            if i == 0:
                cycleend = cycleList[0]
                cyclestart = 0
            chargeEdiff = chargeEnergy[cyclestart]
            dchargeEdiff = dischargeEnergy[cyclestart]
            for l in range(cyclestart,cycleend):
                currentlist.append(current[l])
                voltlist.append(voltage[l])
                chargeenergylist.append(abs(chargeEnergy[l] - chargeEdiff))
                dischargeenergylist.append(abs(dischargeEnergy[l]- dchargeEdiff))
            capacity = np.trapz(currentlist,cycletesttime) * (1000/3600)
            capacityrounded = np.around(capacity,4)
            analysisDict['split'][cyclenamelist[i]]['t'] = np.array(cycletesttime)
            analysisDict['split'][cyclenamelist[i]]['I'] = np.array(currentlist) 
            analysisDict['split'][cyclenamelist[i]]['V'] = np.array(voltlist)
            analysisDict['split'][cyclenamelist[i]]['chargeE'] = np.array(chargeenergylist)
            analysisDict['split'][cyclenamelist[i]]['dischargeE'] = np.array(dischargeenergylist)
            analysisDict['split'][cyclenamelist[i]]['C'] = [capacityrounded]
            #analysisDict['split']['Capacities(mAh)'].append(capacityrounded)

    def getCycleindexlist(self,cycleList:list, testTime:list):
        '''
        Corrects the cycleindices based on the before created cycleList and saves it to new list.

        Passed Parameters
        ------------------
        cycleList(list of int):  List containing all Cycleindices(int) read-in from csv-datafile.
        testTime(list of int): List containing increasing testtime(int) read-in from csv-datafile.
        ------------------

        Returns
        ------------------
        testcycleindiceslist(list of int): List containing all cyclelimiting-indices of the test.
        ------------------
        '''
        testcycleindiceslist = []   
        cycleborder = 0         
        cycleindex = 0    
        for i in range(len(testTime)):                       
            a = len(testcycleindiceslist)
            b = cycleList[cycleborder]
            if  a == b+1:    
                if cycleborder != len(cycleList)-1:     # increase cyleborder only if its not already the last cycle
                    cycleborder = cycleborder +1                 
                    cycleindex = cycleindex + 1       
            testcycleindiceslist.append(cycleindex)
        return testcycleindiceslist

    def saveDatatoDic(self,testTime:list,stepindex:list,current:list, voltage: list, chargeEnergy:list, dischargeEnergy:list, analysisDict:dict, cycleindexlist:list):
        '''
        Saves raw and within calcualted data of one test as numpy arrays to the analysisDict.

        Passed Parameters
        ------------------
        testTime(list of int): List containing increasing testtime(int) read-in from csv-datafile.
        stepindex(list of int): List containing all Stepindices(int) read-in from csv-datafile.
        current(list of float): List containing all Currentvalues(float) read-in from csv-datafile.
        voltage(list of float): List containing all Voltagevalues(float) read-in from csv-datafile.
        chargeEnergy(list of float): List containing all Chargeenergyvalues(loat) read-in from csv-datafile.
        dischargeEnergy(list of float): List containing all Dischargeenergyvalues(float) read-in from csv-datafile.
        analysisDict(Dictioanry): Global Dictionary to save all raw and split up Data
        cycleindexlist(list of int): List contaoning all Cycleinideces read in from csv file.
        ------------------
                
        Returns
        ------------------

        ------------------
        '''
        analysisDict['raw']['Cycle_Index'] = np.array(cycleindexlist)
        analysisDict['raw']['Step_Index'] = np.array(stepindex)
        analysisDict['raw']['Testtime(s)'] = np.array(testTime)
        analysisDict['raw']['Voltage(V)'] = np.array(voltage)
        analysisDict['raw']['Current(A)'] = np.array(current)
        analysisDict['raw']['charge_Energy(Wh)'] = np.array(chargeEnergy)
        analysisDict['raw']['discharge_Energy(Wh)'] = np.array(dischargeEnergy)

    def changeDatatype(self,datadict:dict):
        '''
        Changes data to lists and floats.

        Passed Parameters
        ------------------
        datadict(nested dict): Containing all data from a hdf5file.
        ------------------
                
        Returns
        ------------------

        ------------------
        '''
        for key in datadict:
            if key == 'raw':
                for cycle in datadict[key]:
                    o = list(datadict[key][cycle])
                    datadict[key][cycle] = o
                    for i in range(len(datadict[key][cycle])):
                        datadict[key][cycle][i] = datadict[key][cycle][i].astype(np.float64)
            if key == 'split':
                for cycle in (datadict[key]):
                    for param in (datadict[key][cycle]):
                        try:
                            l = list(datadict[key][cycle][param])
                            datadict[key][cycle][param] = l
                            for i in range(len(datadict[key][cycle][param])):
                                datadict[key][cycle][param][i] = datadict[key][cycle][param][i].astype(np.float64)
                        except:
                            o = list(datadict[key][cycle])
                            datadict[key][cycle] = o
                            for i in range(len(datadict[key][cycle])):
                                datadict[key][cycle][i] = datadict[key][cycle][i].astype(np.float64)
    
    # try to change datatype to float when reading in/saving data but not succeded yet
    def loadHDF5(self, hdf5name:str):
        path = os.getcwd()
        os.chdir(arbin_config['pathHDF5'])
        hdf5dict = dict(hdfdict.load(hdf5name, mode='r+',lazy=False))
        os.chdir(path)
        self.changeDatatype(hdf5dict)
        return hdf5dict

#Note: Change all(split: batterylife, raw: Cycle_Index, Step_Index) to float when creating !!!!!!!!!!
    def checkDatatypes(datadict:dict):
        '''
        Checks data for one kind of datatype and prints out the keys for wrong types.

        Passed Parameters
        ------------------
        datadict(nested dict): Containing all data from a hdf5file.
        ------------------
                
        Returns
        ------------------

        ------------------
        '''
        for key in datadict['split']:
            try:
                for param in datadict['split'][key]:
                    l = isinstance(datadict['split'][key][param][0],float)
                    if l == False:
                        print(key)
            except:
                l = isinstance(datadict['split'][key][0],float)
                if l == False:
                    print(key)

        for key in datadict['raw']:
            try:
                for param in datadict['raw'][key]:
                    l = isinstance(datadict['raw'][key][param][0],float)
                    if l == False:
                        print(key)
            except:
                l = isinstance(datadict['raw'][key][0],float)
                if l == False:
                    print(key)



