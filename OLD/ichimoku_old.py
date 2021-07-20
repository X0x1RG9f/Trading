#!/usr/bin/python3
# encoding: utf-8

############################################
#                                          #
# /!\ PYTHON 3 ONLY                        #
#                                          #
# ICHIMOKU CLOUDS Ludovic COURGNAUD        #
# 04-2020                                  #
#                                          #
# SENDS EMAILS FOR IMPORTANT EVENTS :      #
#    - Price above cloud                   #
#    - Price under cloud                   #
#    - Kijunsen Cross Tenkansen            #
#    - Kijunsen Cross Price                #
#                                          #
############################################

###################################################### IMPORTS #####################################################################
import requests
import pandas as pd
import os
import string
import sys
import urllib
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import argparse
from datetime import datetime
from datetime import timezone
import numpy as np
import json
import time
import itertools
#import threading

start_time = time.time()

###################################################### CONFIG ######################################################################
MARKETS			= ""

CONFIG			= ""
INTERVAL		= ""
DEBUG			= False
OUTPUT			= ""
RECHECK			= False
CLOUD_ONLY		= False

SMTP_SERVER		= ""
SMTP_PORT		= ""
SMTP_AUTH		= ""
RECIPIENTS		= ""

scores			= {}
closes			= {}

##################################################### FUNCTIONS ####################################################################

#
# Print with debug condition
#
def myprint(str):
	if DEBUG:
		print(str)

#
# Parse args from command line
#
def parse_args():
	global MARKETS

	global CONFIG
	global INTERVAL
	global DEBUG
	global OUTPUT
	global RM_VALUES
	global RECHECK
	global CLOUD_ONLY

	global SMTP_SERVER
	global SMTP_AUTH
	global SMTP_PORT
	global RECIPIENTS


	example_text = '''Examples:
 		python3 ichimoku.py -m MSFT -i 15m --txt
 		python3 ichimoku.py -f ./markets.txt --html --debug
 		python3 ichimoku.py -m 'MSFT, CS.PA' -r 'myemail@test.com' -a 'myemail@gmail.com:mypassword' '''

	parser = argparse.ArgumentParser(prog='./ichimoku.py', epilog=example_text,  formatter_class=argparse.RawDescriptionHelpFormatter)

	# Mandatory args
	parser.add_argument("-f",  "--markets-file", type=str, help="Input file containing markets to follow (one per line).")
	parser.add_argument("-m",  "--markets", type=str, help="Input string containing markets to follow (comma separated).")

	# Optional args
	parser.add_argument("-i",  "--interval", type=str, help="Interval of stock data to process. Default '1h'.", choices=['30m', '1h', '4h', '1d'], default="1h")
	parser.add_argument("-c",  "--config", type=str, help="Ichimoku settings. Default '9,26,52'.",  choices=['9,26,52', '7,22,44'], default='9,26,52')
	parser.add_argument("-d",  "--debug", help="Activate debug mode. Default 'False'.",  action='store_true', default=False)
	parser.add_argument("-o",  "--output", help="Results output mode.",  choices=['TXT', 'EMAIL', 'HTML'], default="TXT")
	parser.add_argument("-r",  "--remove-values", type=int, help="Number of values to be removed. Use for past analasys only. Default 0.", default=0)
	parser.add_argument("-n",  "--check-null", help="Perform second stock request if many null values. Default 'False'.",  action='store_true', default=False)
	parser.add_argument("-x",  "--cloud-only", help="Process only scores for Cloud Signals (Up / Above). Default 'False'.",  action='store_true', default=False)

	# Optional SMTP args
	parser.add_argument("-s",  "--smtp-server", type=str, help="SMTP Server from which notification will be sent. Default 'smtp.gmail.com'", default='smtp.gmail.com')
	parser.add_argument("-p",  "--smtp-port", type=int, help="SMTP Server port from which notification will be sent. Default '587'.", default=587)
	parser.add_argument("-a",  "--smtp-auth", type=str, help="SMTP Server credentials (login:password).")
	parser.add_argument("-t",  "--to", type=str, help="Email recipient(s) for notification ('a@a.com, b@b.com').")

	args = parser.parse_args()

	INTERVAL	= args.interval

	CONFIG		= args.config.replace(" ", "").split(',')
	mp		= map(int, CONFIG)
	CONFIG 		= list(mp)

	DEBUG		= args.debug
	OUTPUT		= args.output
	RM_VALUES	= args.remove_values
	RECHECK		= args.check_null
	CLOUD_ONLY	= args.cloud_only

	RECIPIENTS	= args.to
	SMTP_SERVER	= args.smtp_server
	SMTP_PORT	= args.smtp_port

	if (args.smtp_auth != None) :
		SMTP_AUTH	= args.smtp_auth.split(":")

	if (args.markets_file == None) and (args.markets == None):
		print("ERROR: At least one market or file should be provided as argument. ")
		sys.exit(0)

	if (args.markets_file != None):
		if not os.path.isfile(args.markets_file):
			print("ERROR: File '" + args.markets_file + "' not found.")
			sys.exit(0)
		else:
			with open(args.markets_file) as f:
				MARKETS = f.read().splitlines()
	else:
		MARKETS = args.markets.replace(' ', '').split(",")

	if (OUTPUT == "EMAIL") and ((RECIPIENTS == None) or (SMTP_SERVER == None) or (SMTP_AUTH == None)) :
		myprint("WARNING: MAIL output specified but no SMTP information provided and / or recipients. Defaulting to TXT output")
		OUTPUT = "TXT"

	myprint("INFO: OUTPUTING AS " + OUTPUT + "!")
	myprint("")



#
# Retrieve data from Yahoo Finance & return DataFrame
#
def get_quote_data(symbol, ntvl, iteration):
	rng = "2y"

	if (ntvl == "30m"):
		rng = "10d"
	if (ntvl == "1h"):
		rng = "4mo"
	if (ntvl == "4h"):
		ntvl = "1h"
		rng  = "4mo"

	res = requests.get('https://query1.finance.yahoo.com/v8/finance/chart/' + symbol + '?range=' + rng + '&interval=' + ntvl)
	data = res.json()

	myprint('GET QUOTE DATA : https://query1.finance.yahoo.com/v8/finance/chart/' + symbol + '?range=' + rng + '&interval=' + ntvl)

	if (data['chart']['result'] == None):
		myprint("ERROR: Market unknown! Passing...")
		return None

	body = data['chart']['result'][0]
	df = pd.DataFrame(body['indicators']['quote'][0])

	df['timestamp'] 	= body['timestamp']

	df['timezone']		= body['meta']['exchangeTimezoneName']
	df['exchange']		= body['meta']['exchangeName']

	df['KIJUNSEN'] 		= ""
	df['TENKANSEN'] 	= ""
	df['SSA']		= ""
	df['SSB'] 		= ""

	df['CLOUD_COLOR']	= ""
	df['CLOUD_TREND']	= ""

	df['SIGNAL_X_PRC_CLD']	= 1
	df['SIGNAL_X_CHI_KIJ']	= 1
	df['SIGNAL_X_KIJ_TEN']	= 1
	df['SIGNAL_X_KIJ_PRC']	= 1
	df['SIGNAL_X_CHI_PRC']	= 1
	df['SIGNAL_X_CHI_SSB']	= 1

	df['SIGNAL_CHI_PRC']	= 1
	df['SIGNAL_KIJ_PRC']	= 1

	#df['SIGNAL_CLD_SRF']	= 1

	df['SIGNAL_SS26']	= 1
	df['SIGNAL_ICHI_SUP']	= 1

	df['SIGNAL_CLOSE']	= 0
	df['SIGNAL_AVG']	= 0.0

	pd.options.mode.chained_assignment = None
	pd.set_option('display.max_rows', None)

	# Checking for Null / Error values, excluding weekends
	for i in range (df.index[0], df.index[-1] + 1):
		if np.isnan(df['open'][i]) and (datetime.fromtimestamp(df['timestamp'][i]).weekday() < 6):
			if RECHECK:
				if (iteration <= 1):
					time.sleep(1)
					myprint("WARNING: Market has too many Null values for processing. Trying again...")
					df = get_quote_data(symbol, ntvl, iteration + 1)
					break
				else:
					myprint("WARNING: Market has too many Null values for processing. Maybe errors...")
					break
			else:
				myprint("WARNING: Market has too many Null values for processing. Maybe errors...")
				break


	if (iteration <=1 ):
		if (df['volume'][df.index[-1]] == 0):
			df = df[:-1]

		for i in range (0,RM_VALUES):
			df = df[:-1]

		df = df[-500:]
		df.dropna(inplace=True)
		df.reset_index(drop=True, inplace=True)

		if (len(df) <= int(CONFIG[2] * 1.5)):
			myprint("ERROR: Market has too few history for Ichimoku! Passing...")
			return None

	return df



#
# Get the quote data for larger interval (for score processing)
#
def get_quote_data_sup(symbol):
	if (INTERVAL == "30m") :
		return get_quote_data(symbol, "1h", 1)
	if (INTERVAL == "1h") :
		return get_quote_data(symbol, "1d", 1)
	if (INTERVAL == "4h") :
		return get_quote_data(symbol, "1d", 1)
	if (INTERVAL == "1d") :
		return get_quote_data(symbol, "1wk", 1)

	return None


#
# Transform a 1h dataframe into a 4h (Yahoo does not provide 4h's one)
#
def transform_four_hours(df):
	myprint("ENTERING H4 PROCESSING...")

	df_size = 130

	# Sequences for candle transformation (depends on markets)
	eu_sequence = [4,4,1]
	us_sequence = [3,4]
	#cr_sequence = [4,4,4,4,4,4]
	#mp_sequence = [4,4,4,4,4,4]

	sequence = ""

	if (df['timezone'][0].split('/')[0] == "Europe"):
		sequence = eu_sequence

	if (df['timezone'][0].split('/')[0] == "America") and (df['exchange'][0] != "CMX"):
		sequence = us_sequence

	if (sequence == ""):
		myprint("ERROR: Stock market not supported yet for H4 Ichimoku, PASSING.")
		return None

	dt = datetime.today()
	dt = datetime(dt.year, dt.month, dt.day)
	timestamp = dt.replace(tzinfo=timezone.utc).timestamp()

	today_candle = 0
	for i in range (len(df) - 15, len(df)):
		if (df['timestamp'][i] >= timestamp):
			today_candle += 1

	start_sequence	= 0
	start_candle 	= df.index[-1]

	# Process : How many candle do we have a remove at the end for correct H4 ?
	start_sequence = 0
	for i in range (0, len(sequence)):
		if today_candle >= np.sum(sequence[i:len(sequence)]):
			start_sequence = i
			start_candle = start_candle - (today_candle - np.sum(sequence[i:len(sequence)]))
			break

	avg_candle = np.sum(sequence) / len(sequence)

	# Insure we have sufficient values to trasnform H1 data to H4 data (80 rows min for ichimoku)
	if ((len(df) / avg_candle) <= df_size):
		myprint("ERROR: Market has too few history for H4 ichimoku! Passing...")
		return None

	df4 = pd.DataFrame(columns=list(df.columns), index=[x for x in range(0, df_size)])

	df4['timezone']		= df['timezone'][0]
	df4['exchange']		= df['exchange'][0]

	df4['KIJUNSEN'] 	= ""
	df4['TENKANSEN'] 	= ""
	df4['SSA']		= ""
	df4['SSB'] 		= ""

	df4['CLOUD_COLOR']	= ""
	df4['CLOUD_TREND']	= ""

	df4['SIGNAL_X_PRC_CLD']	= 1
	df4['SIGNAL_X_CHI_KIJ']	= 1
	df4['SIGNAL_X_KIJ_TEN']	= 1
	df4['SIGNAL_X_KIJ_PRC']	= 1
	df4['SIGNAL_X_CHI_PRC']	= 1
	df4['SIGNAL_X_CHI_SSB']	= 1

	df4['SIGNAL_CHI_PRC']	= 1
	df4['SIGNAL_KIJ_PRC']	= 1

	#df4['SIGNAL_CLD_SRF']	= 1

	df4['SIGNAL_SS26']	= 1
	df4['SIGNAL_ICHI_SUP']	= 1

	df4['SIGNAL_CLOSE']	= 0
	df4['SIGNAL_AVG']	= 0.0


	cpt1 = start_candle
	cpt2 = 1
	while (df_size-cpt2 >= 0):
		for i in range (0, len(sequence)):
			if (i >= start_sequence):
				s = sequence[i]
				if sequence[i] > 1 :
					df4['low'][df_size-cpt2]         =  np.min(df['low'][cpt1-s+1:cpt1+1])
					df4['high'][df_size-cpt2]        =  np.max(df['high'][cpt1-s+1:cpt1+1])
					df4['volume'][df_size-cpt2]      =  np.sum(df['volume'][cpt1-s+1:cpt1+1])
					df4['open'][df_size-cpt2]        =  df['open'][cpt1-s+1]
					df4['close'][df_size-cpt2]       =  df['close'][cpt1]
					df4['timestamp'][df_size-cpt2]   =  df['timestamp'][cpt1-s+1]
				else:
					df4['low'][df_size-cpt2]         =  df['low'][cpt1]
					df4['high'][df_size-cpt2]        =  df['high'][cpt1]
					df4['volume'][df_size-cpt2]      =  df['volume'][cpt1]
					df4['open'][df_size-cpt2]        =  df['open'][cpt1]
					df4['close'][df_size-cpt2]       =  df['close'][cpt1]
					df4['timestamp'][df_size-cpt2]   =  df['timestamp'][cpt1]


				cpt1 -= s
				cpt2 += 1
		start_sequence = 0

	for i in range (0,RM_VALUES):
		df4 = df4[:-1]

	return df4

#
# Sends Email to recipients
#
def send_email(msg):
	myprint("SENDING EMAIL...")

	sender = "Trading Server"

	message = MIMEMultipart("alternative")
	message["Subject"] = "Trading Opportunities (" +  datetime.now().strftime('%d/%m %H:%M')  + ") !"
	message["From"] = "Trading Server"
	message["To"] = RECIPIENTS

	message.attach(MIMEText(msg,"html"))

	server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
	server.ehlo()
	server.starttls()
	server.ehlo()
	server.login(SMTP_AUTH[0], SMTP_AUTH[1])
	server.sendmail( sender, RECIPIENTS, message.as_string() )


#
# Process Ichimoku Cloud data from received Yahoo DataFrame
#
def processIchimoku(df, full):
	# NOT IMPORTANT PROCESSING ALL DATA, ONLY FEW WINDOWS NECESSARY
	for i in range (df.index[-1] - 8, df.index[-1] + 1 ):
		# KIJUN SEN & TENKAN SEN
		df['KIJUNSEN'][i]		= (np.max(df['high'][i-(CONFIG[1]-1):i+1]) + np.min(df['low'][i-(CONFIG[1]-1):i+1]) ) / 2
		df['TENKANSEN'][i]		= (np.max(df['high'][i-(CONFIG[0]-1):i+1]) + np.min(df['low'][i-(CONFIG[0]-1):i+1]) ) / 2

		df['KIJUNSEN'][i-CONFIG[1]]	= (np.max(df['high'][(i-CONFIG[1])-(CONFIG[1]-1):i-CONFIG[1]+1]) + np.min(df['low'][(i-CONFIG[1])-(CONFIG[1]-1):i-CONFIG[1]+1]) ) / 2
		df['TENKANSEN'][i-CONFIG[1]]	= (np.max(df['high'][(i-CONFIG[1])-(CONFIG[0]-1):i-CONFIG[1]+1]) + np.min(df['low'][(i-CONFIG[1])-(CONFIG[0]-1):i-CONFIG[1]+1]) ) / 2

		df['KIJUNSEN'][i-CONFIG[1]-CONFIG[1]]	= (np.max(df['high'][(i-CONFIG[1]-CONFIG[1])-(CONFIG[1]-1):i-CONFIG[1]-CONFIG[1]+1]) + np.min(df['low'][(i-CONFIG[1]-CONFIG[1])-(CONFIG[1]-1):i-CONFIG[1]-CONFIG[1]+1]) ) / 2
		df['TENKANSEN'][i-CONFIG[1]-CONFIG[1]]	= (np.max(df['high'][(i-CONFIG[1]-CONFIG[1])-(CONFIG[0]-1):i-CONFIG[1]-CONFIG[1]+1]) + np.min(df['low'][(i-CONFIG[1]-CONFIG[1])-(CONFIG[0]-1):i-CONFIG[1]-CONFIG[1]+1]) ) / 2

		# SSA & SSB
		df['SSA'][i+CONFIG[1]] 	= (df['KIJUNSEN'][i] + df['TENKANSEN'][i]) / 2
		df['SSB'][i+CONFIG[1]] 	= (np.max(df['high'][i-(CONFIG[2]-1):i+1])  + np.min(df['low'][i-(CONFIG[2]-1):i+1])  ) / 2

		df['SSA'][i-CONFIG[1]] 	= (df['KIJUNSEN'][i-CONFIG[1]-CONFIG[1]] + df['TENKANSEN'][i-CONFIG[1]-CONFIG[1]]) / 2
		df['SSB'][i-CONFIG[1]] 	= (np.max(df['high'][(i-CONFIG[1]-CONFIG[1])-(CONFIG[2]-1):(i-CONFIG[1]-CONFIG[1]+1)])  + np.min(df['low'][(i-CONFIG[1]-CONFIG[1])-(CONFIG[2]-1):(i-CONFIG[1]-CONFIG[1]+1)])  ) / 2

		df['SSA'][i] 		= (df['KIJUNSEN'][i-CONFIG[1]] + df['TENKANSEN'][i-CONFIG[1]]) / 2
		df['SSB'][i] 		= (np.max(df['high'][(i-CONFIG[1])-(CONFIG[2]-1):(i-CONFIG[1])+1])  + np.min(df['low'][(i-CONFIG[1])-(CONFIG[2]-1):(i-CONFIG[1])+1])  ) / 2
		print( df['SSA'][i])
		# Cloud is green or red ?
		if ( df['SSA'][i+CONFIG[1]] >= df['SSB'][i+CONFIG[1]] ):	df['CLOUD_COLOR'][i+CONFIG[1]] = "GREEN"
		if ( df['SSA'][i+CONFIG[1]] <  df['SSB'][i+CONFIG[1]] ):	df['CLOUD_COLOR'][i+CONFIG[1]] = "RED"

	df['SIGNAL_AVG'][df.index[-1]] = np.average(df['close'][df.index[-1]-CONFIG[1]:df.index[-1]])
	df['SIGNAL_AVG'][df.index[-1]] = 100 - (df['SIGNAL_AVG'][df.index[-1]] * 100) / df['close'][df.index[-1]]

	# PROCESS SCORES
	#
	# 1. PRICE AND CLOUD (25 POINTS)
	#  1.1 SCORE x2 IF CANDLE IS RIGHT COLOR (50 POINTS)
	# 2. CHIKOU CROSSING KIJUN (15 POINTS)
	# 3. KIJUN CROSSING TENKAN (6 POINTS)
	# 4. KIJUN CROSSING PRICE (5 POINTS)
	# 5. PRICE POSITION WITH KIJUN (3 POINTS)
	# 6. CHIKOU CROSSING SSB (3 POINTS)
	# 7. CHIKOU CROSSING PRICE (30 POINTS)
	# 8. CHIKOU POSITION WITH PRICE (20 POINTS)
	# 9. CLOUD+26 COLOR (2 POINTS)
	#  9.1 SCORE +1 IF SSA MOVING IN RIGHT DIRECTION (3 POINTS)
	#  9.2 SCORE +1 IF CLOUD GROWING IN RIGHT DIRECTION (4 POINTS)
	# 10. CLOUD SURFACE 2 TIMES PRICE SURFACE (2 POINTS)
	#  10.1 SCORE x2 IF MORE THAN 4 TIMES PRICE SURFACE
	#
	for i in range (df.index[-1] - 7, df.index[-1] + 1):
		myprint(i)
		myprint(df['SSA'][i])
		# Are we in a bearish trend (SELL)
		if ( (df['close'][i] < df['SSA'][i]) and (df['close'][i] < df['SSB'][i]) ):
			if ( (df['open'][i] < df['SSA'][i]) or (df['open'][i] < df['SSB'][i]) ):
				df['CLOUD_TREND'][i] = 'SELL'

		# Are we in a bullish trend (BUY)
		if ( (df['close'][i] > df['SSA'][i]) and (df['close'][i] > df['SSB'][i]) ):
			if ( (df['open'][i] > df['SSA'][i]) or (df['open'][i] > df['SSB'][i]) ):
				df['CLOUD_TREND'][i] = 'BUY'

		# Do we have one or more close signals ?
		if ((df['KIJUNSEN'][i-1] <= df['close'][i-1] and df['KIJUNSEN'][i] >= df['close'][i]) ):	df['SIGNAL_CLOSE'][i] = 1
		if ((df['KIJUNSEN'][i-1] >= df['close'][i-1] and df['KIJUNSEN'][i] <= df['close'][i]) ):	df['SIGNAL_CLOSE'][i] = -1

		if ( (df['CLOUD_TREND'][i] != 'BUY' ) and (df['KIJUNSEN'][i-1] >= df['TENKANSEN'][i-1]) and (df['KIJUNSEN'][i] < df['TENKANSEN'][i]) ): df['SIGNAL_CLOSE'][i] = -1
		if ( (df['CLOUD_TREND'][i] != 'SELL') and (df['KIJUNSEN'][i-1] <= df['TENKANSEN'][i-1]) and (df['KIJUNSEN'][i] > df['TENKANSEN'][i]) ): df['SIGNAL_CLOSE'][i] = 1

	if not full:
		return df

	for i in range (df.index[-1] - 7, df.index[-1] + 1):
		# 1. Do we have a cloud buying signal (price going above cloud) ?
		if ( (df['CLOUD_TREND'][i] == 'BUY' ) and (df['CLOUD_TREND'][i-1] != 'BUY' ) ):
			df['SIGNAL_X_PRC_CLD'][i] = 25

			if (df['open'][i] < df['close'][i]) :
				df['SIGNAL_X_PRC_CLD'][i] = df['SIGNAL_X_PRC_CLD'][i] * 2

		# 1. Do we have a cloud selling signal (price going under cloud) ?
		if ( (df['CLOUD_TREND'][i] == 'SELL') and (df['CLOUD_TREND'][i-1] != 'SELL') ):
			df['SIGNAL_X_PRC_CLD'][i] = -25

			if (df['open'][i] > df['close'][i]) :
				df['SIGNAL_X_PRC_CLD'][i] = df['SIGNAL_X_PRC_CLD'][i] * 2

		# 2. Is Chikou crossing Kijun ?
		if ((df['close'][i-1] <= df['KIJUNSEN'][i-(CONFIG[1]+1)]) and (df['close'][i] >= df['KIJUNSEN'][i-CONFIG[1]]) ):  df['SIGNAL_X_CHI_KIJ'][i] = 15
		if ((df['close'][i-1] >= df['KIJUNSEN'][i-(CONFIG[1]+1)]) and (df['close'][i] <= df['KIJUNSEN'][i-CONFIG[1]]) ):  df['SIGNAL_X_CHI_KIJ'][i] = -15

		# 3. Is Kijun crossing Tenkan ?
		if (df['KIJUNSEN'][i-1] >= df['TENKANSEN'][i-1]) and (df['KIJUNSEN'][i] <  df['TENKANSEN'][i]): df['SIGNAL_X_KIJ_TEN'][i] = 6
		if (df['KIJUNSEN'][i-1] <= df['TENKANSEN'][i-1]) and (df['KIJUNSEN'][i] >  df['TENKANSEN'][i]): df['SIGNAL_X_KIJ_TEN'][i] = -6


		# 4. Is Kijun crossing Price ?
		if (df['KIJUNSEN'][i-1] >= df['close'][i-1] and df['KIJUNSEN'][i] <= df['close'][i]):	df['SIGNAL_X_KIJ_PRC'][i] = 5
		if (df['KIJUNSEN'][i-1] <= df['close'][i-1] and df['KIJUNSEN'][i] >= df['close'][i]):	df['SIGNAL_X_KIJ_PRC'][i] = -5

		# 5. Is Price under of above Kijun ?
		if (df['KIJUNSEN'][i] < df['close'][i]):	df['SIGNAL_KIJ_PRC'][i] = 3
		if (df['KIJUNSEN'][i] > df['close'][i]):	df['SIGNAL_KIJ_PRC'][i] = -3

		# 6. Is Chikou crossing SSB ?
		if (df['SSB'][i-(CONFIG[1]+1)] >= df['close'][i-1]) and (df['SSB'][i-CONFIG[1]] < df['close'][i]) : df['SIGNAL_X_CHI_SSB'][i] = 3
		if (df['SSB'][i-(CONFIG[1]+1)] <= df['close'][i-1]) and (df['SSB'][i-CONFIG[1]] > df['close'][i]) : df['SIGNAL_X_CHI_SSB'][i] = -3

		# 7. Is Chikou crossing Price ?
		if (df['close'][i-(CONFIG[1]+1)] >= df['close'][i-1]) and (df['close'][i-CONFIG[1]] < df['close'][i]) : df['SIGNAL_X_CHI_PRC'][i] = 30
		if (df['close'][i-(CONFIG[1]+1)] <= df['close'][i-1]) and (df['close'][i-CONFIG[1]] > df['close'][i]) : df['SIGNAL_X_CHI_PRC'][i] = -30

		# 8. Is Chikou under or above Price ?
		if (df['close'][i] >= df['close'][i-CONFIG[1]]):	df['SIGNAL_CHI_PRC'][i] = 20
		if (df['close'][i] < df['close'][i-CONFIG[1]]):		df['SIGNAL_CHI_PRC'][i] = -20

		# 9. Is Cloud+26 Green ? Is SSA+26 going UP ? Is Cloud growing ?
		if (df['CLOUD_COLOR'][i+CONFIG[1]] == "GREEN"):
			df['SIGNAL_SS26'][i] = 2
			if (df['SSA'][i+(CONFIG[1]-1)] <= df['SSA'][i+CONFIG[1]]) :
				df['SIGNAL_SS26'][i] += 1
				if ( (df['SSA'][i+(CONFIG[1]-1)] - df['SSB'][i+(CONFIG[1]-1)]) < (df['SSA'][i+CONFIG[1]] - df['SSB'][i+CONFIG[1]]) ):
					df['SIGNAL_SS26'][i] += 1

		# 9. Is Cloud+26 Green ? Is SSA+26 going UP ? Is Cloud growing ?
		if (df['CLOUD_COLOR'][i+CONFIG[1]] == "RED"):
			df['SIGNAL_SS26'][i] = -2
			if (df['SSA'][i+(CONFIG[1]-1)] >= df['SSA'][i+CONFIG[1]]) :
				df['SIGNAL_SS26'][i] -= 1
				if ( (df['SSA'][i+(CONFIG[1]-1)] - df['SSB'][i+(CONFIG[1]-1)]) > (df['SSA'][i+CONFIG[1]] - df['SSB'][i+CONFIG[1]]) ):
					df['SIGNAL_SS26'][i] -= 1

		# 10. Is the Cloud surface important compared with Price (Open / Close)
		#prc_variation = abs(df['open'][i] - df['close'][i])
		#cld_variation = abs(df['SSA'][i] - df['SSB'][i])
		# Difficulty to handle positive or negative score...

	return df

#
# Process score for DataFrame (using DataFrame -1 also)
#
def process_score(df, dfsup):
	myprint("PROCESSING SCORE...")

	# Adding a little score for bigger interval (e.g. for H1, checking H4) : looking for cloud trend, chikou trend, etc.
	if (dfsup is not None):
		if (dfsup['CLOUD_TREND'][dfsup.index[-1]] == "BUY" ):
			df['SIGNAL_ICHI_SUP'] = 2
			if (dfsup['close'][dfsup.index[-1] - CONFIG[1]] < dfsup['close'][dfsup.index[-1]]):
				df['SIGNAL_ICHI_SUP'] += 1
			if (dfsup['SSB'][dfsup.index[-1] - CONFIG[1]] < dfsup['close'][dfsup.index[-1]]):
				df['SIGNAL_ICHI_SUP'] += 1
		if (dfsup['CLOUD_TREND'][dfsup.index[-1]] == "SELL" ):
			df['SIGNAL_ICHI_SUP'] = -2
			if (dfsup['close'][dfsup.index[-1] - CONFIG[1]] > dfsup['close'][dfsup.index[-1]]):
				df['SIGNAL_ICHI_SUP'] -= 1
			if (dfsup['SSB'][dfsup.index[-1] - CONFIG[1]] > dfsup['close'][dfsup.index[-1]]):
				df['SIGNAL_ICHI_SUP'] -= 1

	# Processing scores for each symbol
	nodes 		= {}
	histo_scores	= [0,0,0]
	cloud_signal	= False

	# Processing the 3 last scores : we don't want to receive a score if the score -2 was higher (because we already had the alert)
	for index,histo_score in enumerate(histo_scores):
		for i in range (df.index[-1] - 2 + index, len(df) - 2 + index):
			if (df['CLOUD_TREND'][i] == "SELL" or df['CLOUD_TREND'][i] == "BUY"):
				nodes['A'] = df['SIGNAL_X_PRC_CLD'][i]
				nodes['B'] = df['SIGNAL_X_KIJ_TEN'][i]
				nodes['C'] = df['SIGNAL_X_KIJ_PRC'][i]
				nodes['D'] = df['SIGNAL_X_CHI_PRC'][i]
				nodes['E'] = df['SIGNAL_X_CHI_SSB'][i]
				nodes['F'] = df['SIGNAL_SS26'][i]
				nodes['G'] = df['SIGNAL_ICHI_SUP'][i]
				nodes['H'] = df['SIGNAL_CHI_PRC'][i]
				nodes['I'] = df['SIGNAL_KIJ_PRC'][i]
				nodes['J'] = df['SIGNAL_X_CHI_KIJ'][i]

				if (df['SIGNAL_X_PRC_CLD'][i] == 1) and (df['SIGNAL_X_KIJ_TEN'][i] == 1) and (df['SIGNAL_X_KIJ_PRC'][i] == 1) and (df['SIGNAL_X_CHI_PRC'][i] == 1) and (df['SIGNAL_X_CHI_SSB'][i] == 1) and (df['SIGNAL_X_CHI_KIJ'][i] == 1):
					histo_scores[index] += 0
					continue

				# Processing score with all positives and negatives nodes. 2 or more positive (or negative) will have an effect on the score
				totalbuy  = 1
				totalsell = 1
				cpt_buysignal  = 0
				cpt_sellsignal = 0

				if (nodes['A'] != 1):
					cloud_signal = True

				for node in nodes:
					if (nodes[node] > 1):
						totalbuy       = totalbuy * nodes[node]
						cpt_buysignal  += 1
					if (nodes[node] < -1):
						totalsell       = totalsell * (0 - nodes[node])
						cpt_sellsignal += 1

				if (totalbuy > totalsell and cpt_buysignal >= 1):
					histo_scores[index] += (totalbuy * cpt_buysignal)
					if (totalsell != 1) :
						histo_scores[index] -= totalsell

				if (totalsell > totalbuy and cpt_sellsignal > 1):
					histo_scores[index] -= (totalsell * cpt_sellsignal)
					if (totalbuy != 1) :
						histo_scores[index] += totalbuy


	myprint("FINAL SCORE : " + str(histo_scores[2]) + " points")
	myprint("PREVIOUS SCORES : " + str(histo_scores[0]) + ", " + str(histo_scores[1]) + " points")

	if (histo_scores[2] > 0 and df['CLOUD_TREND'][df.index[-1]] != "BUY") :
		myprint("LONG signal but price under Cloud. No Email will be sent...")
		return 0

	if (histo_scores[2] < 0 and df['CLOUD_TREND'][df.index[-1]] != "SELL") :
		myprint("SHORT signal but price above Cloud. No Email will be sent...")
		return 0

	if (histo_scores[2] > 0 and df['SIGNAL_KIJ_PRC'][df.index[-1]] < 0) :
		myprint("LONG signal but price under KIJUNSEN. No Email will be sent...")
		return 0

	if (histo_scores[2] < 0 and df['SIGNAL_KIJ_PRC'][df.index[-1]] > 0):
		myprint("SHORT signal but price above KIJUNSEN. No Email will be sent...")
		return 0

	if (not cloud_signal) and (CLOUD_ONLY) :
		myprint("No Cloud Signal found with option 'CLOUD-ONLY' activated. No Email will be sent...")
		return 0

	if ( (histo_scores[2] > 0 and (histo_scores[2] <= histo_scores[1] or histo_scores[2] <= histo_scores[0])) or (histo_scores[2] < 0 and (histo_scores[2] >= histo_scores[1] or histo_scores[2] >= histo_scores[0])) ):
		myprint("Score is lower than 2 previous scorse. No email will be sent...")
		return 0

	myprint("Score added to scores pool!")
	return histo_scores[2]


#
# Write Email with correct values taken from DataFrame
#
def write_email(scores, closes):
	myprint("BUILDING MESSAGE...")

	if (OUTPUT == "TXT"):
		MSG		= "SIGNALS " + INTERVAL + "\n\n"
		BUY_MSG		= "BUY :\n"
		SELL_MSG 	= "SELL :\n"
		CLSEB_MSG 	= "CLOSE BUY :\n"
		CLSES_MSG 	= "CLOSE SELL :\n"
	else :
		MSG		= "<html><body>SIGNALS " + INTERVAL + "<br/><br/>"
		BUY_MSG		= "<span style='color:green'><b>BUY :</b></span><br/><ul>"
		SELL_MSG 	= "<span style='color:red'><b>SELL :</b></span><br/><ul>"
		CLSEB_MSG 	= "<span style='color:orange'><b>CLOSE BUY :</b></span><br/><ul>"
		CLSES_MSG 	= "<span style='color:orange'><b>CLOSE SELL :</b></span><br/><ul>"

	buy	= False
	sell	= False
	close_b	= False
	close_s	= False

	table = sorted(scores.items(), key=lambda x: x[1], reverse=True)
	for score in table:
		if (score[1] > 0):
			buy = True
			if (OUTPUT == "TXT"):
				BUY_MSG = BUY_MSG + "\t- " + score[0] + " : " + str(int(score[1])) + " points\n"
			else:
				BUY_MSG = BUY_MSG + "<li><span style='color:green'><b>" + score[0] + " : " + str(int(score[1])) + " points</b></span></li>"


	table = sorted(scores.items(), key=lambda x: x[1])
	for score in table:
		if (score[1] < 0):
			sell = True
			if (OUTPUT == "TXT"):
				SELL_MSG = SELL_MSG + "\t- " + score[0] + " : " + str(int(score[1])) + " points\n"
			else:
				SELL_MSG = SELL_MSG + "<li><span style='color:red'><b>" + score[0] + " : " + str(int(score[1])) + " points</b></span></li>"

	closes = sorted(closes.items(), key=lambda x: x[0])
	for cls in closes:
		if (OUTPUT == "TXT"):
			tmpmess = "\t- " + cls[0] + " : " + str(int(cls[1])) + " points\n"
		else:
			tmpmess ="<li><span style='color:orange'><b>" + cls[0] + " : " + str(int(cls[1])) + " points</b></span></li>"

		if (cls[1] == 1):
			if os.path.isfile("./MYTRADES/" + cls[0] + "_" + INTERVAL + "_long"):
				close_b = True
				CLSEB_MSG = CLSEB_MSG + tmpmess
		else:
			if os.path.isfile("./MYTRADES/" + cls[0] + "_" + INTERVAL + "_short"):
				close_s = True
				CLSES_MSG = CLSES_MSG + tmpmess

	if (OUTPUT != "TXT"):
		if (buy):
			MSG = MSG + BUY_MSG + "</ul><br/>"
		if (sell):
			MSG = MSG + SELL_MSG + "</ul><br/>"
		if (close_b):
			MSG = MSG + CLSEB_MSG + "</ul><br/>"
		if (close_s):
			MSG = MSG + CLSES_MSG + "</ul><br/>"
	else:
		if (buy):
			MSG = MSG + BUY_MSG + "\n"
		if (sell):
			MSG = MSG + SELL_MSG + "\n"
		if (close_b):
			MSG = MSG + CLSEB_MSG + "\n"
		if (close_s):
			MSG = MSG + CLSES_MSG + "\n"

	if (buy or sell or close_b or close_s):
		return MSG
	else:
		return None


def process_symbol(symbol):
	global scores
	global closes

	myprint("SYMBOL: " + symbol)

	df 	= get_quote_data(symbol, INTERVAL, 1)
	dfsup 	= get_quote_data_sup(symbol)

	symbol = symbol.rstrip().replace(".","_").replace("-","_").replace("/","_")

	if (INTERVAL == "4h"):
		df = transform_four_hours(df)

	if (df is None) :
		return

	df 	= processIchimoku(df, True)

	if (dfsup is not None):
		dfsup 	= processIchimoku(dfsup, False)

	score		= process_score(df, dfsup)

#	myprint(df[['timestamp', 'open', 'close', 'CLOUD_TREND', 'SIGNAL_X_PRC_CLD', 'SIGNAL_X_CHI_KIJ', 'SIGNAL_X_KIJ_TEN', 'SIGNAL_X_KIJ_PRC', 'SIGNAL_X_CHI_PRC', 'SIGNAL_X_CHI_SSB', 'SIGNAL_CHI_PRC', 'SIGNAL_KIJ_PRC', 'SIGNAL_SS26', 'SIGNAL_ICHI_SUP', 'SIGNAL_CLOSE', 'SIGNAL_AVG']])
	myprint(df[['SSA', 'open', 'close', 'CLOUD_TREND', 'SIGNAL_X_PRC_CLD', 'SIGNAL_X_CHI_KIJ', 'SIGNAL_X_KIJ_TEN', 'SIGNAL_X_KIJ_PRC', 'SIGNAL_X_CHI_PRC', 'SIGNAL_X_CHI_SSB', 'SIGNAL_CHI_PRC', 'SIGNAL_KIJ_PRC', 'SIGNAL_SS26', 'SIGNAL_ICHI_SUP', 'SIGNAL_CLOSE', 'SIGNAL_AVG']])

	# We do not want score lower than 750 points
	if (score > 750 or score < -750):
		f = open('test.csv', 'a')
		if (score > 0):
			f.write("LONG,"  + str(df['timestamp'][len(df)-1]) + "," + str(symbol) + "," + str(int(score)) + ',' + str(df['close'][len(df)-1]) + "\n")
		else:
			f.write("SHORT,"  + str(df['timestamp'][len(df)-1]) + "," + str(symbol) + "," + str(int(score)) + ',' + str(df['close'][len(df)-1]) + "\n")

		f.close()
		scores[symbol]  = score

	# We do not want a sell score if we have a Close sell signal
	#if (score < 0 and df['SIGNAL_CLOSE'][df.index[-1]] == -1):
	#	scores[symbol] = 0

	# We do not want a buy score if we have a Buy sell signal
	#if (score > 0 and df['SIGNAL_CLOSE'][df.index[-1]] == 1):
	#	scores[symbol] = 0

	if (df['SIGNAL_CLOSE'][df.index[-1]] != 0):
		f = open('test.csv', 'a')
		f.write("CLOSE,"  + str(df['timestamp'][len(df)-1]) + "," + str(symbol) + ',0,' + str(df['close'][len(df)-1]) + "\n")
		f.close()
		closes[symbol]  = df['SIGNAL_CLOSE'][df.index[-1]]


#
# Main function
#
def main():
	global scores
	global closes

	# For each market, retrieve, process and write in email
#	threads = []
	for symbol in MARKETS:
		process_symbol(symbol)
#		t = threading.Thread(target=process_symbol, args=(symbol,))
#		threads.append(t)
#		t.start()

#	for x in threads:
#		x.join()

	# Write & send message
	MSG = write_email(scores, closes)
	if (MSG != None):
		if (OUTPUT == "EMAIL"):
			send_email(MSG + "</body></html>")
		else:
			print(MSG)


################################################### START PROGRAM ##################################################################
parse_args()
main()
print("--- %s seconds ---" % (time.time() - start_time))
