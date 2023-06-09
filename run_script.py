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
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)	                        # initial socket
    except socket.error:
        print("Failed to create socket!")
        sys.exit()
    try:
        s.connect((options.hostname, port))								                        # connect socket
    except socket.error:
        print("failed to connect to ip " + options.hostname)
        sys.exit()
    cmd_interpret = command_interpret(s)
    main(options, cmd_interpret, IPC_queue)
    s.close()

## main function
def main(options, cmd_interpret, IPC_queue = None):

    num_boards = len(board_type)
    Pixel_board = options.pixel_address
    QSel_board  = options.pixel_charge

    if(options.firmware):
        if(not options.old_data_format):
            print("Setting firmware...")
            print("Active channels: ", active_channels_key)
            active_channels(cmd_interpret, key = active_channels_key)
            print("Timestamp: ", options.timestamp)
            timestamp(cmd_interpret, key = options.timestamp)
        # Enable_FPGA_Descramblber(1, cmd_interpret)
        Enable_FPGA_Descramblber(cmd_interpret, options.polarity)

    # if(options.reset_pulse_register):
    #     print("\n", "Resetting Pulse Register 0x0002")
    #     software_clear_fifo(cmd_interpret)

    if(options.inspect_serial_output):		
        # _ 2b data rate 3b LED configuration 1b testmode 1b timestamp
        testregister = cmd_interpret.read_config_reg(13)
        print('\n')
        print("Written into Reg 13: ", format(testregister, '016b'))
        print('\n')		              
        testregister_2 = cmd_interpret.read_status_reg(2)
        print("Status Reg Addr 2  : ", format(testregister_2, '016b'))
        testregister_3 = cmd_interpret.read_status_reg(3)
        print("Status Reg Addr 3  : ", format(testregister_3, '016b'))
        print("Status Reg Addr 2+3: ", (format(testregister_2, '016b'))+
        (format(testregister_3, '016b')))
        print('\n')

        fixed_32 = 0xabaaafaa
        fixed_16 = int(format(fixed_32,  '032b')[-16:], base=2)
        fixed_8  = int(format(fixed_32,  '032b')[-8:],  base=2)

        quad_8  = ""
        for elem in format(fixed_8,  '08b'): quad_8 = quad_8 + elem + elem + elem + elem
        doub_16 = ""
        for elem in format(fixed_16,  '016b'): doub_16 = doub_16 + elem + elem

        print("Processed Data Checks, look only at relavant bit length")
        print("Fixed Pattern 8    : ", format(fixed_8,  '08b'))
        if(format(fixed_8,  '08b') in format(testregister_2, '016b') and 
        format(fixed_8,  '08b') in format(testregister_3, '016b')):
            print("08 bit pattern found in both Status Reg 2 & 3")
        elif(format(fixed_8,  '08b') in format(testregister_2, '016b') or 
        format(fixed_8,  '08b') in format(testregister_3, '016b')):
            print("08 bit pattern found in ONLY ONE of Status Reg 2 & 3!")
        else: print("08 bit pattern not found in any of the Status Reg 2 or 3!")

        print("Fixed Pattern 16   : ", format(fixed_16, '016b'))
        if(format(fixed_16,  '016b') in format(testregister_2, '016b')*2 and 
        format(fixed_16,  '016b') in format(testregister_3, '016b')*2):
            print("16 bit pattern found in both Status Reg 2 & 3")
        elif(format(fixed_16,  '016b') in format(testregister_2, '016b')*2 or 
        format(fixed_16,  '016b') in format(testregister_3, '016b')*2):
            print("16 bit pattern found in ONLY ONE of Status Reg 2 & 3!")
        else: print("16 bit pattern not found in any of the Status Reg 2 or 3!")

        print("Fixed Pattern 32   : ", format(fixed_32, '032b'))
        if(format(fixed_32,  '032b') in (format(testregister_2, '016b')+format(testregister_3, '016b'))*2):
            print("32 bit pattern found in Status Reg 2 + 3")
        else: print("32 bit pattern not found in Status Reg 2 + 3!")

        print('\n')
        print("Raw Data Checks")
        print("Inflated 8-bit pattern : ", quad_8)
        print("Inflated 16-bit pattern: ", doub_16)
        if(quad_8 in (format(testregister_2, '016b')+format(testregister_3, '016b'))*2):
            print("Quadrupled 8 bit pattern found in Status Reg 2 + 3")
        else: print("Quadrupled 8 bit pattern not found in Status Reg 2 + 3!")
        if(doub_16 in (format(testregister_2, '016b')+format(testregister_3, '016b'))*2):
            print("Doubled 16 bit pattern found in Status Reg 2 + 3")
        else: print("Doubled 16 bit pattern not found in Status Reg 2 + 3!")
        print('\n')

    if(options.do_fc):
        register_11(cmd_interpret, key = register_11_key)
        register_12(cmd_interpret, key = register_12_key)
        fc_signal_start(cmd_interpret)
    if(options.memo_fc):
        start_L1A(cmd_interpret)
    if(options.memo_fc_start_onetime_ws):
        start_onetime_L1A_WS(cmd_interpret)
    if(options.memo_fc_start_periodic_ws):
        start_periodic_L1A_WS(cmd_interpret)

    if(options.verbose):
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
    
    if(options.i2c):
        print("Inside I2C config")
        DAC_Value_List = []
        for i in range(num_boards):
            DAC_Value_List.append(single_pixel_threshold(board_size[i], options.pixel_address[i], options.pixel_threshold[i]))

    ###################################### Begin Dir making
    if(not options.nodaq):
        userdefinedir = options.output_directory
        userdefinedir_log = "%s_log"%userdefinedir
        ##  Creat a directory named path with date of today
        today = datetime.date.today()
        todaystr = "../ETROC-Data/" + today.isoformat() + "_Array_Test_Results"
        try:
            os.mkdir(todaystr)
            print("Directory %s was created!"%todaystr)
        except FileExistsError:
            print("Directory %s already exists!"%todaystr)
        userdefine_dir = todaystr + "/%s"%userdefinedir
        # userdefine_dir_log = todaystr + "/%s"%userdefinedir_log
        try:
            os.mkdir(userdefine_dir)
            # os.mkdir(userdefine_dir_log)
        except FileExistsError:
            print("User defined directory %s already created!"%(userdefine_dir))
            # print("User defined directory %s already created!"%(userdefine_dir_log))
            if(options.overwrite != True): 
                print("Overwriting is not enabled, exiting code abruptly...")
                sys.exit(1)
    ###################################### End Dir making
    logtime_stampe = time.strftime('%m-%d_%H-%M-%S',time.localtime(time.time()))
    
    if(options.i2c):
        print("Inside I2C setting")
        for B_num in range(num_boards):

            slaveA_addr = slaveA_addr_list[B_num]
            slaveB_addr = slaveB_addr_list[B_num]
            reg_val = []
            if(board_type[B_num]==1):
                reg_val = config_etroc1(B_num, options.charge_injection, DAC_Value_List, options.pixel_address, options.pixel_charge, cmd_interpret)
            elif(board_type[B_num]==2):
                pass
            elif(board_type[B_num]==3):
                pass
            if(options.verbose):
                print("Write data into I2C slave:")
                print(reg_val)
            for i in range(len(reg_val)):
                time.sleep(0.01)
                if i < 32:
                    iic_write(1, slaveA_addr_list[B_num], 0, i, reg_val[i], cmd_interpret)
                else:
                    iic_write(1, slaveB_addr_list[B_num], 0, i-32, reg_val[i], cmd_interpret)
            iic_read_val = []
            for j in range(len(reg_val)):
                time.sleep(0.01)
                if j < 32:
                    iic_read_val += [iic_read(0, slaveA_addr_list[B_num], 1, j, cmd_interpret)]
                else:
                    iic_read_val += [iic_read(0, slaveB_addr_list[B_num], 1, j-32, cmd_interpret)]
            if(options.verbose):
                print("I2C read back data:")
                print(iic_read_val)
            if iic_read_val == reg_val:
                print("I2C SUCCESS! Write data matches read data for Board ", B_num)
            else:
                print("I2C ERROR! Write data does not match read data for Board ", B_num)

    time.sleep(1)                                 # delay one second
    software_clear_fifo(cmd_interpret)            # clear fifo content

    if(not options.nodaq):
        ## start receive_data, write_data, daq_plotting threading
        store_dict = userdefine_dir
        read_queue = Queue()
        translate_queue = Queue() 
        plot_queue = Queue()
        read_stop_event = threading.Event()     # This is how we stop the read thread
        stop_DAQ_event = threading.Event()     # This is how we notify the Write thread that we are done taking data
        receive_data = Receive_data('Receive_data', read_queue, cmd_interpret, options.num_fifo_read, read_stop_event, options.useIPC, stop_DAQ_event, IPC_queue)
        write_data = Write_data('Write_data', read_queue, translate_queue, options.num_file, options.num_line, options.time_limit, store_dict, options.binary_only, options.compressed_binary, options.skip_binary, options.make_plots, read_stop_event, stop_DAQ_event)
        if(options.make_plots or (not options.binary_only)):
            translate_data = Translate_data('Translate_data', translate_queue, plot_queue, cmd_interpret, options.num_file, options.num_line,  options.time_limit, options.timestamp, store_dict, options.binary_only, options.make_plots, board_ID, read_stop_event, options.compressed_translation, stop_DAQ_event)
        if(options.make_plots):
            daq_plotting = DAQ_Plotting('DAQ_Plotting', plot_queue, options.timestamp, store_dict, options.pixel_address, board_type, board_size, options.plot_queue_time, read_stop_event)

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
    parser.add_option("-n", "--num_file", dest="num_file", action="store", type="int", help="Number of files created by DAQ script", default=1)
    parser.add_option("-l", "--num_line", dest="num_line", action="store", type="int", help="Number of lines per file created by DAQ script", default=50000)
    parser.add_option("-r", "--num_fifo_read", dest="num_fifo_read", action="store", type="int", help="Number of lines read per call of fifo readout", default=50000)
    parser.add_option("-t", "--time_limit", dest="time_limit", action="store", type="int", help="Number of seconds to run this code", default=-1)
    parser.add_option("-o", "--output_directory", dest="output_directory", action="store", type="string", help="User defined output directory", default="unnamed_output_directory")
    parser.add_option("-a", "--pixel_address", dest="pixel_address", action="callback", type="string", help="Single pixel address under test for each board", callback=int_list_callback)
    parser.add_option("--pixel_threshold", dest="pixel_threshold", action="callback", type="string", help="Single pixel threshold for pixels under test for each board", callback=int_list_callback)
    parser.add_option("-q", "--pixel_charge", dest="pixel_charge", action="callback", type="string", help="Single pixel charge to be injected (fC) for pixels under test for each board", callback=int_list_callback)
    parser.add_option("-i", "--charge_injection",action="store_true", dest="charge_injection", default=False, help="Flag that enables Qinj")
    parser.add_option("-b", "--binary_only",action="store_true", dest="binary_only", default=False, help="Save only the untranslated FPGA binary data (raw output)")
    parser.add_option("-c", "--compressed_binary",action="store_true", dest="compressed_binary", default=False, help="Save FPGA binary data (raw output) in int format")
    parser.add_option("--skip_binary",action="store_true", dest="skip_binary", default=False, help="DO NOT save (raw) binary outputsto files")
    parser.add_option("--compressed_translation",action="store_true", dest="compressed_translation", default=False, help="Save only FPGA translated data frames with DATA")
    parser.add_option("-s", "--timestamp", type="int",action="store", dest="timestamp", default=0x000C, help="Set timestamp binary, see daq_helpers for more info")
    parser.add_option("--polarity", type="int",action="store", dest="polarity", default=0x000b, help="Set fc polarity, see daq_helpers for more info")
    parser.add_option("-v", "--verbose",action="store_true", dest="verbose", default=False, help="Print status messages to stdout")
    parser.add_option("-w", "--overwrite",action="store_true", dest="overwrite", default=False, help="Overwrite previously saved files")
    parser.add_option("-p", "--make_plots",action="store_true", dest="make_plots", default=False, help="Enable plotting of real time hits")
    parser.add_option("--plot_queue_time", dest="plot_queue_time", action="store", type="float", help="Time (s) used to pop lines off the queue for plotting", default=0.1)
    parser.add_option("--old_data_format",action="store_true", dest="old_data_format", default=False, help="(Dev Only) Set if Data is in old format for ETROC1")
    parser.add_option("--i2c",action="store_true", dest="i2c", default=False, help="Config ETROC boards over I2C")
    parser.add_option("--nodaq",action="store_true", dest="nodaq", default=False, help="Switch off DAQ via the FPGA")
    parser.add_option("--useIPC",action="store_true", dest="useIPC", default=False, help="Use Inter Process Communication to control L1A enable/disable")
    parser.add_option("--firmware",action="store_true", dest="firmware", default=False, help="Configure FPGA firmware settings")
    parser.add_option("--inspect_serial_output",action="store_true", dest="inspect_serial_output", default=False, help="(DEV ONLY) Decode the register binary values for serial port inspection with test pattern mode data")
    parser.add_option("--do_fc",action="store_true", dest="do_fc", default=False, help="(DEV ONLY) Do Fast Command register setting in frequency train mode")
    parser.add_option("--memo_fc",action="store_true", dest="memo_fc", default=False, help="(DEV ONLY) Do Fast Command with Memory")
    parser.add_option("--memo_fc_start_periodic_ws",action="store_true", dest="memo_fc_start_periodic_ws", default=False, help="(WS DEV ONLY) Do Fast Command with Memory, invoke start_periodic_L1A_WS() from daq_helpers.py")
    parser.add_option("--memo_fc_start_onetime_ws", action="store_true", dest="memo_fc_start_onetime_ws" , default=False, help="(WS DEV ONLY) Do Fast Command with Memory, invoke start_onetime_L1A_WS() from daq_helpers.py")
    return parser

if __name__ == "__main__":

    parser = getOptionParser()
    (options, args) = parser.parse_args()

    if(options.pixel_address == None): options.pixel_address = [5, 5, 5, 5]
    if(options.pixel_threshold == None): options.pixel_threshold = [552, 560, 560, 560]
    if(options.pixel_charge == None): options.pixel_charge = [30, 30, 30, 30]
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
        print("Number of files created by DAQ script: ", options.num_file)
        print("Number of lines per file created by DAQ script: ", options.num_line)
        print("Number of lines read per call of fifo readout: ", options.num_fifo_read)
        print("Number of seconds to run this code (>0 means effective): ", options.time_limit)
        print("User defined Output Directory: ", options.output_directory)
        print("(ETROC1) Single pixel address under test for each board: ", options.pixel_address)
        print("(ETROC1) Single pixel threshold for pixels under test for each board: ", options.pixel_threshold)
        print("(ETROC1) Single pixel charge to be injected (fC) for pixels under test for each board: ", options.pixel_charge)
        print("(ETROC1) Flag that enables Qinj: ", options.charge_injection)
        print("Save only the untranslated FPGA binary data (raw output): ", options.binary_only)
        print("Save FPGA binary data (raw output) in int format: ", options.compressed_binary)
        print("Save only FPGA translated data frames with DATA: ", options.compressed_translation)
        print("DO NOT save binary data (raw output): ", options.skip_binary)
        print("Set timestamp binary (Reg 13), see daq_helpers.py -> timestamp() for more info: ", "0x{:04x}".format(options.timestamp))
        print("Set polarity binary (Reg 14), see daq_helpers.py -> Enable_FPGA_Descramblber() for more info: ", "0x{:04x}".format(options.polarity))
        print("Enable plotting of real time hits: ", options.make_plots)
        print("Time (s) used to pop lines off the queue for plotting: ", options.plot_queue_time)
        print("Config (ETROC1) boards over I2C: ", options.i2c)
        print("Switch off DAQ via the FPGA?: ", options.nodaq)
        print("Use IPC to control the L1A: ", options.useIPC)
        print("Configure FPGA firmware settings?: ", options.firmware)
        print("--------End of inputs from the USER--------")
        print("-------------------------------------------")
        print("\n")
        print("-------------------------------------------")
        print("-------Inputs that have been pre-set-------")
        print("ETROC Board Type: ",   board_type)
        print("ETROC Board Size: ",   board_size)
        print("ETROC Board Name: ",   board_name)
        print("ETROC Chip ID: ",      board_ID) 
        print("Set active channel binary (Reg 15), see daq_helpers.py -> active_channels() for more info: ", "0x{:04x}".format(active_channels_key))
        print("-------------------------------------------")
        print("-------------------------------------------")
        print("\n")

    if(options.binary_only==True and options.make_plots==True):
        print("ERROR! Can't make plots without translating data!")
        sys.exit(1)
    
    main_process(None, options)
