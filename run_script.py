#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys
import copy
import time
import visa
import struct
import socket
import threading
import datetime
import heartrate
from queue import Queue
import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.axes_grid1.inset_locator import zoomed_inset_axes
from mpl_toolkits.axes_grid1.inset_locator import mark_inset
from optparse import OptionParser

from command_interpret import *
from ETROC1_ArrayReg import *
from daq_helpers import *
from board_details import *
from config_etroc1 import *
#========================================================================================#
freqency = 1000
duration = 1000
'''
@author: Wei Zhang, Murtaza Safdari, Jongho Lee
@date: 2023-03-24
This script is used for testing ETROC1/2 Array chips. 
The main function of this script is I2C write and read, Ethernet communication, 
instrument control and so on.
'''
hostname = '192.168.2.3'					# FPGA IP address
port = 1024									# port number
#--------------------------------------------------------------------------#

## main function
def main(options, cmd_interpret):

    active_channels(cmd_interpret, key = active_channels_key)
    timestamp(cmd_interpret, key = options.timestamp)

    num_boards = len(board_size)
    DAC_Value_List = []
    for i in range(num_boards):
        DAC_Value_List.append(single_pixel_threshold(board_size[i], options.pixel_address[i], options.pixel_threshold[i]))

    Pixel_board = options.pixel_address
    QSel_board  = options.pixel_charge			                                        # Select Injected Charge
    ###################################### Begin Dir naming
    userdefinedir = options.output_directory
    userdefinedir_log = "%s_log"%userdefinedir
    ##  Creat a directory named path with date of today
    today = datetime.date.today()
    todaystr = "../" + today.isoformat() + "_Array_Test_Results"
    try:
        os.mkdir(todaystr)
        print("Directory %s was created!"%todaystr)
    except FileExistsError:
        print("Directory %s already exists!"%todaystr)
    userdefine_dir = todaystr + "/%s"%userdefinedir
    userdefine_dir_log = todaystr + "/%s"%userdefinedir_log
    try:
        os.mkdir(userdefine_dir)
        os.mkdir(userdefine_dir_log)
    except FileExistsError:
        print("User defined directories %s and %s already created!!!"%(userdefine_dir, userdefine_dir_log))
    ###################################### End Dir naming
    logtime_stampe = time.strftime('%m-%d_%H-%M-%S',time.localtime(time.time()))
    
    for B_num in range(num_boards):
        slaveA_addr = slaveA_addr_list[B_num]                                           # I2C slave A address
        slaveB_addr = slaveB_addr_list[B_num]                                           # I2C slave B address

        if(board_type[B_num]==1):
            reg_val = config_etroc1(B_num, options.charge_injection, DAC_Value_List, 
                                    options.pixel_address, options.pixel_charge, cmd_interpret)
        elif(board_type[B_num]==2):
            pass
        elif(board_type[B_num]==3):
            pass

        ## write data to I2C register one by one
        if(options.verbose):
            print("Write data into I2C slave:")
            print(reg_val)
        for i in range(len(reg_val)):
            time.sleep(0.01)
            if i < 32:                                                                  # I2C slave A write
                iic_write(1, slaveA_addr_list[B_num], 0, i, reg_val[i], cmd_interpret)
            else:                                                                       # I2C slave B write
                iic_write(1, slaveB_addr_list[B_num], 0, i-32, reg_val[i], cmd_interpret)

        ## read back data from I2C register one by one
        iic_read_val = []
        for j in range(len(reg_val)):
            time.sleep(0.01)
            if j < 32:
                iic_read_val += [iic_read(0, slaveA_addr_list[B_num], 1, j, cmd_interpret)]            # I2C slave A read
            else:
                iic_read_val += [iic_read(0, slaveB_addr_list[B_num], 1, j-32, cmd_interpret)]         # I2C slave B read
        if(options.verbose):
            print("I2C read back data:")
            print(iic_read_val)

        # compare I2C write in data with I2C read back data
        if iic_read_val == reg_val:
            print("I2C SUCCESS! Write data matches read data for Board ", B_num)
        else:
            print("I2C ERROR! Write data does not match read data for Board ", B_num)

    time.sleep(1)                                                                       # delay one second
    software_clear_fifo(cmd_interpret)                                                               # clear fifo content

    ## start receive_data and write_data threading
    store_dict = userdefine_dir
    queue = Queue()                                                                           # define a queue
    receive_data = Receive_data('Receive_data', queue, options.num_file, options.num_line, cmd_interpret)    # initial receive_data class
    write_data = Write_data('Write_data', queue, options.num_file, options.num_line, 
                            options.timestamp, store_dict, options.binary_only)               # initial write_data class
    
    receive_data.start()                                                                # start receive_data threading
    write_data.start()                                                                  # start write_data threading

    receive_data.join()                                                                 # threading 
    write_data.join()
#--------------------------------------------------------------------------#
## if statement
if __name__ == "__main__":
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)	                        # initial socket
    except socket.error:
        print("Failed to create socket!")
        sys.exit()
    try:
        s.connect((hostname, port))								                        # connect socket
    except socket.error:
        print("failed to connect to ip " + hostname)
    cmd_interpret = command_interpret(s)					                            # Class instance

    def int_list_callback(option, opt, value, parser):
        setattr(parser.values, option.dest, list(map(int, value.split(','))))

    parser = OptionParser()
    parser.add_option("-n", "--num_file", dest="num_file", action="store", type="int",
                      help="Number of files created by DAQ script", default=1)
    parser.add_option("-l", "--num_line", dest="num_line", action="store", type="int",
                      help="Number of lines per file created by DAQ script", default=50000)
    parser.add_option("-o", "--output_directory", dest="output_directory", action="store", type="string",
                      help="User defined output directory", default="unnamed_output_directory")
    parser.add_option("-a", "--pixel_address", dest="pixel_address", action="callback", type="string",
                      help="Single pixel address under test for each board", callback=int_list_callback)
    parser.add_option("-t", "--pixel_threshold", dest="pixel_threshold", action="callback", type="string",
                      help="Single pixel threshold for pixels under test for each board", callback=int_list_callback)
    parser.add_option("-q", "--pixel_charge", dest="pixel_charge", action="callback", type="string",
                      help="Single pixel charge to be injected (fC) for pixels under test for each board", callback=int_list_callback)
    parser.add_option("-i", "--charge_injection",
                      action="store_true", dest="charge_injection", default=False,
                      help="Flag that enables Qinj")
    parser.add_option("-b", "--binary_only",
                      action="store_true", dest="binary_only", default=False,
                      help="Save only the untranslated FPGA binary data (raw output)")
    parser.add_option("-s", "--timestamp", type="int",
                      action="store", dest="timestamp", default=0x0000,
                      help="Set timestamp binary, see daq_helpers for more info")
    parser.add_option("-v", "--verbose",
                      action="store_true", dest="verbose", default=False,
                      help="Print status messages to stdout")
    (options, args) = parser.parse_args()

    if(options.pixel_address == None): options.pixel_address = [5, 5, 5]
    if(options.pixel_threshold == None): options.pixel_threshold = [552, 560, 560]
    if(options.pixel_charge == None): options.pixel_charge = [30, 30, 30]

    if(options.verbose):
        print("Verbose Output: ", options.verbose)
        print("\n")
        print("-------------------------------------------")
        print("--------Set of inputs from the USER--------")
        print("Number of files created by DAQ script: ", options.num_file)
        print("Number of lines per file created by DAQ script: ", options.num_line)
        print("User defined Output Directory: ", options.output_directory)
        print("Single pixel address under test for each board: ", options.pixel_address)
        print("Single pixel threshold for pixels under test for each board: ", options.pixel_threshold)
        print("Single pixel charge to be injected (fC) for pixels under test for each board: ", options.pixel_charge)
        print("Flag that enables Qinj: ", options.charge_injection)
        print("Save only the untranslated FPGA binary data (raw output): ", options.binary_only)
        print("Set timestamp binary, see daq_helpers for more info: ", options.timestamp)
        print("Set timestamp binary, see daq_helpers for more info (explicit hex string): ", "0x{:04x}".format(options.timestamp))
        print("--------End of inputs from the USER--------")
        print("-------------------------------------------")
        print("\n")
        print("-------------------------------------------")
        print("-------Inputs that have been pre-set-------")
        print("ETROC Board Type: ",   board_type)
        print("ETROC Board Size: ",   board_size)
        print("ETROC Board Name: ",   board_name)
        print("I2C A Address List: ", slaveA_addr_list)
        print("I2C B Address List: ", slaveB_addr_list)
        print("Load Capacitance of the preamp first stage: ", CLSel_board)
        print("Feedback resistance seleciton: ", RfSel_board)
        print("Bias current selection of the input transistor in the preamp: ", IBSel_board)
        print("Set active channel binary, see daq_helpers for more info: ", active_channels_key)
        print("Set active channel binary, see daq_helpers for more info (explicit hex string): ", "0x{:04x}".format(active_channels_key))
        print("-------------------------------------------")
        print("-------------------------------------------")
        print("\n")
        
    main(options, cmd_interpret)											    # execute main function
    s.close()												    # close socket