#!/usr/bin/env python
# -*- coding: utf-8 -*-
#========================================================================================#
'''
@author: Wei Zhang, Murtaza Safdari, Jongho Lee
@date: 2023-03-24
This script is used to define the I2C addresses of all the relevant boards
Also used to define any relevant details for each corresponding board
'''
#--------------------------------------------------------------------------#

'''
A address is set using jumper pins on the ETROC1 board
There are 7 bits with 2 addressable, default value is 00000_A1_A2
Any inserted jumpers will flip the bit. Avoid address 00

'''
'''
B address is set using jumper pins on the ETROC1 board
There are 7 bits with 2 addressable, default value is 11111_B1_B2
Any inserted jumpers will flip the bit

'''

## Register 15, needs firmware option
active_channels_key = 0x0011

# register_11_key and register_12_key are useful for do_fc only

## Register 11, needs do_fc option
## 4-digit 16 bit hex, Duration
register_11_key = 0x0021

## Register 12, needs do_fc option
## 4-digit 16 bit hex, 0xWXYZ
## WX (8 bit) -  Error Mask
## Y - trigSize[1:0],Period,testTrig
## Z - Input command
register_12_key = 0x0006

## Register 14, needs firmware option
# 0xWXYZ
# Z is a bit 4 bit binary wxyz
# z is the enable descrambler
# y is disable GTX
# x is polarity
# w is the memo FC (active high)
register_14_key = 0x000b

# Use this to control how many boards are actually attempted for connection
# ETROC version number
board_type       = [2, 1, 1, 1]

board_size       = [256, 16, 16, 16]
board_name       = ["F28", "F29", "F30", "F47"]
board_ID         = ["10111111100001111","00000000000000000","00000000000000000", "00000000000000000"]