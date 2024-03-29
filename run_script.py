#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys
import copy
import time
#import visa
import struct
import socket
import threading
import datetime
#import heartrate
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
# hostname = '192.168.2.7'					# FPGA IP address
port = 1024									# port number
#--------------------------------------------------------------------------#

def main_process(IPC_queue, options, log_file = None):
    if log_file is not None:
        sys.stdout = open(log_file + ".out", "w")
    print('start main process')
    try:
        # initial socket
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    except socket.error:
        print("Failed to create socket!")
        sys.exit()
    try:
        # connect socket
        s.connect((options.hostname, port))
    except socket.error:
        print("failed to connect to ip " + options.hostname)
        sys.exit()
    cmd_interpret = command_interpret(s)
    main(options, cmd_interpret, IPC_queue)
    s.close()

def set_trigger_linked(cmd_interpret):
    reads = 0
    clears_error = 0
    clears_fifo = 0
    testregister_2 = format(cmd_interpret.read_status_reg(2), '016b')
    print("Register 2 upon checking:", testregister_2)
    data_error = testregister_2[-1]
    df_synced = testregister_2[-2]
    trigger_error = testregister_2[-3]
    trigger_synced = testregister_2[-4]
    linked_flag = (data_error=="0" and df_synced=="1" and trigger_error=="0" and trigger_synced=="1")
    if linked_flag:
        print("Already Linked:",testregister_2)
        return True
    else:
        while linked_flag is False:
            time.sleep(1.01)
            testregister_2 = format(cmd_interpret.read_status_reg(2), '016b')
            reads += 1
            print("Read register:",reads)
            print("Register after waiting to link",testregister_2)
            df_synced = testregister_2[-2]
            data_error = testregister_2[-1]
            trigger_synced = testregister_2[-4]
            trigger_error = testregister_2[-3]
            linked_flag = (data_error=="0" and df_synced=="1" and trigger_error=="0" and trigger_synced=="1")
            error_flag = (data_error=="0" and trigger_error=="0")
            print("Linked flag is",linked_flag)
            print("Error flag is",error_flag)
            if linked_flag is False:
                if error_flag is False:
                    software_clear_error(cmd_interpret)
                    clears_error += 1
                    print("Cleared Error:",clears_error)
                    if clears_error == 4:
                        software_clear_fifo(cmd_interpret)
                        clears_fifo += 1
                        print("Cleared FIFO:",clears_fifo)
                else:
                    software_clear_fifo(cmd_interpret)
                    clears_fifo += 1
                    print("Cleared FIFO:",clears_fifo)
    print("Register 2 after trying to link:", testregister_2)
    return True

def set_linked(cmd_interpret):
    reads = 0
    clears = 0
    testregister_2 = format(cmd_interpret.read_status_reg(2), '016b')
    print("Register 2 upon checking:", testregister_2)
    data_error = testregister_2[-1]
    df_synced = testregister_2[-2]
    linked_flag = (data_error=="0" and df_synced=="1")
    if linked_flag:
        print("Already Linked:",testregister_2)
        return True
    else:
        while linked_flag is False:
            time.sleep(1.01)
            testregister_2 = format(cmd_interpret.read_status_reg(2), '016b')
            reads += 1
            print("Read register:",reads)
            print("Register after waiting to link",testregister_2)
            df_synced = testregister_2[-2]
            data_error = testregister_2[-1]
            linked_flag = (data_error=="0" and df_synced=="1")
            print("Linked flag is",linked_flag)
            if linked_flag is False:
                software_clear_fifo(cmd_interpret)
                clears += 1
                print("Cleared FIFO:",clears)
    print("Register 2 after trying to link:", testregister_2)
    return True

def check_trigger_linked(cmd_interpret):
    testregister_2 = format(cmd_interpret.read_status_reg(2), '016b')
    print("Register 2 upon checking:", testregister_2)
    data_error = testregister_2[-1]
    df_synced = testregister_2[-2]
    trigger_error = testregister_2[-3]
    trigger_synced = testregister_2[-4]
    if (data_error=="0" and df_synced=="1" and trigger_error=="0" and trigger_synced=="1"):
        print("All is linked with no errors")
        return True
    return False

def check_linked(cmd_interpret):
    testregister_2 = format(cmd_interpret.read_status_reg(2), '016b')
    print("Register 2 upon checking:", testregister_2)
    data_error = testregister_2[-1]
    df_synced = testregister_2[-2]
    if (data_error=="0" and df_synced=="1"):
        print("All is linked with no errors")
        return True
    return False
    
def get_fpga_data(cmd_interpret, time_limit, overwrite, output_directory, isQInj, DAC_Val):
    fpga_data = Save_FPGA_data('Save_FPGA_data', cmd_interpret, time_limit, overwrite, output_directory, isQInj, DAC_Val)
    try:
        fpga_data.start()
        while fpga_data.is_alive():
            fpga_data.join(0.8)
    except KeyboardInterrupt as e:
        fpga_data.alive = False
        fpga_data.join()

## main function
def main(options, cmd_interpret, IPC_queue = None):
    
    if(options.firmware):
        print("Setting firmware...")
        active_channels(cmd_interpret, key = active_channels_key)
        timestamp(cmd_interpret, key = options.timestamp)
        triggerBitDelay(cmd_interpret, options.trigger_bit_delay)
        Enable_FPGA_Descramblber(cmd_interpret, options.polarity)
    
    if(options.clear_fifo):
        time.sleep(0.1)                                 # delay 1000 milliseconds
        software_clear_fifo(cmd_interpret)              # clear fifo content
        time.sleep(0.1)                                 # delay 1000 milliseconds
        software_clear_fifo(cmd_interpret)              # clear fifo content  
        print("Cleared FIFO") 

    if(options.clear_error):
        time.sleep(0.1)                                 # delay 1000 milliseconds
        software_clear_error(cmd_interpret)             # clear error content
        time.sleep(0.1)                                 # delay 1000 milliseconds
        software_clear_error(cmd_interpret)             # clear error content  
        print("Cleared Error")  

    if(options.counter_duration):
        counterDuration(cmd_interpret, options.counter_duration)

    # Loop till we create the LED Errors
    # Please ensure LED Pages is set to 011
    if(options.reset_till_linked):
        time.sleep(0.1)
        set_linked(cmd_interpret)

    if(options.memo_fc):
        start_L1A(cmd_interpret)
    if(options.memo_fc_start_onetime_ws):
        start_onetime_L1A_WS(cmd_interpret)
    if(options.memo_fc_start_periodic_ws):
        start_periodic_L1A_WS(cmd_interpret)

    if(options.verbose):
        read_register_7 = cmd_interpret.read_config_reg(7)
        string_7   = format(read_register_7, '016b')
        print("Time (s) for counting stats in FPGA: ", string_7[-6:], int(string_7[-6:], base=2))
        print('\n')
        read_register_8 = cmd_interpret.read_config_reg(8)
        string_8   = format(read_register_8, '016b')
        print("Written into Reg 8: ", string_8)
        print("Enhance data LED (LED Page 011): ", string_8[-12])
        print("Enable L1A upon Rx trigger bit : ", string_8[-11])
        print("10 bit delay (trigger bit->L1A): ", string_8[-10:], int(string_8[-10:], base=2))
        print('\n')
        read_register_11 = cmd_interpret.read_config_reg(11)
        read_register_12 = cmd_interpret.read_config_reg(12)
        print("Written into Reg 11: ", format(read_register_11, '016b'))
        print("Written into Reg 12: ", format(read_register_12, '016b'))
        print('\n')
        register_13 = cmd_interpret.read_config_reg(13)
        string_13   = format(register_13, '016b')
        print("Written into Reg 13: ", string_13)
        print("Data Rate              : ", string_13[-7:-5])
        print("LED pages              : ", string_13[-5:-2])
        print("Testmode               : ", string_13[-2])
        print("Timestamp (active low) : ", string_13[-1])
        print('\n')
        register_14 = cmd_interpret.read_config_reg(14)
        string_14   = format(register_14, '016b')
        print("Written into Reg 14: ", string_14)
        print("Enable Memo FC mode: ", string_14[-4])
        print("Polarity           : ", string_14[-3])
        print("Disable GTX        : ", string_14[-2])
        print("Enable Descrambler : ", string_14[-1])
        print('\n')
        register_15 = cmd_interpret.read_config_reg(15)
        string_15   = format(register_15, '016b')
        print("Written into Reg 15: ", string_15)
        print("Channel Enable     : ", string_15[-4:])
        print("Board Type         : ", string_15[-8:-4])
        print("Data Source        : ", string_15[-16:-8])
        print('\n')

    if(not options.nodaq):
        userdefinedir = options.output_directory
        today = datetime.date.today()
        todaystr = "../ETROC-Data/" + today.isoformat() + "_Array_Test_Results"
        try:
            os.mkdir(todaystr)
            print("Directory %s was created!"%todaystr)
        except FileExistsError:
            print("Directory %s already exists!"%todaystr)
        userdefine_dir = todaystr + "/%s"%userdefinedir
        try:
            os.mkdir(userdefine_dir)
        except FileExistsError:
            print("User defined directory %s already created!"%(userdefine_dir))
            if(options.overwrite != True): 
                print("Overwriting is not enabled, exiting code abruptly...")
                sys.exit(1)

    if(options.fpga_data or options.fpga_data_QInj):
        if(options.reset_till_trigger_linked):
            print("Checking trigger link at beginning")
            set_trigger_linked(cmd_interpret)
        get_fpga_data(cmd_interpret, options.fpga_data_time_limit, options.overwrite, options.output_directory, options.fpga_data_QInj, options.DAC_Val)
        if(options.check_trigger_link_at_end):
            print("Checking trigger link at end")
            linked_flag = check_trigger_linked(cmd_interpret)
            while linked_flag is False:
                set_trigger_linked(cmd_interpret)
                get_fpga_data(cmd_interpret, options.fpga_data_time_limit, options.overwrite, options.output_directory, options.fpga_data_QInj, options.DAC_Val)
                linked_flag = check_trigger_linked(cmd_interpret)
        elif(options.check_link_at_end):
            print("Checking data link at end")
            linked_flag = check_linked(cmd_interpret)
            while linked_flag is False:
                set_linked(cmd_interpret)
                get_fpga_data(cmd_interpret, options.fpga_data_time_limit, options.overwrite, options.output_directory, options.fpga_data_QInj, options.DAC_Val)
                linked_flag = check_linked(cmd_interpret)

    if(not options.nodaq):
        ## start receive_data, write_data, daq_plotting threading
        store_dict = userdefine_dir
        read_queue = Queue()
        translate_queue = Queue() 
        plot_queue = Queue()
        read_thread_handle = threading.Event()    # This is how we stop the read thread
        write_thread_handle = threading.Event()   # This is how we stop the write thread
        translate_thread_handle = threading.Event() # This is how we stop the translate thread (if translate enabled) (set down below...)
        plotting_thread_handle = threading.Event() # This is how we stop the plotting thread (if plotting enabled) (set down below...)
        stop_DAQ_event = threading.Event()     # This is how we notify the Read thread that we are done taking data
                                               # Kill order is read, write, translate
        receive_data = Receive_data('Receive_data', read_queue, cmd_interpret, options.num_fifo_read, read_thread_handle, write_thread_handle, options.time_limit, options.useIPC, stop_DAQ_event, IPC_queue)
        write_data = Write_data('Write_data', read_queue, translate_queue, options.num_line, store_dict, options.binary_only, options.compressed_binary, options.skip_binary, options.make_plots, read_thread_handle, write_thread_handle, translate_thread_handle, stop_DAQ_event)
        if(options.make_plots or (not options.binary_only)):
            # translate_thread_handle = threading.Event()
            translate_data = Translate_data('Translate_data', translate_queue, plot_queue, cmd_interpret, options.num_line, options.timestamp, store_dict, options.binary_only, options.make_plots, board_ID, write_thread_handle, translate_thread_handle, plotting_thread_handle, options.compressed_translation, stop_DAQ_event)
        if(options.make_plots):
            # plotting_thread_handle = threading.Event()
            daq_plotting = DAQ_Plotting('DAQ_Plotting', plot_queue, options.timestamp, store_dict, options.pixel_address, board_type, board_size, options.plot_queue_time, translate_thread_handle, plotting_thread_handle)
        # read_write_data.start()
        try:
            # Start the thread
            receive_data.start()
            write_data.start()
            if(options.make_plots or (not options.binary_only)): translate_data.start()
            if(options.make_plots): daq_plotting.start()
            # If the child thread is still running
            while receive_data.is_alive():
                # Try to join the child thread back to parent for 0.5 seconds
                receive_data.join(0.5)
            if(options.make_plots or (not options.binary_only)):
                while translate_data.is_alive():
                    translate_data.join(0.5)
            while write_data.is_alive():
                write_data.join(0.5)
            if(options.make_plots):
                while daq_plotting.is_alive():
                    daq_plotting.join(0.5)
        # When ctrl+c is received
        except KeyboardInterrupt as e:
            # Set the alive attribute to false
            receive_data.alive = False
            write_data.alive = False
            if(options.make_plots or (not options.binary_only)): translate_data.alive = False
            if(options.make_plots): daq_plotting.alive = False
            # Block until child thread is joined back to the parent
            receive_data.join()
            if(options.make_plots or (not options.binary_only)): translate_data.join()
            write_data.join()
            if(options.make_plots): daq_plotting.join()
        # wait for thread to finish before proceeding)
        # read_write_data.join()
#--------------------------------------------------------------------------#
## if statement

def getOptionParser():
    
    def int_list_callback(option, opt, value, parser):
        setattr(parser.values, option.dest, list(map(int, value.split(','))))

    parser = OptionParser()
    parser.add_option("--hostname", dest="hostname", action="store", type="string", help="FPGA IP Address", default="192.168.2.3")
    parser.add_option("-l", "--num_line", dest="num_line", action="store", type="int", help="Number of lines per file created by DAQ script", default=50000)
    parser.add_option("-r", "--num_fifo_read", dest="num_fifo_read", action="store", type="int", help="Number of lines read per call of fifo readout", default=50000)
    parser.add_option("-t", "--time_limit", dest="time_limit", action="store", type="int", help="Number of integer seconds to run this code", default=-1)
    parser.add_option("-o", "--output_directory", dest="output_directory", action="store", type="string", help="User defined output directory", default="unnamed_output_directory")
    parser.add_option("--binary_only",action="store_true", dest="binary_only", default=False, help="Save only the untranslated FPGA binary data (raw output)")
    parser.add_option("--compressed_binary",action="store_true", dest="compressed_binary", default=False, help="Save FPGA binary data (raw output) in int format")
    parser.add_option("--skip_binary",action="store_true", dest="skip_binary", default=False, help="DO NOT save (raw) binary outputsto files")
    parser.add_option("--compressed_translation",action="store_true", dest="compressed_translation", default=False, help="Save only FPGA translated data frames with DATA")
    parser.add_option("-s", "--timestamp", type="int",action="store", dest="timestamp", default=0x000C, help="Set timestamp binary, see daq_helpers for more info")
    parser.add_option("-p", "--polarity", type="int",action="store", dest="polarity", default=0x000b, help="Set fc polarity, see daq_helpers for more info")
    parser.add_option("-d", "--trigger_bit_delay", type="int",action="store", dest="trigger_bit_delay", default=0x0400, help="Set trigger bit delay, see daq_helpers for more info")
    parser.add_option("-c", "--counter_duration", type="int",action="store", dest="counter_duration", default=0x0005, help="LSB 6 bits - Time (s) for FPGA data counting")
    parser.add_option("--DAC_Val", dest="DAC_Val", action="store", type="int", help="DAC value set for FPGA data taking", default=-1)
    parser.add_option("-v", "--verbose",action="store_true", dest="verbose", default=False, help="Print status messages to stdout")
    parser.add_option("-w", "--overwrite",action="store_true", dest="overwrite", default=False, help="Overwrite previously saved files")
    parser.add_option("--make_plots",action="store_true", dest="make_plots", default=False, help="Enable plotting of real time hits")
    parser.add_option("--plot_queue_time", dest="plot_queue_time", action="store", type="float", help="Time (s) used to pop lines off the queue for plotting", default=0.1)
    parser.add_option("--nodaq",action="store_true", dest="nodaq", default=False, help="Switch off DAQ via the FPGA")
    parser.add_option("--useIPC",action="store_true", dest="useIPC", default=False, help="Use Inter Process Communication to control L1A enable/disable")
    parser.add_option("-f", "--firmware",action="store_true", dest="firmware", default=False, help="Configure FPGA firmware settings")
    parser.add_option("--memo_fc",action="store_true", dest="memo_fc", default=False, help="(DEV ONLY) Do Fast Command with Memory")
    parser.add_option("--reset_till_linked",action="store_true", dest="reset_till_linked", default=False, help="FIFO clear and reset till data frames are synced and no data error is seen (Please ensure LED Pages is set to 011)")
    parser.add_option("--reset_till_trigger_linked",action="store_true", dest="reset_till_trigger_linked", default=False, help="FIFO clear and reset till data frames AND trigger bits are synced and no data error is seen (Please ensure LED Pages is set to 011)")
    parser.add_option("--check_link_at_end",action="store_true", dest="check_link_at_end", default=False, help="Check data link after getting FPGA and if not linked then take FPGA data again)")
    parser.add_option("--check_trigger_link_at_end",action="store_true", dest="check_trigger_link_at_end", default=False, help="Check trigger link after getting FPGA and if not linked then take FPGA data again)")
    parser.add_option("--fpga_data_time_limit", dest="fpga_data_time_limit", action="store", type="int", default=5, help="(DEV ONLY) Set time limit in integer seconds for FPGA Data saving thread")
    parser.add_option("--fpga_data",action="store_true", dest="fpga_data", default=False, help="(DEV ONLY) Save FPGA Register data")
    parser.add_option("--fpga_data_QInj",action="store_true", dest="fpga_data_QInj", default=False, help="(DEV ONLY) Save FPGA Register data and send QInj")
    parser.add_option("--clear_fifo",action="store_true", dest="clear_fifo", default=False, help="Clear FIFO at beginning of script")
    parser.add_option("--clear_error",action="store_true", dest="clear_error", default=False, help="Clear error at beginning of script")
    parser.add_option("--memo_fc_start_periodic_ws",action="store_true", dest="memo_fc_start_periodic_ws", default=False, help="(WS DEV ONLY) Do Fast Command with Memory, invoke start_periodic_L1A_WS() from daq_helpers.py")
    parser.add_option("--memo_fc_start_onetime_ws", action="store_true", dest="memo_fc_start_onetime_ws" , default=False, help="(WS DEV ONLY) Do Fast Command with Memory, invoke start_onetime_L1A_WS() from daq_helpers.py")
    return parser

if __name__ == "__main__":

    parser = getOptionParser()
    (options, args) = parser.parse_args()
    if(options.num_fifo_read>65536):   # See command_interpret.py read_memory()
        print("Max Number of lines read by fifo capped at 65536, you entered ",options.num_fifo_read,", setting to 65536")
        options.num_fifo_read = 65536
        
    import platform
    system = platform.system()
    if system == 'Windows' or system == '':
        options.useIPC = False

    if(options.verbose):
        print("Verbose Output: ", options.verbose)
        print("\n")
        print("-------------------------------------------")
        print("--------Set of inputs from the USER--------")
        print("Overwrite previously saved files: ", options.overwrite)
        print("FPGA IP Address: ", options.hostname)
        print("Number of lines per file created by DAQ script: ", options.num_line)
        print("Number of lines read per call of fifo readout: ", options.num_fifo_read)
        print("Number of seconds to run this code (>0 means effective): ", options.time_limit)
        print("User defined Output Directory: ", options.output_directory)
        print("Save only the untranslated FPGA binary data (raw output): ", options.binary_only)
        print("Save FPGA binary data (raw output) in int format: ", options.compressed_binary)
        print("Save only FPGA translated data frames with DATA: ", options.compressed_translation)
        print("DO NOT save binary data (raw output): ", options.skip_binary)
        print("Enable plotting of real time hits: ", options.make_plots)
        print("--------End of inputs from the USER--------")
        print("-------------------------------------------")
        print("\n")
        print("-------------------------------------------")
        print("-------Inputs that have been pre-set-------")
        print("ETROC Board Type: ",   board_type)
        print("ETROC Board Size: ",   board_size)
        print("ETROC Board Name: ",   board_name)
        print("ETROC Chip ID: ",      board_ID) 
        print("-------------------------------------------")
        print("-------------------------------------------")
        print("\n")

    if(options.binary_only==True and options.make_plots==True):
        print("ERROR! Can't make plots without translating data!")
        sys.exit(1)
    
    main_process(None, options)
